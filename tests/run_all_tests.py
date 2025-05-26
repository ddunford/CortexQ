#!/usr/bin/env python3
"""
Comprehensive test runner for the Enterprise RAG System backend.
Executes all unit, integration, and end-to-end tests with coverage reporting.
"""

import os
import sys
import subprocess
import time
import argparse
from pathlib import Path
import json

# Add the core-api src directory to Python path
# Check if we're in Docker container (/app) or host system
if os.path.exists('/app/src'):
    sys.path.insert(0, '/app/src')
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core-api', 'src'))

def run_command(command, description, capture_output=True):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Determine working directory - use /app if in container, otherwise project root
    if os.path.exists('/app/src'):
        work_dir = '/app'
    else:
        work_dir = os.path.join(os.path.dirname(__file__), '..')
    
    try:
        if capture_output:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                cwd=work_dir
            )
        else:
            result = subprocess.run(
                command, 
                shell=True,
                cwd=work_dir
            )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully in {duration:.2f}s")
            if capture_output and result.stdout:
                print(f"\nOutput:\n{result.stdout}")
        else:
            print(f"❌ {description} failed in {duration:.2f}s")
            if capture_output:
                if result.stdout:
                    print(f"\nStdout:\n{result.stdout}")
                if result.stderr:
                    print(f"\nStderr:\n{result.stderr}")
        
        return result
    
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return None

def check_dependencies():
    """Check if required dependencies are installed."""
    print("\n🔍 Checking test dependencies...")
    
    required_packages = [
        'pytest',
        'pytest-cov',
        'pytest-asyncio',
        'pytest-mock',
        'coverage'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} is missing")
    
    if missing_packages:
        print(f"\n⚠️  Installing missing packages: {', '.join(missing_packages)}")
        install_cmd = f"pip install {' '.join(missing_packages)}"
        result = run_command(install_cmd, "Installing missing test dependencies")
        
        if result and result.returncode != 0:
            print("❌ Failed to install dependencies. Please install manually:")
            print(f"   {install_cmd}")
            return False
    
    return True

def run_unit_tests(verbose=False, coverage=True):
    """Run all unit tests."""
    test_dir = "tests/unit"
    
    if not os.path.exists(test_dir):
        print(f"❌ Unit test directory {test_dir} not found")
        return False
    
    # Build pytest command
    cmd_parts = ["python", "-m", "pytest"]
    
    if coverage:
        # Adjust coverage path based on environment
        if os.path.exists('/app/src'):
            cov_path = "src"
        else:
            cov_path = "core-api/src"
        
        cmd_parts.extend([
            f"--cov={cov_path}",
            "--cov-report=html:tests/coverage/html",
            "--cov-report=xml:tests/coverage/coverage.xml",
            "--cov-report=term-missing"
        ])
    
    if verbose:
        cmd_parts.append("-v")
    
    cmd_parts.extend([
        "--tb=short",
        "--asyncio-mode=auto",
        test_dir
    ])
    
    command = " ".join(cmd_parts)
    result = run_command(command, "Running unit tests", capture_output=False)
    
    return result and result.returncode == 0

def run_integration_tests(verbose=False):
    """Run all integration tests."""
    test_dir = "tests/integration"
    
    if not os.path.exists(test_dir):
        print(f"❌ Integration test directory {test_dir} not found")
        return False
    
    # Build pytest command
    cmd_parts = ["python", "-m", "pytest"]
    
    if verbose:
        cmd_parts.append("-v")
    
    cmd_parts.extend([
        "--tb=short",
        "--asyncio-mode=auto",
        test_dir
    ])
    
    command = " ".join(cmd_parts)
    result = run_command(command, "Running integration tests", capture_output=False)
    
    return result and result.returncode == 0

def run_e2e_tests(verbose=False):
    """Run all end-to-end tests."""
    test_dir = "tests/e2e"
    
    if not os.path.exists(test_dir):
        print(f"⚠️  End-to-end test directory {test_dir} not found, skipping...")
        return True
    
    # Build pytest command
    cmd_parts = ["python", "-m", "pytest"]
    
    if verbose:
        cmd_parts.append("-v")
    
    cmd_parts.extend([
        "--tb=short",
        "--asyncio-mode=auto",
        test_dir
    ])
    
    command = " ".join(cmd_parts)
    result = run_command(command, "Running end-to-end tests", capture_output=False)
    
    return result and result.returncode == 0

