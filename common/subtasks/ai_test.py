"""
AI Test subtask - adapter for the ai-test project's llama.cpp benchmark.

This subtask invokes the ai-test project (perf-test-llamacpp.js) on the device,
collects the structured results, and returns them for caching on the server.

The ai-test project path is resolved from common.cfg [PATHS] ai_test_path,
or defaults to ../ai-test relative to the project root.
"""

import os
import sys
import subprocess
import json
import glob
import logging
import platform
import configparser
from datetime import datetime
from typing import Dict, Any, Optional, List

from .base import BaseSubtask
from . import register_subtask_class

logger = logging.getLogger(__name__)


def _get_project_root() -> str:
    """Get the task project root directory"""
    # common/subtasks/ai_test.py -> common/subtasks -> common -> project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_ai_test_path() -> str:
    """
    Resolve the ai-test project path.

    Priority:
    1. common.cfg [PATHS] ai_test_path
    2. Default: ../ai-test relative to project root
    """
    project_root = _get_project_root()

    # Try reading from common.cfg
    cfg_path = os.path.join(project_root, 'common', 'common.cfg')
    if os.path.exists(cfg_path):
        try:
            config = configparser.ConfigParser()
            config.read(cfg_path, encoding='utf-8')
            custom_path = config.get('PATHS', 'ai_test_path', fallback='')
            if custom_path:
                resolved = os.path.abspath(custom_path)
                if os.path.isdir(resolved):
                    return resolved
                logger.warning(f"Configured ai_test_path not found: {resolved}")
        except (configparser.Error, Exception) as e:
            logger.debug(f"Could not read ai_test_path from common.cfg: {e}")

    # Default: sibling directory
    default_path = os.path.normpath(os.path.join(project_root, '..', 'ai-test'))
    if os.path.isdir(default_path):
        return default_path

    # Also try ../test/ai-test (common layout)
    alt_path = os.path.normpath(os.path.join(project_root, '..', 'test', 'ai-test'))
    if os.path.isdir(alt_path):
        return alt_path

    return default_path  # Return even if missing, so error message is clear


