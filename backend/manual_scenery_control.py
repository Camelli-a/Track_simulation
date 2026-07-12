"""
手动视景控制系统
基于正确的理解：选定边号，给出相对于该边起点的位移
"""
import time
import sys
from app.communication.scenery_source import ScenerySource

class ManualSceneryControl:
    def __init__(self):
        self.source = None
        self.current_edge = 100      # 当前边号
        self.current_offset = 0      # 相对于当前边起点的位移（mm）
        self.current_direction = 1   # 当前方向：1=正向，-1=反向
        self.current_speed = 3000    # 当前速度（mm/s）
        
    def start(self):
        """启动视景系统"""
        self.source = ScenerySource(
            scenery_host="192.168.100.124",
            scenery_port=8303,
            local_port=8302
        )
        self.source.start()
        time.sleep(1)
        print("视景系统手动控制已启动")
        print("=" * 60)
        self.show_help()
        self.show_status()
        
    def stop(self):
        """停止视景系统"""
        if self.source:
            self.source.stop()
        print("视景系统已停止")
    
    def update_position(self):
        """更新位置到视景系统"""
        self.source.update_own_train(
            speed_mmps=self.current_speed,
            section_distance_mm=self.current_offset,
            edge_id=self.current_edge,
            direction=self.current_direction
        )
        print(f"位置已更新: 边号={self.current_edge}, 位移={self.current_offset}mm, 方向={self.current_direction}")
        
        # 显示速度转换
        speed_kmh = self.current_speed / 1000 * 3.6
        print(f"当前速度: {self.current_speed}mm/s ({speed_kmh:.1f}km/h)")
    
    def move_forward(self, distance_mm=1000):
        """向前移动指定距离"""
        if self.current_direction == 1:
            self.current_offset += distance_mm
        else:
            self.current_offset -= distance_mm
        print(f"向前移动 {distance_mm}mm")
        self.update_position()
    
    def move_backward(self, distance_mm=1000):
        """向后移动指定距离"""
        if self.current_direction == 1:
            self.current_offset -= distance_mm
        else:
            self.current_offset += distance_mm
        print(f"向后移动 {distance_mm}mm")
        self.update_position()
    
    def set_edge(self, edge_id):
        """设置边号"""
        self.current_edge = edge_id
        print(f"边号已设置为: {edge_id}")
        self.update_position()
    
    def set_offset(self, offset_mm):
        """直接设置位移"""
        self.current_offset = offset_mm
        print(f"位移已设置为: {offset_mm}mm")
        self.update_position()
    
    def set_direction(self, direction):
        """设置方向"""
        if direction not in [1, -1]:
            print("错误: 方向必须是 1 (正向) 或 -1 (反向)")
            return
        self.current_direction = direction
        print(f"方向已设置为: {'正向' if direction == 1 else '反向'}")
        self.update_position()
    
    def set_speed(self, speed_mmps):
        """设置速度"""
        self.current_speed = speed_mmps
        speed_kmh = speed_mmps / 1000 * 3.6
        print(f"速度已设置为: {speed_mmps}mm/s ({speed_kmh:.1f}km/h)")
        self.update_position()
    
    def show_status(self):
        """显示当前状态"""
        if not self.source:
            return
        
        status = self.source.status()
        print("\n当前状态:")
        print(f"  目标地址: {status['target']}")
        print(f"  已发送包: {status['send_count']}")
        print(f"  错误数: {status['error_count']}")
        print(f"  当前边号: {self.current_edge}")
        print(f"  当前位移: {self.current_offset}mm ({self.current_offset/1000:.1f}m)")
        print(f"  当前方向: {'正向' if self.current_direction == 1 else '反向'}")
        print(f"  当前速度: {self.current_speed}mm/s ({self.current_speed/1000*3.6:.1f}km/h)")
        print("-" * 40)
    
    def show_help(self):
        """显示帮助信息"""
        print("手动控制命令:")
        print("  f <距离>    - 向前移动 (例: f 1000)")
        print("  b <距离>    - 向后移动 (例: b 500)")
        print("  edge <边号> - 设置边号 (例: edge 100)")
        print("  offset <mm> - 直接设置位移 (例: offset 5000)")
        print("  dir <1/-1>  - 设置方向 (例: dir 1)")
        print("  speed <mm/s>- 设置速度 (例: speed 3000)")
        print("  status      - 显示当前状态")
        print("  help        - 显示帮助")
        print("  quit        - 退出")
        print()
        print("建议的测试步骤:")
        print("1. 先设置一个合理的边号 (edge 100)")
        print("2. 设置一个小的位移 (offset 1000)")
        print("3. 缓慢向前移动 (f 500 多次)")
        print("4. 观察视景系统反应")
        print()
        print("基于附件2数据表的边号参考:")
        print("  边号100: 长度150.897Km")
        print("  边号101: 可能是起点")
        print("  边号200, 300: 其他边号")
        print()

def main():
    control = ManualSceneryControl()
    control.start()
    
    try:
        while True:
            try:
                cmd = input("\n命令> ").strip()
                if not cmd:
                    continue
                
                parts = cmd.split()
                action = parts[0].lower()
                
                if action == "quit" or action == "q":
                    break
                
                elif action == "f" or action == "forward":
                    # 向前移动
                    distance = 1000  # 默认1米
                    if len(parts) >= 2:
                        try:
                            distance = int(parts[1])
                        except ValueError:
                            print("错误: 距离必须是数字")
                            continue
                    control.move_forward(distance)
                
                elif action == "b" or action == "backward":
                    # 向后移动
                    distance = 1000  # 默认1米
                    if len(parts) >= 2:
                        try:
                            distance = int(parts[1])
                        except ValueError:
                            print("错误: 距离必须是数字")
                            continue
                    control.move_backward(distance)
                
                elif action == "edge":
                    # 设置边号
                    if len(parts) >= 2:
                        try:
                            edge = int(parts[1])
                            control.set_edge(edge)
                        except ValueError:
                            print("错误: 边号必须是数字")
                    else:
                        print("用法: edge <边号>")
                
                elif action == "offset":
                    # 设置位移
                    if len(parts) >= 2:
                        try:
                            offset = int(parts[1])
                            control.set_offset(offset)
                        except ValueError:
                            print("错误: 位移必须是数字")
                    else:
                        print("用法: offset <毫米>")
                
                elif action == "dir" or action == "direction":
                    # 设置方向
                    if len(parts) >= 2:
                        try:
                            direction = int(parts[1])
                            control.set_direction(direction)
                        except ValueError:
                            print("错误: 方向必须是 1 或 -1")
                    else:
                        print("用法: dir <1或-1>")
                
                elif action == "speed":
                    # 设置速度
                    if len(parts) >= 2:
                        try:
                            speed = int(parts[1])
                            control.set_speed(speed)
                        except ValueError:
                            print("错误: 速度必须是数字")
                    else:
                        print("用法: speed <毫米/秒>")
                
                elif action == "status":
                    control.show_status()
                
                elif action == "help":
                    control.show_help()
                
                else:
                    print("未知命令，输入 'help' 查看帮助")
            
            except KeyboardInterrupt:
                print("\n中断，输入 'quit' 退出")
            except Exception as e:
                print(f"错误: {e}")
    
    except EOFError:
        print("\nEOF，退出")
    finally:
        control.stop()

if __name__ == "__main__":
    main()