def run_specific_test_file(test_file, verbose=False):
    """Run a specific test file."""
    if not os.path.exists(test_file):
        print(f"❌ Test file {test_file} not found")
        return False
    
    # Build pytest command
    cmd_parts = ["python", "-m", "pytest"]
    
    if verbose:
        cmd_parts.append("-v")
    
    cmd_parts.extend([
        "--tb=short",
        "--asyncio-mode=auto",
        test_file
    ])
    
    command = " ".join(cmd_parts)
    result = run_command(command, f"Running test file: {test_file}", capture_output=False)
    
    return result and result.returncode == 0

def run_linting():
    """Run code linting checks."""
    print("\n🔍 Running code quality checks...")
    
    # Check if flake8 is available
    try:
        import flake8
        # Adjust path based on environment
        if os.path.exists('/app/src'):
            src_path = "src"
        else:
            src_path = "core-api/src"
        
        flake8_cmd = f"python -m flake8 {src_path} --max-line-length=120 --ignore=E203,W503"
        result = run_command(flake8_cmd, "Running flake8 linting")
        
        if result and result.returncode == 0:
            print("✅ Code passes flake8 linting")
        else:
            print("⚠️  Code has linting issues")
    except ImportError:
        print("⚠️  flake8 not installed, skipping linting")

def check_import_structure():
    """Check that all modules can be imported correctly."""
    print("\n🔍 Checking import structure...")
    
    core_modules = [
        'main',
        'rag_processor',
        'background_processor',
        'llm_service',
        'embeddings_service',
        'storage_utils',
        'auth_utils',
        'classifiers',
        'database'
    ]
    
    import_errors = []
    
    for module in core_modules:
        try:
            __import__(module)
            print(f"✅ {module} imports successfully")
        except Exception as e:
            import_errors.append((module, str(e)))
            print(f"❌ {module} import failed: {e}")
    
    if import_errors:
        print(f"\n⚠️  {len(import_errors)} modules have import issues")
        return False
    else:
        print("\n✅ All core modules import successfully")
        return True

def generate_test_report(results):
    """Generate a comprehensive test report."""
    print("\n" + "="*80)
    print("📊 TEST EXECUTION SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    print(f"Total test suites: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    # Check for coverage report
    coverage_html = "tests/coverage/html/index.html"
    if os.path.exists(coverage_html):
        print(f"\n📈 Coverage report generated: {coverage_html}")
    
    return passed_tests == total_tests

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Enterprise RAG System Test Runner")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--no-coverage", action="store_true", help="Skip coverage reporting")
    parser.add_argument("--unit-only", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration-only", action="store_true", help="Run only integration tests")
    parser.add_argument("--e2e-only", action="store_true", help="Run only end-to-end tests")
    parser.add_argument("--file", help="Run specific test file")
    parser.add_argument("--no-lint", action="store_true", help="Skip linting checks")
    parser.add_argument("--no-imports", action="store_true", help="Skip import checks")
    
    args = parser.parse_args()
    
    print("🚀 Enterprise RAG System - Backend Test Suite")
    print("=" * 60)
    
    # Create coverage directory
    os.makedirs("tests/coverage", exist_ok=True)
    
    results = {}
    
    # Check dependencies first
    if not check_dependencies():
        print("❌ Dependency check failed. Please install required packages.")
        return 1
    
    # Check imports unless skipped
    if not args.no_imports:
        results["Import Structure"] = check_import_structure()
    
    # Run linting unless skipped
    if not args.no_lint:
        run_linting()
    
    # Run specific test file if provided
    if args.file:
        results[f"Test File: {args.file}"] = run_specific_test_file(args.file, args.verbose)
    else:
        # Run test suites based on arguments
        if args.unit_only:
            results["Unit Tests"] = run_unit_tests(args.verbose, not args.no_coverage)
        elif args.integration_only:
            results["Integration Tests"] = run_integration_tests(args.verbose)
        elif args.e2e_only:
            results["End-to-End Tests"] = run_e2e_tests(args.verbose)
        else:
            # Run all tests
            results["Unit Tests"] = run_unit_tests(args.verbose, not args.no_coverage)
            results["Integration Tests"] = run_integration_tests(args.verbose)
            results["End-to-End Tests"] = run_e2e_tests(args.verbose)
    
    # Generate final report
    all_passed = generate_test_report(results)
    
    if all_passed:
        print("\n🎉 All tests passed! The backend is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 