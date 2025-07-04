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

from .base import SubtaskResultDefinition
from . import register_subtask


# Define the result specification for this subtask
DAWN_E2E_RESULT_DEF = SubtaskResultDefinition(
    name="dawn_e2e_tests",
    description="Downloads and runs Dawn E2E tests, returning test failure information",
    result_type="object",
    required_fields=["status", "test_summary", "failures", "timestamp"],
    is_critical=False,
    format_hint="Object containing test execution status, summary statistics, and detailed failure information"
)


@register_subtask('dawn_e2e_tests', DAWN_E2E_RESULT_DEF)
def dawn_e2e_tests() -> Dict[str, Any]:
    """
    Download and run Dawn E2E tests.
    
    This function:
    1. Determines system architecture and OS
    2. Copies the latest Dawn E2E test binary from \\webgfx-200.guest.corp.microsoft.com\backup\<arch>\<os>\dawn\
    3. Extracts the binary to client/backup/<arch>/<os>/dawn/
    4. Runs dawn_end2end_tests.exe with specified parameters
    5. Parses the JSON output for test failures
    
    Returns:
        Dict[str, Any]: Test execution results with the following structure:
            - status: Overall execution status ('success', 'download_failed', 'extraction_failed', 'test_failed', 'parse_failed')
            - test_summary: Summary statistics (total_tests, passed, failed, skipped)
            - failures: List of detailed failure information
            - timestamp: When the test was executed
            - download_info: Information about the copied binary
            - execution_info: Details about test execution
            - error: Error message if something went wrong
        
    Example:
        >>> result = execute_subtask('dawn_e2e_tests')
        >>> print(result['result']['test_summary']['failed'])  # Number of failed tests
        >>> print(len(result['result']['failures']))  # Detailed failure list
    """
    start_time = datetime.now()
    
    try:
        # Step 1: Determine architecture and OS
        arch_info = get_system_architecture()
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
        download_result = download_latest_dawn_binary(arch, os_name)
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
        extraction_result = extract_dawn_binary(download_result['file_path'], arch, os_name)
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
        test_result = run_dawn_tests(extraction_result['extraction_path'])
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
        
        # Step 5: Parse the test results
        parse_result = parse_dawn_test_results(extraction_result['extraction_path'])
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
            'failures': parse_result['failures'],
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


def get_system_architecture() -> Dict[str, Any]:
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


