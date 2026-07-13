"""
快速测试脚本 - 跳过前端，直接测试核心功能
"""
import requests
import json
import time

def test_plc_to_speed_curve():
    """测试从PLC到速度曲线的完整链路"""
    print("=== 快速测试：PLC -> 车辆 -> 速度曲线 ===")
    
    # 1. 检查API服务是否运行
    try:
        health = requests.get("http://localhost:8000/", timeout=2)
        print(f"✅ API服务正常: {health.json()}")
    except:
        print("❌ API服务未运行，请先启动：uvicorn main:app --reload")
        return
    
    # 2. 创建车辆
    print("\n2. 创建车辆...")
    create_url = "http://localhost:8000/api/v1/vehicle/manage"
    create_data = {
        "type": "add_train",
        "vehicle_id": "TRAIN-001"
    }
    
    try:
        create_resp = requests.post(create_url, json=create_data)
        if create_resp.status_code == 200:
            create_result = create_resp.json()
            if create_result.get("ok"):
                print(f"✅ 车辆创建成功: {create_result['vehicle_id']}")
            else:
                print(f"❌ 车辆创建失败: {create_result}")
        else:
            print(f"❌ HTTP错误: {create_resp.status_code}")
    except Exception as e:
        print(f"❌ 创建车辆失败: {e}")
        return
    
    # 3. 查看车辆列表
    print("\n3. 查看车辆列表...")
    try:
        list_url = "http://localhost:8000/api/v1/vehicle/trains"
        list_resp = requests.get(list_url)
        if list_resp.status_code == 200:
            vehicles = list_resp.json()
            print(f"✅ 车辆列表: {json.dumps(vehicles, indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ 获取车辆列表失败: {list_resp.status_code}")
    except Exception as e:
        print(f"❌ 获取车辆列表失败: {e}")
    
    # 4. 测试速度曲线API（这个不需要信号系统）
    print("\n4. 测试速度曲线API...")
    try:
        # 获取速度曲线状态
        speed_status_url = "http://localhost:8000/api/v1/speedcurve/TRAIN-001/status"
        speed_resp = requests.get(speed_status_url)
        if speed_resp.status_code == 200:
            speed_status = speed_resp.json()
            print(f"✅ 速度曲线状态: {json.dumps(speed_status, indent=2, ensure_ascii=False)}")
            
            # 获取历史数据
            history_url = "http://localhost:8000/api/v1/speedcurve/TRAIN-001/history"
            history_resp = requests.get(history_url)
            if history_resp.status_code == 200:
                history = history_resp.json()
                print(f"✅ 历史数据点数: {len(history)}")
                if history:
                    latest = history[-1]
                    print(f"   最新数据:")
                    print(f"     时间: {latest['timestamp']}")
                    print(f"     位置: {latest['position_m']}m")
                    print(f"     速度: {latest['speed_kmh']}km/h")
                    print(f"     牵引: {latest['traction_percent']}%")
                    print(f"     制动: {latest['brake_percent']}%")
        else:
            print(f"❌ 速度曲线API错误: {speed_resp.status_code}")
    except Exception as e:
        print(f"❌ 速度曲线测试失败: {e}")
    
    # 5. 发送控制命令（模拟PLC数据）
    print("\n5. 发送控制命令测试...")
    try:
        control_url = "http://localhost:8000/api/v1/vehicle/control"
        control_data = {
            "vehicle_id": "TRAIN-001",
            "command": "traction",
            "traction_level": 2,
            "traction_percent": 50.0,
            "direction": "forward"
        }
        
        control_resp = requests.post(control_url, json=control_data)
        if control_resp.status_code == 200:
            print(f"✅ 控制命令发送成功: {control_resp.json()}")
        else:
            print(f"❌ 控制命令失败: {control_resp.status_code}")
    except Exception as e:
        print(f"❌ 控制命令失败: {e}")
    
    # 6. 等待几秒，再次检查速度曲线
    print("\n6. 等待3秒，检查数据更新...")
    time.sleep(3)
    
    try:
        speed_status_url = "http://localhost:8000/api/v1/speedcurve/TRAIN-001/status"
        speed_resp = requests.get(speed_status_url)
        if speed_resp.status_code == 200:
            updated_status = speed_resp.json()
            print(f"✅ 更新后的状态:")
            print(f"   连接状态: {updated_status['connected']}")
            print(f"   当前速度: {updated_status['current_speed_kmh']}km/h")
            print(f"   当前位置: {updated_status['current_position_m']}m")
            print(f"   牵引百分比: {updated_status['current_traction_percent']}%")
            print(f"   制动百分比: {updated_status['current_brake_percent']}%")
    except Exception as e:
        print(f"❌ 检查更新失败: {e}")
    
    print("\n=== 测试完成 ===")
    print("如果速度曲线有数据，说明PLC->车辆->速度曲线链路正常！")

if __name__ == "__main__":
    test_plc_to_speed_curve()