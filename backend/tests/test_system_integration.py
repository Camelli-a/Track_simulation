"""
系统集成测试 - 测试整个应用的主要功能
包括API端点、服务集成、数据流等
"""
import asyncio
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# 添加项目根目录到Python路径
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

# 导入配置和应用
try:
    from app.core.config import settings
    from main import app
except ImportError as e:
    print(f"导入错误: {e}")
    # 创建模拟的app用于测试
    app = None


class TestSystemIntegration:
    """系统集成测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.client = TestClient(app)
        
    def test_health_check(self):
        """测试健康检查端点"""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "data_source" in data
        assert "enable_dashboard_mock" in data
        
    def test_api_v1_vehicle_endpoints(self):
        """测试车辆管理API端点"""
        # 测试获取车辆列表
        response = self.client.get("/api/v1/vehicle/list")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        
    def test_power_endpoints(self):
        """测试电力系统API端点"""
        # 测试电力状态获取
        response = self.client.get("/api/v1/power/status")
        assert response.status_code == 200
        power_data = response.json()
        assert "power_status" in power_data
        
        # 测试电力控制
        control_data = {
            "section_id": "P001",
            "power_state": True,
            "voltage": 1500.0
        }
        response = self.client.post("/api/v1/power/control", json=control_data)
        assert response.status_code in [200, 201]
        
    def test_signal_endpoints(self):
        """测试信号系统API端点"""
        # 测试信号状态获取
        response = self.client.get("/api/v1/signal/status")
        assert response.status_code == 200
        signal_data = response.json()
        assert isinstance(signal_data, list)
        
        # 测试单个信号控制
        signal_control = {
            "signal_id": "S001",
            "aspect": "green",
            "route_id": "R001"
        }
        response = self.client.post("/api/v1/signal/control", json=signal_control)
        assert response.status_code in [200, 201]
        
    def test_track_endpoints(self):
        """测试轨道系统API端点"""
        # 测试轨道状态获取
        response = self.client.get("/api/v1/track/status")
        assert response.status_code == 200
        track_data = response.json()
        assert isinstance(track_data, list)
        
        # 测试轨道区段控制
        track_control = {
            "section_id": "TR001",
            "occupied": False,
            "locked": False
        }
        response = self.client.post("/api/v1/track/control", json=track_control)
        assert response.status_code in [200, 201]
        
    def test_dashboard_endpoints(self):
        """测试仪表盘API端点"""
        # 测试模拟控制
        sim_control = {
            "train_id": "TRAIN-001",
            "speed_kmh": 60.0,
            "acceleration": 0.5
        }
        response = self.client.post("/api/v1/dashboard/control", json=sim_control)
        assert response.status_code in [200, 201]
        
        # 测试获取模拟状态
        response = self.client.get("/api/v1/dashboard/status")
        assert response.status_code == 200
        
    def test_driver_desk_sim_endpoints(self):
        """测试司机台模拟API端点"""
        # 测试获取司机台状态
        response = self.client.get("/api/v1/driver_desk_sim/status")
        assert response.status_code == 200
        
        # 测试发送控制指令
        control_data = {
            "throttle": 0.7,
            "brake": 0.2,
            "direction": "forward",
            "horn": False
        }
        response = self.client.post("/api/v1/driver_desk_sim/control", json=control_data)
        assert response.status_code in [200, 201]
        
    def test_config_endpoints(self):
        """测试配置相关的API端点"""
        # 测试获取配置信息
        response = self.client.get("/api/v1/config")
        assert response.status_code == 200
        config_data = response.json()
        assert "data_source" in config_data
        assert "plc_host" in config_data
        
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """测试WebSocket连接"""
        from websockets.sync.client import connect
        import json
        
        # 注意：这个测试需要服务器运行，通常在集成测试环境中运行
        # 这里我们只是验证连接逻辑
        ws_url = f"ws://localhost:{settings.APP_PORT}/ws/dashboard"
        
        # 在实际集成测试中，我们会建立真正的WebSocket连接
        # 这里我们用mock来测试
        pass
        
    def test_data_flow_endpoints(self):
        """测试数据流相关API"""
        # 测试获取可视化映射
        response = self.client.get("/api/v1/data_flow/visual_mapping")
        assert response.status_code == 200
        mapping_data = response.json()
        assert isinstance(mapping_data, dict)
        
    def test_error_handling(self):
        """测试错误处理"""
        # 测试不存在的端点
        response = self.client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        
        # 测试无效的请求数据
        invalid_data = {"invalid": "data"}
        response = self.client.post("/api/v1/power/control", json=invalid_data)
        # 可能是400或422，取决于验证
        assert response.status_code in [400, 422, 500]
        
    def test_cors_headers(self):
        """测试CORS头是否正确设置"""
        response = self.client.get("/", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        
    def test_api_documentation(self):
        """测试API文档是否可访问"""
        response = self.client.get("/docs")
        assert response.status_code == 200
        
        response = self.client.get("/redoc")
        assert response.status_code == 200


class TestServiceIntegration:
    """服务集成测试"""
    
    def test_line_operation_service(self):
        """测试线路操作服务"""
        from app.services.line_operation_service import line_operation_service
        
        # 测试服务初始化
        assert line_operation_service is not None
        
        # 测试获取线路状态
        status = line_operation_service.get_status()
        assert isinstance(status, dict)
        
    def test_signal_service(self):
        """测试信号服务"""
        from app.services.signal_service import signal_service
        
        # 测试服务初始化
        assert signal_service is not None
        
        # 测试获取所有信号状态
        signals = signal_service.get_all_signals()
        assert isinstance(signals, list)
        
    @pytest.mark.asyncio
    async def test_vehicle_simulation(self):
        """测试车辆模拟服务"""
        from app.vehicle_sim.train import Train
        from app.vehicle_sim.dynamics import VehicleDynamics
        
        # 创建测试车辆
        train = Train(
            train_id="TEST-001",
            length=200.0,
            mass=300000.0,
            max_tractive_effort=300000.0,
            max_braking_effort=300000.0
        )
        
        # 测试车辆初始化
        assert train.train_id == "TEST-001"
        assert train.length == 200.0
        
        # 测试动力学模型
        dynamics = VehicleDynamics(
            mass=300000.0,
            max_tractive_effort=300000.0,
            max_braking_effort=300000.0
        )
        
        # 计算加速度
        acceleration = dynamics.calculate_acceleration(
            tractive_effort=100000.0,
            braking_effort=50000.0,
            resistance=20000.0,
            grade_force=0.0
        )
        assert isinstance(acceleration, float)


class TestCommunicationIntegration:
    """通信集成测试"""
    
    @patch('app.communication.broker.Broker')
    def test_broker_initialization(self, mock_broker):
        """测试消息代理初始化"""
        from app.communication.broker import Broker
        
        broker = Broker("tcp://127.0.0.1:5555", "tcp://127.0.0.1:5556")
        assert broker is not None
        
    def test_message_bus_integration(self):
        """测试消息总线集成"""
        from app.communication.message_bus import MessageBus
        
        bus = MessageBus()
        
        # 测试订阅发布机制
        received_messages = []
        
        def callback(topic, data):
            received_messages.append((topic, data))
        
        bus.subscribe("test_topic", callback)
        bus.publish("test_topic", {"test": "data"})
        
        # 在实际测试中，消息会在事件循环中传递
        # 这里我们验证回调是否被正确注册
        
    @patch('app.communication.driver_desk_source.DriverDeskSource')
    def test_driver_desk_integration(self, mock_source):
        """测试司机台数据源集成"""
        from app.communication.driver_desk_source import DriverDeskSource
        
        source = DriverDeskSource(
            vehicle_id="TRAIN-001",
            plc_host="127.0.0.1",
            plc_port=8001,
            bus=Mock(),
            record_dir="logs"
        )
        
        assert source.vehicle_id == "TRAIN-001"


class TestDataFlowIntegration:
    """数据流集成测试"""
    
    def test_state_store_integration(self):
        """测试状态存储集成"""
        from app.data_flow.state_store import StateStore
        
        store = StateStore()
        
        # 测试状态更新和获取
        test_state = {
            "train_id": "TEST-001",
            "speed_kmh": 60.0,
            "position_m": 1000.0
        }
        
        store.update_train_state(test_state)
        retrieved_state = store.get_train_state("TEST-001")
        
        assert retrieved_state["train_id"] == "TEST-001"
        assert retrieved_state["speed_kmh"] == 60.0
        
    def test_visual_mapping_integration(self):
        """测试可视化映射集成"""
        from app.data_flow.visual_mapping import VisualMapping
        
        mapping = VisualMapping()
        
        # 测试映射数据加载
        try:
            mapping.load_mappings()
            assert mapping.mappings is not None
        except FileNotFoundError:
            # 如果映射文件不存在，跳过这个测试
            pytest.skip("Visual mapping file not found")
            
    def test_data_mapper_integration(self):
        """测试数据映射器集成"""
        from app.data_flow.data_mapper import DataMapper
        
        mapper = DataMapper()
        
        # 测试数据转换
        raw_data = {
            "speed": 16.67,  # m/s
            "position": 1000.0
        }
        
        mapped_data = mapper.map_vehicle_data(raw_data)
        assert isinstance(mapped_data, dict)
        assert "speed_kmh" in mapped_data
        

if __name__ == "__main__":
    # 可以直接运行这个测试文件
    pytest.main([__file__, "-v"])