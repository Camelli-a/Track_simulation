"""
交互式视景系统调试工具
可以实时调整参数并观察效果
"""
import time
import threading
from app.communication.scenery_source import ScenerySource

class InteractiveSceneryTest:
    def __init__(self):
        self.source = None
        self.running = False
        self.current_params = {
            "speed_mmps": 5000,
            "distance_mm": 10000,
            "edge_id": 100,
            "direction": 1,
            "run_state": 0x13,  # 惰行
            "accel": 50
        }
    
    def start(self):
        """启动视景系统"""
        self.source = ScenerySource(
            scenery_host="192.168.100.124",
            scenery_port=8303,
            local_port=8302
        )
        self.source.start()
        self.running = True
        
        # 启动状态监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_status, daemon=True)
        self.monitor_thread.start()
        
        print("视景系统交互调试工具已启动")
        print("=" * 50)
        self.show_status()
        self.show_help()
    
    def stop(self):
        """停止视景系统"""
        self.running = False
        if self.source:
            self.source.stop()
        print("视景系统已停止")
    
    def _monitor_status(self):
        """监控状态线程"""
        while self.running:
            time.sleep(5)
            if self.source:
                status = self.source.status()
                print(f"[监控] 已发送: {status['send_count']}, 错误: {status['error_count']}")
    
    def update_params(self, **kwargs):
        """更新参数"""
        self.current_params.update(kwargs)
        
        # 应用更新
        self.source.update_own_train(
            speed_mmps=self.current_params["speed_mmps"],
            section_distance_mm=self.current_params["distance_mm"],
            edge_id=self.current_params["edge_id"],
            direction=self.current_params["direction"],
            run_state=self.current_params.get("run_state", 0x13),
            accel=self.current_params.get("accel", 50)
        )
        
        print(f"参数已更新:")
        print(f"  速度: {self.current_params['speed_mmps']} mm/s ({self.current_params['speed_mmps']/1000*3.6:.1f} km/h)")
        print(f"  距离: {self.current_params['distance_mm']:,} mm ({self.current_params['distance_mm']/1000:.1f} m)")
        print(f"  边号: {self.current_params['edge_id']}")
        print(f"  方向: {'正向(+1)' if self.current_params['direction'] == 1 else '反向(-1)'}")
        print(f"  等待视景系统更新...")
    
    def show_status(self):
        """显示当前状态"""
        if not self.source:
            return
        
        status = self.source.status()
        print(f"当前状态:")
        print(f"  目标: {status['target']}")
        print(f"  已发送包: {status['send_count']}")
        print(f"  错误数: {status['error_count']}")
        print(f"  计数器: {status['live_counter']}")
        print()
        
        # 显示当前参数
        print(f"当前参数:")
        print(f"  速度: {self.current_params['speed_mmps']} mm/s")
        print(f"  距离: {self.current_params['distance_mm']} mm")
        print(f"  边号: {self.current_params['edge_id']}")
        print(f"  方向: {self.current_params['direction']}")
        print("-" * 50)
    
    def show_help(self):
        """显示帮助信息"""
        print("可用命令:")
        print("  speed <毫米/秒>  - 设置车速 (例: speed 5000)")
        print("  pos <毫米> <边号> <方向> - 设置位置 (例: pos 10000 100 1)")
        print("  edge <边号>     - 只设置边号")
        print("  dir <1/-1>      - 设置方向")
        print("  status          - 显示当前状态")
        print("  test <编号>     - 运行预设测试")
        print("  help            - 显示帮助")
        print("  quit            - 退出")
        print()
        print("预设测试:")
        print("  1: 小距离测试 (1-10米)")
        print("  2: 中等距离测试 (10-100米)")
        print("  3: 大距离测试 (100-1000米)")
        print("  4: 边号扫描测试")
        print()
    
    def run_preset_test(self, test_id):
        """运行预设测试"""
        tests = {
            1: self._test_small_distances,
            2: self._test_medium_distances,
            3: self._test_large_distances,
            4: self._test_edge_scan
        }
        
        test_func = tests.get(test_id)
        if test_func:
            test_func()
        else:
            print(f"未知测试编号: {test_id}")
    
    def _test_small_distances(self):
        """小距离测试"""
        print("开始小距离测试 (1-10米)...")
        distances = [1000, 2000, 5000, 8000, 10000]  # 1-10米
        
        for dist in distances:
            print(f"测试距离: {dist} mm ({dist/1000} m)")
            self.update_params(distance_mm=dist, edge_id=100)
            time.sleep(2)
        
        print("小距离测试完成")
    
    def _test_medium_distances(self):
        """中等距离测试"""
        print("开始中等距离测试 (10-100米)...")
        distances = [10000, 20000, 50000, 80000, 100000]  # 10-100米
        
        for dist in distances:
            print(f"测试距离: {dist:,} mm ({dist/1000} m)")
            self.update_params(distance_mm=dist, edge_id=100)
            time.sleep(2)
        
        print("中等距离测试完成")
    
    def _test_large_distances(self):
        """大距离测试"""
        print("开始大距离测试 (100-1000米)...")
        distances = [100000, 200000, 500000, 800000, 1000000]  # 100-1000米
        
        for dist in distances:
            print(f"测试距离: {dist:,} mm ({dist/1000} m)")
            self.update_params(distance_mm=dist, edge_id=100)
            time.sleep(2)
        
        print("大距离测试完成")
    
    def _test_edge_scan(self):
        """边号扫描测试"""
        print("开始边号扫描测试...")
        edges = [1, 2, 3, 10, 20, 50, 100, 200, 300]
        
        for edge in edges:
            print(f"测试边号: {edge}")
            self.update_params(edge_id=edge, distance_mm=10000)
            time.sleep(2)
        
        print("边号扫描测试完成")

def main():
    test = InteractiveSceneryTest()
    test.start()
    
    try:
        while True:
            cmd = input("\n> ").strip()
            if not cmd:
                continue
            
            parts = cmd.split()
            action = parts[0].lower()
            
            if action == "quit" or action == "q":
                break
            
            elif action == "speed" and len(parts) >= 2:
                try:
                    speed = int(parts[1])
                    test.update_params(speed_mmps=speed)
                except ValueError:
                    print("错误: 速度必须是数字")
            
            elif action == "pos" and len(parts) >= 4:
                try:
                    distance = int(parts[1])
                    edge = int(parts[2])
                    direction = int(parts[3])
                    test.update_params(distance_mm=distance, edge_id=edge, direction=direction)
                except ValueError:
                    print("错误: 参数必须是数字")
                except IndexError:
                    print("用法: pos <毫米> <边号> <方向>")
            
            elif action == "edge" and len(parts) >= 2:
                try:
                    edge = int(parts[1])
                    test.update_params(edge_id=edge)
                except ValueError:
                    print("错误: 边号必须是数字")
            
            elif action == "dir" and len(parts) >= 2:
                try:
                    direction = int(parts[1])
                    if direction not in [1, -1]:
                        print("错误: 方向必须是 1 或 -1")
                    else:
                        test.update_params(direction=direction)
                except ValueError:
                    print("错误: 方向必须是数字")
            
            elif action == "status":
                test.show_status()
            
            elif action == "test" and len(parts) >= 2:
                try:
                    test_id = int(parts[1])
                    test.run_preset_test(test_id)
                except ValueError:
                    print("错误: 测试编号必须是数字")
            
            elif action == "help":
                test.show_help()
            
            else:
                print("未知命令，输入 'help' 查看帮助")
    
    except KeyboardInterrupt:
        print("\n接收到中断信号")
    finally:
        test.stop()

if __name__ == "__main__":
    main()