def download_latest_dawn_binary(arch: str, os_name: str) -> Dict[str, Any]:
    """
    Copy the latest Dawn binary from the network backup location.
    
    Args:
        arch: System architecture (e.g., 'x64', 'arm64')
        os_name: Operating system (e.g., 'windows', 'linux', 'macos')
        
    Returns:
        Dict[str, Any]: Copy result information
    """
    try:
        # Construct the UNC path to the backup location
        backup_path = Path(f"\\\\webgfx-200.guest.corp.microsoft.com\\backup\\{arch}\\{os_name}\\dawn")
        
        logging.info(f"Attempting to access binary directory: {backup_path}")
        
        # Check if the backup path exists and is accessible
        if not backup_path.exists():
            return {
                'success': False,
                'error': f"Backup path not accessible: {backup_path}"
            }
        
        # List all files in the directory and find Dawn binaries
        try:
            files = list(backup_path.glob("*.zip"))
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to list files in {backup_path}: {e}"
            }
        
        # Parse filenames to find binaries matching the expected pattern
        # Look for files matching pattern: date-buildnumber-longhash
        # Example: 20250318-20717-5e38b2fe49fd5640a12d7d0258148de825e4c520.zip
        binary_pattern = r'(\d{8})-(\d+)-([a-f0-9]{40})\.zip'
        matches = []
        
        for file_path in files:
            match = re.match(binary_pattern, file_path.name, re.IGNORECASE)
            if match:
                matches.append((match.group(1), match.group(2), match.group(3), file_path))
        
        if not matches:
            return {
                'success': False,
                'error': f"No Dawn binaries found in {backup_path}. Expected format: YYYYMMDD-buildnumber-hash.zip"
            }
        
        # Find the latest version
        latest_binary = find_latest_binary_with_paths(matches)
        if not latest_binary:
            return {
                'success': False,
                'error': "Could not determine latest binary version"
            }
        
        date, build_number, hash_val, source_file_path = latest_binary
        binary_filename = f"{date}-{build_number}-{hash_val}.zip"
        
        # Create local download directory
        local_dir = Path("client/backup") / arch / os_name / "dawn"
        local_dir.mkdir(parents=True, exist_ok=True)
        
        local_file_path = local_dir / binary_filename
        
        # Copy the binary from network location to local directory
        logging.info(f"Copying {binary_filename} from {source_file_path} to {local_file_path}")
        
        try:
            shutil.copy2(source_file_path, local_file_path)
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to copy {source_file_path} to {local_file_path}: {e}"
            }
        
        # Verify copy
        if not local_file_path.exists() or local_file_path.stat().st_size == 0:
            return {
                'success': False,
                'error': f"Copied file {local_file_path} is missing or empty"
            }
        
        return {
            'success': True,
            'binary_name': binary_filename,
            'file_path': str(local_file_path),
            'source_path': str(source_file_path),
            'file_size': local_file_path.stat().st_size,
            'version_info': {
                'date': date,
                'build_number': build_number,
                'hash': hash_val
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error during binary copy: {e}"
        }


def find_latest_binary(binary_matches: List[tuple]) -> Optional[tuple]:
    """
    Find the latest binary based on build number comparison.
    
    Args:
        binary_matches: List of tuples (date, build_number, hash)
        
    Returns:
        Optional[tuple]: Latest binary tuple or None
    """
    if not binary_matches:
        return None
    
    # Sort by date first, then by build number
    def version_key(match):
        date, build_number, hash_val = match
        try:
            # Convert date from YYYYMMDD to comparable format
            date_int = int(date)
            build_int = int(build_number)
            return (date_int, build_int)
        except ValueError:
            # Fallback: return date and build number as strings
            return (date, build_number)
    
    try:
        sorted_binaries = sorted(binary_matches, key=version_key, reverse=True)
        return sorted_binaries[0]
    except Exception as e:
        logging.warning(f"Failed to sort binaries by build number, using first: {e}")
        return binary_matches[0]


def find_latest_binary_with_paths(binary_matches: List[tuple]) -> Optional[tuple]:
    """
    Find the latest binary based on build number comparison (version with file paths).
    
    Args:
        binary_matches: List of tuples (date, build_number, hash, file_path)
        
    Returns:
        Optional[tuple]: Latest binary tuple or None
    """
    if not binary_matches:
        return None
    
    # Sort by date first, then by build number
    def version_key(match):
        date, build_number, hash_val, file_path = match
        try:
            # Convert date from YYYYMMDD to comparable format
            date_int = int(date)
            build_int = int(build_number)
            return (date_int, build_int)
        except ValueError:
            # Fallback: return date and build number as strings
            return (date, build_number)
    
    try:
        sorted_binaries = sorted(binary_matches, key=version_key, reverse=True)
        return sorted_binaries[0]
    except Exception as e:
        logging.warning(f"Failed to sort binaries by build number, using first: {e}")
        return binary_matches[0]


def extract_dawn_binary(zip_file_path: str, arch: str, os_name: str) -> Dict[str, Any]:
    """
    Extract the Dawn binary to the appropriate location.
    
    Args:
        zip_file_path: Path to the downloaded zip file
        arch: System architecture
        os_name: Operating system name
        
    Returns:
        Dict[str, Any]: Extraction result information
    """
    try:
        extraction_dir = Path("client/backup") / arch / os_name / "dawn" / "extracted"
        extraction_dir.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"Extracting {zip_file_path} to {extraction_dir}")
        
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extraction_dir)
        
        # Find the dawn_end2end_tests.exe file
        exe_files = list(extraction_dir.rglob("dawn_end2end_tests.exe"))
        if not exe_files:
            # Also check for files without .exe extension (Linux/macOS)
            exe_files = list(extraction_dir.rglob("dawn_end2end_tests"))
        
        if not exe_files:
            return {
                'success': False,
                'error': f"dawn_end2end_tests executable not found in extracted files"
            }
        
        exe_path = exe_files[0]
        
        # Make executable on Unix systems
        if os_name != 'windows':
            exe_path.chmod(0o755)
        
        return {
            'success': True,
            'extraction_path': str(extraction_dir),
            'executable_path': str(exe_path),
            'extracted_files': [str(f) for f in extraction_dir.rglob("*") if f.is_file()]
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to extract binary: {e}"
        }


