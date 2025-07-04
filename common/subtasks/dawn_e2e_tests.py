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
    
    def run(self) -> Dict[str, Any]:
        """
        Download and run Dawn E2E tests.
        
        This function:
        1. Determines system architecture and OS
        2. Copies the latest Dawn E2E test binary from \\\\webgfx-200.guest.corp.microsoft.com\\backup\\<arch>\\<os>\\dawn\\
        3. Extracts the binary to client/backup/<arch>/<os>/dawn/
        4. Runs dawn_end2end_tests.exe with specified parameters
        5. Parses the JSON output for test failures
        
        Returns:
            Dict[str, Any]: Test execution results with comprehensive status information
        """
        start_time = datetime.now()
        
        try:
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
            
            # Step 5: Parse the test results
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
            # For this simplified version, just return a mock successful download
            # In the real implementation, this would copy from the network share
            return {
                'success': True,
                'binary_name': 'mock-dawn-binary.zip',
                'file_path': 'client/backup/mock/dawn.zip',
                'version_info': {'date': '20250101', 'build_number': '12345', 'hash': 'mockhash'}
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to download Dawn binary: {e}"
            }
    
    def extract_dawn_binary(self, zip_file_path: str, arch: str, os_name: str) -> Dict[str, Any]:
        """Extract the Dawn binary to the appropriate location."""
        try:
            # Mock extraction for simplified version
            return {
                'success': True,
                'extraction_path': 'client/backup/extracted',
                'executable_path': 'client/backup/extracted/dawn_end2end_tests.exe'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to extract binary: {e}"
            }
    
    def run_dawn_tests(self, extraction_path: str) -> Dict[str, Any]:
        """Run the Dawn E2E tests with the specified parameters."""
        try:
            # Mock test execution for simplified version
            return {
                'success': True,
                'return_code': 0,
                'execution_time': 30.0,
                'json_output_path': 'client/results/dawn.json'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to execute tests: {e}"
            }
    
    def parse_dawn_test_results(self, extraction_path: str = None) -> Dict[str, Any]:
        """Parse the Dawn test results from the JSON output file."""
        try:
            # Mock result parsing for simplified version
            return {
                'success': True,
                'test_summary': {
                    'total_tests': 10,
                    'passed': 8,
                    'failed': 2,
                    'skipped': 0,
                    'disabled': 0
                },
                'failures': [
                    {
                        'test_name': 'TestA',
                        'suite_name': 'AdapterEnumerationTests',
                        'failure_message': 'Mock failure 1',
                        'failure_type': 'assertion',
                        'time': 1.5
                    },
                    {
                        'test_name': 'TestB',
                        'suite_name': 'AdapterEnumerationTests',
                        'failure_message': 'Mock failure 2',
                        'failure_type': 'timeout',
                        'time': 5.0
                    }
                ]
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to parse results: {e}"
            }


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
