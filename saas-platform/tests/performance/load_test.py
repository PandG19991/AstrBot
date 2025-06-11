"""
性能负载测试

使用Locust进行AstrBot SaaS平台的性能压力测试
测试场景包括：
1. 用户注册登录
2. 会话创建和消息发送  
3. AI功能调用
4. API响应时间测试
5. 并发用户场景
"""
import json
import random
import time
from uuid import uuid4
from typing import Dict, Any
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AstrBotSaaSUser(FastHttpUser):
    """AstrBot SaaS平台负载测试用户"""
    
    # 用户行为间隔时间（秒）
    wait_time = between(1, 5)
    
    def on_start(self):
        """用户启动时的初始化操作"""
        self.tenant_id = None
        self.user_id = None
        self.auth_token = None
        self.session_id = None
        self.agent_id = None
        
        # 创建测试租户和用户
        self.setup_test_data()
    
    def setup_test_data(self):
        """设置测试数据"""
        try:
            # 1. 创建测试租户
            tenant_data = {
                "name": f"LoadTest-Tenant-{uuid4().hex[:8]}",
                "contact_email": f"test+{uuid4().hex[:8]}@loadtest.com",
                "description": "Load test tenant",
                "plan_type": "professional"
            }
            
            response = self.client.post(
                "/api/v1/tenants",
                json=tenant_data,
                name="create_tenant"
            )
            
            if response.status_code == 200:
                tenant_info = response.json()["data"]
                self.tenant_id = tenant_info["id"]
                logger.info(f"Created test tenant: {self.tenant_id}")
            else:
                logger.error(f"Failed to create tenant: {response.status_code}")
                return
            
            # 2. 创建测试用户（客服）
            user_data = {
                "username": f"agent_{uuid4().hex[:8]}",
                "email": f"agent+{uuid4().hex[:8]}@loadtest.com",
                "full_name": "Load Test Agent",
                "user_type": "agent",
                "password": "loadtest123"
            }
            
            response = self.client.post(
                "/api/v1/users",
                json=user_data,
                headers={"X-Tenant-ID": self.tenant_id},
                name="create_user"
            )
            
            if response.status_code == 200:
                user_info = response.json()["data"]
                self.agent_id = user_info["id"]
                
                # 3. 用户登录获取Token
                login_data = {
                    "username": user_data["username"],
                    "password": user_data["password"]
                }
                
                login_response = self.client.post(
                    "/api/v1/auth/login",
                    json=login_data,
                    headers={"X-Tenant-ID": self.tenant_id},
                    name="user_login"
                )
                
                if login_response.status_code == 200:
                    auth_info = login_response.json()["data"]
                    self.auth_token = auth_info["access_token"]
                    logger.info(f"User logged in successfully: {self.agent_id}")
                else:
                    logger.error(f"Failed to login: {login_response.status_code}")
            
            # 4. 创建测试最终用户
            customer_data = {
                "username": f"customer_{uuid4().hex[:8]}",
                "email": f"customer+{uuid4().hex[:8]}@loadtest.com", 
                "full_name": "Load Test Customer",
                "user_type": "customer"
            }
            
            response = self.client.post(
                "/api/v1/users",
                json=customer_data,
                headers={"X-Tenant-ID": self.tenant_id},
                name="create_customer"
            )
            
            if response.status_code == 200:
                customer_info = response.json()["data"]
                self.user_id = customer_info["id"]
                logger.info(f"Created test customer: {self.user_id}")
                
        except Exception as e:
            logger.error(f"Setup test data failed: {str(e)}")
    
    def get_auth_headers(self) -> Dict[str, str]:
        """获取认证头"""
        headers = {"X-Tenant-ID": self.tenant_id}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    @task(10)
    def create_session_and_messages(self):
        """创建会话并发送消息 - 最高频任务"""
        if not self.tenant_id or not self.user_id:
            return
        
        try:
            # 1. 创建会话
            session_data = {
                "user_id": self.user_id,
                "platform_type": random.choice(["webchat", "wechat", "qq"]),
                "session_metadata": {
                    "source": "load_test",
                    "test_id": uuid4().hex[:8]
                }
            }
            
            response = self.client.post(
                "/api/v1/sessions",
                json=session_data,
                headers=self.get_auth_headers(),
                name="create_session"
            )
            
            if response.status_code == 200:
                session_info = response.json()["data"]
                session_id = session_info["id"]
                
                # 2. 发送用户消息
                user_messages = [
                    "你好，我需要帮助",
                    "请问你们的产品怎么样？", 
                    "价格如何？",
                    "有什么优惠活动吗？",
                    "如何购买？"
                ]
                
                message_data = {
                    "session_id": session_id,
                    "sender_id": self.user_id,
                    "sender_type": "user",
                    "content": random.choice(user_messages),
                    "message_type": "text"
                }
                
                self.client.post(
                    "/api/v1/messages",
                    json=message_data,
                    headers=self.get_auth_headers(),
                    name="send_user_message"
                )
                
                # 3. 客服回复消息
                agent_replies = [
                    "您好！很高兴为您服务",
                    "我们的产品具有以下特点...",
                    "关于价格，我来为您详细介绍",
                    "目前有新用户优惠活动",
                    "购买流程很简单，我来引导您"
                ]
                
                agent_message_data = {
                    "session_id": session_id,
                    "sender_id": self.agent_id,
                    "sender_type": "agent", 
                    "content": random.choice(agent_replies),
                    "message_type": "text"
                }
                
                self.client.post(
                    "/api/v1/messages",
                    json=agent_message_data,
                    headers=self.get_auth_headers(),
                    name="send_agent_message"
                )
                
        except Exception as e:
            logger.error(f"Create session and messages failed: {str(e)}")
    
    @task(5)
    def ai_auto_reply(self):
        """AI自动回复测试"""
        if not self.tenant_id:
            return
        
        try:
            # 创建临时会话用于AI回复测试
            session_data = {
                "user_id": self.user_id,
                "platform_type": "webchat"
            }
            
            session_response = self.client.post(
                "/api/v1/sessions",
                json=session_data,
                headers=self.get_auth_headers(),
                name="create_session_for_ai"
            )
            
            if session_response.status_code == 200:
                session_id = session_response.json()["data"]["id"]
                
                # AI自动回复请求
                ai_questions = [
                    "什么是人工智能？",
                    "如何使用你们的产品？",
                    "有哪些付费计划？",
                    "技术支持联系方式？",
                    "系统安全性如何？"
                ]
                
                ai_request = {
                    "session_id": session_id,
                    "message_content": random.choice(ai_questions),
                    "enable_streaming": False
                }
                
                self.client.post(
                    "/api/v1/ai/auto-reply",
                    json=ai_request,
                    headers=self.get_auth_headers(),
                    name="ai_auto_reply"
                )
                
        except Exception as e:
            logger.error(f"AI auto reply failed: {str(e)}")
    
    @task(3)
    def get_session_history(self):
        """获取会话历史"""
        if not self.tenant_id:
            return
        
        try:
            # 获取会话列表
            response = self.client.get(
                "/api/v1/sessions",
                params={"page": 1, "size": 10, "status": "active"},
                headers=self.get_auth_headers(),
                name="get_sessions"
            )
            
            if response.status_code == 200:
                sessions = response.json()["data"]["items"]
                
                if sessions:
                    # 随机选择一个会话获取消息历史
                    session_id = random.choice(sessions)["id"]
                    
                    self.client.get(
                        f"/api/v1/messages/sessions/{session_id}",
                        params={"page": 1, "size": 20},
                        headers=self.get_auth_headers(),
                        name="get_message_history"
                    )
                    
        except Exception as e:
            logger.error(f"Get session history failed: {str(e)}")
    
    @task(2)
    def agent_suggestions(self):
        """获取客服建议"""
        if not self.tenant_id:
            return
        
        try:
            # 创建会话用于建议测试
            session_data = {
                "user_id": self.user_id,
                "platform_type": "webchat"
            }
            
            session_response = self.client.post(
                "/api/v1/sessions", 
                json=session_data,
                headers=self.get_auth_headers(),
                name="create_session_for_suggestions"
            )
            
            if session_response.status_code == 200:
                session_id = session_response.json()["data"]["id"]
                
                # 请求客服建议
                suggestion_request = {
                    "session_id": session_id,
                    "message_content": "用户询问退款政策",
                    "suggestion_type": "response"
                }
                
                self.client.post(
                    "/api/v1/ai/agent-suggestions",
                    json=suggestion_request,
                    headers=self.get_auth_headers(),
                    name="get_agent_suggestions"
                )
                
        except Exception as e:
            logger.error(f"Agent suggestions failed: {str(e)}")
    
    @task(2)
    def session_summary(self):
        """会话总结测试"""
        if not self.tenant_id:
            return
        
        try:
            # 获取已关闭的会话
            response = self.client.get(
                "/api/v1/sessions",
                params={"page": 1, "size": 5, "status": "closed"},
                headers=self.get_auth_headers(),
                name="get_closed_sessions"
            )
            
            if response.status_code == 200:
                sessions = response.json()["data"]["items"]
                
                if sessions:
                    # 随机选择一个已关闭会话生成总结
                    session_id = random.choice(sessions)["id"]
                    
                    summary_request = {
                        "session_id": session_id,
                        "summary_type": random.choice(["brief", "detailed", "analysis"])
                    }
                    
                    self.client.post(
                        "/api/v1/ai/session-summary",
                        json=summary_request,
                        headers=self.get_auth_headers(),
                        name="generate_session_summary"
                    )
                    
        except Exception as e:
            logger.error(f"Session summary failed: {str(e)}")
    
    @task(1)
    def analytics_stats(self):
        """数据分析统计测试"""
        if not self.tenant_id:
            return
        
        try:
            # 获取会话统计
            self.client.get(
                "/api/v1/sessions/stats/summary",
                params={
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                },
                headers=self.get_auth_headers(),
                name="get_session_stats"
            )
            
            # 获取消息统计
            self.client.get(
                "/api/v1/analytics/messages",
                params={
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31", 
                    "granularity": "day"
                },
                headers=self.get_auth_headers(),
                name="get_message_analytics"
            )
            
        except Exception as e:
            logger.error(f"Analytics stats failed: {str(e)}")
    
    @task(1)
    def health_checks(self):
        """健康检查测试"""
        try:
            # API健康检查
            self.client.get("/api/v1/health", name="api_health_check")
            
            # AI功能健康检查
            if self.tenant_id:
                self.client.get(
                    "/api/v1/ai/health",
                    headers=self.get_auth_headers(),
                    name="ai_health_check"
                )
                
        except Exception as e:
            logger.error(f"Health checks failed: {str(e)}")