def run_dawn_tests(extraction_path: str) -> Dict[str, Any]:
    """
    Run the Dawn E2E tests with the specified parameters.
    
    Args:
        extraction_path: Directory where the binary was extracted
        
    Returns:
        Dict[str, Any]: Test execution result information
    """
    try:
        # Find the executable
        extraction_dir = Path(extraction_path)
        exe_files = list(extraction_dir.rglob("dawn_end2end_tests.exe"))
        if not exe_files:
            exe_files = list(extraction_dir.rglob("dawn_end2end_tests"))
        
        if not exe_files:
            return {
                'success': False,
                'error': "dawn_end2end_tests executable not found"
            }
        
        exe_path = exe_files[0]
        
        # Create results directory (use absolute path)
        results_dir = Path("client/results").resolve()
        results_dir.mkdir(parents=True, exist_ok=True)
        json_output_path = results_dir / "dawn.json"
        
        # Construct the command
        command = [
            str(exe_path),
            "--enable-backend-validation=disabled",
            "--backend=d3d12",
            "--exclusive-device-type-preference=discrete,integrated",
            "--gtest_filter=AdapterEnumerationTests*",
            f"--gtest_output=json:{json_output_path}"
        ]
        
        logging.info(f"Running command: {' '.join(command)}")
        
        # Run the command
        start_time = datetime.now()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(extraction_dir)
            )
            end_time = datetime.now()
            
            return {
                'success': True,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'execution_time': (end_time - start_time).total_seconds(),
                'json_output_path': str(json_output_path),
                'command': command
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': "Test execution timed out after 5 minutes"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to execute tests: {e}"
            }
        
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error during test execution: {e}"
        }


def parse_dawn_test_results(extraction_path: str = None) -> Dict[str, Any]:
    """
    Parse the Dawn test results from the JSON output file.
    
    Args:
        extraction_path: Path where the test was executed (to locate the JSON file)
    
    Returns:
        Dict[str, Any]: Parsed test results including failures
    """
    try:
        if extraction_path:
            # Look for the JSON file in the extraction directory structure
            extraction_dir = Path(extraction_path)
            json_files = list(extraction_dir.rglob("dawn.json"))
            if json_files:
                json_file_path = json_files[0]
            else:
                json_file_path = Path("client/results/dawn.json")
        else:
            json_file_path = Path("client/results/dawn.json")
        
        if not json_file_path.exists():
            return {
                'success': False,
                'error': f"Test results file not found: {json_file_path}"
            }
        
        # Read and parse the JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # Initialize summary
        test_summary = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'disabled': 0
        }
        
        failures = []
        
        # Parse different JSON formats that gtest might produce
        if 'testsuites' in test_data:
            # Standard gtest JSON format
            for testsuite in test_data['testsuites']:
                # Use the outer testsuite object for metadata
                suite_data = testsuite
                
                test_summary['total_tests'] += suite_data.get('tests', 0)
                test_summary['failed'] += suite_data.get('failures', 0)
                test_summary['skipped'] += suite_data.get('skipped', 0)
                test_summary['disabled'] += suite_data.get('disabled', 0)
                
                # Process individual test cases from the 'testsuite' list if it exists
                test_cases = []
                if 'testsuite' in suite_data and isinstance(suite_data['testsuite'], list):
                    test_cases = suite_data['testsuite']
                elif 'testcase' in suite_data:
                    test_cases = suite_data['testcase']
                    if not isinstance(test_cases, list):
                        test_cases = [test_cases]
                
                for testcase in test_cases:
                    if 'failure' in testcase:
                        failure_info = {
                            'test_name': testcase.get('name', 'unknown'),
                            'suite_name': suite_data.get('name', 'unknown'),
                            'failure_message': testcase['failure'].get('message', 'No message'),
                            'failure_type': testcase['failure'].get('type', 'unknown'),
                            'time': testcase.get('time', 0)
                        }
                        failures.append(failure_info)
        
        # Calculate passed tests
        test_summary['passed'] = (test_summary['total_tests'] - 
                                 test_summary['failed'] - 
                                 test_summary['skipped'] - 
                                 test_summary['disabled'])
        
        return {
            'success': True,
            'test_summary': test_summary,
            'failures': failures,
            'raw_data_available': True,
            'json_file_path': str(json_file_path)
        }
        
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'error': f"Failed to parse JSON results: {e}"
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error parsing results: {e}"
        }


def get_dawn_test_summary() -> Dict[str, Any]:
    """
    Get a quick summary of the last Dawn test execution.
    
    Returns:
        Dict[str, Any]: Quick summary suitable for logging or display
    """
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
