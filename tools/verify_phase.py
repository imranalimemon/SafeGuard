"""Repeatable phase gate. Each cv2-sensitive unittest group gets its own process."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GROUP = ['detection_model', 'ppe_association', 'ppe_defaults', 'status', 'live_stream', 'mask_visibility', 'violation_workflow', 'uploads', 'saved_settings', 'alerts']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, type=int)
    parser.add_argument('--extra', nargs='*', default=['backend.test_security'])
    args = parser.parse_args()
    output = ROOT / 'docs' / 'evidence' / f'phase{args.phase}'
    output.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    commands = [(ROOT, [python, '-B', '-m', 'unittest', *['backend.test_' + name for name in GROUP]])]
    commands += [(ROOT, [python, '-B', '-m', 'unittest', name]) for name in ['backend.test_camera_capture', 'backend.test_launchers', *args.extra]]
    front = ROOT / 'frontend'
    commands += [(front, ['node', '--test', *[str(p.relative_to(front)) for p in sorted((front / 'test').glob('*.test.mjs'))]]),
                 (front, ['node', 'test/ui_status.test.cjs']),
                 (front, ['node', 'node_modules/vite/bin/vite.js', 'build'])]
    results = []
    for index, (cwd, command) in enumerate(commands, 1):
        run = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', env={**os.environ, 'ALERT_DELIVERY_MODE': 'preview', 'PYTHONDONTWRITEBYTECODE': '1'})
        log = output / f'{index:02d}.log'
        log.write_text('COMMAND: ' + subprocess.list2cmdline(command) + '\nCWD: ' + str(cwd) + '\n' + run.stdout + run.stderr, encoding='utf-8')
        results.append({'command': command, 'cwd': str(cwd), 'exit_code': run.returncode, 'log': str(log.relative_to(ROOT))})
        print(f'{index}: exit {run.returncode}; {log}', flush=True)
    (output / 'tests.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return int(any(item['exit_code'] for item in results))

if __name__ == '__main__':
    raise SystemExit(main())
