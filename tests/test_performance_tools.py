"""Deterministic tests of frame formulas and capture stream selection."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/performance/analyze_frames.py'
SPEC = importlib.util.spec_from_file_location('analyze_frames', TOOL)
frames = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(frames)
GUI_SPEC = importlib.util.spec_from_file_location('measure_gui', TOOL.with_name('measure_gui.py'))
gui_measurement = importlib.util.module_from_spec(GUI_SPEC)
GUI_SPEC.loader.exec_module(gui_measurement)


def row(interval, process=42, chain='0xA', dropped='0'):
    return {'ProcessID': str(process), 'SwapChainAddress': chain,
            'MsBetweenPresents': str(interval), 'Dropped': dropped}


def analyze(rows, **kwargs):
    options = {'process_id': 42, 'swapchain': '0xa',
               'interval_column': 'MsBetweenPresents', 'spike_thresholds_ms': (10.0, 50.0)}
    options.update(kwargs)
    return frames.analyze_rows(rows, **options)


class FrameAnalysisTests(unittest.TestCase):
    def test_average_and_slowest_one_percent_use_interval_means(self):
        result = analyze([row(10)] * 99 + [row(100)])
        self.assertEqual(result['frame_count'], 100)
        self.assertAlmostEqual(result['average_fps'], 100000 / 1090)
        self.assertEqual(result['one_percent_low_fps'], 10)
        self.assertEqual(result['slowest_one_percent_frame_count'], 1)
        self.assertEqual(result['frame_time_ms']['p50'], 10)
        self.assertEqual(result['frame_time_ms']['p95'], 10)
        self.assertAlmostEqual(result['frame_time_ms']['p99'], 10.9)
        self.assertEqual(result['spikes_strictly_above_ms'], {'10.0': 1, '50.0': 1})

    def test_one_percent_tail_rounds_up_and_is_not_inverse_p99(self):
        result = analyze([row(10)] * 99 + [row(20), row(100)])
        self.assertEqual(result['slowest_one_percent_frame_count'], 2)
        self.assertAlmostEqual(result['one_percent_low_fps'], 1000 / 60)
        self.assertEqual(result['frame_time_ms']['p99'], 20)
        self.assertNotEqual(result['one_percent_low_fps'], 1000 / result['frame_time_ms']['p99'])

    def test_explicit_process_and_swapchain_isolate_streams(self):
        result = analyze([row(10), row('invalid', process=999), row(1000, chain='0xB'), row(20, chain='0XA')])
        self.assertEqual(result['frame_count'], 2)
        self.assertAlmostEqual(result['average_fps'], 1000 / 15)
        self.assertEqual(result['counts']['rows_other_streams'], 2)

    def test_dropped_selection_is_explicit_and_counts_exclusions(self):
        rows = [row(10), row(100, dropped='true'), row(20)]
        result = analyze(rows, dropped_column='Dropped', drop_policy='presented')
        self.assertEqual(result['frame_count'], 2)
        self.assertEqual(result['counts']['rows_excluded_by_drop_policy'], 1)
        self.assertEqual(result['counts']['selected_stream_dropped_rows'], 1)
        self.assertIn('not displayed cadence', result['warnings'][0])
        dropped = analyze(rows, dropped_column='Dropped', drop_policy='dropped')
        self.assertEqual(dropped['frame_count'], 1)
        self.assertEqual(dropped['average_fps'], 10)
        with self.assertRaisesRegex(ValueError, 'requires --dropped-column'):
            analyze(rows, drop_policy='presented')

    def test_invalid_dropped_flags_fail_instead_of_silently_becoming_presented(self):
        with self.assertRaisesRegex(ValueError, 'Unrecognized dropped-frame'):
            analyze([row(10, dropped='maybe')], dropped_column='Dropped')

    def test_invalid_selected_intervals_fail_by_default(self):
        for invalid in ('', 'NaN', 'inf', '-inf', 'zero', '0', '-1'):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, 'invalid positive frame interval'):
                    analyze([row(invalid)])

    def test_skipped_invalid_intervals_are_reported(self):
        result = analyze([row(0), row('NaN'), row(10)], skip_invalid_intervals=True)
        self.assertEqual(result['counts']['rows_invalid_intervals'], 2)
        self.assertIn('unknown elapsed time', result['warnings'][0])
        self.assertEqual(result['frame_count'], 1)
        self.assertEqual(result['average_fps'], 100)

    def test_interval_units_and_column_mapping(self):
        result = frames.analyze_rows([{'pid': '42', 'chain': '0xa', 'seconds': '0.01'}],
            process_id=42, swapchain='0xa', process_column='pid', swapchain_column='chain',
            interval_column='seconds', interval_units='s')
        self.assertEqual(result['average_fps'], 100)
        self.assertEqual(result['frame_time_ms']['max'], 10)

    def test_no_stream_or_missing_columns_fail(self):
        with self.assertRaisesRegex(ValueError, 'No valid intervals'):
            analyze([row(10, process=999)])
        with self.assertRaisesRegex(ValueError, 'Missing CSV columns'):
            analyze([{'ProcessID': '42'}])
        with self.assertRaisesRegex(ValueError, 'No valid intervals'):
            analyze([])

    def test_invalid_selection_and_spike_thresholds_fail(self):
        for options in ({'process_id': 0}, {'swapchain': ''}, {'interval_units': 'ns'},
                        {'spike_thresholds_ms': (float('nan'),)}, {'spike_thresholds_ms': (-1,)},
                        {'drop_policy': 'typo'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                analyze([row(10)], **options)

    def test_small_samples_warn_and_percentile_interpolation_is_documented(self):
        result = analyze([row(10), row(20)])
        self.assertTrue(result['sample_count_warning'])
        self.assertEqual(result['frame_time_ms']['p50'], 15)
        self.assertEqual(result['one_percent_low_fps'], 50)
        self.assertIn('type 7', result['definitions']['percentiles'])

    def test_cli_provenance_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'frames.csv'
            output = Path(directory) / 'report.json'
            with source.open('w', newline='', encoding='utf-8-sig') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row(10)))
                writer.writeheader()
                writer.writerow(row(10))
            command = [sys.executable, str(TOOL), str(source), '--run-id', 'synthetic-test',
                       '--process-id', '42', '--swapchain', '0xA', '--interval-column',
                       'MsBetweenPresents', '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            result = json.loads(output.read_text())
            self.assertEqual(result['run_id'], 'synthetic-test')
            self.assertEqual(len(result['source_csv_sha256']), 64)
            self.assertEqual(result['average_fps'], 100)
            saved = output.read_bytes()
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(output.read_bytes(), saved)
            self.assertIn('Output already exists', repeated.stderr)

    def test_malformed_csv_rows_and_overflow_fail(self):
        with self.assertRaisesRegex(ValueError, 'more fields than the header'):
            analyze([dict(row(10), **{}) | {None: ['extra']}])
        malformed = row(10)
        malformed['ProcessID'] = None
        with self.assertRaisesRegex(ValueError, 'missing process or swap-chain'):
            analyze([malformed])
        with self.assertRaisesRegex(ValueError, 'overflow the numeric total'):
            analyze([row(1e308), row(1e308)])
        with self.assertRaisesRegex(ValueError, 'nonfinite FPS'):
            analyze([row(5e-324)])

    def test_duplicate_and_empty_csv_headers_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'frames.csv'
            for data in ('', 'ProcessID,ProcessID,MsBetweenPresents\n42,42,10\n'):
                source.write_text(data)
                with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'unique column'):
                    frames.read_csv(source, process_id=42, swapchain='0xa', interval_column='MsBetweenPresents')


class GuiCaptureIsolationTests(unittest.TestCase):
    def test_existing_overlay_override_is_isolated_and_restored(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            real_home = parent / 'existing-override'
            real_home.mkdir()
            sentinel = real_home / 'overlay_config.txt'
            sentinel.write_text('scale=2.0\ncrosshair=keep.png\n')
            with patch.dict(os.environ, {'AURORA_OVERLAY_HOME': str(real_home)}):
                with self.assertRaisesRegex(RuntimeError, 'trial failure'):
                    with gui_measurement.isolated_controller_home(parent / 'isolated') as docs:
                        self.assertNotEqual(Path(os.environ['AURORA_OVERLAY_HOME']), real_home)
                        self.assertEqual(Path(os.environ['AURORA_OVERLAY_HOME']), docs)
                        self.assertEqual(Path.home(), parent / 'isolated')
                        raise RuntimeError('trial failure')
                self.assertEqual(os.environ['AURORA_OVERLAY_HOME'], str(real_home))
            self.assertEqual(sentinel.read_text(), 'scale=2.0\ncrosshair=keep.png\n')

    def test_asset_manifest_tracks_names_and_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory)
            (assets / 'a.png').write_bytes(b'first')
            original = gui_measurement.asset_manifest(assets)
            (assets / 'ignored.txt').write_bytes(b'non-image')
            self.assertEqual(gui_measurement.asset_manifest(assets), original)
            (assets / 'a.png').rename(assets / 'b.png')
            renamed = gui_measurement.asset_manifest(assets)
            self.assertNotEqual(renamed, original)
            (assets / 'b.png').write_bytes(b'second')
            self.assertNotEqual(gui_measurement.asset_manifest(assets), renamed)


if __name__ == '__main__':
    unittest.main()
