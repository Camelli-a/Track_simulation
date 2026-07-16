# 系统测试指南

本文档描述如何运行和使用本项目的系统测试。

## 目录

1. [测试结构](#测试结构)
2. [运行测试](#运行测试)
3. [测试类别](#测试类别)
4. [测试环境](#测试环境)
5. [添加新测试](#添加新测试)
6. [故障排除](#故障排除)

## 测试结构

```
backend/
├── tests/
│   ├── conftest.py              # 测试配置和夹具
│   ├── test_system_integration.py # 系统集成测试主文件
│   └── test_*.py                # 其他单元测试
├── run_system_tests.py          # 测试运行脚本
├── test_system.bat              # Windows测试脚本
└── test_system.sh               # Linux/Mac测试脚本
```

## 运行测试

### 方法1：使用测试脚本（推荐）

#### Windows
```bash
cd backend
test_system.bat
```

#### Linux/Mac
```bash
cd backend
chmod +x test_system.sh
./test_system.sh
```

### 方法2：使用Python脚本

```bash
cd backend

# 运行所有测试
python run_system_tests.py

# 运行特定类别测试
python run_system_tests.py --category api
python run_system_tests.py --category services
python run_system_tests.py --category communication
python run_system_tests.py --category dataflow

# 运行单个测试文件
python run_system_tests.py --file tests/test_system_integration.py

# 生成覆盖率报告
python run_system_tests.py --coverage
```

### 方法3：直接使用pytest

```bash
cd backend

# 运行所有测试
pytest tests/ -v

# 运行系统集成测试
pytest tests/test_system_integration.py -v

# 运行特定测试类
pytest tests/test_system_integration.py::TestSystemIntegration -v

# 运行特定测试方法
pytest tests/test_system_integration.py::TestSystemIntegration::test_health_check -v
```

## 测试类别

系统测试分为以下几个类别：

### 1. 系统集成测试 (`TestSystemIntegration`)
- 健康检查端点
- API端点测试（车辆、电力、信号、轨道、仪表盘等）
- WebSocket连接测试
- 错误处理测试
- CORS头测试
- API文档可访问性测试

### 2. 服务集成测试 (`TestServiceIntegration`)
- 线路操作服务
- 信号服务
- 车辆模拟服务
- 动力学模型测试

### 3. 通信集成测试 (`TestCommunicationIntegration`)
- 消息代理初始化
- 消息总线集成
- 司机台数据源集成

### 4. 数据流集成测试 (`TestDataFlowIntegration`)
- 状态存储集成
- 可视化映射集成
- 数据映射器集成

## 测试环境

测试运行时自动设置以下环境变量：

```python
APP_ENV=test
DATA_SOURCE=mock
ENABLE_DASHBOARD_MOCK=True
ENABLE_ZMQ_BROKER_MANAGER=False
ENABLE_ZMQ_DASHBOARD_LISTENER=False
ENABLE_SIGNAL_ZMQ_ADAPTER=False
ENABLE_VEHICLE_PROCESS_MANAGER=False
```

这些设置确保：
- 使用模拟数据源而非真实PLC连接
- 禁用ZMQ相关组件以减少测试复杂度
- 启用仪表盘模拟用于前端测试

## 添加新测试

### 步骤1：在现有测试类中添加

```python
def test_new_feature(self):
    """测试新功能"""
    # 测试代码
    response = self.client.get("/api/v1/new_endpoint")
    assert response.status_code == 200
```

### 步骤2：创建新的测试类

```python
class TestNewComponent:
    """新组件测试"""
    
    def setup_method(self):
        self.client = TestClient(app)
    
    def test_component_feature(self):
        # 测试代码
        pass
```

### 步骤3：添加新的测试夹具（如需要）

在 `conftest.py` 中添加：

```python
@pytest.fixture
def new_fixture():
    """新的测试夹具"""
    return SomeObject()
```

## 故障排除

### 常见问题

#### 1. 导入错误
```
ModuleNotFoundError: No module named 'app'
```
**解决**：确保在backend目录下运行测试

#### 2. 环境变量问题
```
KeyError: 'APP_ENV'
```
**解决**：运行测试脚本会自动设置环境变量

#### 3. 依赖缺失
```
ImportError: cannot import name 'some_module'
```
**解决**：安装缺失的依赖
```bash
pip install -r requirements.txt
```

#### 4. 测试失败
- 检查API端点是否实现
- 验证请求/响应格式
- 确认服务是否正确初始化

### 调试测试

```bash
# 启用详细输出
pytest tests/ -v

# 启用更详细的输出
pytest tests/ -v -s

# 只运行失败的测试
pytest --lf

# 运行上次失败的测试
pytest --ff
```

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest --cov=app --cov-report=term --cov-report=html

# 查看覆盖率报告
# 打开 htmlcov/index.html
```

## 测试最佳实践

1. **独立测试**：每个测试应该独立，不依赖其他测试的状态
2. **模拟外部依赖**：使用mock替代真实的PLC、数据库等外部依赖
3. **快速执行**：测试应该快速执行，避免长时间等待
4. **明确断言**：断言应该清晰明确，便于调试
5. **覆盖边界条件**：测试正常流程和异常情况
6. **清理资源**：测试完成后清理创建的资源

## CI/CD集成

测试可以集成到CI/CD流程中：

```yaml
# GitHub Actions示例
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          python run_system_tests.py
```

---

**最后更新**: 2024-01-15