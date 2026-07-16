"""
无硬件环境压测脚本
专门针对没有PLC、视景系统等硬件连接的情况
使用模拟数据模式进行API压测
"""

import asyncio
import aiohttp
import time
import json
import statistics
from typing import List, Dict, Any
import random


class NoHardwareLoadTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_service(self) -> bool:
        """检查服务是否可用"""
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(f"{self.base_url}/", timeout=5)
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ 服务状态正常:")
                    print(f"  - 状态: {data.get('status', 'unknown')}")
                    print(f"  - 数据源: {data.get('data_source', 'unknown')}")
                    print(f"  - 模拟模式: {data.get('enable_dashboard_mock', 'unknown')}")
                    return True
                else:
                    print(f"✗ 服务返回状态码: {response.status}")
                    return False
        except Exception as e:
            print(f"✗ 无法连接到服务: {e}")
            return False
    
    async def basic_api_test(self):
        """基础API功能测试"""
        print(f"\n{'='*60}")
        print("基础API功能测试")
        print(f"{'='*60}")
        
        endpoints = [
            ("/api/v1/vehicle/status", "GET"),
            ("/api/v1/signal/status", "GET"),
            ("/api/v1/power/status", "GET"),
            ("/api/v1/track/status", "GET"),
            ("/api/v1/driver-desk-sim/status", "GET"),
        ]
        
        results = []
        for endpoint, method in endpoints:
            start_time = time.time()
            try:
                if method == "GET":
                    async with self.session.get(f"{self.base_url}{endpoint}") as response:
                        status = response.status
                        if status == 200:
                            data = await response.json()
                            success = True
                        else:
                            success = False
                else:
                    success = False
            except Exception:
                success = False
                
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # 毫秒
            
            result = {
                "endpoint": endpoint,
                "success": success,
                "latency_ms": latency,
                "status_code": status if 'status' in locals() else None
            }
            results.append(result)
            
            status_icon = "✓" if success else "✗"
            print(f"{status_icon} {endpoint}: {latency:.2f}ms")
        
        return results
    
    async def api_concurrency_test(self, endpoint: str, num_requests: int = 100, 
                                  concurrent_limit: int = 10):
        """API并发测试"""
        print(f"\n正在测试 {endpoint} - {num_requests}请求，{concurrent_limit}并发")
        
        start_time = time.time()
        semaphore = asyncio.Semaphore(concurrent_limit)
        latencies = []
        errors = 0
        
        async def make_request(request_id: int):
            async with semaphore:
                request_start = time.time()
                try:
                    async with self.session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status != 200:
                            raise Exception(f"HTTP {response.status}")
                except Exception as e:
                    nonlocal errors
                    errors += 1
                    return None
                finally:
                    request_end = time.time()
                    latencies.append(request_end - request_start)
        
        # 创建任务
        tasks = [make_request(i) for i in range(num_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        if latencies:
            avg_latency = statistics.mean(latencies) * 1000
            p95_latency = statistics.quantiles(latencies, n=20)[18] * 1000 if len(latencies) >= 20 else 0
        else:
            avg_latency = p95_latency = 0
        
        result = {
            "endpoint": endpoint,
            "total_requests": num_requests,
            "success_requests": num_requests - errors,
            "error_requests": errors,
            "success_rate": (num_requests - errors) / num_requests * 100 if num_requests > 0 else 0,
            "total_time": total_time,
            "requests_per_second": num_requests / total_time if total_time > 0 else 0,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "concurrent_limit": concurrent_limit
        }
        
        self.test_results.append(result)
        return result
    
    async def control_api_test(self):
        """控制类API测试"""
        print(f"\n{'='*60}")
        print("控制类API测试")
        print(f"{'='*60}")
        
        # 车辆控制测试
        vehicle_controls = [
            {"vehicle_id": "TRAIN-001", "command": "start"},
            {"vehicle_id": "TRAIN-001", "command": "stop"},
            {"vehicle_id": "TRAIN-001", "command": "set_speed", "speed": 60},
            {"vehicle_id": "TRAIN-001", "command": "set_speed", "speed": 80},
        ]
        
        results = []
        for control in vehicle_controls:
            start_time = time.time()
            try:
                async with self.session.post(
                    f"{self.base_url}/api/v1/vehicle/control",
                    json=control
                ) as response:
                    status = response.status
                    success = status == 200
                    if success:
                        data = await response.json()
            except Exception:
                success = False
                
            end_time = time.time()
            latency = (end_time - start_time) * 1000
            
            results.append({
                "control": control["command"],
                "success": success,
                "latency_ms": latency
            })
            
            status_icon = "✓" if success else "✗"
            print(f"{status_icon} 车辆控制 '{control['command']}': {latency:.2f}ms")
        
        return results
    
    async def mixed_load_test(self, duration_seconds: int = 30):
        """混合负载测试 - 模拟真实使用场景"""
        print(f"\n{'='*60}")
        print(f"混合负载测试 ({duration_seconds}秒)")
        print(f"{'='*60}")
        
        endpoints = [
            ("/api/v1/vehicle/status", "GET"),
            ("/api/v1/signal/status", "GET"),
            ("/api/v1/power/status", "GET"),
            ("/api/v1/track/status", "GET"),
        ]
        
        request_counts = {endpoint[0]: 0 for endpoint in endpoints}
        error_counts = {endpoint[0]: 0 for endpoint in endpoints}
        latencies = []
        
        start_time = time.time()
        
        async def make_random_request():
            endpoint, method = random.choice(endpoints)
            request_start = time.time()
            
            try:
                if method == "GET":
                    async with self.session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status == 200:
                            request_counts[endpoint] += 1
                        else:
                            error_counts[endpoint] += 1
            except Exception:
                error_counts[endpoint] += 1
            
            request_end = time.time()
            latencies.append(request_end - request_start)
        
        # 持续创建请求
        tasks = []
        while time.time() - start_time < duration_seconds:
            task = asyncio.create_task(make_random_request())
            tasks.append(task)
            
            # 控制请求速率
            await asyncio.sleep(random.uniform(0.01, 0.05))
        
        # 等待剩余任务完成
        await asyncio.sleep(1)
        
        end_time = time.time()
        total_time = end_time - start_time
        total_requests = sum(request_counts.values())
        total_errors = sum(error_counts.values())
        
        if latencies:
            avg_latency = statistics.mean(latencies) * 1000
            p95_latency = statistics.quantiles(latencies, n=20)[18] * 1000 if len(latencies) >= 20 else 0
        else:
            avg_latency = p95_latency = 0
        
        result = {
            "test_type": "mixed_load",
            "duration_seconds": duration_seconds,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "success_rate": (total_requests - total_errors) / total_requests * 100 if total_requests > 0 else 0,
            "requests_per_second": total_requests / total_time if total_time > 0 else 0,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "request_distribution": request_counts,
            "error_distribution": error_counts
        }
        
        self.test_results.append(result)
        return result
    
    async def scalability_test(self, max_concurrent: int = 50, 
                             step_size: int = 10):
        """可扩展性测试 - 逐步增加并发"""
        print(f"\n{'='*60}")
        print(f"可扩展性测试 (最大{max_concurrent}并发)")
        print(f"{'='*60}")
        
        endpoint = "/api/v1/vehicle/status"
        scalability_results = []
        
        for concurrent in range(step_size, max_concurrent + 1, step_size):
            print(f"测试 {concurrent} 并发...")
            
            start_time = time.time()
            success_count = 0
            error_count = 0
            
            async def single_request():
                nonlocal success_count, error_count
                try:
                    async with self.session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status == 200:
                            success_count += 1
                        else:
                            error_count += 1
                except Exception:
                    error_count += 1
            
            # 创建并发请求
            tasks = [single_request() for _ in range(concurrent)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            result = {
                "concurrent_users": concurrent,
                "success_count": success_count,
                "error_count": error_count,
                "success_rate": success_count / concurrent * 100 if concurrent > 0 else 0,
                "total_time": total_time,
                "requests_per_second": concurrent / total_time if total_time > 0 else 0
            }
            
            scalability_results.append(result)
            print(f"  -> 成功率: {result['success_rate']:.1f}%, "
                  f"吞吐量: {result['requests_per_second']:.2f} 请求/秒")
            
            # 短暂暂停
            await asyncio.sleep(1)
        
        overall_result = {
            "test_type": "scalability",
            "endpoint": endpoint,
            "max_concurrent": max_concurrent,
            "results": scalability_results
        }
        
        self.test_results.append(overall_result)
        return overall_result
    
    def generate_report(self):
        """生成测试报告"""
        print(f"\n{'='*80}")
        print("无硬件压测报告汇总")
        print(f"{'='*80}")
        
        total_requests = sum(r.get('total_requests', 0) for r in self.test_results 
                           if isinstance(r, dict) and 'total_requests' in r)
        total_errors = sum(r.get('error_requests', 0) for r in self.test_results 
                         if isinstance(r, dict) and 'error_requests' in r)
        
        for i, result in enumerate(self.test_results, 1):
            if isinstance(result, dict):
                if 'test_type' in result:
                    print(f"\n{i}. {result['test_type'].upper()} 测试:")
                    
                    if result['test_type'] == 'mixed_load':
                        print(f"   时长: {result['duration_seconds']}秒")
                        print(f"   总请求数: {result['total_requests']}")
                        print(f"   成功率: {result['success_rate']:.2f}%")
                        print(f"   吞吐量: {result['requests_per_second']:.2f} 请求/秒")
                        print(f"   平均延迟: {result['avg_latency_ms']:.2f}ms")
                        
                    elif result['test_type'] == 'scalability':
                        print(f"   端点: {result['endpoint']}")
                        print(f"   最大并发: {result['max_concurrent']}")
                        for r in result['results']:
                            print(f"     {r['concurrent_users']}并发: "
                                  f"成功率{r['success_rate']:.1f}%, "
                                  f"吞吐量{r['requests_per_second']:.2f}请求/秒")
                
                elif 'endpoint' in result and 'success_rate' in result:
                    print(f"\n{i}. API并发测试 ({result['endpoint']}):")
                    print(f"   总请求数: {result['total_requests']}")
                    print(f"   成功率: {result['success_rate']:.2f}%")
                    print(f"   吞吐量: {result['requests_per_second']:.2f} 请求/秒")
                    print(f"   平均延迟: {result['avg_latency_ms']:.2f}ms")
                    print(f"   P95延迟: {result['p95_latency_ms']:.2f}ms")
        
        if total_requests > 0:
            print(f"\n{'='*80}")
            print("总体性能指标:")
            print(f"总测试请求数: {total_requests}")
            print(f"总体成功率: {(total_requests - total_errors)/total_requests*100:.2f}%")
            print(f"{'='*80}")
        
        # 保存报告
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = f"no_hardware_load_test_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n详细报告已保存到: {report_file}")


async def main():
    """主函数"""
    print("轨道模拟系统无硬件压测")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标服务: http://localhost:8000")
    print("注意: 此测试使用模拟数据模式，无需硬件连接")
    
    async with NoHardwareLoadTest() as tester:
        # 检查服务
        if not await tester.check_service():
            print("\n请先启动后端服务:")
            print("1. 使用模拟配置: cp .env.mock .env")
            print("2. 启动服务: uvicorn main:app --reload")
            return
        
        # 基础功能测试
        await tester.basic_api_test()
        
        # API并发测试
        await tester.api_concurrency_test("/api/v1/vehicle/status", num_requests=200, concurrent_limit=20)
        await tester.api_concurrency_test("/api/v1/signal/status", num_requests=150, concurrent_limit=15)
        
        # 控制API测试
        await tester.control_api_test()
        
        # 混合负载测试
        await tester.mixed_load_test(duration_seconds=20)
        
        # 可扩展性测试（较小规模）
        await tester.scalability_test(max_concurrent=40, step_size=10)
        
        # 生成报告
        tester.generate_report()
        
        print(f"\n压测完成! 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())