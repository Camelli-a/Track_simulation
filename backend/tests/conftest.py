"""
测试配置文件和夹具
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_test_environment():
    """为每个测试设置环境变量"""
    # 设置为测试模式
    os.environ["APP_ENV"] = "test"
    os.environ["DATA_SOURCE"] = "mock"
    os.environ["ENABLE_DASHBOARD_MOCK"] = "True"
    os.environ["ENABLE_ZMQ_BROKER_MANAGER"] = "False"
    os.environ["ENABLE_ZMQ_DASHBOARD_LISTENER"] = "False"
    os.environ["ENABLE_SIGNAL_ZMQ_ADAPTER"] = "False"
    os.environ["ENABLE_VEHICLE_PROCESS_MANAGER"] = "False"
    
    yield
    
    # 清理环境变量
    for key in ["APP_ENV", "DATA_SOURCE", "ENABLE_DASHBOARD_MOCK", 
                "ENABLE_ZMQ_BROKER_MANAGER", "ENABLE_ZMQ_DASHBOARD_LISTENER",
                "ENABLE_SIGNAL_ZMQ_ADAPTER", "ENABLE_VEHICLE_PROCESS_MANAGER"]:
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def mock_settings():
    """模拟设置"""
    with patch('app.core.config.Settings') as mock:
        mock_instance = Mock()
        mock_instance.APP_ENV = "test"
        mock_instance.DATA_SOURCE = "mock"
        mock_instance.ENABLE_DASHBOARD_MOCK = True
        mock_instance.ENABLE_ZMQ_BROKER_MANAGER = False
        mock_instance.ENABLE_ZMQ_DASHBOARD_LISTENER = False
        mock_instance.ENABLE_SIGNAL_ZMQ_ADAPTER = False
        mock_instance.ENABLE_VEHICLE_PROCESS_MANAGER = False
        mock_instance.PLC_HOST = "127.0.0.1"
        mock_instance.PLC_PORT = 8001
        mock_instance.ZMQ_BROKER_FRONTEND = "tcp://127.0.0.1:5555"
        mock_instance.ZMQ_BROKER_BACKEND = "tcp://127.0.0.1:5556"
        mock_instance.CORS_ORIGINS = ["http://localhost:5173"]
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def test_client():
    """创建测试客户端"""
    from fastapi.testclient import TestClient
    from main import app
    
    return TestClient(app)


@pytest.fixture
def mock_message_bus():
    """模拟消息总线"""
    bus = Mock()
    bus.subscribe = Mock()
    bus.publish = Mock()
    bus.start = Mock()
    bus.stop = Mock()
    return bus


@pytest.fixture
def mock_driver_desk_source():
    """模拟司机台数据源"""
    source = Mock()
    source.start = Mock()
    source.stop = Mock()
    source.send_to_plc = Mock()
    return source


@pytest.fixture
def mock_train():
    """模拟列车"""
    train = Mock()
    train.train_id = "TEST-001"
    train.length = 200.0
    train.mass = 300000.0
    train.speed_kmh = 0.0
    train.position_m = 0.0
    train.step = Mock()
    return train


@pytest.fixture
def mock_vehicle_manager():
    """模拟车辆管理器"""
    manager = Mock()
    manager.get_train = Mock(return_value=Mock())
    manager.add_train = Mock()
    manager.remove_train = Mock()
    manager.get_all_trains = Mock(return_value=[])
    return manager


@pytest.fixture
def sample_vehicle_data():
    """样本车辆数据"""
    return {
        "train_id": "TEST-001",
        "speed_kmh": 60.0,
        "position_m": 1000.0,
        "acceleration": 0.5,
        "tractive_effort": 100000.0,
        "braking_effort": 0.0,
        "direction": "forward",
        "power_state": True,
        "brake_state": False,
        "ato_mode": "manual",
        "target_speed": 80.0
    }


@pytest.fixture
def sample_signal_data():
    """样本信号数据"""
    return {
        "signal_id": "S001",
        "aspect": "green",
        "route_id": "R001",
        "speed_limit": 80.0,
        "position_m": 500.0,
        "occupied": False,
        "locked": False
    }


@pytest.fixture
def sample_power_data():
    """样本电力数据"""
    return {
        "section_id": "P001",
        "power_state": True,
        "voltage": 1500.0,
        "current": 100.0,
        "power_kw": 150.0,
        "temperature": 25.0,
        "fault_status": "normal"
    }


@pytest.fixture
def sample_track_data():
    """样本轨道数据"""
    return {
        "section_id": "TR001",
        "occupied": False,
        "locked": False,
        "length_m": 1000.0,
        "gradient": 0.0,
        "curve_radius": 0.0,
        "speed_limit": 80.0,
        "power_section": "P001"
    }


@pytest.fixture
def async_loop():
    """异步事件循环"""
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop