"""
视景系统位置测试脚本
用于快速测试多个合理的位置组合
"""
import time
import sys
from app.communication.scenery_source import ScenerySource

def test_position(source, distance_mm, edge_id, direction, description):
    """测试单个位置"""
    print(f"\n测试: {description}")
    print(f"  distance_mm={distance_mm}, edge_id={edge_id}, direction={direction}")
    
    source.update_own_train(
        speed_mmps=5000,  # 5米/秒 = 18公里/小时
        section_distance_mm=distance_mm,
        edge_id=edge_id,
        direction=direction
    )
    
    # 等待几秒让视景系统更新
    time.sleep(2)
    return True

def main():
    # 创建视景源
    source = ScenerySource(
        scenery_host="192.168.100.124",
        scenery_port=8303,
        local_port=8302
    )
    
    source.start()
    print("视景系统已启动，开始位置测试...")
    
    # 等待启动完成
    time.sleep(1)
    
    # 测试方案1：基于数据表的小距离测试
    test_cases = [
        # (distance_mm, edge_id, direction, description)
        (1000, 100, 1, "位置1: 小距离，边号100，正方向"),
        (5000, 100, 1, "位置2: 中等距离，边号100，正方向"),
        (10000, 100, 1, "位置3: 较大距离，边号100，正方向"),
        (5000, 200, 1, "位置4: 中等距离，边号200，正方向"),
        (1000, 300, 1, "位置5: 小距离，边号300，正方向"),
        # 尝试更保守的位置
        (100, 100, 1, "位置6: 非常小的距离，边号100，正方向"),
        (0, 100, 1, "位置7: 零距离，边号100，正方向"),
    ]
    
    for distance_mm, edge_id, direction, description in test_cases:
        test_position(source, distance_mm, edge_id, direction, description)
    
    print("\n所有测试完成。等待10秒观察视景系统反应...")
    time.sleep(10)
    
    # 获取最终状态
    status = source.status()
    print(f"\n最终状态: sent={status['send_count']}, errors={status['error_count']}")
    
    source.stop()
    print("测试完成。")

if __name__ == "__main__":
    main()