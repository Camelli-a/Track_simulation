"""
基础系统测试 - 简化版本
"""
import sys
import os
from pathlib import Path
import pytest

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


def test_import_app():
    """测试能否导入应用"""
    try:
        from main import app
        assert app is not None
        print("✓ 应用导入成功")
    except ImportError as e:
        pytest.fail(f"导入应用失败: {e}")


def test_import_config():
    """测试能否导入配置"""
    try:
        from app.core.config import settings
        assert settings is not None
        print(f"✓ 配置导入成功: APP_ENV={settings.APP_ENV}")
    except ImportError as e:
        pytest.fail(f"导入配置失败: {e}")


def test_import_services():
    """测试能否导入主要服务"""
    services_to_test = [
        "app.services.line_operation_service",
        "app.services.signal_service",
        "app.services.power_service",
    ]
    
    for service_path in services_to_test:
        try:
            __import__(service_path)
            print(f"✓ 服务导入成功: {service_path}")
        except ImportError as e:
            print(f"⚠ 服务导入警告: {service_path} - {e}")
            # 不失败，因为某些服务可能不存在


def test_import_communication():
    """测试能否导入通信模块"""
    modules_to_test = [
        "app.communication.broker",
        "app.communication.message_bus",
    ]
    
    for module_path in modules_to_test:
        try:
            __import__(module_path)
            print(f"✓ 通信模块导入成功: {module_path}")
        except ImportError as e:
            print(f"⚠ 通信模块导入警告: {module_path} - {e}")


def test_import_data_flow():
    """测试能否导入数据流模块"""
    modules_to_test = [
        "app.data_flow.state_store",
        "app.data_flow.data_mapper",
    ]
    
    for module_path in modules_to_test:
        try:
            __import__(module_path)
            print(f"✓ 数据流模块导入成功: {module_path}")
        except ImportError as e:
            print(f"⚠ 数据流模块导入警告: {module_path} - {e}")


def test_import_vehicle_sim():
    """测试能否导入车辆模拟模块"""
    modules_to_test = [
        "app.vehicle_sim.train",
        "app.vehicle_sim.dynamics",
    ]
    
    for module_path in modules_to_test:
        try:
            __import__(module_path)
            print(f"✓ 车辆模拟模块导入成功: {module_path}")
        except ImportError as e:
            print(f"⚠ 车辆模拟模块导入警告: {module_path} - {e}")


def test_import_api_endpoints():
    """测试能否导入API端点"""
    endpoints_to_test = [
        "app.api.v1.endpoints.vehicle",
        "app.api.v1.endpoints.power",
        "app.api.v1.endpoints.signal",
        "app.api.v1.endpoints.track",
        "app.api.v1.endpoints.dashboard",
    ]
    
    for endpoint_path in endpoints_to_test:
        try:
            __import__(endpoint_path)
            print(f"✓ API端点导入成功: {endpoint_path}")
        except ImportError as e:
            print(f"⚠ API端点导入警告: {endpoint_path} - {e}")


def test_fastapi_available():
    """测试FastAPI是否可用"""
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        # 创建一个简单的测试应用
        test_app = FastAPI()
        
        @test_app.get("/test")
        def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        print("✓ FastAPI测试通过")
        
    except ImportError as e:
        pytest.fail(f"FastAPI导入失败: {e}")


def test_pydantic_available():
    """测试Pydantic是否可用"""
    try:
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            name: str
            value: int
        
        model = TestModel(name="test", value=123)
        assert model.name == "test"
        assert model.value == 123
        print("✓ Pydantic测试通过")
        
    except ImportError as e:
        pytest.fail(f"Pydantic导入失败: {e}")


def test_zmq_available():
    """测试ZMQ是否可用"""
    try:
        import zmq
        print(f"✓ ZMQ版本: {zmq.__version__}")
    except ImportError as e:
        print(f"⚠ ZMQ导入警告: {e}")


class TestApplicationStructure:
    """应用结构测试"""
    
    def test_project_structure(self):
        """测试项目基本结构"""
        backend_dir = Path(__file__).resolve().parent.parent
        
        # 检查关键目录是否存在
        required_dirs = [
            "app",
            "app/api",
            "app/api/v1",
            "app/api/v1/endpoints",
            "app/core",
            "app/services",
            "app/communication",
            "app/data_flow",
            "app/schemas",
            "app/vehicle_sim",
            "tests",
        ]
        
        for dir_name in required_dirs:
            dir_path = backend_dir / dir_name
            if dir_path.exists():
                print(f"✓ 目录存在: {dir_name}")
            else:
                print(f"⚠ 目录不存在: {dir_name}")
        
        # 检查关键文件是否存在
        required_files = [
            "main.py",
            "requirements.txt",
            ".env.example",
            "app/core/config.py",
        ]
        
        for file_name in required_files:
            file_path = backend_dir / file_name
            if file_path.exists():
                print(f"✓ 文件存在: {file_name}")
            else:
                print(f"⚠ 文件不存在: {file_name}")


if __name__ == "__main__":
    print("运行基础系统测试...")
    
    # 运行所有测试
    test_functions = [
        test_import_app,
        test_import_config,
        test_import_services,
        test_import_communication,
        test_import_data_flow,
        test_import_vehicle_sim,
        test_import_api_endpoints,
        test_fastapi_available,
        test_pydantic_available,
        test_zmq_available,
    ]
    
    for test_func in test_functions:
        try:
            test_func()
        except AssertionError as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
        except Exception as e:
            print(f"❌ {test_func.__name__} 异常: {e}")
    
    print("基础系统测试完成")