class WebSocketUser(HttpUser):
    """WebSocket连接测试用户"""
    
    wait_time = between(2, 8)
    
    def on_start(self):
        """启动WebSocket连接"""
        self.tenant_id = f"tenant_{uuid4().hex[:8]}"
        self.agent_id = f"agent_{uuid4().hex[:8]}"
    
    @task
    def websocket_connection_test(self):
        """WebSocket连接测试"""
        try:
            # 模拟WebSocket连接请求
            ws_params = {
                "tenant_id": self.tenant_id,
                "agent_id": self.agent_id,
                "token": "test_token"
            }
            
            # 发送WebSocket握手请求
            response = self.client.get(
                "/api/v1/ws/agent",
                params=ws_params,
                headers={
                    "Upgrade": "websocket",
                    "Connection": "Upgrade"
                },
                name="websocket_handshake"
            )
            
        except Exception as e:
            logger.error(f"WebSocket connection test failed: {str(e)}")


# 压力测试事件监听器
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时的设置"""
    logger.info("=== AstrBot SaaS Load Test Started ===")
    logger.info(f"Target host: {environment.host}")
    logger.info(f"User classes: {[cls.__name__ for cls in environment.user_classes]}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的清理"""
    logger.info("=== AstrBot SaaS Load Test Completed ===")
    
    # 打印测试结果摘要
    if environment.stats.total.num_requests > 0:
        logger.info(f"Total requests: {environment.stats.total.num_requests}")
        logger.info(f"Total failures: {environment.stats.total.num_failures}")
        logger.info(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
        logger.info(f"50th percentile: {environment.stats.total.get_response_time_percentile(0.5):.2f}ms")
        logger.info(f"95th percentile: {environment.stats.total.get_response_time_percentile(0.95):.2f}ms")


# 自定义测试场景
class CustomerServiceScenario(AstrBotSaaSUser):
    """客服场景专项测试"""
    
    weight = 3
    
    @task
    def full_customer_service_flow(self):
        """完整客服流程"""
        if not self.tenant_id or not self.user_id:
            return
        
        try:
            # 1. 用户发起咨询
            session_data = {
                "user_id": self.user_id,
                "platform_type": "webchat",
                "session_metadata": {"scenario": "customer_service"}
            }
            
            session_response = self.client.post(
                "/api/v1/sessions",
                json=session_data,
                headers=self.get_auth_headers(),
                name="cs_create_session"
            )
            
            if session_response.status_code != 200:
                return
            
            session_id = session_response.json()["data"]["id"]
            
            # 2. 用户发送问题
            self.client.post(
                "/api/v1/messages",
                json={
                    "session_id": session_id,
                    "sender_id": self.user_id,
                    "sender_type": "user",
                    "content": "我的订单有问题，需要退款",
                    "message_type": "text"
                },
                headers=self.get_auth_headers(),
                name="cs_user_message"
            )
            
            # 3. AI自动回复
            self.client.post(
                "/api/v1/ai/auto-reply",
                json={
                    "session_id": session_id,
                    "message_content": "我的订单有问题，需要退款",
                    "enable_streaming": False
                },
                headers=self.get_auth_headers(),
                name="cs_ai_reply"
            )
            
            # 4. 客服接入
            self.client.put(
                f"/api/v1/sessions/{session_id}/status",
                json={
                    "status": "agent_active",
                    "agent_id": self.agent_id,
                    "status_reason": "用户问题需要人工处理"
                },
                headers=self.get_auth_headers(),
                name="cs_agent_takeover"
            )
            
            # 5. 客服回复
            self.client.post(
                "/api/v1/messages",
                json={
                    "session_id": session_id,
                    "sender_id": self.agent_id,
                    "sender_type": "agent",
                    "content": "您好，我来帮您处理退款问题。请提供订单号。",
                    "message_type": "text"
                },
                headers=self.get_auth_headers(),
                name="cs_agent_reply"
            )
            
            # 6. 会话结束
            self.client.put(
                f"/api/v1/sessions/{session_id}/status",
                json={
                    "status": "closed",
                    "agent_id": self.agent_id,
                    "status_reason": "问题已解决"
                },
                headers=self.get_auth_headers(),
                name="cs_close_session"
            )
            
            # 等待一段时间模拟真实场景
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logger.error(f"Customer service flow failed: {str(e)}")


class AIFeatureScenario(AstrBotSaaSUser):
    """AI功能专项测试"""
    
    weight = 2
    
    @task
    def ai_intensive_test(self):
        """AI功能密集测试"""
        if not self.tenant_id:
            return
        
        try:
            # 创建会话
            session_data = {
                "user_id": self.user_id,
                "platform_type": "webchat"
            }
            
            session_response = self.client.post(
                "/api/v1/sessions",
                json=session_data,
                headers=self.get_auth_headers(),
                name="ai_create_session"
            )
            
            if session_response.status_code != 200:
                return
            
            session_id = session_response.json()["data"]["id"]
            
            # 多次AI请求测试
            ai_requests = [
                "请介绍一下人工智能技术",
                "如何提高客服服务质量？",
                "什么是多租户SaaS架构？",
                "推荐一些客服话术模板"
            ]
            
            for i, question in enumerate(ai_requests):
                # AI自动回复
                self.client.post(
                    "/api/v1/ai/auto-reply",
                    json={
                        "session_id": session_id,
                        "message_content": question,
                        "enable_streaming": False
                    },
                    headers=self.get_auth_headers(),
                    name=f"ai_request_{i+1}"
                )
                
                # 获取客服建议
                self.client.post(
                    "/api/v1/ai/agent-suggestions",
                    json={
                        "session_id": session_id,
                        "message_content": question,
                        "suggestion_type": "response"
                    },
                    headers=self.get_auth_headers(),
                    name=f"ai_suggestion_{i+1}"
                )
                
                time.sleep(0.5)  # 避免过于密集的请求
            
        except Exception as e:
            logger.error(f"AI intensive test failed: {str(e)}")


if __name__ == "__main__":
    """
    运行负载测试
    
    使用方法：
    1. 安装依赖: pip install locust
    2. 启动测试: locust -f load_test.py --host=http://localhost:8000
    3. 访问Web UI: http://localhost:8089
    
    命令行运行示例：
    locust -f load_test.py --host=http://localhost:8000 -u 50 -r 5 -t 300s --html=report.html
    """
    print("Load test script for AstrBot SaaS Platform")
    print("Run with: locust -f load_test.py --host=http://localhost:8000") 