#!/usr/bin/env python3
"""
Comprehensive Test Runner for Enterprise RAG System
Executes all tests with detailed reporting, coverage analysis, and performance metrics.
"""

import os
import sys
import subprocess
import time
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import importlib.util

# Add the core-api src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "core-api" / "src"))

def check_dependencies():
    """Check if all required testing dependencies are installed."""
    required_packages = [
        'pytest',
        'pytest-asyncio',
        'pytest-cov',
        'pytest-html',
        'pytest-xdist',
        'pytest-mock',
        'coverage',
        'httpx',
        'fastapi[all]',
        'sqlalchemy',
        'psycopg2-binary',
        'redis',
        'minio',
        'sentence-transformers',
        'openai',
        'pydantic',
        'bcrypt',
        'python-jose[cryptography]',
        'python-multipart'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if '[' in package:
                # Handle packages with extras like fastapi[all]
                package_name = package.split('[')[0]
            else:
                package_name = package
            
            __import__(package_name.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All required dependencies are installed")
    return True


def run_linting():
    """Run code linting and formatting checks."""
    print("\n🔍 Running code quality checks...")
    
    # Check if flake8 is available
    try:
        result = subprocess.run(['flake8', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("Running flake8 linting...")
            result = subprocess.run([
                'flake8', 
                'core-api/src/',
                'tests/',
                '--max-line-length=100',
                '--ignore=E501,W503,E203'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Flake8 linting passed")
            else:
                print(f"⚠️ Flake8 found issues:\n{result.stdout}")
        else:
            print("⚠️ Flake8 not available, skipping linting")
    except FileNotFoundError:
        print("⚠️ Flake8 not installed, skipping linting")
    
    # Check if black is available
    try:
        result = subprocess.run(['black', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("Checking code formatting with black...")
            result = subprocess.run([
                'black', 
                '--check',
                '--diff',
                'core-api/src/',
                'tests/'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Code formatting is correct")
            else:
                print(f"⚠️ Code formatting issues found:\n{result.stdout}")
        else:
            print("⚠️ Black not available, skipping format check")
    except FileNotFoundError:
        print("⚠️ Black not installed, skipping format check")


def run_unit_tests(verbose: bool = False, coverage: bool = True):
    """Run unit tests with coverage reporting."""
    print("\n🧪 Running unit tests...")
    
    cmd = ['python', '-m', 'pytest', 'tests/unit/']
    
    if verbose:
        cmd.append('-v')
    
    if coverage:
        cmd.extend([
            '--cov=core-api/src',
            '--cov-report=html:tests/reports/coverage_html',
            '--cov-report=xml:tests/reports/coverage.xml',
            '--cov-report=term-missing'
        ])
    
    # Add HTML report
    cmd.extend([
        '--html=tests/reports/unit_tests.html',
        '--self-contained-html'
    ])
    
    # Run tests in parallel if pytest-xdist is available
    try:
        import xdist
        cmd.extend(['-n', 'auto'])
        print("Running tests in parallel...")
    except ImportError:
        print("Running tests sequentially...")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"Unit tests completed in {end_time - start_time:.2f} seconds")
    
    if result.returncode == 0:
        print("✅ All unit tests passed")
    else:
        print(f"❌ Some unit tests failed:\n{result.stdout}\n{result.stderr}")
    
    return result.returncode == 0


def run_integration_tests(verbose: bool = False):
    """Run integration tests."""
    print("\n🔗 Running integration tests...")
    
    cmd = ['python', '-m', 'pytest', 'tests/integration/']
    
    if verbose:
        cmd.append('-v')
    
    cmd.extend([
        '--html=tests/reports/integration_tests.html',
        '--self-contained-html'
    ])
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"Integration tests completed in {end_time - start_time:.2f} seconds")
    
    if result.returncode == 0:
        print("✅ All integration tests passed")
    else:
        print(f"❌ Some integration tests failed:\n{result.stdout}\n{result.stderr}")
    
    return result.returncode == 0


def run_e2e_tests(verbose: bool = False):
    """Run end-to-end tests."""
    print("\n🎯 Running end-to-end tests...")
    
    cmd = ['python', '-m', 'pytest', 'tests/e2e/']
    
    if verbose:
        cmd.append('-v')
    
    cmd.extend([
        '--html=tests/reports/e2e_tests.html',
        '--self-contained-html'
    ])
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    print(f"E2E tests completed in {end_time - start_time:.2f} seconds")
    
    if result.returncode == 0:
        print("✅ All E2E tests passed")
    else:
        print(f"❌ Some E2E tests failed:\n{result.stdout}\n{result.stderr}")
    
    return result.returncode == 0


def run_performance_tests():
    """Run performance and load tests."""
    print("\n⚡ Running performance tests...")
    
    # Check if locust is available for load testing
    try:
        import locust
        print("Locust available for load testing")
        
        # Run basic performance tests
        cmd = [
            'python', '-m', 'pytest', 
            'tests/unit/', 
            '-k', 'performance',
            '--benchmark-only',
            '--benchmark-json=tests/reports/benchmark.json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Performance tests completed")
        else:
            print(f"⚠️ Performance tests had issues:\n{result.stdout}")
            
    except ImportError:
        print("⚠️ Locust not installed, skipping load tests")
        
        # Run basic performance markers if available
        cmd = [
            'python', '-m', 'pytest', 
            'tests/unit/', 
            '-m', 'performance',
            '-v'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("Basic performance tests completed")


def run_security_tests():
    """Run security-focused tests."""
    print("\n🔒 Running security tests...")
    
    # Run security-related test markers
    cmd = [
        'python', '-m', 'pytest', 
        'tests/unit/test_auth_utils.py',
        'tests/unit/test_api_routes.py::TestErrorHandling',
        '-v'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Security tests passed")
    else:
        print(f"❌ Security tests failed:\n{result.stdout}")
    
    return result.returncode == 0


def generate_test_report():
    """Generate comprehensive test report."""
    print("\n📊 Generating comprehensive test report...")
    
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_results": {},
        "coverage": {},
        "performance": {},
        "summary": {}
    }
    
    # Read coverage data if available
    coverage_file = Path("tests/reports/coverage.xml")
    if coverage_file.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            coverage_data = {}
            for package in root.findall('.//package'):
                name = package.get('name')
                line_rate = float(package.get('line-rate', 0))
                coverage_data[name] = {
                    "line_coverage": line_rate * 100,
                    "branch_coverage": float(package.get('branch-rate', 0)) * 100
                }
            
            report_data["coverage"] = coverage_data
            
        except Exception as e:
            print(f"⚠️ Could not parse coverage data: {e}")
    
    # Read benchmark data if available
    benchmark_file = Path("tests/reports/benchmark.json")
    if benchmark_file.exists():
        try:
            with open(benchmark_file, 'r') as f:
                benchmark_data = json.load(f)
                report_data["performance"] = benchmark_data
        except Exception as e:
            print(f"⚠️ Could not parse benchmark data: {e}")
    
    # Generate summary
    total_tests = 0
    passed_tests = 0
    
    # Count test files
    test_files = list(Path("tests").rglob("test_*.py"))
    report_data["summary"] = {
        "total_test_files": len(test_files),
        "test_categories": {
            "unit": len(list(Path("tests/unit").glob("test_*.py"))),
            "integration": len(list(Path("tests/integration").glob("test_*.py"))),
            "e2e": len(list(Path("tests/e2e").glob("test_*.py")))
        }
    }
    
    # Save report
    os.makedirs("tests/reports", exist_ok=True)
    with open("tests/reports/comprehensive_report.json", 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print("✅ Comprehensive test report generated: tests/reports/comprehensive_report.json")
    
    # Generate HTML summary
    html_report = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Enterprise RAG System - Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            .success {{ color: green; }}
            .warning {{ color: orange; }}
            .error {{ color: red; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Enterprise RAG System - Test Report</h1>
            <p>Generated: {report_data['timestamp']}</p>
        </div>
        
        <div class="section">
            <h2>Test Summary</h2>
            <table>
                <tr><th>Category</th><th>Count</th></tr>
                <tr><td>Total Test Files</td><td>{report_data['summary']['total_test_files']}</td></tr>
                <tr><td>Unit Tests</td><td>{report_data['summary']['test_categories']['unit']}</td></tr>
                <tr><td>Integration Tests</td><td>{report_data['summary']['test_categories']['integration']}</td></tr>
                <tr><td>E2E Tests</td><td>{report_data['summary']['test_categories']['e2e']}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Test Files</h2>
            <ul>
    """
    
    for test_file in sorted(test_files):
        html_report += f"<li>{test_file.relative_to(Path('tests'))}</li>\n"
    
    html_report += """
            </ul>
        </div>
        
        <div class="section">
            <h2>Reports</h2>
            <ul>
                <li><a href="unit_tests.html">Unit Test Report</a></li>
                <li><a href="integration_tests.html">Integration Test Report</a></li>
                <li><a href="e2e_tests.html">E2E Test Report</a></li>
                <li><a href="coverage_html/index.html">Coverage Report</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    
    with open("tests/reports/index.html", 'w') as f:
        f.write(html_report)
    
    print("✅ HTML test report generated: tests/reports/index.html")


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Comprehensive test runner for Enterprise RAG System")
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--e2e', action='store_true', help='Run E2E tests only')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    parser.add_argument('--security', action='store_true', help='Run security tests only')
    parser.add_argument('--no-coverage', action='store_true', help='Skip coverage reporting')
    parser.add_argument('--no-lint', action='store_true', help='Skip linting')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--fast', action='store_true', help='Run fast tests only (skip slow integration tests)')
    
    args = parser.parse_args()
    
    print("🚀 Enterprise RAG System - Comprehensive Test Runner")
    print("=" * 60)
    
    # Create reports directory
    os.makedirs("tests/reports", exist_ok=True)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    start_time = time.time()
    all_passed = True
    
    # Run linting if not skipped
    if not args.no_lint:
        run_linting()
    
    # Run specific test categories or all tests
    if args.unit:
        all_passed &= run_unit_tests(args.verbose, not args.no_coverage)
    elif args.integration:
        all_passed &= run_integration_tests(args.verbose)
    elif args.e2e:
        all_passed &= run_e2e_tests(args.verbose)
    elif args.performance:
        run_performance_tests()
    elif args.security:
        all_passed &= run_security_tests()
    else:
        # Run all tests
        all_passed &= run_unit_tests(args.verbose, not args.no_coverage)
        
        if not args.fast:
            all_passed &= run_integration_tests(args.verbose)
            all_passed &= run_e2e_tests(args.verbose)
        
        run_performance_tests()
        all_passed &= run_security_tests()
    
    # Generate comprehensive report
    generate_test_report()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n" + "=" * 60)
    print(f"🏁 Test execution completed in {total_time:.2f} seconds")
    
    if all_passed:
        print("✅ All tests passed successfully!")
        print("📊 View detailed reports in: tests/reports/index.html")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the reports for details.")
        print("📊 View detailed reports in: tests/reports/index.html")
        sys.exit(1)


if __name__ == "__main__":
    main() 