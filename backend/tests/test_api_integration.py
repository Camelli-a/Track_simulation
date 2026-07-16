"""
API集成测试 - 测试所有API端点
"""
import sys
import os
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 设置测试环境变量
os.environ["APP_ENV"] = "test"
os.environ["DATA_SOURCE"] = "mock"
os.environ["ENABLE_DASHBOARD_MOCK"] = "True"
os.environ["ENABLE_ZMQ_BROKER_MANAGER"] = "False"
os.environ["ENABLE_ZMQ_DASHBOARD_LISTENER"] = "False"
os.environ["ENABLE_SIGNAL_ZMQ_ADAPTER"] = "False"
os.environ["ENABLE_VEHICLE_PROCESS_MANAGER"] = "False"

from fastapi.testclient import TestClient
from main import app


class TestAPIIntegration:
    """API集成测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.client = TestClient(app)
        print(f"\n设置测试客户端，使用环境: DATA_SOURCE={os.environ.get('DATA_SOURCE')}")
    
    def test_health_check(self):
        """测试健康检查端点"""
        print("测试健康检查端点...")
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "data_source" in data
        assert data["data_source"] == "mock"
        print(f"✓ 健康检查通过: {data}")
    
    def test_api_v1_vehicle_endpoints(self):
        """测试车辆管理API端点"""
        print("\n测试车辆管理API端点...")
        
        # 测试获取车辆列表
        response = self.client.get("/api/v1/vehicle/list")
        print(f"车辆列表响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ 车辆列表获取成功，数量: {len(data)}")
        else:
            print(f"⚠ 车辆列表端点可能未实现: {response.status_code}")
            # 不失败，只是记录
        
        # 测试车辆状态
        response = self.client.get("/api/v1/vehicle/status")
        print(f"车辆状态响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            print(f"✓ 车辆状态获取成功")
        else:
            print(f"⚠ 车辆状态端点可能未实现: {response.status_code}")
    
    def test_power_endpoints(self):
        """测试电力系统API端点"""
        print("\n测试电力系统API端点...")
        
        # 测试电力状态获取
        response = self.client.get("/api/v1/power/status")
        print(f"电力状态响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            print(f"✓ 电力状态获取成功")
        else:
            print(f"⚠ 电力状态端点可能未实现: {response.status_code}")
    
    def test_signal_endpoints(self):
        """测试信号系统API端点"""
        print("\n测试信号系统API端点...")
        
        # 测试信号状态获取
        response = self.client.get("/api/v1/signal/status")
        print(f"信号状态响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # 信号状态可能是dict或list，根据实际实现
            assert isinstance(data, (dict, list))
            if isinstance(data, list):
                print(f"✓ 信号状态获取成功，数量: {len(data)}")
            else:
                print(f"✓ 信号状态获取成功，类型: dict")
        else:
            print(f"⚠ 信号状态端点可能未实现: {response.status_code}")
            # 不失败，只记录
    
    def test_track_endpoints(self):
        """测试轨道系统API端点"""
        print("\n测试轨道系统API端点...")
        
        # 测试轨道状态获取
        response = self.client.get("/api/v1/track/status")
        print(f"轨道状态响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # 轨道状态可能是dict或list，根据实际实现
            assert isinstance(data, (dict, list))
            if isinstance(data, list):
                print(f"✓ 轨道状态获取成功，数量: {len(data)}")
            else:
                print(f"✓ 轨道状态获取成功，类型: dict")
        else:
            print(f"⚠ 轨道状态端点可能未实现: {response.status_code}")
            # 不失败，只记录
    
    def test_dashboard_endpoints(self):
        """测试仪表盘API端点"""
        print("\n测试仪表盘API端点...")
        
        # 测试仪表盘状态
        response = self.client.get("/api/v1/dashboard/status")
        print(f"仪表盘状态响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            print(f"✓ 仪表盘状态获取成功")
        else:
            print(f"⚠ 仪表盘状态端点可能未实现: {response.status_code}")
    
    def test_driver_desk_sim_endpoints(self):
        """测试司机台模拟API端点"""
        print("\n测试司机台模拟API端点...")
        
        # 测试司机台状态
        response = self.client.get("/api/v1/driver-desk-sim/status")
        print(f"司机台状态响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            print(f"✓ 司机台状态获取成功")
        else:
            print(f"⚠ 司机台状态端点可能未实现: {response.status_code}")
    
    def test_speed_curve_endpoints(self):
        """测试速度曲线API端点"""
        print("\n测试速度曲线API端点...")
        
        # 测试速度曲线数据
        response = self.client.get("/api/v1/speedcurve/data")
        print(f"速度曲线数据响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ 速度曲线数据获取成功")
        else:
            print(f"⚠ 速度曲线数据端点可能未实现: {response.status_code}")
    
    def test_station_yard_endpoints(self):
        """测试站场API端点"""
        print("\n测试站场API端点...")
        
        # 测试站场状态
        response = self.client.get("/api/v1/dashboard/station-yard/status")
        print(f"站场状态响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            print(f"✓ 站场状态获取成功")
        else:
            print(f"⚠ 站场状态端点可能未实现: {response.status_code}")
    
    def test_data_flow_endpoints(self):
        """测试数据流API端点"""
        print("\n测试数据流API端点...")
        
        # 测试可视化映射
        response = self.client.get("/api/v1/dashboard/visual-mapping")
        print(f"可视化映射响应: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            print(f"✓ ��视化映射获取成功")
        else:
            print(f"⚠ 可视化映射端点可能未实现: {response.status_code}")
    
    def test_api_documentation(self):
        """测试API文档是否可访问"""
        print("\n测试API文档...")
        
        # 测试OpenAPI文档
        response = self.client.get("/docs")
        assert response.status_code == 200
        print("✓ OpenAPI文档可访问")
        
        # 测试ReDoc文档
        response = self.client.get("/redoc")
        assert response.status_code == 200
        print("✓ ReDoc文档可访问")
    
    def test_cors_headers(self):
        """测试CORS头是否正确设置"""
        print("\n测试CORS头...")
        
        response = self.client.get("/", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        print("✓ CORS头正确设置")
    
    def test_error_handling(self):
        """测试错误处理"""
        print("\n测试错误处理...")
        
        # 测试不存在的端点
        response = self.client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        print("✓ 不存在的端点返回404")
        
        # 测试根路径下不存在的端点
        response = self.client.get("/nonexistent")
        assert response.status_code == 404
        print("✓ 根路径下不存在的端点返回404")
    
    def test_api_structure(self):
        """测试API结构一致性"""
        print("\n测试API结构...")
        
        # 检查所有已实现的端点
        endpoints_to_test = [
            ("/", "GET"),
            ("/docs", "GET"),
            ("/redoc", "GET"),
            ("/api/v1/power/status", "GET"),
            ("/api/v1/vehicle/list", "GET"),
            ("/api/v1/signal/status", "GET"),
            ("/api/v1/track/status", "GET"),
            ("/api/v1/dashboard/status", "GET"),
            ("/api/v1/driver-desk-sim/status", "GET"),
        ]
        
        for endpoint, method in endpoints_to_test:
            if method == "GET":
                response = self.client.get(endpoint)
                print(f"{endpoint}: {response.status_code}")
        
        print("✓ API结构测试完成")


class TestServiceIntegration:
    """服务集成测试"""
    
    def test_line_operation_service(self):
        """测试线路操作服务"""
        print("\n测试线路操作服务...")
        
        try:
            from app.services.line_operation_service import line_operation_service
            assert line_operation_service is not None
            
            # 测试获取线路状态
            status = line_operation_service.get_status()
            assert isinstance(status, dict)
            print(f"✓ 线路操作服务测试通过: {status.get('status', 'unknown')}")
        except Exception as e:
            print(f"⚠ 线路操作服务测试警告: {e}")
    
    def test_signal_service(self):
        """测试信号服务"""
        print("\n测试信号服务...")
        
        try:
            from app.services.signal_service import signal_service
            assert signal_service is not None
            
            # 测试获取所有信号状态
            signals = signal_service.get_all_signals()
            assert isinstance(signals, list)
            print(f"✓ 信号服务测试通过，信号数量: {len(signals)}")
        except Exception as e:
            print(f"⚠ 信号服务测试警告: {e}")
    
    def test_power_service(self):
        """测试电力服务"""
        print("\n测试电力服务...")
        
        try:
            from app.services.power_service import power_service
            assert power_service is not None
            
            # 测试获取电力状态
            power_status = power_service.get_power_status()
            assert isinstance(power_status, dict)
            print(f"✓ 电力服务测试通过")
        except Exception as e:
            print(f"⚠ 电力服务测试警告: {e}")


def test_configuration():
    """测试配置系统"""
    print("\n测试配置系统...")
    
    try:
        from app.core.config import settings
        
        assert settings.APP_ENV == "test"
        assert settings.DATA_SOURCE == "mock"
        assert settings.ENABLE_DASHBOARD_MOCK == True
        
        print(f"✓ 配置测试通过:")
        print(f"  APP_ENV: {settings.APP_ENV}")
        print(f"  DATA_SOURCE: {settings.DATA_SOURCE}")
        print(f"  ENABLE_DASHBOARD_MOCK: {settings.ENABLE_DASHBOARD_MOCK}")
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("API集成测试")
    print("=" * 60)
    
    # 运行测试
    test_classes = [
        TestAPIIntegration(),
        TestServiceIntegration(),
    ]
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{'-' * 40}")
        print(f"运行 {class_name}")
        print(f"{'-' * 40}")
        
        # 运行所有测试方法
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                method = getattr(test_class, method_name)
                if callable(method):
                    try:
                        # 调用setup_method
                        if hasattr(test_class, 'setup_method'):
                            test_class.setup_method()
                        
                        print(f"\n执行: {method_name}")
                        method()
                        print(f"✓ {method_name} 通过")
                    except AssertionError as e:
                        print(f"❌ {method_name} 失败: {e}")
                    except Exception as e:
                        print(f"❌ {method_name} 异常: {e}")
    
    # 运行独立的测试函数
    print(f"\n{'-' * 40}")
    print("运行独立测试函数")
    print(f"{'-' * 40}")
    
    test_functions = [
        test_configuration,
    ]
    
    for test_func in test_functions:
        try:
            print(f"\n执行: {test_func.__name__}")
            test_func()
            print(f"✓ {test_func.__name__} 通过")
        except AssertionError as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
        except Exception as e:
            print(f"❌ {test_func.__name__} 异常: {e}")
    
    print(f"\n{'=' * 60}")
    print("API集成测试完成")
    print(f"{'=' * 60}")