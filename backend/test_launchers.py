"""Launcher preflight tests in a fake checkout; never start real services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows batch launcher')
class LauncherTests(unittest.TestCase):
    def run_launcher(self, fallback_works):
        with tempfile.TemporaryDirectory(prefix='safeguard-launcher-') as temp:
            root = Path(temp)
            shutil.copyfile(Path(__file__).resolve().parents[1] / 'start.bat', root / 'start.bat')
            files = {
                'node_modules/.bin/concurrently.cmd': '@echo MANAGER_STARTED preview=%ALERT_DELIVERY_MODE%\n@exit /b 0\n',
                'frontend/node_modules/vite/bin/vite.js': '',
                '.venv/Scripts/activate.bat': '@set "PATH=%~dp0;%PATH%"\n@set "VIRTUAL_ENV=%~dp0"\n',
                '.venv/Scripts/python.cmd': '@exit /b 1\n',
                'path-bin/python.cmd': f'@exit /b {0 if fallback_works else 1}\n',
                'path-bin/node.cmd': '@exit /b 0\n',
                'path-bin/npm.cmd': '@exit /b 0\n',
            }
            for relative, source in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            env = {**os.environ, 'PATH': str(root / 'path-bin') + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32')}
            env.pop('ALERT_DELIVERY_MODE', None)
            return subprocess.run(['cmd.exe', '/d', '/c', str(root / 'start.bat')],
                                  env=env, cwd=root, capture_output=True, text=True, timeout=15)

    def test_broken_preferred_venv_falls_back_to_original_path(self):
        result = self.run_launcher(True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Trying the original PATH Python', result.stdout)
        self.assertIn('MANAGER_STARTED preview=preview', result.stdout)

    def test_missing_runtime_fails_before_process_manager(self):
        result = self.run_launcher(False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Backend runtime dependencies are missing', result.stdout)
        self.assertNotIn('MANAGER_STARTED', result.stdout)


if __name__ == '__main__':
    unittest.main()
