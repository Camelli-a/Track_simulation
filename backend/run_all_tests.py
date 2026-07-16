#!/usr/bin/env python3
"""
运行所有测试脚本
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path

def print_header(title):
    """打印标题"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def run_test_file(test_file, verbose=False):
    """运行单个测试文件"""
    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在: {test_file}")
        return False
    
    print(f"\n运行测试: {test_file}")
    
    try:
        if test_file.endswith(".py"):
            # 直接运行Python文件
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                cwd=Path(test_file).parent.parent
            )
            
            if verbose:
                print("输出:")
                print(result.stdout)
                if result.stderr:
                    print("错误:")
                    print(result.stderr)
            
            if result.returncode == 0:
                print(f"✅ {test_file} 通过")
                return True
            else:
                print(f"❌ {test_file} 失败 (返回码: {result.returncode})")
                return False
        else:
            print(f"⚠ 不支持的文件类型: {test_file}")
            return False
            
    except Exception as e:
        print(f"❌ 运行测试时出错 {test_file}: {e}")
        return False

def run_pytest(pattern=None, verbose=False):
    """运行pytest测试"""
    cmd = [sys.executable, "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if pattern:
        cmd.append(pattern)
    else:
        cmd.append("tests/")
    
    print(f"运行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        print("输出摘要:")
        lines = result.stdout.split('\n')
        
        # 只显示关键信息
        for line in lines:
            if any(keyword in line.lower() for keyword in ["passed", "failed", "error", "warning", "test"]):
                print(f"  {line}")
        
        if result.returncode == 0:
            print("✅ 所有pytest测试通过")
            return True
        else:
            print("❌ pytest测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 运行pytest时出错: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="运行所有系统测试")
    parser.add_argument("--basic", action="store_true", help="运行基础测试")
    parser.add_argument("--api", action="store_true", help="运行API测试")
    parser.add_argument("--unit", action="store_true", help="运行单元测试")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--pytest", action="store_true", help="使用pytest运行")
    
    args = parser.parse_args()
    
    # 默认运行所有测试
    if not any([args.basic, args.api, args.unit, args.all, args.pytest]):
        args.all = True
    
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    print_header("系统测试运行器")
    print(f"工作目录: {backend_dir}")
    print(f"Python版本: {sys.version}")
    
    success = True
    
    # 运行基础测试
    if args.basic or args.all:
        print_header("基础系统测试")
        success = run_test_file("tests/test_system_basic.py", args.verbose) and success
    
    # 运行API测试
    if args.api or args.all:
        print_header("API集成测试")
        success = run_test_file("tests/test_api_integration.py", args.verbose) and success
    
    # 运行单元测试
    if args.unit or args.all:
        print_header("单元测试")
        # 运行现有的单元测试
        test_files = [
            "tests/test_signal_ato_controller.py",
            "tests/test_line_operation_service.py",
            "tests/test_signal_control.py",
            "tests/test_signal_gradient.py",
            "tests/test_signal_hardware_adapter.py",
            "tests/test_signal_route_lifecycle.py",
            "tests/test_signal_speed_limit.py",
            "tests/test_signal_track_config.py",
            "tests/test_signal_zmq_adapter.py",
            "tests/test_station_yard_geometry.py",
            "tests/test_vehicle_management_api.py",
            "tests/test_dashboard_ato_guidance.py",
            "tests/test_data_flow_frontend_contract.py",
            "tests/test_data_flow_mapper.py",
            "tests/test_driver_desk_test_rig.py",
        ]
        
        for test_file in test_files:
            if os.path.exists(test_file):
                file_success = run_test_file(test_file, args.verbose)
                success = file_success and success
    
    # 使用pytest运行
    if args.pytest or args.all:
        print_header("pytest测试")
        pytest_success = run_pytest(verbose=args.verbose)
        success = pytest_success and success
    
    print_header("测试结果汇总")
    if success:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())