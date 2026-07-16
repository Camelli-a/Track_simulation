@echo off
REM 系统测试脚本 - Windows版本

echo === 系统集成测试 ===
echo.

REM 设置测试环境
set APP_ENV=test
set DATA_SOURCE=mock
set ENABLE_DASHBOARD_MOCK=True
set ENABLE_ZMQ_BROKER_MANAGER=False
set ENABLE_ZMQ_DASHBOARD_LISTENER=False
set ENABLE_SIGNAL_ZMQ_ADAPTER=False
set ENABLE_VEHICLE_PROCESS_MANAGER=False

echo 环境变量设置完成
echo.

REM 检查Python环境
echo 检查Python环境...
python --version
python -m pytest --version

echo.
echo 运行系统集成测试...
echo.

REM 运行系统测试
python -m pytest tests/test_system_integration.py -v

echo.
echo 运行API相关测试...
echo.

REM 运行API测试
python -m pytest tests/test_system_integration.py::TestSystemIntegration -v

echo.
echo 运行服务集成测试...
echo.

REM 运行服务测试
python -m pytest tests/test_system_integration.py::TestServiceIntegration -v

echo.
echo === 测试完成 ===
pause