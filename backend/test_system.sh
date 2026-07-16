#!/bin/bash
# 系统测试脚本

echo "=== 系统集成测试 ==="
echo ""

# 设置测试环境
export APP_ENV=test
export DATA_SOURCE=mock
export ENABLE_DASHBOARD_MOCK=True
export ENABLE_ZMQ_BROKER_MANAGER=False
export ENABLE_ZMQ_DASHBOARD_LISTENER=False
export ENABLE_SIGNAL_ZMQ_ADAPTER=False
export ENABLE_VEHICLE_PROCESS_MANAGER=False

echo "环境变量设置完成"
echo ""

# 检查Python环境
echo "检查Python环境..."
python --version
python -m pytest --version

echo ""
echo "运行系统集成测试..."
echo ""

# 运行系统测试
python -m pytest tests/test_system_integration.py -v

echo ""
echo "运行API相关测试..."
echo ""

# 运行API测试
python -m pytest tests/test_system_integration.py::TestSystemIntegration -v

echo ""
echo "运行服务集成测试..."
echo ""

# 运行服务测试
python -m pytest tests/test_system_integration.py::TestServiceIntegration -v

echo ""
echo "=== 测试完成 ==="