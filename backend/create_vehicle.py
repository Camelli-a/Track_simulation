"""
创建车辆的简单脚本
"""
import requests
import json

def create_vehicle():
    url = "http://localhost:8000/api/v1/vehicle/manage"
    
    # 创建车辆
    payload = {
        "type": "add_train",
        "vehicle_id": "TRAIN-001"
    }
    
    print(f"创建车辆: {payload}")
    
    try:
        response = requests.post(url, json=payload)
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and response.json().get("ok"):
            print("✅ 车辆创建成功!")
            
            # 查看车辆列表
            list_url = "http://localhost:8000/api/v1/vehicle/trains"
            list_response = requests.get(list_url)
            print(f"\n当前车辆列表:")
            print(json.dumps(list_response.json(), indent=2, ensure_ascii=False))
        else:
            print("❌ 车辆创建失败")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def list_vehicles():
    """查看所有车辆"""
    url = "http://localhost:8000/api/v1/vehicle/trains"
    
    try:
        response = requests.get(url)
        print(f"\n=== 车辆列表 ===")
        print(f"状态码: {response.status_code}")
        data = response.json()
        
        if "trains" in data:
            for train in data["trains"]:
                print(f"车辆ID: {train['vehicle_id']}")
                print(f"  槽位: {train['train_index']}")
                print(f"  位置: {train['position']}m")
                print(f"  速度: {train['speed']}km/h")
                print(f"  模式: {train['mode']}")
                print(f"  紧急制动: {train['emergency_brake']}")
                print("  ---")
        else:
            print("无车辆数据")
            
    except Exception as e:
        print(f"❌ 获取车辆列表失败: {e}")

if __name__ == "__main__":
    print("=== 车辆管理工具 ===")
    
    # 先查看现有车辆
    list_vehicles()
    
    # 创建新车辆
    create = input("\n是否创建新车辆? (y/n): ")
    if create.lower() == 'y':
        vehicle_id = input("车辆ID (默认 TRAIN-001): ") or "TRAIN-001"
        slot = input("槽位 (可选，按回车自动分配): ") or None
        
        payload = {"type": "add_train", "vehicle_id": vehicle_id}
        if slot:
            payload["train_index"] = int(slot)
            
        url = "http://localhost:8000/api/v1/vehicle/manage"
        response = requests.post(url, json=payload)
        
        print(f"\n创建结果:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
        # 再次查看车辆列表
        list_vehicles()