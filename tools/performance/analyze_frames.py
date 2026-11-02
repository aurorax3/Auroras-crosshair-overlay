"""Analyze one explicitly selected PresentMon process/swap-chain interval stream.

All calculations use the caller's selected interval column and units. These are
frame-interval metrics, not an input-latency or displayed-frame-rate measurement.
Only Python's standard library is required.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def percentile(ordered, fraction):
    """Linearly interpolated percentile (the common inclusive/type-7 convention)."""
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def dropped_value(value):
    normalized = value.strip().lower()
    if normalized in ('0', 'false', 'no'):
        return False
    if normalized in ('1', 'true', 'yes'):
        return True
    raise ValueError(f'Unrecognized dropped-frame value: {value!r}')


def analyze_rows(rows, *, process_id, swapchain, interval_column,
                 process_column='ProcessID', swapchain_column='SwapChainAddress',
                 interval_units='ms', dropped_column=None, drop_policy='all',
                 skip_invalid_intervals=False, spike_thresholds_ms=(16.667, 33.333, 50.0, 100.0)):
    if process_id <= 0 or not swapchain.strip():
        raise ValueError('A positive process ID and nonempty swap chain are required')
    if interval_units not in ('ms', 's', 'us'):
        raise ValueError('Interval units must be ms, s or us')
    if drop_policy not in ('all', 'presented', 'dropped'):
        raise ValueError('Invalid dropped-frame selection')
    if drop_policy != 'all' and not dropped_column:
        raise ValueError('Dropped-frame filtering requires --dropped-column')
    if any(not math.isfinite(x) or x <= 0 for x in spike_thresholds_ms):
        raise ValueError('Spike thresholds must be finite and positive')
    conversion = {'ms': 1.0, 's': 1000.0, 'us': 0.001}[interval_units]
    counts = {'rows_total': 0, 'rows_other_streams': 0, 'rows_selected_stream': 0,
              'rows_excluded_by_drop_policy': 0, 'rows_invalid_intervals': 0,
              'selected_stream_dropped_rows': 0 if dropped_column else None}
    intervals = []
    for number, row in enumerate(rows, 2):
        counts['rows_total'] += 1
        if None in row:
            raise ValueError(f'CSV row {number}: more fields than the header')
        required = [process_column, swapchain_column, interval_column]
        if dropped_column:
            required.append(dropped_column)
        missing = [column for column in required if column not in row]
        if missing:
            raise ValueError(f'Missing CSV columns: {", ".join(missing)}')
        if row[process_column] is None or row[swapchain_column] is None:
            raise ValueError(f'CSV row {number}: missing process or swap-chain field')
        if (str(row[process_column]).strip() != str(process_id) or
                str(row[swapchain_column]).strip().lower() != swapchain.strip().lower()):
            counts['rows_other_streams'] += 1
            continue
        counts['rows_selected_stream'] += 1
        dropped = dropped_value(row[dropped_column] or '') if dropped_column else None
        if dropped:
            counts['selected_stream_dropped_rows'] += 1
        if ((drop_policy == 'presented' and dropped) or
                (drop_policy == 'dropped' and not dropped)):
            counts['rows_excluded_by_drop_policy'] += 1
            continue
        raw = row[interval_column]
        try:
            interval = float(raw) * conversion
            if not math.isfinite(interval) or interval <= 0:
                raise ValueError('interval is not finite and positive')
        except (ValueError, TypeError, OverflowError):
            counts['rows_invalid_intervals'] += 1
            if skip_invalid_intervals:
                continue
            raise ValueError(f'CSV row {number}: invalid positive frame interval {raw!r}') from None
        intervals.append(interval)
    if not intervals:
        raise ValueError('No valid intervals remain in the selected process/swap-chain stream')
    ordered = sorted(intervals)
    frame_count = len(ordered)
    try:
        total_ms = math.fsum(ordered)
    except OverflowError:
        raise ValueError('Selected intervals overflow the numeric total') from None
    tail_count = max(1, math.ceil(frame_count * 0.01))
    tail_ms = math.fsum(ordered[-tail_count:])
    average_fps = frame_count * 1000.0 / total_ms
    low_fps = tail_count * 1000.0 / tail_ms
    if not math.isfinite(average_fps) or not math.isfinite(low_fps):
        raise ValueError('Selected intervals produce nonfinite FPS metrics')
    return {
        'selection': {'process_id': process_id, 'swapchain': swapchain,
                      'process_column': process_column, 'swapchain_column': swapchain_column,
                      'interval_column': interval_column, 'interval_units': interval_units,
                      'dropped_column': dropped_column, 'drop_policy': drop_policy,
                      'skip_invalid_intervals': skip_invalid_intervals},
        'counts': counts,
        'frame_count': frame_count,
        'interval_total_ms': total_ms,
        'average_fps': average_fps,
        'one_percent_low_fps': low_fps,
        'slowest_one_percent_frame_count': tail_count,
        'frame_time_ms': {'mean': total_ms / frame_count, 'p50': percentile(ordered, 0.50),
                          'p95': percentile(ordered, 0.95), 'p99': percentile(ordered, 0.99),
                          'max': ordered[-1]},
        'spikes_strictly_above_ms': {str(threshold): sum(x > threshold for x in intervals)
                                   for threshold in spike_thresholds_ms},
        'definitions': {
            'average_fps': '1000 / arithmetic mean of selected positive frame intervals in milliseconds',
            'one_percent_low_fps': '1000 / arithmetic mean of slowest ceil(N * 0.01) frame intervals',
            'percentiles': 'linear interpolation at (N - 1) * percentile (type 7)',
            'scope': 'Selected interval-column stream only; not input latency or proof of displayed FPS'},
        'warnings': ([
            'Dropped-frame filtering excludes those intervals from elapsed time; FPS is conditional on selected rows, not displayed cadence'
        ] if counts['rows_excluded_by_drop_policy'] else []) + ([
            'Invalid intervals were explicitly excluded; remaining metrics omit their unknown elapsed time'
        ] if counts['rows_invalid_intervals'] else []),
        'sample_count_warning': 'Fewer than 100 frames; the slowest 1% contains only one frame' if frame_count < 100 else None,
        'unavailable_metrics': ['input latency', 'gameplay stability outside the capture', 'GPU utilization'],
    }


def read_csv(path, **options):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('CSV needs a header with unique column names')
        required = [options.get('process_column', 'ProcessID'),
                    options.get('swapchain_column', 'SwapChainAddress'), options['interval_column']]
        if options.get('dropped_column'):
            required.append(options['dropped_column'])
        missing = [name for name in required if name not in reader.fieldnames]
        if missing:
            raise ValueError(f'Missing CSV columns: {", ".join(missing)}')
        return analyze_rows(reader, **options)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--process-id', type=int, required=True)
    parser.add_argument('--swapchain', required=True)
    parser.add_argument('--process-column', default='ProcessID')
    parser.add_argument('--swapchain-column', default='SwapChainAddress')
    parser.add_argument('--interval-column', required=True, help='Explicit PresentMon version/metric column, e.g. MsBetweenPresents or CPUFrameTime')
    parser.add_argument('--interval-units', choices=('ms', 's', 'us'), default='ms')
    parser.add_argument('--dropped-column')
    parser.add_argument('--drop-policy', choices=('all', 'presented', 'dropped'), default='all')
    parser.add_argument('--skip-invalid-intervals', action='store_true', help='Explicitly exclude missing/nonpositive/nonfinite selected intervals and report the count')
    parser.add_argument('--spike-threshold-ms', action='append', type=float)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.output and args.output.exists():
            raise ValueError('Output already exists; choose a new run output')
        report = read_csv(args.csv, process_id=args.process_id, swapchain=args.swapchain,
                          interval_column=args.interval_column, process_column=args.process_column,
                          swapchain_column=args.swapchain_column, interval_units=args.interval_units,
                          dropped_column=args.dropped_column, drop_policy=args.drop_policy,
                          skip_invalid_intervals=args.skip_invalid_intervals,
                          spike_thresholds_ms=args.spike_threshold_ms or (16.667, 33.333, 50.0, 100.0))
        report.update(schema_version=1, run_id=args.run_id, input_csv=str(args.csv.resolve()),
                      source_csv_sha256=hashlib.sha256(args.csv.read_bytes()).hexdigest())
        text = json.dumps(report, indent=2, allow_nan=False) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(text)
        else:
            print(text, end='')
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
