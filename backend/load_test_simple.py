"""
简单的API压测脚本
测试轨道模拟系统的API接口性能
"""

import asyncio
import aiohttp
import time
import json
import statistics
from typing import List, Dict
import random


class SimpleLoadTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(self, endpoint: str, method: str = "GET", 
                           payload: Dict = None, num_requests: int = 100) -> Dict:
        """测试单个端点"""
        start_time = time.time()
        tasks = []
        errors = 0
        
        for i in range(num_requests):
            if method == "GET":
                task = self.session.get(f"{self.base_url}{endpoint}")
            elif method == "POST" and payload:
                # 为每个请求添加唯一标识
                if isinstance(payload, dict):
                    modified_payload = payload.copy()
                    modified_payload["request_id"] = i
                else:
                    modified_payload = payload
                task = self.session.post(f"{self.base_url}{endpoint}", 
                                        json=modified_payload)
            else:
                task = self.session.get(f"{self.base_url}{endpoint}")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        response_times = []
        for response in responses:
            if isinstance(response, Exception):
                errors += 1
            elif isinstance(response, aiohttp.ClientResponse):
                # 记录响应时间（简化版，实际需要更精确计时）
                pass
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / num_requests if num_requests > 0 else 0
        
        return {
            "endpoint": endpoint,
            "method": method,
            "total_requests": num_requests,
            "success_requests": num_requests - errors,
            "error_requests": errors,
            "total_time": total_time,
            "avg_time_per_request": avg_time,
            "requests_per_second": num_requests / total_time if total_time > 0 else 0
        }
    
    async def run_vehicle_tests(self, num_requests: int = 50):
        """车辆API压测"""
        print(f"\n{'='*60}")
        print("车辆API压测")
        print(f"{'='*60}")
        
        results = []
        
        # 测试1: 获取车辆状态
        status_result = await self.test_endpoint(
            endpoint="/api/v1/vehicle/status",
            method="GET",
            num_requests=num_requests
        )
        results.append(status_result)
        print(f"✓ 车辆状态接口: {status_result['requests_per_second']:.2f} 请求/秒")
        
        # 测试2: 车辆控制（模拟多个车辆控制命令）
        control_commands = [
            {"vehicle_id": "TRAIN-001", "command": "start"},
            {"vehicle_id": "TRAIN-001", "command": "stop"},
            {"vehicle_id": "TRAIN-001", "command": "set_speed", "speed": 60},
            {"vehicle_id": "TRAIN-001", "command": "set_speed", "speed": 80},
        ]
        
        for i, command in enumerate(control_commands):
            control_result = await self.test_endpoint(
                endpoint="/api/v1/vehicle/control",
                method="POST",
                payload=command,
                num_requests=num_requests // 4
            )
            results.append(control_result)
            print(f"✓ 车辆控制({command['command']}): {control_result['requests_per_second']:.2f} 请求/秒")
        
        return results
    
    async def run_signal_tests(self, num_requests: int = 50):
        """信号API压测"""
        print(f"\n{'='*60}")
        print("信号API压测")
        print(f"{'='*60}")
        
        results = []
        
        # 测试1: 获取信号状态
        status_result = await self.test_endpoint(
            endpoint="/api/v1/signal/status",
            method="GET",
            num_requests=num_requests
        )
        results.append(status_result)
        print(f"✓ 信号状态接口: {status_result['requests_per_second']:.2f} 请求/秒")
        
        # 测试2: 获取移动授权状态
        ma_result = await self.test_endpoint(
            endpoint="/api/v1/signal/ma",
            method="GET",
            num_requests=num_requests
        )
        results.append(ma_result)
        print(f"✓ 移动授权接口: {ma_result['requests_per_second']:.2f} 请求/秒")
        
        return results
    
    async def run_mixed_tests(self, num_requests: int = 100):
        """混合API压测 - 模拟真实场景"""
        print(f"\n{'='*60}")
        print("混合场景压测")
        print(f"{'='*60}")
        
        endpoints = [
            ("/api/v1/vehicle/status", "GET", None),
            ("/api/v1/signal/status", "GET", None),
            ("/api/v1/power/status", "GET", None),
            ("/api/v1/track/status", "GET", None),
        ]
        
        results = []
        for i, (endpoint, method, payload) in enumerate(endpoints):
            result = await self.test_endpoint(
                endpoint=endpoint,
                method=method,
                payload=payload,
                num_requests=num_requests // len(endpoints)
            )
            results.append(result)
            print(f"✓ {endpoint}: {result['requests_per_second']:.2f} 请求/秒")
        
        return results
    
    def print_summary(self, all_results: List[Dict]):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("压测结果摘要")
        print(f"{'='*60}")
        
        total_requests = sum(r['total_requests'] for r in all_results)
        total_errors = sum(r['error_requests'] for r in all_results)
        total_time = sum(r['total_time'] for r in all_results)
        avg_rps = statistics.mean([r['requests_per_second'] for r in all_results if r['requests_per_second'] > 0])
        
        print(f"总请求数: {total_requests}")
        print(f"成功请求: {total_requests - total_errors}")
        print(f"失败请求: {total_errors}")
        print(f"错误率: {(total_errors/total_requests*100):.2f}%" if total_requests > 0 else "0%")
        print(f"总耗时: {total_time:.2f}秒")
        print(f"平均吞吐量: {avg_rps:.2f} 请求/秒")
        
        print(f"\n各接口性能排名:")
        sorted_results = sorted(all_results, key=lambda x: x['requests_per_second'], reverse=True)
        for i, result in enumerate(sorted_results[:5], 1):
            print(f"{i}. {result['endpoint']}: {result['requests_per_second']:.2f} 请求/秒 "
                  f"(成功率: {((result['total_requests']-result['error_requests'])/result['total_requests']*100):.1f}%)")


async def main():
    """主函数"""
    print("轨道模拟系统压测开始...")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        async with SimpleLoadTest() as tester:
            # 先检查API是否可用
            try:
                async with aiohttp.ClientSession() as session:
                    response = await session.get("http://localhost:8000/")
                    if response.status == 200:
                        print("✓ API服务正常")
                    else:
                        print(f"⚠ API返回状态码: {response.status}")
            except Exception as e:
                print(f"✗ 无法连接到API: {e}")
                print("请确保后端服务已启动: uvicorn main:app --reload")
                return
            
            all_results = []
            
            # 运行车辆API压测
            vehicle_results = await tester.run_vehicle_tests(num_requests=50)
            all_results.extend(vehicle_results)
            
            # 运行信号API压测
            signal_results = await tester.run_signal_tests(num_requests=50)
            all_results.extend(signal_results)
            
            # 运行混合场景压测
            mixed_results = await tester.run_mixed_tests(num_requests=100)
            all_results.extend(mixed_results)
            
            # 打印汇总结果
            tester.print_summary(all_results)
            
    except Exception as e:
        print(f"压测过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())