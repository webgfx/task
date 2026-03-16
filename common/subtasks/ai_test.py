"""
AI Test driver — runs external ai-test project benchmarks on the client device.

This driver locates the ai-test project (expected to be a sibling directory of the
task repo), executes the requested benchmark script, reads the generated result
files, and returns the structured data for the server to store and compare.

Directory layout expected:
    project/
    ├── task/          ← this repo
    └── ai-test/       ← the ai-test project (sibling)

Supported scripts (passed via kwargs['script']):
    perf-test-llamacpp   (default)
    perf-test-ort
    perf-test-ort-web

The driver:
1. Resolves the ai-test project path
2. Snapshots existing result directories
3. Runs the requested Node.js script with any extra arguments
4. Finds newly created result files
5. Returns the parsed JSON results to the server
"""

import os
import json
import logging
import platform
import shutil
import subprocess
import configparser
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseSubtask
from . import register_subtask_class

logger = logging.getLogger(__name__)

# Map of short names to script filenames
SCRIPT_MAP = {
    'perf-test-llamacpp': 'perf-test-llamacpp.js',
    'perf-test-ort': 'perf-test-ort.js',
    'perf-test-ort-web': 'perf-test-ort-web.js',
    'perf-test-ort-py': 'perf-test-ort.py',
}


