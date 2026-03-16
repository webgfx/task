"""
AI Test driver — runs the unified perf-test.js from the external ai-test project.

The ai-test project is expected as a sibling directory of the task repo:
    project/
    ├── task/          (this repo)
    └── ai-test/       (the ai-test project)

The entry point is always:
    node scripts/perf-test.js [options]

Options are passed via Task kwargs when scheduling the task:
    runtime:          Comma-separated runtimes, e.g. "ort,llamacpp" (default: "llamacpp")
    ort_backend:      ORT backend, e.g. "webgpu" or "cuda"
    llamacpp_backend: llama.cpp backend, e.g. "vulkan" or "cuda"
    model:            Model short name, e.g. "qwen-3-1.7B"
    prompt_lengths:   Comma-separated prompt lengths, e.g. "128,256"
    extra_args:       Additional CLI arguments as a list

Example task definition:
    {
        "name": "ai_test",
        "client": "webgfx-103",
        "kwargs": {
            "runtime": "ort,llamacpp",
            "ort_backend": "webgpu",
            "llamacpp_backend": "vulkan",
            "model": "qwen-3-1.7B",
            "prompt_lengths": "128,256"
        }
    }
"""

import os
import json
import logging
import shutil
import subprocess
import configparser
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseTask
from . import register_task_class

logger = logging.getLogger(__name__)


def _get_project_root() -> str:
    """Return the task project root (three levels up from this file)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_ai_test_path() -> str:
    """Resolve the ai-test project directory."""
    root = _get_project_root()

    # Config file override
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

    # Sibling directory
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
    if os.name == 'nt':
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


def _snapshot_dirs(path: str) -> set:
    if not os.path.isdir(path):
        return set()
    return set(os.listdir(path))


def _find_new_results(results_dir: str, before: set) -> Optional[Dict[str, Any]]:
    """Find result JSON files in directories created after the snapshot."""
    if not os.path.isdir(results_dir):
        return None

    after = set(os.listdir(results_dir))
    new_dirs = sorted(after - before, reverse=True)
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


class AiTestTask(BaseTask):
    """
    Driver for the external ai-test benchmark project.

    Runs:  node scripts/perf-test.js [options]

    Kwargs:
        runtime:          "ort", "llamacpp", or "ort,llamacpp"
        ort_backend:      "webgpu", "cuda", etc.
        llamacpp_backend: "vulkan", "cuda", etc.
        model:            Model short name, e.g. "qwen-3-1.7B"
        prompt_lengths:   Comma-separated, e.g. "128,256"
        extra_args:       List of additional CLI arguments
    """

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        output: Dict[str, Any] = {
            'ai_test_path': None,
            'test_status': 'skip',
            'results': None,
            'run_id': None,
            'command': '',
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

        script_path = os.path.join(ai_test_path, 'scripts', 'perf-test.js')
        if not os.path.isfile(script_path):
            output['errors'].append(f'perf-test.js not found at: {script_path}')
            return output

        # 2. Find Node.js
        node = _find_node()
        if not node:
            output['errors'].append('Node.js not found')
            return output

        # 3. Build command line
        cmd = [node, script_path]

        runtime = kwargs.get('runtime', 'llamacpp')
        if runtime:
            cmd.extend(['--runtime', runtime])

        ort_backend = kwargs.get('ort_backend', '')
        if ort_backend:
            cmd.extend(['--ort-backend', ort_backend])

        llamacpp_backend = kwargs.get('llamacpp_backend', '')
        if llamacpp_backend:
            cmd.extend(['--llamacpp-backend', llamacpp_backend])

        model = kwargs.get('model', '')
        if model:
            cmd.extend(['-m', model])

        prompt_lengths = kwargs.get('prompt_lengths', '')
        if prompt_lengths:
            cmd.extend(['-pl', prompt_lengths])

        extra = kwargs.get('extra_args', [])
        if extra:
            cmd.extend(extra)

        output['command'] = ' '.join(cmd)
        logger.info(f"AI_TEST: {output['command']}")

        # 4. Snapshot results dir
        results_dir = _get_results_dir(ai_test_path)
        before = _snapshot_dirs(results_dir)

        # 5. Run
        try:
            proc = subprocess.run(
                cmd,
                cwd=ai_test_path,
                capture_output=True,
                text=True,
                timeout=3600,
                env={**os.environ},
            )
            output['stdout'] = proc.stdout
            output['stderr'] = proc.stderr

            if proc.returncode != 0:
                output['errors'].append(f'Script exited with code {proc.returncode}')
                combined_out = proc.stdout + proc.stderr
                if 'No llama.cpp versions found' in combined_out:
                    output['test_status'] = 'skip'
                    output['errors'] = ['llama.cpp binaries not available']
                    return output

        except subprocess.TimeoutExpired:
            output['errors'].append('Script timed out after 3600 seconds')
            output['test_status'] = 'fail'
            return output
        except Exception as e:
            output['errors'].append(str(e))
            output['test_status'] = 'fail'
            return output

        # 6. Collect results
        new_results = _find_new_results(results_dir, before)
        if new_results:
            output['results'] = new_results
            output['run_id'] = new_results.get('run_id')
            output['test_status'] = 'pass'
        else:
            output['test_status'] = 'pass' if proc.returncode == 0 else 'fail'
            if proc.returncode == 0:
                output['errors'].append('No result files generated')

        return output

    def get_result(self) -> Any:
        return self._last_result

    def get_description(self) -> str:
        return "Run ai-test benchmarks (ORT/llama.cpp) via node scripts/perf-test.js"


register_task_class('ai_test', AiTestTask())

