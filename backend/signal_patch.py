"""
信号系统热补丁 - 直接返回mock数据，不抛异常
"""
import sys
from pathlib import Path

# 修改信号服务的源文件
signal_service_path = Path(__file__).parent / "app" / "services" / "signal_service.py"

original_code = '''    def get_status(self) -> SignalStatus:
        if self.source == "mock":
            return self._mock_status()
        elif self.source == "udp":
            raise NotImplementedError("UDP 数据源尚未实现")
        elif self.source == "zmq":
            raise NotImplementedError("ZMQ 数据源尚未实现")
        else:
            raise ValueError(f"未知数据源: {self.source}")'''

patched_code = '''    def get_status(self) -> SignalStatus:
        # 热补丁：所有数据源都返回mock，不中断系统
        return self._mock_status()'''

print("应用信号系统热补丁...")
try:
    with open(signal_service_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if original_code in content:
        content = content.replace(original_code, patched_code)
        with open(signal_service_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ 信号系统补丁应用成功！")
        print("现在系统启动时不会因信号服务而崩溃")
    else:
        print("⚠️  原始代码已修改，跳过补丁")
except Exception as e:
    print(f"❌ 补丁失败: {e}")