def _get_project_root() -> str:
    """Return the task project root (three levels up from this file)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_ai_test_path() -> str:
    """
    Resolve the ai-test project directory.

    Search order:
    1. common.cfg [PATHS] ai_test_path
    2. Sibling: <project_root>/../ai-test
    3. Sibling under test/: <project_root>/../test/ai-test
    """
    root = _get_project_root()

    # 1. Config file override
    cfg_path = os.path.join(root, 'common', 'common.cfg')
    if os.path.exists(cfg_path):
        try:
            cfg = configparser.ConfigParser()
            cfg.read(cfg_path, encoding='utf-8')
            custom = cfg.get('PATHS', 'ai_test_path', fallback='')
            if custom:
                resolved = os.path.abspath(custom)
                if os.path.isdir(resolved):
                    return resolved
        except Exception:
            pass

    # 2. Sibling directory
    for candidate in [
        os.path.normpath(os.path.join(root, '..', 'ai-test')),
        os.path.normpath(os.path.join(root, '..', 'test', 'ai-test')),
    ]:
        if os.path.isdir(candidate):
            return candidate

    return os.path.normpath(os.path.join(root, '..', 'ai-test'))


def _find_node() -> Optional[str]:
    """Find the Node.js executable."""
    node = shutil.which('node')
    if node:
        return node
    if platform.system() == 'Windows':
        for p in [
            os.path.expandvars(r'%ProgramFiles%\nodejs\node.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\nodejs\node.exe'),
            os.path.expandvars(r'%APPDATA%\nvm\current\node.exe'),
        ]:
            if os.path.isfile(p):
                return p
    return None


def _get_results_dir(ai_test_path: str) -> str:
    """Read the results directory from ai-test/config.json."""
    config_file = os.path.join(ai_test_path, 'config.json')
    if os.path.isfile(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            rp = cfg.get('paths', {}).get('results', '')
            if rp:
                return rp if os.path.isabs(rp) else os.path.join(ai_test_path, rp)
        except Exception:
            pass
    return os.path.join(ai_test_path, 'gitignore', 'results')


def _snapshot_dirs(results_dir: str) -> set:
    """Return the set of subdirectory names currently in results_dir."""
    if not os.path.isdir(results_dir):
        return set()
    return set(os.listdir(results_dir))


def _find_new_results(results_dir: str, before: set) -> Optional[Dict[str, Any]]:
    """Find result JSON files in directories created after `before` snapshot."""
    if not os.path.isdir(results_dir):
        return None

    after = set(os.listdir(results_dir))
    new_dirs = sorted(after - before, reverse=True)

    # Fallback: pick the most recent directory
    if not new_dirs:
        all_dirs = sorted(
            [d for d in after if os.path.isdir(os.path.join(results_dir, d))],
            reverse=True,
        )
        new_dirs = all_dirs[:1]

    for dir_name in new_dirs:
        dir_path = os.path.join(results_dir, dir_name)
        if not os.path.isdir(dir_path):
            continue
        # Read all *-results.json files in the directory
        result_files = [f for f in os.listdir(dir_path) if f.endswith('-results.json')]
        if result_files:
            combined = {'run_id': dir_name, 'files': {}}
            for rf in result_files:
                try:
                    with open(os.path.join(dir_path, rf), 'r', encoding='utf-8') as f:
                        combined['files'][rf] = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not read {rf}: {e}")
            if combined['files']:
                return combined
    return None


class AiTestSubtask(BaseSubtask):
    """
    Driver for the external ai-test benchmark project.

    Kwargs accepted at scheduling time:
        script:   Which benchmark to run (default: 'perf-test-llamacpp')
        args:     Extra CLI arguments as a list of strings
    """

    def run(self, **kwargs) -> Dict[str, Any]:
        """Execute the ai-test benchmark and return collected results."""
        script_name = kwargs.get('script', 'perf-test-llamacpp')
        extra_args: List[str] = kwargs.get('args', [])

        output: Dict[str, Any] = {
            'script': script_name,
            'ai_test_path': None,
            'test_status': 'skip',
            'results': None,
            'run_id': None,
            'stdout': '',
            'stderr': '',
            'errors': [],
            'timestamp': datetime.now().isoformat(),
        }

        # 1. Locate ai-test
        ai_test_path = _resolve_ai_test_path()
        output['ai_test_path'] = ai_test_path

        if not os.path.isdir(ai_test_path):
            output['errors'].append(f'ai-test project not found at: {ai_test_path}')
            return output

        # 2. Resolve script file
        script_file = SCRIPT_MAP.get(script_name, f'{script_name}.js')
        script_path = os.path.join(ai_test_path, 'scripts', script_file)

        if not os.path.isfile(script_path):
            output['errors'].append(f'Script not found: {script_path}')
            return output

        # 3. Determine runner (node for .js, python for .py)
        if script_file.endswith('.py'):
            runner = shutil.which('python') or shutil.which('python3')
            if not runner:
                output['errors'].append('Python not found')
                return output
        else:
            runner = _find_node()
            if not runner:
                output['errors'].append('Node.js not found')
                return output

        # 4. Snapshot existing result directories
        results_dir = _get_results_dir(ai_test_path)
        before = _snapshot_dirs(results_dir)

        # 5. Run the script
        cmd = [runner, script_path] + extra_args
        logger.info(f"AI_TEST: Running {' '.join(cmd)} in {ai_test_path}")

        try:
            proc = subprocess.run(
                cmd,
                cwd=ai_test_path,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max
                env={**os.environ},
            )
            output['stdout'] = proc.stdout
            output['stderr'] = proc.stderr

            if proc.returncode != 0:
                output['errors'].append(f'Script exited with code {proc.returncode}')
                # Check for common skip reasons
                combined_out = proc.stdout + proc.stderr
                if 'No llama.cpp versions found' in combined_out:
                    output['test_status'] = 'skip'
                    output['errors'] = ['llama.cpp binaries not available on this device']
                    return output

        except subprocess.TimeoutExpired:
            output['errors'].append('Script timed out after 3600 seconds')
            output['test_status'] = 'fail'
            return output
        except Exception as e:
            output['errors'].append(str(e))
            output['test_status'] = 'fail'
            return output

        # 6. Collect newly generated results
        new_results = _find_new_results(results_dir, before)
        if new_results:
            output['results'] = new_results
            output['run_id'] = new_results.get('run_id')
            output['test_status'] = 'pass'
        else:
            # Script ran but no result files — check if it was a pass or fail
            output['test_status'] = 'pass' if proc.returncode == 0 else 'fail'
            if proc.returncode == 0 and not new_results:
                output['errors'].append('Script completed but no result files were generated')

        return output

    def get_result(self) -> Any:
        return self._last_result

    def get_description(self) -> str:
        return ("Driver for the external ai-test benchmark project. "
                "Runs llama.cpp, ORT, or ORT-Web perf tests and collects results.")


# Register the subtask
register_subtask_class('ai_test', AiTestSubtask())

