"""
精确的视景系统位置测试
基于附件2数据表进行计算
"""
import time
import sys
from app.communication.scenery_source import ScenerySource

def test_precise_positions():
    """基于数据表的精确位置测试"""
    source = ScenerySource(
        scenery_host="192.168.100.124",
        scenery_port=8303,
        local_port=8302
    )
    
    source.start()
    print("视景系统精确测试开始...")
    time.sleep(1)
    
    # 基于附件2数据表的测试案例
    # 注意：数据表中的Km需要转换为mm
    # 1 km = 1,000,000 mm
    
    # 分析边号100的数据：
    # BeginKm = 219.153 km = 219,153,000 mm
    # EndKm = 370.055 km = 370,055,000 mm
    # 这是一个非常大的距离范围
    
    # 测试案例1：使用数据表中的实际起始点
    test_cases = [
        # 基于边号100的数据
        {
            "desc": "边号100起始点附近",
            "distance_mm": 219153000,  # 219.153 km in mm
            "edge_id": 100,
            "direction": 1
        },
        {
            "desc": "边号100中间点",
            "distance_mm": 294604000,  # (219.153+370.055)/2 = 294.604 km
            "edge_id": 100,
            "direction": 1
        },
        {
            "desc": "边号100结束点附近",
            "distance_mm": 370055000,  # 370.055 km in mm
            "edge_id": 100,
            "direction": 1
        },
        # 测试更小的边号（从数据表看，似乎边号越大，距离越大？）
        {
            "desc": "尝试最小边号200",
            "distance_mm": 5000,
            "edge_id": 200,
            "direction": 1
        },
        {
            "desc": "尝试边号300",
            "distance_mm": 10000,
            "edge_id": 300,
            "direction": 1
        },
    ]
    
    for i, test in enumerate(test_cases):
        print(f"\n测试{i+1}: {test['desc']}")
        print(f"  distance_mm={test['distance_mm']:,} mm")
        print(f"  edge_id={test['edge_id']}, direction={test['direction']}")
        
        source.update_own_train(
            speed_mmps=5000,
            section_distance_mm=test['distance_mm'],
            edge_id=test['edge_id'],
            direction=test['direction']
        )
        
        # 等待视景系统更新
        time.sleep(3)
        
        # 检查状态
        status = source.status()
        print(f"  已发送包: {status['send_count']}")
    
    print("\n等待观察视景系统反应...")
    time.sleep(5)
    
    final_status = source.status()
    print(f"\n最终状态: sent={final_status['send_count']}, errors={final_status['error_count']}")
    
    source.stop()
    print("精确测试完成。")

def test_smaller_distances():
    """测试更小的距离范围"""
    print("\n=== 测试较小距离范围 ===")
    source = ScenerySource(
        scenery_host="192.168.100.124",
        scenery_port=8303,
        local_port=8302
    )
    
    source.start()
    time.sleep(1)
    
    # 测试更合理的距离（可能在起点道岔附近）
    small_tests = [
        {"desc": "非常小的距离", "mm": 1000, "edge": 1, "dir": 1},
        {"desc": "较小距离", "mm": 5000, "edge": 1, "dir": 1},
        {"desc": "中等距离", "mm": 10000, "edge": 1, "dir": 1},
        {"desc": "尝试edge=2", "mm": 5000, "edge": 2, "dir": 1},
        {"desc": "尝试edge=3", "mm": 10000, "edge": 3, "dir": 1},
    ]
    
    for test in small_tests:
        print(f"\n测试: {test['desc']}")
        print(f"  distance={test['mm']}mm, edge={test['edge']}, dir={test['dir']}")
        
        source.update_own_train(
            speed_mmps=3000,
            section_distance_mm=test['mm'],
            edge_id=test['edge'],
            direction=test['dir']
        )
        time.sleep(2)
    
    time.sleep(5)
    source.stop()
    print("小距离测试完成。")

if __name__ == "__main__":
    print("开始视景系统精确位置测试...")
    
    # 先测试基于数据表的精确位置
    test_precise_positions()
    
    # 再测试更小的距离范围
    test_smaller_distances()
    
    print("\n所有测试完成。请检查视景系统显示。")