"""Compare real Tk controller workloads. Linux/Xvfb results are not game metrics."""
import argparse
from contextlib import contextmanager
import importlib.util
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS = ROOT / 'AuroraCrosshairDX/resources/crosshairs'

@contextmanager
def isolated_controller_home(home):
    """Override both original and candidate path selectors, restoring callers."""
    docs = home / 'Documents/Crosshair overlay'
    with patch.object(Path, 'home', return_value=home), patch.dict(os.environ, {'AURORA_OVERLAY_HOME': str(docs)}):
        yield docs


def asset_manifest(assets):
    digest = hashlib.sha256()
    paths = sorted(path for path in assets.rglob('*') if path.is_file() and path.suffix.lower() == '.png')
    for path in paths:
        digest.update(path.relative_to(assets).as_posix().encode('utf-8'))
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {'png_count': len(paths), 'relative_paths_and_contents_sha256': digest.hexdigest()}


def trial(source, assets, seconds, display_description):
    import tkinter as tk
    from tkinter import messagebox
    import psutil
    import PIL
    spec = importlib.util.spec_from_file_location('controller_under_measurement', source)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(source.parent))
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='aurora-perf-') as td:
        home = Path(td)
        docs = home/'Documents/Crosshair overlay'
        resources = docs/'AuroraCrosshairDX/resources/crosshairs'
        resources.parent.mkdir(parents=True)
        try:
            resources.symlink_to(assets, target_is_directory=True)
            resource_layout = 'symlink'
        except OSError:
            # Windows without symlink privilege can still run the same workload.
            shutil.copytree(assets, resources)
            resource_layout = 'copy prepared before timing'
        config = docs/'overlay_config.txt'
        config.write_text('scale=1.0\ncrosshair=dots/osupink.png\n')
        target = os.fspath(config)
        commits = []
        def audit(event, args):
            if event == 'open' and args[0] == target and args[2] & (os.O_WRONLY | os.O_RDWR):
                commits.append(time.perf_counter())
            if event == 'os.rename' and os.fspath(args[1]) == target:
                commits.append(time.perf_counter())
        sys.addaudithook(audit)
        process = psutil.Process()
        callbacks = []
        def fail_dialog(title, msg, **kwargs):
            raise RuntimeError(f'{title}: {msg}')
        with isolated_controller_home(home), patch.object(messagebox, 'showerror', side_effect=fail_dialog):
            wall = time.perf_counter()
            cpu = time.process_time()
            root = tk.Tk()
            def callback_error(*args):
                callbacks.append(str(args))
                root.quit()
            root.report_callback_exception = callback_error
            app = module.CrosshairController(root)
            if app.config_path.resolve() != config.resolve():
                raise RuntimeError('Controller ignored isolated configuration path')
            root.update()
            startup = {'wall_seconds': time.perf_counter()-wall, 'cpu_seconds': time.process_time()-cpu,
                       'rss_bytes': process.memory_info().rss, 'config_commits': len(commits),
                       'tabs': len(app.tabs), 'previews': len(app.crosshair_buttons)}
            results = {'startup': startup, 'idle': []}
            phase = {}
            def end_idle():
                elapsed = time.perf_counter()-phase['wall']
                cpu_delta = time.process_time()-phase['cpu']
                results['idle'].append({'requested_state': phase['state'], 'tk_state': root.state(),
                    'wall_seconds': elapsed, 'cpu_seconds': cpu_delta,
                    'cpu_percent_one_core': cpu_delta/elapsed*100,
                    'rss_start_bytes': phase['rss'], 'rss_end_bytes': process.memory_info().rss,
                    'config_commits': len(commits)-phase['commits']})
                if phase['state'] == 'visible':
                    root.withdraw()
                    root.after(300, lambda: begin_idle('withdrawn'))
                else:
                    root.deiconify()
                    root.after(300, begin_burst)
            def begin_idle(state):
                phase.update(state=state, wall=time.perf_counter(), cpu=time.process_time(),
                             rss=process.memory_info().rss, commits=len(commits))
                root.after(round(seconds*1000), end_idle)
            def begin_burst():
                phase.update(wall=time.perf_counter(), cpu=time.process_time(), commits=len(commits))
                step(0)
            def step(index):
                # The same callbacks a 100-event drag invokes; events arrive every 5ms.
                value = 0.5+2.5*index/99
                app.scale_var.set(value)
                app.on_scale_changed(str(value))
                if index < 99:
                    root.after(5, lambda: step(index+1))
                else:
                    root.after(300, end_burst)
            def end_burst():
                results['slider_burst'] = {'events': 100, 'event_interval_ms': 5,
                    'wall_seconds': time.perf_counter()-phase['wall'],
                    'cpu_seconds': time.process_time()-phase['cpu'],
                    'config_commits': len(commits)-phase['commits'],
                    'final_config': config.read_text()}
                saved = dict(line.split('=', 1) for line in config.read_text().splitlines() if '=' in line)
                if float(saved.get('scale', 'nan')) != 3.0 or saved.get('crosshair') != 'dots/osupink.png':
                    callbacks.append('Slider final configuration did not persist correctly')
                root.quit()
            root.after(300, lambda: begin_idle('visible'))
            root.mainloop()
            root.destroy()
            if callbacks:
                raise RuntimeError(callbacks)
        results['environment'] = {'platform': platform.platform(), 'python': sys.version,
            'tk': tk.TkVersion, 'pillow': PIL.__version__, 'psutil': psutil.__version__,
            'logical_cpus': os.cpu_count(), 'display': os.environ.get('DISPLAY'),
            'display_description': display_description,
            'hidden_state': 'withdrawn, not Windows minimized',
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'source': str(source), 'assets': str(assets),
            'cpu_scope': 'Python process only; excludes display server CPU',
            'cpu_model': platform.processor() or 'unavailable',
            'resource_layout': resource_layout,
            'adjacent_python_sha256': {str(path.name): hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in sorted(source.parent.glob('*.py'))}}
        return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--assets', type=Path, default=DEFAULT_ASSETS)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--display-description', default='Existing Tk display; document server/window-manager configuration separately')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--trial', action='store_true')
    args = parser.parse_args()
    if args.trials < 1 or not 0 < args.seconds <= 3600:
        parser.error('--trials must be positive and --seconds must be in (0, 3600]')
    if not args.source.is_file() or not args.assets.is_dir():
        parser.error('--source must be a file and --assets must be a directory')
    if args.output and args.output.exists():
        parser.error('output already exists; select a new run output')
    source_digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    resources_digest = asset_manifest(args.assets)
    if args.trial:
        print(json.dumps(trial(args.source.resolve(), args.assets.resolve(), args.seconds, args.display_description)))
        return
    trials = []
    for index in range(args.trials):
        try:
            child = subprocess.run([sys.executable, __file__, '--trial', '--source', str(args.source),
                                    '--seconds', str(args.seconds), '--assets', str(args.assets),
                                    '--run-id', args.run_id, '--display-description', args.display_description],
                                   text=True, capture_output=True, timeout=2 * args.seconds + 30)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f'Trial {index + 1} exceeded its bounded capture timeout') from None
        if child.returncode:
            raise RuntimeError(f'Trial {index + 1} failed: {child.stderr or child.stdout}')
        trials.append(json.loads(child.stdout))
        print(f'Completed trial {index+1}/{args.trials}', flush=True)
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != source_digest:
        raise RuntimeError('Source changed during capture; discard this mixed run')
    if asset_manifest(args.assets) != resources_digest:
        raise RuntimeError('Resource files changed during capture; discard this mixed run')
    report = {'schema_version': 1, 'run_id': args.run_id, 'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'source_sha256': source_digest, 'asset_manifest': resources_digest, 'source': str(args.source.resolve()), 'scenario': 'fresh process, warm up 300ms, visible idle, withdrawn idle, 100 slider callbacks at 5ms, settle 300ms',
              'trials': trials, 'unavailable_metrics': ['native Windows overlay CPU/memory/GPU', 'game FPS and frame times', 'reliable input latency', 'extended gameplay stability']}
    report['summary'] = {'startup_wall_seconds_median': statistics.median(t['startup']['wall_seconds'] for t in trials),
        'startup_rss_bytes_median': statistics.median(t['startup']['rss_bytes'] for t in trials),
        'visible_idle_cpu_percent_one_core_median': statistics.median(t['idle'][0]['cpu_percent_one_core'] for t in trials),
        'withdrawn_idle_cpu_percent_one_core_median': statistics.median(t['idle'][1]['cpu_percent_one_core'] for t in trials),
        'slider_config_commits': [t['slider_burst']['config_commits'] for t in trials]}
    text = json.dumps(report, indent=2)
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text+'\n')
    print(json.dumps(report['summary'], indent=2))
if __name__ == '__main__':
    main()
