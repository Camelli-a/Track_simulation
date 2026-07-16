"""
高级压测脚本
支持多种压测场景：API并发、WebSocket连接、压力测试
"""

import asyncio
import aiohttp
import time
import json
import statistics
from typing import List, Dict, Any
import random
import websockets
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
import numpy as np


class AdvancedLoadTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.http_session = None
        self.ws_connections = []
        self.test_results = []
        
    async def __aenter__(self):
        self.http_session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.http_session:
            await self.http_session.close()
        # 关闭所有WebSocket连接
        for ws in self.ws_connections:
            if not ws.closed:
                await ws.close()
    
    async def api_stress_test(self, endpoint: str, method: str = "GET",
                             payload: Dict = None, concurrent_users: int = 10,
                             requests_per_user: int = 10) -> Dict:
        """API压力测试 - 模拟并发用户"""
        print(f"\n正在执行API压力测试: {endpoint}")
        print(f"并发用户数: {concurrent_users}, 每用户请求数: {requests_per_user}")
        
        start_time = time.time()
        all_latencies = []
        all_errors = []
        
        async def user_request(user_id: int):
            user_errors = 0
            user_latencies = []
            
            for req_num in range(requests_per_user):
                req_start = time.time()
                
                try:
                    if method == "GET":
                        async with self.http_session.get(f"{self.base_url}{endpoint}") as response:
                            if response.status != 200:
                                user_errors += 1
                    elif method == "POST" and payload:
                        modified_payload = payload.copy()
                        modified_payload["user_id"] = user_id
                        modified_payload["req_num"] = req_num
                        async with self.http_session.post(
                            f"{self.base_url}{endpoint}", 
                            json=modified_payload
                        ) as response:
                            if response.status != 200:
                                user_errors += 1
                except Exception as e:
                    user_errors += 1
                
                req_end = time.time()
                user_latencies.append(req_end - req_start)
                
            return user_latencies, user_errors
        
        # 创建并发用户任务
        tasks = [user_request(i) for i in range(concurrent_users)]
        results = await asyncio.gather(*tasks)
        
        # 收集结果
        for user_latencies, user_errors in results:
            all_latencies.extend(user_latencies)
            all_errors.append(user_errors)
        
        end_time = time.time()
        total_time = end_time - start_time
        total_requests = concurrent_users * requests_per_user
        total_errors = sum(all_errors)
        
        if all_latencies:
            avg_latency = statistics.mean(all_latencies) * 1000  # 转换为毫秒
            p95_latency = np.percentile(all_latencies, 95) * 1000
            p99_latency = np.percentile(all_latencies, 99) * 1000
        else:
            avg_latency = p95_latency = p99_latency = 0
        
        result = {
            "test_type": "api_stress",
            "endpoint": endpoint,
            "method": method,
            "concurrent_users": concurrent_users,
            "requests_per_user": requests_per_user,
            "total_requests": total_requests,
            "total_time": total_time,
            "total_errors": total_errors,
            "success_rate": (total_requests - total_errors) / total_requests * 100 if total_requests > 0 else 0,
            "requests_per_second": total_requests / total_time if total_time > 0 else 0,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "latency_distribution": all_latencies
        }
        
        self.test_results.append(result)
        return result
    
    async def websocket_connection_test(self, num_connections: int = 10, 
                                       duration_seconds: int = 30) -> Dict:
        """WebSocket连接压测"""
        print(f"\n正在执行WebSocket连接压测")
        print(f"连接数: {num_connections}, 持续时间: {duration_seconds}秒")
        
        ws_endpoint = "ws://localhost:8000/dashboard/ws"
        connected_count = 0
        message_counts = []
        start_time = time.time()
        
        async def ws_client(client_id: int):
            nonlocal connected_count
            messages_received = 0
            
            try:
                async with websockets.connect(ws_endpoint) as websocket:
                    connected_count += 1
                    print(f"客户端 {client_id}: 连接成功")
                    
                    # 接收消息
                    while time.time() - start_time < duration_seconds:
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(), 
                                timeout=1.0
                            )
                            messages_received += 1
                            if messages_received % 10 == 0:
                                print(f"客户端 {client_id}: 收到 {messages_received} 条消息")
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            print(f"客户端 {client_id}: 接收错误 - {e}")
                            break
                    
                    return messages_received
                    
            except Exception as e:
                print(f"客户端 {client_id}: 连接失败 - {e}")
                return 0
        
        # 创建WebSocket客户端
        tasks = [ws_client(i) for i in range(num_connections)]
        message_counts = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        total_messages = sum(message_counts)
        avg_messages_per_connection = total_messages / num_connections if num_connections > 0 else 0
        
        result = {
            "test_type": "websocket",
            "endpoint": ws_endpoint,
            "num_connections": num_connections,
            "connected_count": connected_count,
            "connection_success_rate": connected_count / num_connections * 100 if num_connections > 0 else 0,
            "duration_seconds": duration_seconds,
            "total_messages": total_messages,
            "avg_messages_per_connection": avg_messages_per_connection,
            "messages_per_second": total_messages / total_time if total_time > 0 else 0,
            "message_counts": message_counts
        }
        
        self.test_results.append(result)
        return result
    
    async def mixed_workload_test(self, duration_seconds: int = 60) -> Dict:
        """混合工作负载测试 - 模拟真实场景"""
        print(f"\n正在执行混合工作负载测试")
        print(f"持续时间: {duration_seconds}秒")
        
        api_endpoints = [
            ("/api/v1/vehicle/status", "GET", None),
            ("/api/v1/signal/status", "GET", None),
            ("/api/v1/power/status", "GET", None),
            ("/api/v1/track/status", "GET", None),
        ]
        
        control_payloads = [
            {"vehicle_id": "TRAIN-001", "command": "set_speed", "speed": random.randint(30, 80)},
            {"vehicle_id": "TRAIN-001", "command": "stop"},
            {"vehicle_id": "TRAIN-001", "command": "start"},
        ]
        
        start_time = time.time()
        request_counts = {endpoint[0]: 0 for endpoint in api_endpoints}
        request_counts["/api/v1/vehicle/control"] = 0
        error_counts = {endpoint[0]: 0 for endpoint in api_endpoints}
        error_counts["/api/v1/vehicle/control"] = 0
        latencies = []
        
        async def make_request():
            # 随机选择API端点
            endpoint, method, payload = random.choice(api_endpoints)
            
            # 10%的概率发送控制命令
            if random.random() < 0.1:
                endpoint = "/api/v1/vehicle/control"
                method = "POST"
                payload = random.choice(control_payloads)
            
            req_start = time.time()
            
            try:
                if method == "GET":
                    async with self.http_session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status != 200:
                            error_counts[endpoint] += 1
                        else:
                            request_counts[endpoint] += 1
                elif method == "POST" and payload:
                    async with self.http_session.post(
                        f"{self.base_url}{endpoint}", 
                        json=payload
                    ) as response:
                        if response.status != 200:
                            error_counts[endpoint] += 1
                        else:
                            request_counts[endpoint] += 1
            except Exception:
                error_counts[endpoint] += 1
            
            req_end = time.time()
            latencies.append(req_end - req_start)
        
        # 创建持续请求任务
        tasks = []
        while time.time() - start_time < duration_seconds:
            task = asyncio.create_task(make_request())
            tasks.append(task)
            await asyncio.sleep(random.uniform(0.01, 0.1))  # 随机间隔
        
        # 等待所有任务完成
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        total_requests = sum(request_counts.values())
        total_errors = sum(error_counts.values())
        
        if latencies:
            avg_latency = statistics.mean(latencies) * 1000
            p95_latency = np.percentile(latencies, 95) * 1000
        else:
            avg_latency = p95_latency = 0
        
        result = {
            "test_type": "mixed_workload",
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
                             step_size: int = 5) -> Dict:
        """可扩展性测试 - 逐步增加并发用户"""
        print(f"\n正在执行可扩展性测试")
        print(f"最大并发数: {max_concurrent}, 步长: {step_size}")
        
        scalability_results = []
        endpoint = "/api/v1/vehicle/status"
        
        for concurrent in range(step_size, max_concurrent + 1, step_size):
            print(f"测试 {concurrent} 并发用户...")
            
            start_time = time.time()
            success_count = 0
            error_count = 0
            latencies = []
            
            async def single_request():
                nonlocal success_count, error_count
                req_start = time.time()
                
                try:
                    async with self.http_session.get(f"{self.base_url}{endpoint}") as response:
                        if response.status == 200:
                            success_count += 1
                        else:
                            error_count += 1
                except Exception:
                    error_count += 1
                
                req_end = time.time()
                latencies.append(req_end - req_start)
            
            # 创建并发请求
            tasks = [single_request() for _ in range(concurrent)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            if latencies:
                avg_latency = statistics.mean(latencies) * 1000
            else:
                avg_latency = 0
            
            result = {
                "concurrent_users": concurrent,
                "total_requests": concurrent,
                "success_count": success_count,
                "error_count": error_count,
                "success_rate": success_count / concurrent * 100 if concurrent > 0 else 0,
                "total_time": total_time,
                "requests_per_second": concurrent / total_time if total_time > 0 else 0,
                "avg_latency_ms": avg_latency
            }
            
            scalability_results.append(result)
            print(f"  -> 成功率: {result['success_rate']:.1f}%, "
                  f"吞吐量: {result['requests_per_second']:.2f} 请求/秒, "
                  f"平均延迟: {result['avg_latency_ms']:.2f}ms")
            
            # 短暂暂停
            await asyncio.sleep(2)
        
        overall_result = {
            "test_type": "scalability",
            "endpoint": endpoint,
            "max_concurrent": max_concurrent,
            "step_size": step_size,
            "results": scalability_results
        }
        
        self.test_results.append(overall_result)
        return overall_result
    
    def generate_report(self):
        """生成压测报告"""
        print(f"\n{'='*80}")
        print("压测报告汇总")
        print(f"{'='*80}")
        
        for i, result in enumerate(self.test_results, 1):
            print(f"\n{i}. {result['test_type'].upper()} 测试:")
            
            if result['test_type'] == 'api_stress':
                print(f"   端点: {result['endpoint']}")
                print(f"   并���用户: {result['concurrent_users']}")
                print(f"   总请求数: {result['total_requests']}")
                print(f"   成功率: {result['success_rate']:.2f}%")
                print(f"   吞吐量: {result['requests_per_second']:.2f} 请求/秒")
                print(f"   平均延迟: {result['avg_latency_ms']:.2f}ms")
                print(f"   P95延迟: {result['p95_latency_ms']:.2f}ms")
                print(f"   P99延迟: {result['p99_latency_ms']:.2f}ms")
                
            elif result['test_type'] == 'websocket':
                print(f"   连接数: {result['num_connections']}")
                print(f"   成功连接: {result['connected_count']}")
                print(f"   连接成功率: {result['connection_success_rate']:.2f}%")
                print(f"   总消息数: {result['total_messages']}")
                print(f"   消息速率: {result['messages_per_second']:.2f} 条/秒")
                
            elif result['test_type'] == 'mixed_workload':
                print(f"   测试时长: {result['duration_seconds']}秒")
                print(f"   总请求数: {result['total_requests']}")
                print(f"   成功率: {result['success_rate']:.2f}%")
                print(f"   吞吐量: {result['requests_per_second']:.2f} 请求/秒")
                print(f"   平均延迟: {result['avg_latency_ms']:.2f}ms")
                print(f"   P95延迟: {result['p95_latency_ms']:.2f}ms")
                
            elif result['test_type'] == 'scalability':
                print(f"   最大并发: {result['max_concurrent']}")
                print(f"   测试结果:")
                for r in result['results']:
                    print(f"     {r['concurrent_users']}并发: "
                          f"成功率{r['success_rate']:.1f}%, "
                          f"吞吐量{r['requests_per_second']:.2f}请求/秒, "
                          f"延迟{r['avg_latency_ms']:.2f}ms")
        
        # 计算总体指标
        total_requests = sum(r.get('total_requests', 0) for r in self.test_results)
        total_errors = sum(r.get('total_errors', 0) for r in self.test_results)
        
        if total_requests > 0:
            print(f"\n{'='*80}")
            print("总体性能指标:")
            print(f"总测试请求数: {total_requests}")
            print(f"总体成功率: {(total_requests - total_errors)/total_requests*100:.2f}%")
            print(f"{'='*80}")
        
        # 保存报告到文件
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = f"load_test_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n详细报告已保存到: {report_file}")


