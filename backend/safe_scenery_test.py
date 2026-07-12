"""
基于附件2数据表的安全视景测试
确保位置在轨道范围内
"""
import time
from app.communication.scenery_source import ScenerySource

def run_safe_test():
    """运行安全测试"""
    source = ScenerySource(
        scenery_host="192.168.100.124",
        scenery_port=8303,
        local_port=8302
    )
    
    source.start()
    print("安全视景测试开始...")
    time.sleep(1)
    
    # ============================================
    # 基于附件2数据表的安全参数
    # ============================================
    
    # 注意：数据表中的Km需要转换为mm
    # 1 Km = 1,000,000 mm
    
    # 测试案例1：起点道岔附近（假设边号101是起点）
    print("\n=== 测试1: 起点道岔附近 ===")
    print("参数: distance=1000mm, edge=101, dir=1")
    source.update_own_train(
        speed_mmps=3000,  # 3米/秒 = 10.8公里/小时
        section_distance_mm=1000,  # 1米
        edge_id=101,
        direction=1
    )
    time.sleep(3)
    
    # 测试案例2：边号100起始点（219.153Km转换为mm）
    print("\n=== 测试2: 边号100起始点附近 ===")
    # 219.153 Km = 219,153,000 mm
    # 使用相对小的偏移：219,153,000 + 10,000 mm
    distance_mm = 219153000 + 10000  # 219.163 Km
    print(f"参数: distance={distance_mm:,}mm, edge=100, dir=1")
    source.update_own_train(
        speed_mmps=3000,
        section_distance_mm=distance_mm,
        edge_id=100,
        direction=1
    )
    time.sleep(3)
    
    # 测试案例3：边号100中间点
    print("\n=== 测试3: 边号100中间点 ===")
    # 中间点：(219.153 + 370.055)/2 = 294.604 Km
    distance_mm = 294604000  # 294.604 Km
    print(f"参数: distance={distance_mm:,}mm, edge=100, dir=1")
    source.update_own_train(
        speed_mmps=3000,
        section_distance_mm=distance_mm,
        edge_id=100,
        direction=1
    )
    time.sleep(3)
    
    # 测试案例4：非常保守的小距离
    print("\n=== 测试4: 非常保守的小距离 ===")
    print("参数: distance=5000mm, edge=200, dir=1")
    source.update_own_train(
        speed_mmps=2000,
        section_distance_mm=5000,
        edge_id=200,
        direction=1
    )
    time.sleep(3)
    
    # 测试案例5：尝试边号300
    print("\n=== 测试5: 边号300测试 ===")
    print("参数: distance=8000mm, edge=300, dir=1")
    source.update_own_train(
        speed_mmps=2000,
        section_distance_mm=8000,
        edge_id=300,
        direction=1
    )
    time.sleep(3)
    
    # 测试案例6：反向移动测试
    print("\n=== 测试6: 反向移动测试 ===")
    print("参数: distance=5000mm, edge=101, dir=-1")
    source.update_own_train(
        speed_mmps=2000,
        section_distance_mm=5000,
        edge_id=101,
        direction=-1
    )
    time.sleep(3)
    
    # 最终状态
    status = source.status()
    print(f"\n最终状态: sent={status['send_count']}, errors={status['error_count']}")
    
    source.stop()
    print("安全测试完成。")
    
    print("\n" + "="*60)
    print("安全参数总结：")
    print("="*60)
    print("1. 起点附近: pos 1000 101 1")
    print("2. 边号100起始点: pos 219163000 100 1")
    print("3. 边号100中间点: pos 294604000 100 1")
    print("4. 保守小距离: pos 5000 200 1")
    print("5. 边号300: pos 8000 300 1")
    print("6. 反向: pos 5000 101 -1")
    print("\n注意：如果还是'着火'，可能是：")
    print("1. 边号不对（需要知道正确的边号映射）")
    print("2. 距离单位问题（可能是m而不是mm）")
    print("3. 起点道岔位置不同")

if __name__ == "__main__":
    run_safe_test()