class AiTestSubtask(BaseSubtask):
    """Subtask to run llama.cpp AI benchmark via the ai-test project"""

    def run(self) -> Dict[str, Any]:
        """
        Run the ai-test llama.cpp benchmark on the device.

        Returns:
            Dict[str, Any]: Benchmark results including:
                - ai_test_path: Path to the ai-test project used
                - llamacpp_available: Whether llama.cpp binaries were found
                - test_status: 'pass', 'fail', or 'skip'
                - results: Parsed llamacpp-results.json content
                - result_file: Path to the results JSON file
                - stdout: Script stdout output
                - errors: List of errors encountered
                - timestamp: When the test was run
        """
        results = {
            'ai_test_path': None,
            'llamacpp_available': False,
            'test_status': 'skip',
            'results': None,
            'result_file': None,
            'stdout': '',
            'errors': [],
            'timestamp': datetime.now().isoformat(),
        }

        try:
            # Step 1: Locate ai-test project
            ai_test_path = _get_ai_test_path()
            results['ai_test_path'] = ai_test_path

            if not os.path.isdir(ai_test_path):
                results['errors'].append(f'ai-test project not found at: {ai_test_path}')
                results['test_status'] = 'skip'
                logger.warning(f"ai-test project not found at {ai_test_path}")
                return results

            script_path = os.path.join(ai_test_path, 'scripts', 'perf-test-llamacpp.js')
            if not os.path.isfile(script_path):
                results['errors'].append(f'perf-test-llamacpp.js not found at: {script_path}')
                results['test_status'] = 'skip'
                return results

            logger.info(f"Found ai-test project at: {ai_test_path}")

            # Step 2: Check Node.js is available
            node_path = self._find_node()
            if not node_path:
                results['errors'].append('Node.js not found on this device')
                results['test_status'] = 'skip'
                return results

            # Step 3: Snapshot existing result dirs before the run
            results_dir = self._get_results_dir(ai_test_path)
            existing_dirs = set()
            if results_dir and os.path.isdir(results_dir):
                existing_dirs = set(os.listdir(results_dir))

            # Step 4: Run the benchmark
            logger.info(f"Running llama.cpp benchmark via ai-test...")
            cmd = [node_path, script_path]
            run_result = self._run_script(cmd, ai_test_path)

            results['stdout'] = run_result.get('stdout', '')
            if run_result.get('stderr'):
                # stderr may contain warnings, not necessarily errors
                logger.debug(f"Script stderr: {run_result['stderr'][:500]}")

            if not run_result['success']:
                error_msg = run_result.get('error', 'Unknown error')
                results['errors'].append(f'Benchmark script failed: {error_msg}')
                # If it exited with non-zero but produced output, still try to read results
                if 'No llama.cpp versions found' in (run_result.get('stderr', '') + run_result.get('stdout', '')):
                    results['test_status'] = 'skip'
                    results['errors'] = [
                        'llama.cpp binaries not available on this device'
                    ]
                    return results

            # Step 5: Find and read the new results file
            result_data = self._find_new_results(results_dir, existing_dirs)
            if result_data:
                results['results'] = result_data['data']
                results['result_file'] = result_data['file']
                results['llamacpp_available'] = True

                # Determine status from results
                bench_results = result_data['data'].get('results', [])
                if bench_results:
                    has_errors = any(r.get('error') for r in bench_results)
                    has_data = any(r.get('tgTs') is not None for r in bench_results)
                    if has_data:
                        results['test_status'] = 'pass'
                    elif has_errors:
                        results['test_status'] = 'fail'
                    else:
                        results['test_status'] = 'pass'
                else:
                    results['test_status'] = 'fail' if not run_result['success'] else 'pass'
            else:
                # Script ran but no result file found
                if run_result['success']:
                    results['test_status'] = 'pass'
                else:
                    results['test_status'] = 'fail'
                    results['errors'].append('No result file produced by benchmark')

        except Exception as e:
            error_msg = f"AI test failed with exception: {str(e)}"
            results['errors'].append(error_msg)
            results['test_status'] = 'fail'
            logger.error(error_msg)

        return results

    def _find_node(self) -> Optional[str]:
        """Find Node.js executable"""
        import shutil
        node = shutil.which('node')
        if node:
            return node

        # Common Windows paths
        if platform.system() == 'Windows':
            for candidate in [
                os.path.expandvars(r'%ProgramFiles%\nodejs\node.exe'),
                os.path.expandvars(r'%ProgramFiles(x86)%\nodejs\node.exe'),
                os.path.expandvars(r'%APPDATA%\nvm\current\node.exe'),
            ]:
                if os.path.isfile(candidate):
                    return candidate

        return None

    def _get_results_dir(self, ai_test_path: str) -> Optional[str]:
        """Get the results directory from ai-test config"""
        config_path = os.path.join(ai_test_path, 'config.json')
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                results_path = config.get('paths', {}).get('results', '')
                if results_path and os.path.isabs(results_path):
                    return results_path
                elif results_path:
                    return os.path.join(ai_test_path, results_path)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not read ai-test config.json: {e}")

        # Default fallback
        return os.path.join(ai_test_path, 'gitignore', 'results')

    def _run_script(self, cmd: List[str], cwd: str) -> Dict[str, Any]:
        """Run the benchmark script and capture output"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout for full benchmark
                env={**os.environ},
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode,
                'error': result.stderr.strip() if result.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': '',
                'error': 'Benchmark timed out after 1800 seconds',
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': '',
                'error': str(e),
            }

    def _find_new_results(self, results_dir: str,
                          existing_dirs: set) -> Optional[Dict[str, Any]]:
        """Find the newly created results directory and read llamacpp-results.json"""
        if not results_dir or not os.path.isdir(results_dir):
            return None

        # Find directories that didn't exist before the run
        current_dirs = set(os.listdir(results_dir))
        new_dirs = current_dirs - existing_dirs

        if not new_dirs:
            # Fallback: pick the most recent directory
            all_dirs = sorted(
                [d for d in current_dirs if os.path.isdir(os.path.join(results_dir, d))],
                reverse=True
            )
            if all_dirs:
                new_dirs = {all_dirs[0]}

        for dir_name in sorted(new_dirs, reverse=True):
            result_file = os.path.join(results_dir, dir_name, 'llamacpp-results.json')
            if os.path.isfile(result_file):
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return {'data': data, 'file': result_file}
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Could not read results file {result_file}: {e}")

        return None

    def get_result(self) -> Any:
        """Get the last execution result"""
        return self._last_result

    def get_description(self) -> str:
        """Get a human-readable description of what this subtask does"""
        return ("Run llama.cpp AI benchmark via the ai-test project, "
                "testing inference performance across available backends")


# Register the subtask
register_subtask_class('ai_test', AiTestSubtask())

