"""
Dawn E2E tests subtask for downloading and running Dawn end-to-end tests.

This subtask downloads the latest Dawn E2E test binary based on the system
architecture and OS, extracts it, runs the tests, and reports failures.
"""

import os
import sys
import platform
import json
import subprocess
import zipfile
import shutil
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base import BaseSubtask
from . import register_subtask_class


class DawnE2ETestsSubtask(BaseSubtask):
    """Dawn E2E tests subtask for downloading and running Dawn end-to-end tests."""
    
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Download and run Dawn E2E tests.
        
        This function:
        1. Determines system architecture and OS
        2. Copies the latest Dawn E2E test binary from \\\\webgfx-200.guest.corp.microsoft.com\\backup\\<arch>\\<os>\\dawn\\
        3. Extracts the binary to ignore\\client\\backup\\<arch>\\<os>\\dawn\\
        4. Runs dawn_end2end_tests.exe with specified parameters
        5. Parses the JSON output for test failures (to be implemented later)
        
        Returns:
            Dict[str, Any]: Test execution results with comprehensive status information
        """
        start_time = datetime.now()
        
        try:
            # Set up task context for logging paths
            # This can be overridden by the calling task execution framework
            if not hasattr(self, 'task_context'):
                self.task_context = {
                    'task_name': 'dawn_task',
                    'task_timestamp': start_time.strftime('%Y%m%d%H%M%S'),
                    'subtask_name': 'dawn_e2e_tests'
                }
            
            # Step 1: Determine architecture and OS
            arch_info = self.get_system_architecture()
            if not arch_info['success']:
                return {
                    'status': 'system_detection_failed',
                    'error': arch_info['error'],
                    'test_summary': {'total_tests': 0, 'passed': 0, 'failed': 0, 'skipped': 0},
                    'failures': [],
                    'timestamp': start_time.isoformat(),
                    'execution_time': 0
                }
            
            arch = arch_info['architecture']
            os_name = arch_info['os']
            
            logging.info(f"Detected system: {arch}/{os_name}")
            
            # Step 2: Copy the latest Dawn binary from network share
            download_result = self.download_latest_dawn_binary(arch, os_name)
            if not download_result['success']:
                return {
                    'status': 'download_failed',
                    'error': download_result['error'],
                    'test_summary': {'total_tests': 0, 'passed': 0, 'failed': 0, 'skipped': 0},
                    'failures': [],
                    'timestamp': start_time.isoformat(),
                    'download_info': download_result,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # Step 3: Extract the binary
            extraction_result = self.extract_dawn_binary(download_result['file_path'], arch, os_name)
            if not extraction_result['success']:
                return {
                    'status': 'extraction_failed',
                    'error': extraction_result['error'],
                    'test_summary': {'total_tests': 0, 'passed': 0, 'failed': 0, 'skipped': 0},
                    'failures': [],
                    'timestamp': start_time.isoformat(),
                    'download_info': download_result,
                    'extraction_info': extraction_result,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # Step 4: Run the Dawn E2E tests
            test_result = self.run_dawn_tests(extraction_result['extraction_path'])
            if not test_result['success']:
                return {
                    'status': 'test_failed',
                    'error': test_result['error'],
                    'test_summary': {'total_tests': 0, 'passed': 0, 'failed': 0, 'skipped': 0},
                    'failures': [],
                    'timestamp': start_time.isoformat(),
                    'download_info': download_result,
                    'extraction_info': extraction_result,
                    'execution_info': test_result,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # Step 5: Parse the test results (placeholder for now)
            parse_result = self.parse_dawn_test_results(extraction_result['extraction_path'])
            if not parse_result['success']:
                return {
                    'status': 'parse_failed',
                    'error': parse_result['error'],
                    'test_summary': {'total_tests': 0, 'passed': 0, 'failed': 0, 'skipped': 0},
                    'failures': [],
                    'timestamp': start_time.isoformat(),
                    'download_info': download_result,
                    'extraction_info': extraction_result,
                    'execution_info': test_result,
                    'parse_info': parse_result,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # Success - return comprehensive results
            end_time = datetime.now()
            return {
                'status': 'success',
                'test_summary': parse_result['test_summary'],
                'pass_fail': parse_result['pass_fail'],  # Array of failed test names
                'failures': parse_result['failures'],    # Detailed failure information
                'timestamp': start_time.isoformat(),
                'download_info': download_result,
                'extraction_info': extraction_result,
                'execution_info': test_result,
                'parse_info': parse_result,
                'execution_time': (end_time - start_time).total_seconds()
            }
            
        except Exception as e:
            logging.error(f"Dawn E2E tests failed with unexpected error: {e}")
            return {
                'status': 'unexpected_error',
                'error': str(e),
                'test_summary': {'total_tests': 0, 'passed': 0, 'failed': 0, 'skipped': 0},
                'failures': [],
                'timestamp': start_time.isoformat(),
                'execution_time': (datetime.now() - start_time).total_seconds()
            }
    
    def get_result(self) -> Any:
        """Get the result of the Dawn E2E tests execution."""
        return self.result
    
    def get_description(self) -> str:
        """Get a simple description of this subtask."""
        return "Run Dawn E2E tests"
    
    def get_system_architecture(self) -> Dict[str, Any]:
        """
        Determine the system architecture and OS for Dawn binary selection.
        
        Returns:
            Dict[str, Any]: System information including architecture and OS
        """
        try:
            # Get architecture from platform.machine() and convert to lowercase
            arch = platform.machine().lower()
            
            # Normalize architecture names
            arch_mapping = {
                'x86_64': 'x64',
                'amd64': 'x64',
                'i386': 'x86',
                'i686': 'x86',
                'arm64': 'arm64',
                'aarch64': 'arm64'
            }
            
            architecture = arch_mapping.get(arch, arch)
            
            # Get OS from sys.platform and convert to lowercase
            platform_name = sys.platform.lower()
            
            # Normalize OS names
            os_mapping = {
                'win32': 'windows',
                'win64': 'windows',
                'darwin': 'macos',
                'linux': 'linux',
                'linux2': 'linux'
            }
            
            os_name = os_mapping.get(platform_name, platform_name)
            
            return {
                'success': True,
                'architecture': architecture,
                'os': os_name,
                'raw_architecture': arch,
                'raw_platform': platform_name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to detect system architecture: {e}"
            }
    
    def download_latest_dawn_binary(self, arch: str, os_name: str) -> Dict[str, Any]:
        """Download the latest Dawn binary from the network backup location."""
        try:
            # Network share path
            network_path = f"\\\\webgfx-200.guest.corp.microsoft.com\\backup\\{arch}\\{os_name}\\dawn\\"
            local_backup_path = f"ignore\\client\\backup\\{arch}\\{os_name}\\dawn\\"
            
            logging.info(f"Checking network share: {network_path}")
            
            # Create local backup directory if it doesn't exist
            os.makedirs(local_backup_path, exist_ok=True)
            
            # Check if network path exists and is accessible using more robust method
            if not self._is_network_path_accessible(network_path):
                return {
                    'success': False,
                    'error': f"Network path not accessible: {network_path}"
                }
            
            # Find the latest version on network share
            network_latest = self.find_latest_version(network_path)
            if not network_latest:
                return {
                    'success': False,
                    'error': f"No Dawn binaries found in {network_path}"
                }
            
            # Find the latest local version
            local_latest = self.find_latest_version(local_backup_path)
            
            # Compare versions and determine if we need to download
            need_download = True
            if local_latest:
                network_version = self.extract_version(network_latest['filename'])
                local_version = self.extract_version(local_latest['filename'])
                
                if network_version and local_version:
                    if network_version <= local_version:
                        need_download = False
                        logging.info(f"Local version {local_version} is up to date (network: {network_version})")
                    else:
                        logging.info(f"Network version {network_version} is newer than local {local_version}")
            
            if need_download:
                # Download the latest version
                source_path = os.path.join(network_path, network_latest['filename'])
                dest_path = os.path.join(local_backup_path, network_latest['filename'])
                
                logging.info(f"Downloading {source_path} to {dest_path}")
                shutil.copy2(source_path, dest_path)
                
                return {
                    'success': True,
                    'binary_name': network_latest['filename'],
                    'file_path': dest_path,
                    'version_info': {
                        'date': network_latest['date'],
                        'version': network_latest['version'],
                        'hash': network_latest['hash']
                    },
                    'action': 'downloaded'
                }
            else:
                # Use existing local version
                local_path = os.path.join(local_backup_path, local_latest['filename'])
                return {
                    'success': True,
                    'binary_name': local_latest['filename'],
                    'file_path': local_path,
                    'version_info': {
                        'date': local_latest['date'],
                        'version': local_latest['version'],
                        'hash': local_latest['hash']
                    },
                    'action': 'used_existing'
                }
                
        except Exception as e:
            logging.error(f"Failed to download Dawn binary: {e}")
            return {
                'success': False,
                'error': f"Failed to download Dawn binary: {e}"
            }
    
    def extract_dawn_binary(self, zip_file_path: str, arch: str, os_name: str) -> Dict[str, Any]:
        """Extract the Dawn binary to the appropriate location."""
        try:
            # Determine extraction directory
            backup_dir = os.path.dirname(zip_file_path)
            zip_basename = os.path.splitext(os.path.basename(zip_file_path))[0]
            extraction_path = os.path.join(backup_dir, zip_basename)
            
            # Check if already extracted by searching for the executable
            executable_path = self._find_dawn_executable(extraction_path)
            if executable_path and os.path.exists(executable_path):
                logging.info(f"Dawn binary already extracted at {os.path.dirname(executable_path)}")
                return {
                    'success': True,
                    'extraction_path': extraction_path,
                    'executable_path': executable_path,
                    'action': 'already_extracted'
                }
            
            # Extract the zip file
            logging.info(f"Extracting {zip_file_path} to {extraction_path}")
            
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(extraction_path)
            
            # Find the executable after extraction
            executable_path = self._find_dawn_executable(extraction_path)
            if not executable_path or not os.path.exists(executable_path):
                # List extracted files for debugging
                extracted_files = []
                for root, dirs, files in os.walk(extraction_path):
                    for file in files:
                        extracted_files.append(os.path.relpath(os.path.join(root, file), extraction_path))
                
                return {
                    'success': False,
                    'error': f"dawn_end2end_tests.exe not found in extracted files. Found: {extracted_files[:10]}"  # Show first 10 files
                }
            
            return {
                'success': True,
                'extraction_path': extraction_path,
                'executable_path': executable_path,
                'action': 'extracted'
            }
            
        except zipfile.BadZipFile:
            return {
                'success': False,
                'error': f"Invalid zip file: {zip_file_path}"
            }
        except Exception as e:
            logging.error(f"Failed to extract binary: {e}")
            return {
                'success': False,
                'error': f"Failed to extract binary: {e}"
            }
    
    def run_dawn_tests(self, extraction_path: str) -> Dict[str, Any]:
        """Run the Dawn E2E tests with the specified parameters."""
        try:
            executable_path = self._find_dawn_executable(extraction_path)
            
            if not executable_path or not os.path.exists(executable_path):
                return {
                    'success': False,
                    'error': f"Dawn executable not found in {extraction_path}"
                }
            
            # Create output directory for test results
            # Use task context if available, otherwise create a timestamped directory
            if hasattr(self, 'task_context') and self.task_context:
                task_name = self.task_context.get('task_name', 'dawn_task')
                task_timestamp = self.task_context.get('task_timestamp', datetime.now().strftime('%Y%m%d%H%M%S'))
                subtask_name = self.task_context.get('subtask_name', 'dawn_e2e_tests')
            else:
                task_name = 'dawn_task'
                task_timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                subtask_name = 'dawn_e2e_tests'
            
            # Use absolute path for log directory - go up to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Go up to project root
            output_dir = os.path.join(base_dir, "ignore", "client", "logs", f"{task_timestamp}-{task_name}", subtask_name)
            os.makedirs(output_dir, exist_ok=True)
            
            json_output_path = os.path.join(output_dir, "dawn.json")
            
            # Build command with all required parameters
            cmd = [
                executable_path,
                "--enable-backend-validation=disabled",
                "--backend=d3d12",
                "--exclusive-device-type-preference=discrete,integrated",
                "--gtest_filter=*MaxLimitTests.MaxBufferBindingSize*",
                f"--gtest_output=json:{json_output_path}"
            ]
            
            logging.info(f"Running Dawn E2E tests: {' '.join(cmd)}")
            
            # Run the tests
            start_time = datetime.now()
            try:
                result = subprocess.run(
                    cmd,
                    cwd=extraction_path,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                logging.info(f"Dawn tests completed with return code: {result.returncode}")
                logging.info(f"Execution time: {execution_time:.2f} seconds")
                
                return {
                    'success': True,
                    'return_code': result.returncode,
                    'execution_time': execution_time,
                    'json_output_path': json_output_path,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'command': ' '.join(cmd)
                }
                
            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'error': "Dawn tests timed out after 5 minutes"
                }
                
        except Exception as e:
            logging.error(f"Failed to execute Dawn tests: {e}")
            return {
                'success': False,
                'error': f"Failed to execute tests: {e}"
            }
    
    def parse_dawn_test_results(self, extraction_path: str = None) -> Dict[str, Any]:
        """Parse the Dawn test results from the JSON output file."""
        try:
            # Get the JSON output file path
            if hasattr(self, 'task_context') and self.task_context:
                task_name = self.task_context.get('task_name', 'dawn_task')
                task_timestamp = self.task_context.get('task_timestamp', datetime.now().strftime('%Y%m%d%H%M%S'))
                subtask_name = self.task_context.get('subtask_name', 'dawn_e2e_tests')
            else:
                task_name = 'dawn_task'
                task_timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                subtask_name = 'dawn_e2e_tests'
            
            # Use absolute path for log directory - go up to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Go up to project root
            output_dir = os.path.join(base_dir, "ignore", "client", "logs", f"{task_timestamp}-{task_name}", subtask_name)
            json_output_path = os.path.join(output_dir, "dawn.json")
            
            # Check if JSON output file exists
            if not os.path.exists(json_output_path):
                logging.warning(f"JSON output file not found: {json_output_path}")
                return {
                    'success': False,
                    'error': f"JSON output file not found: {json_output_path}",
                    'test_summary': {
                        'total_tests': 0,
                        'passed': 0,
                        'failed': 0,
                        'skipped': 0,
                        'disabled': 0
                    },
                    'failures': []
                }
            
            # Read and parse the JSON file
            with open(json_output_path, 'r', encoding='utf-8') as f:
                test_data = json.load(f)
            
            logging.info(f"Successfully loaded JSON test results from: {json_output_path}")
            
            # Initialize counters based on your pseudo code
            pass_pass = 0
            pass_fail = []
            
            # Parse test results following the provided pseudo code structure
            if 'testsuites' in test_data:
                for test_suite in test_data['testsuites']:
                    suite_name = test_suite.get('name', 'UnknownSuite')
                    
                    # Handle both 'testsuite' and 'tests' keys (GTest can use either)
                    tests = test_suite.get('testsuite', test_suite.get('tests', []))
                    
                    for test in tests:
                        test_name = f"{suite_name}.{test.get('name', 'UnknownTest')}"
                        
                        # Check for failures (following your pseudo code logic)
                        if 'failures' in test and test['failures']:
                            pass_fail.append(test_name)
                        else:
                            pass_pass += 1
            
            # Calculate total tests as per your requirement
            total_tests = pass_pass + len(pass_fail)
            
            # Build comprehensive result with detailed failure information
            detailed_failures = []
            if pass_fail:
                # Get detailed failure information for the failed tests
                if 'testsuites' in test_data:
                    for test_suite in test_data['testsuites']:
                        suite_name = test_suite.get('name', 'UnknownSuite')
                        tests = test_suite.get('testsuite', test_suite.get('tests', []))
                        
                        for test in tests:
                            test_name = f"{suite_name}.{test.get('name', 'UnknownTest')}"
                            if test_name in pass_fail and 'failures' in test and test['failures']:
                                detailed_failures.append({
                                    'test_name': test_name,
                                    'failure_message': test['failures'][0].get('failure', 'Unknown failure') if test['failures'] else 'Unknown failure'
                                })
            
            # Build result structure matching your requirements
            test_summary = {
                'total_tests': total_tests,    # pass_pass + len(pass_fail)
                'passed': pass_pass,           # pass_pass
                'failed': len(pass_fail),      # len(pass_fail)
                'skipped': 0,                  # Can be enhanced later if needed
                'disabled': 0                  # Can be enhanced later if needed
            }
            
            logging.info(f"Test parsing complete - Total: {total_tests}, Passed: {pass_pass}, Failed: {len(pass_fail)}")
            
            return {
                'success': True,
                'test_summary': test_summary,
                'pass_fail': pass_fail,           # Array of failed test names
                'failures': detailed_failures,    # Detailed failure information
                'json_file_path': json_output_path,
                'raw_data_available': True
            }
            
        except FileNotFoundError:
            logging.error(f"JSON output file not found: {json_output_path}")
            return {
                'success': False,
                'error': f"JSON output file not found: {json_output_path}",
                'test_summary': {
                    'total_tests': 0,
                    'passed': 0,
                    'failed': 0,
                    'skipped': 0,
                    'disabled': 0
                },
                'failures': []
            }
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON file: {e}")
            return {
                'success': False,
                'error': f"Failed to parse JSON file: {e}",
                'test_summary': {
                    'total_tests': 0,
                    'passed': 0,
                    'failed': 0,
                    'skipped': 0,
                    'disabled': 0
                },
                'failures': []
            }
        except Exception as e:
            logging.error(f"Unexpected error parsing test results: {e}")
            return {
                'success': False,
                'error': f"Failed to parse results: {e}",
                'test_summary': {
                    'total_tests': 0,
                    'passed': 0,
                    'failed': 0,
                    'skipped': 0,
                    'disabled': 0
                },
                'failures': []
            }
    
    def find_latest_version(self, directory_path: str) -> Optional[Dict[str, str]]:
        """
        Find the latest version file in the given directory.
        Files are expected to be in format: {yyyymmdd}-{version}-{hash}.zip
        """
        try:
            if not os.path.exists(directory_path):
                return None
            
            # Pattern to match Dawn binary files
            pattern = re.compile(r'^(\d{8})-([^-]+)-([^.]+)\.zip$')
            
            latest_file = None
            latest_version = None
            
            for filename in os.listdir(directory_path):
                match = pattern.match(filename)
                if match:
                    date_str, version_str, hash_str = match.groups()
                    
                    # Try to convert version to a comparable format
                    version = self.parse_version_string(version_str)
                    
                    if latest_version is None or version > latest_version:
                        latest_version = version
                        latest_file = {
                            'filename': filename,
                            'date': date_str,
                            'version': version_str,
                            'hash': hash_str
                        }
            
            return latest_file
            
        except Exception as e:
            logging.error(f"Error finding latest version in {directory_path}: {e}")
            return None
    
    def extract_version(self, filename: str) -> Optional[tuple]:
        """Extract version tuple from filename for comparison."""
        try:
            pattern = re.compile(r'^(\d{8})-([^-]+)-([^.]+)\.zip$')
            match = pattern.match(filename)
            if match:
                _, version_str, _ = match.groups()
                return self.parse_version_string(version_str)
            return None
        except Exception:
            return None
    
    def parse_version_string(self, version_str: str) -> tuple:
        """
        Parse version string into a tuple for comparison.
        Handles various version formats like '1.2.3', '1.2.3-alpha', etc.
        """
        try:
            # Remove any non-numeric suffixes for comparison
            version_clean = re.sub(r'[^0-9.].*$', '', version_str)
            
            # Split by dots and convert to integers
            parts = []
            for part in version_clean.split('.'):
                if part.isdigit():
                    parts.append(int(part))
                else:
                    break
            
            # Pad with zeros to ensure consistent comparison
            while len(parts) < 4:
                parts.append(0)
            
            return tuple(parts)
            
        except Exception:
            # Fallback: use the string as-is for comparison
            return (version_str,)
    
    def _find_dawn_executable(self, extraction_path: str) -> str:
        """
        Find the dawn_end2end_tests.exe file in the extraction directory or its subdirectories.
        
        Args:
            extraction_path: Base path to search for the executable
            
        Returns:
            str: Full path to the executable if found, None otherwise
        """
        if not os.path.exists(extraction_path):
            return None
            
        # Search for dawn_end2end_tests.exe in the extraction path and all subdirectories
        for root, dirs, files in os.walk(extraction_path):
            for file in files:
                if file.lower() == "dawn_end2end_tests.exe":
                    executable_path = os.path.join(root, file)
                    logging.debug(f"Found Dawn executable at: {executable_path}")
                    return executable_path
        
        logging.warning(f"dawn_end2end_tests.exe not found in {extraction_path}")
        return None
    
    def _is_network_path_accessible(self, network_path: str) -> bool:
        """
        Check if a network path is accessible using multiple methods.
        
        Args:
            network_path: UNC path to check
            
        Returns:
            bool: True if accessible, False otherwise
        """
        try:
            # Method 1: Try to list directory contents directly
            try:
                files = os.listdir(network_path)
                logging.debug(f"Network path accessible via os.listdir: {len(files)} items found")
                return True
            except (OSError, PermissionError):
                pass
            
            # Method 2: Try using pathlib (better UNC support)
            try:
                from pathlib import Path
                path_obj = Path(network_path)
                if path_obj.exists() and path_obj.is_dir():
                    # Try to iterate to verify access
                    list(path_obj.iterdir())
                    logging.debug(f"Network path accessible via pathlib")
                    return True
            except (OSError, PermissionError):
                pass
            
            # Method 3: Try using subprocess to call dir command
            try:
                result = subprocess.run(
                    ['dir', network_path], 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result.returncode == 0:
                    logging.debug(f"Network path accessible via dir command")
                    return True
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass
            
            logging.warning(f"Network path not accessible via any method: {network_path}")
            return False
            
        except Exception as e:
            logging.error(f"Error checking network path accessibility: {e}")
            return False


# Register the subtask class instance
register_subtask_class('dawn_e2e_tests', DawnE2ETestsSubtask())


# Legacy function wrapper for backward compatibility
def dawn_e2e_tests() -> Dict[str, Any]:
    """Legacy function wrapper for dawn_e2e_tests subtask."""
    subtask = DawnE2ETestsSubtask()
    return subtask.run()


def get_dawn_test_summary() -> Dict[str, Any]:
    """Get a quick summary of the last Dawn test execution."""
    try:
        result = dawn_e2e_tests()
        
        if result['status'] == 'success':
            summary = result['test_summary']
            return {
                'status': 'completed',
                'total_tests': summary['total_tests'],
                'passed': summary['passed'],
                'failed': summary['failed'],
                'failure_count': len(result['failures']),
                'execution_time': result.get('execution_time', 0),
                'timestamp': result['timestamp']
            }
        else:
            return {
                'status': 'failed',
                'error': result.get('error', 'Unknown error'),
                'timestamp': result['timestamp']
            }
            
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