async def main():
    """主函数"""
    print("轨道模拟系统高级压测")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标服务: http://localhost:8000")
    
    try:
        async with AdvancedLoadTest() as tester:
            # 检查服务可用性
            try:
                async with aiohttp.ClientSession() as session:
                    response = await session.get("http://localhost:8000/")
                    if response.status == 200:
                        data = await response.json()
                        print(f"✓ 服务正常 - 状态: {data.get('status', 'unknown')}")
                        print(f"  数据源: {data.get('data_source', 'unknown')}")
                    else:
                        print(f"⚠ 服务返回状态码: {response.status}")
            except Exception as e:
                print(f"✗ 无法连接到服务: {e}")
                print("请确保后端服务已启动: uvicorn main:app --reload")
                return
            
            # 运行各种压测
            print("\n" + "="*80)
            
            # 1. API压力测试
            api_result = await tester.api_stress_test(
                endpoint="/api/v1/vehicle/status",
                concurrent_users=20,
                requests_per_user=10
            )
            
            # 2. WebSocket连接测试（较小规模）
            ws_result = await tester.websocket_connection_test(
                num_connections=5,
                duration_seconds=10
            )
            
            # 3. 混合工作负载测试
            mixed_result = await tester.mixed_workload_test(
                duration_seconds=30
            )
            
            # 4. 可扩展性测试（较小规模）
            scale_result = await tester.scalability_test(
                max_concurrent=30,
                step_size=5
            )
            
            # 生成报告
            tester.generate_report()
            
            print(f"\n压测完成! 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
    except Exception as e:
        print(f"压测过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())