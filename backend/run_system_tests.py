#!/usr/bin/env python3
"""
系统测试运行脚本
运行所有系统集成测试
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path

def run_pytest_tests(test_pattern=None, verbose=False, coverage=False):
    """运行pytest测试"""
    cmd = [sys.executable, "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=app", "--cov-report=term", "--cov-report=html"])
    
    if test_pattern:
        cmd.append(test_pattern)
    else:
        cmd.append("tests/")
    
    print(f"运行测试命令: {' '.join(cmd)}")
    print(f"当前工作目录: {os.getcwd()}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("标准输出:")
    print(result.stdout)
    
    if result.stderr:
        print("标准错误:")
        print(result.stderr)
    
    print(f"返回码: {result.returncode}")
    
    return result.returncode == 0

def run_specific_test_category(category):
    """运行特定类别的测试"""
    test_files = {
        "api": "tests/test_system_integration.py::TestSystemIntegration",
        "services": "tests/test_system_integration.py::TestServiceIntegration",
        "communication": "tests/test_system_integration.py::TestCommunicationIntegration",
        "dataflow": "tests/test_system_integration.py::TestDataFlowIntegration",
        "all": "tests/"
    }
    
    if category not in test_files:
        print(f"未知的测试类别: {category}")
        print(f"可用的类别: {', '.join(test_files.keys())}")
        return False
    
    return run_pytest_tests(test_files[category], verbose=True)

def run_individual_test_file(test_file):
    """运行单个测试文件"""
    if not os.path.exists(test_file):
        print(f"测试文件不存在: {test_file}")
        return False
    
    return run_pytest_tests(test_file, verbose=True)

def setup_test_environment():
    """设置测试环境"""
    print("设置测试环境...")
    
    # 设置环境变量
    env_vars = {
        "APP_ENV": "test",
        "DATA_SOURCE": "mock",
        "ENABLE_DASHBOARD_MOCK": "True",
        "ENABLE_ZMQ_BROKER_MANAGER": "False",
        "ENABLE_ZMQ_DASHBOARD_LISTENER": "False",
        "ENABLE_SIGNAL_ZMQ_ADAPTER": "False",
        "ENABLE_VEHICLE_PROCESS_MANAGER": "False"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"设置 {key}={value}")
    
    # 创建必要的测试目录
    test_dirs = [
        "logs",
        "test_data"
    ]
    
    for dir_name in test_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(exist_ok=True)
            print(f"创建目录: {dir_path}")
    
    print("测试环境设置完成")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行系统集成测试")
    parser.add_argument("--category", choices=["api", "services", "communication", "dataflow", "all"],
                       default="all", help="测试类别")
    parser.add_argument("--file", help="运行特定的测试文件")
    parser.add_argument("--coverage", action="store_true", help="生成测试覆盖率报告")
    parser.add_argument("--setup-only", action="store_true", help="只设置测试环境不运行测试")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 确保在正确的目录
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # 设置测试环境
    setup_test_environment()
    
    if args.setup_only:
        print("只设置环境，不运行测试")
        return 0
    
    # 运行测试
    success = True
    
    if args.file:
        print(f"运行测试文件: {args.file}")
        success = run_individual_test_file(args.file)
    else:
        print(f"运行测试类别: {args.category}")
        if args.category == "all":
            success = run_pytest_tests(verbose=args.verbose, coverage=args.coverage)
        else:
            success = run_specific_test_category(args.category)
    
    if success:
        print("\n✅ 所有测试通过!")
        return 0
    else:
        print("\n❌ 测试失败!")
        return 1

if __name__ == "__main__":
    sys.exit(main())