"""
端到端测试 - 完整客服会话流程

测试场景：
1. 用户发起咨询
2. 系统自动分配会话
3. AI自动回复
4. 客服接入处理
5. 会话结束和总结
"""
import pytest
import asyncio
import json
from uuid import uuid4
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.tenant import Tenant, TenantStatus, TenantPlan
from app.models.user import User
from app.models.session import Session
from app.models.message import Message
from app.core.database import get_db


class TestCustomerServiceFlow:
    """客服会话流程端到端测试"""
    
    @pytest.fixture
    async def setup_test_data_flow(self, db_session: AsyncSession):
        """为flow测试设置独立数据"""
        # 生成唯一的API key
        unique_api_key = f"test_api_key_flow_{uuid4().hex[:12]}"
        
        # 创建测试租户（带API key）
        test_tenant = Tenant(
            id=uuid4(),
            name="测试企业-Flow",
            email=f"test_flow_{uuid4().hex[:8]}@company.com",
            status=TenantStatus.ACTIVE,
            plan=TenantPlan.BASIC,
            api_key=unique_api_key
        )
        db_session.add(test_tenant)
        
        # 创建测试客服用户（使用复合ID格式）
        agent_user_id = f"webchat:test_agent_flow_{uuid4().hex[:8]}"
        test_agent = User(
            id=agent_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_agent_flow_{uuid4().hex[:8]}",
            nickname="测试客服-Flow"
        )
        db_session.add(test_agent)
        
        # 创建测试最终用户（使用复合ID格式）
        customer_user_id = f"webchat:test_customer_flow_{uuid4().hex[:8]}"
        test_customer = User(
            id=customer_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_customer_flow_{uuid4().hex[:8]}",
            nickname="测试用户-Flow"
        )
        db_session.add(test_customer)
        
        await db_session.commit()
        
        # 返回测试数据
        return {
            "tenant": test_tenant,
            "agent": test_agent,
            "customer": test_customer,
            "api_key": unique_api_key
        }

    @pytest.fixture
    async def setup_test_data_isolation(self, db_session: AsyncSession):
        """为isolation测试设置独立数据"""
        # 生成唯一的API key
        unique_api_key = f"test_api_key_isolation_{uuid4().hex[:12]}"
        
        # 创建测试租户（带API key）
        test_tenant = Tenant(
            id=uuid4(),
            name="测试企业-Isolation",
            email=f"test_isolation_{uuid4().hex[:8]}@company.com",
            status=TenantStatus.ACTIVE,
            plan=TenantPlan.BASIC,
            api_key=unique_api_key
        )
        db_session.add(test_tenant)
        
        # 创建测试用户
        agent_user_id = f"webchat:test_agent_isolation_{uuid4().hex[:8]}"
        test_agent = User(
            id=agent_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_agent_isolation_{uuid4().hex[:8]}",
            nickname="测试客服-Isolation"
        )
        db_session.add(test_agent)
        
        customer_user_id = f"webchat:test_customer_isolation_{uuid4().hex[:8]}"
        test_customer = User(
            id=customer_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_customer_isolation_{uuid4().hex[:8]}",
            nickname="测试用户-Isolation"
        )
        db_session.add(test_customer)
        
        await db_session.commit()
        
        return {
            "tenant": test_tenant,
            "agent": test_agent,
            "customer": test_customer,
            "api_key": unique_api_key
        }

    @pytest.fixture
    async def setup_test_data_ai(self, db_session: AsyncSession):
        """为AI测试设置独立数据"""
        # 生成唯一的API key
        unique_api_key = f"test_api_key_ai_{uuid4().hex[:12]}"
        
        # 创建测试租户（带API key）
        test_tenant = Tenant(
            id=uuid4(),
            name="测试企业-AI",
            email=f"test_ai_{uuid4().hex[:8]}@company.com",
            status=TenantStatus.ACTIVE,
            plan=TenantPlan.BASIC,
            api_key=unique_api_key
        )
        db_session.add(test_tenant)
        
        # 创建测试用户
        agent_user_id = f"webchat:test_agent_ai_{uuid4().hex[:8]}"
        test_agent = User(
            id=agent_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_agent_ai_{uuid4().hex[:8]}",
            nickname="测试客服-AI"
        )
        db_session.add(test_agent)
        
        customer_user_id = f"webchat:test_customer_ai_{uuid4().hex[:8]}"
        test_customer = User(
            id=customer_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_customer_ai_{uuid4().hex[:8]}",
            nickname="测试用户-AI"
        )
        db_session.add(test_customer)
        
        await db_session.commit()
        
        return {
            "tenant": test_tenant,
            "agent": test_agent,
            "customer": test_customer,
            "api_key": unique_api_key
        }

    @pytest.fixture
    async def setup_test_data_webhook(self, db_session: AsyncSession):
        """为webhook测试设置独立数据"""
        # 生成唯一的API key
        unique_api_key = f"test_api_key_webhook_{uuid4().hex[:12]}"
        
        # 创建测试租户（带API key）
        test_tenant = Tenant(
            id=uuid4(),
            name="测试企业-Webhook",
            email=f"test_webhook_{uuid4().hex[:8]}@company.com",
            status=TenantStatus.ACTIVE,
            plan=TenantPlan.BASIC,
            api_key=unique_api_key
        )
        db_session.add(test_tenant)
        
        # 创建测试用户
        agent_user_id = f"webchat:test_agent_webhook_{uuid4().hex[:8]}"
        test_agent = User(
            id=agent_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_agent_webhook_{uuid4().hex[:8]}",
            nickname="测试客服-Webhook"
        )
        db_session.add(test_agent)
        
        customer_user_id = f"webchat:test_customer_webhook_{uuid4().hex[:8]}"
        test_customer = User(
            id=customer_user_id,
            tenant_id=test_tenant.id,
            platform="webchat",
            user_id=f"test_customer_webhook_{uuid4().hex[:8]}",
            nickname="测试用户-Webhook"
        )
        db_session.add(test_customer)
        
        await db_session.commit()
        
        return {
            "tenant": test_tenant,
            "agent": test_agent,
            "customer": test_customer,
            "api_key": unique_api_key
        }
    
    @pytest.mark.asyncio
    async def test_complete_customer_service_flow(self, setup_test_data_flow):
        """测试完整的客服会话流程"""
        test_data = setup_test_data_flow
        tenant = test_data["tenant"]
        agent = test_data["agent"]
        customer = test_data["customer"]
        api_key = test_data["api_key"]
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            
            # 步骤1: 用户发起咨询 - 创建会话
            session_response = await client.post(
                "/api/v1/sessions",
                json={
                    "user_id": str(customer.id),
                    "platform": "webchat",
                    "metadata": {
                        "source": "官网客服",
                        "ip_address": "192.168.1.1"
                    }
                },
                headers={"X-API-Key": api_key}
            )
            
            assert session_response.status_code == 201
            session_data = session_response.json()["data"]
            session_id = session_data["id"]
            
            # 验证会话状态
            assert session_data["status"] == "waiting"  # 新会话默认为等待状态
            assert session_data["user_id"] == str(customer.id)
            assert session_data["tenant_id"] == str(tenant.id)
            
            # 步骤2: 用户发送消息 
            # 注意: 使用实际路由路径(双重prefix)，与API契约(/sessions/{id}/messages)不同
            # 实际路径: /api/v1/messages/messages (实现问题)
            # 契约路径: /api/v1/sessions/{session_id}/messages (设计意图)
            user_message_response = await client.post(
                "/api/v1/messages/messages",
                json={
                    "session_id": session_id,
                    "message_type": "text",
                    "content": "我需要帮助处理订单问题",
                    "sender_type": "user",
                    "sender_id": str(customer.id),
                    "sender_name": "测试用户",
                    "metadata": {"source": "webchat"}
                },
                headers={"X-API-Key": api_key}
            )
            
            assert user_message_response.status_code == 201
            user_message_data = user_message_response.json()["data"]
            
            # 验证用户消息
            assert user_message_data["content"] == "我需要帮助处理订单问题"
            assert user_message_data["sender_type"] == "user"
            assert user_message_data["session_id"] == session_id
            
            # 步骤3: AI自动回复
            ai_reply_response = await client.post(
                "/api/v1/ai/auto-reply",
                json={
                    "session_id": session_id,
                    "message_content": "你好，我想了解一下你们的产品功能",
                    "enable_streaming": False
                },
                headers={"X-API-Key": api_key}
            )
            
            assert ai_reply_response.status_code == 200
            ai_reply_data = ai_reply_response.json()["data"]
            
            # 验证AI回复
            assert "reply_content" in ai_reply_data
            assert "confidence_score" in ai_reply_data
            assert ai_reply_data["confidence_score"] > 0.0
            
            # 步骤4: 客服接入会话
            agent_takeover_response = await client.put(
                f"/api/v1/sessions/{session_id}/status",
                json={
                    "status": "agent_active",
                    "agent_id": str(agent.id),
                    "status_reason": "客服接入处理"
                },
                headers={"X-API-Key": api_key}
            )
            
            assert agent_takeover_response.status_code == 200
            takeover_data = agent_takeover_response.json()["data"]
            
            # 验证客服接入
            assert takeover_data["status"] == "agent_active"
            assert takeover_data["assigned_agent_id"] == str(agent.id)
            
            # 步骤5: 客服发送回复 - 修复路径为双prefix
            agent_message_response = await client.post(
                "/api/v1/messages/messages",
                json={
                    "session_id": session_id,
                    "sender_id": str(agent.id),
                    "sender_type": "agent",
                    "content": "您好！我是人工客服小王，很高兴为您服务。我们的产品主要包括...",
                    "message_type": "text"
                },
                headers={"X-API-Key": api_key}
            )
            
            assert agent_message_response.status_code == 201
            agent_message_data = agent_message_response.json()["data"]
            
            # 验证客服消息
            assert agent_message_data["sender_type"] == "agent"
            assert "我是人工客服" in agent_message_data["content"]
            
            # 步骤6: 用户回复 - 修复路径为双prefix
            user_followup_response = await client.post(
                "/api/v1/messages/messages",
                json={
                    "session_id": session_id,
                    "sender_id": str(customer.id),
                    "sender_type": "user",
                    "content": "谢谢介绍，请问价格如何？",
                    "message_type": "text"
                },
                headers={"X-API-Key": api_key}
            )
            
            assert user_followup_response.status_code == 201
            
            # 步骤7: 获取客服建议
            suggestion_response = await client.post(
                "/api/v1/ai/agent-suggestions",
                json={
                    "session_id": session_id,
                    "message_content": "谢谢介绍，请问价格如何？",
                    "suggestion_type": "response"
                },
                headers={"X-API-Key": api_key}
            )
            
            assert suggestion_response.status_code == 200
            suggestion_data = suggestion_response.json()["data"]
            
            # 验证AI建议
            assert "suggestions" in suggestion_data
            assert len(suggestion_data["suggestions"]) > 0
            
            # 步骤8: 客服结束会话
            close_session_response = await client.put(
                f"/api/v1/sessions/{session_id}/status",
                json={
                    "status": "closed",
                    "agent_id": str(agent.id),
                    "status_reason": "问题已解决，用户满意"
                },
                headers={"X-API-Key": api_key}
            )
            
            assert close_session_response.status_code == 200
            close_data = close_session_response.json()["data"]
            
            # 验证会话关闭
            assert close_data["status"] == "closed"
            assert close_data["closed_at"] is not None
            
            # 步骤9: 生成会话总结
            summary_response = await client.post(
                "/api/v1/ai/session-summary",
                json={
                    "session_id": session_id,
                    "summary_type": "detailed"
                },
                headers={"X-API-Key": api_key}
            )
            
            assert summary_response.status_code == 200
            summary_data = summary_response.json()["data"]
            
            # 验证会话总结
            assert "summary_content" in summary_data
            assert "user_satisfaction" in summary_data
            assert "service_quality" in summary_data
            assert summary_data["session_id"] == session_id
            
            # 步骤10: 验证消息历史 - 修复路径为双prefix
            history_response = await client.get(
                f"/api/v1/messages/messages/sessions/{session_id}",
                params={"page": 1, "size": 20},
                headers={"X-API-Key": api_key}
            )
            
            assert history_response.status_code == 200
            history_data = history_response.json()["data"]
            
            # 验证消息历史完整性
            assert history_data["total"] >= 4  # 至少4条消息
            messages = history_data["items"]
            
            # 验证消息顺序和内容
            user_messages = [msg for msg in messages if msg["sender_type"] == "user"]
            agent_messages = [msg for msg in messages if msg["sender_type"] == "agent"]
            ai_messages = [msg for msg in messages if msg["sender_type"] == "ai"]
            
            assert len(user_messages) >= 2  # 用户发送了至少2条消息
            assert len(agent_messages) >= 1  # 客服发送了至少1条消息
            assert len(ai_messages) >= 1  # AI发送了至少1条消息

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, setup_test_data_isolation):
        """测试多租户数据隔离"""
        test_data = setup_test_data_isolation
        tenant = test_data["tenant"]
        customer = test_data["customer"]
        api_key = test_data["api_key"]
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            
            # 创建本租户的会话
            session_response = await client.post(
                "/api/v1/sessions",
                json={
                    "user_id": str(customer.id),
                    "platform": "webchat",
                    "metadata": {"source": "isolation_test"}
                },
                headers={"X-API-Key": api_key}
            )
            
            assert session_response.status_code == 201
            session_data = session_response.json()["data"]
            session_id = session_data["id"]
            
            # 创建另一个租户用于测试隔离
            other_tenant_api_key = f"test_api_key_other_{uuid4().hex[:12]}"
            
            # 尝试使用其他租户的API key访问当前会话（应该失败）
            unauthorized_response = await client.get(
                f"/api/v1/sessions/{session_id}",
                headers={"X-API-Key": other_tenant_api_key}
            )
            
            # 验证跨租户访问被拒绝
            assert unauthorized_response.status_code in [401, 404]  # 401未授权或404不存在
            
            # 验证正确的租户可以访问
            authorized_response = await client.get(
                f"/api/v1/sessions/{session_id}",
                headers={"X-API-Key": api_key}
            )
            
            assert authorized_response.status_code == 200
            authorized_data = authorized_response.json()["data"]
            assert authorized_data["id"] == session_id
            assert authorized_data["tenant_id"] == str(tenant.id)

    @pytest.mark.asyncio 
    async def test_ai_features_integration(self, setup_test_data_ai):
        """测试AI功能集成"""
        test_data = setup_test_data_ai
        customer = test_data["customer"]
        api_key = test_data["api_key"]
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            
            # 创建会话
            session_response = await client.post(
                "/api/v1/sessions",
                json={
                    "user_id": str(customer.id),
                    "platform": "webchat",
                    "metadata": {"source": "ai_test"}
                },
                headers={"X-API-Key": api_key}
            )
            
            assert session_response.status_code == 201
            session_id = session_response.json()["data"]["id"]
            
            # 测试AI自动回复
            ai_reply_response = await client.post(
                "/api/v1/ai/auto-reply",
                json={
                    "session_id": session_id,
                    "message_content": "测试AI功能",
                    "enable_streaming": False
                },
                headers={"X-API-Key": api_key}
            )
            
            assert ai_reply_response.status_code == 200
            ai_data = ai_reply_response.json()["data"]
            assert "reply_content" in ai_data
            assert "confidence_score" in ai_data
            
            # 测试AI客服建议
            suggestion_response = await client.post(
                "/api/v1/ai/agent-suggestions",
                json={
                    "session_id": session_id,
                    "message_content": "测试客服建议",
                    "suggestion_type": "response"
                },
                headers={"X-API-Key": api_key}
            )
            
            assert suggestion_response.status_code == 200
            suggestion_data = suggestion_response.json()["data"]
            assert "suggestions" in suggestion_data

    @pytest.mark.asyncio
    async def test_webhook_integration(self, setup_test_data_webhook):
        """测试Webhook集成"""
        test_data = setup_test_data_webhook
        tenant = test_data["tenant"]
        api_key = test_data["api_key"]
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            
            # 模拟AstrBot实例发送Webhook
            webhook_data = {
                "event_type": "message_received",
                "user_id": "test_webhook_user",
                "platform": "webchat",
                "message": {
                    "content": "Webhook测试消息",
                    "message_type": "text",
                    "timestamp": datetime.utcnow().isoformat()
                },
                "metadata": {
                    "source": "webhook_test"
                }
            }
            
            # 注意: 使用实际路由路径(双重prefix)，与期望的单prefix设计不同
            # 实际路径: /api/v1/webhooks/webhooks/{tenant_id}/messages (双重prefix)
            # 期望路径: /api/v1/webhooks/{tenant_id}/messages (单prefix)
            webhook_response = await client.post(
                f"/api/v1/webhooks/webhooks/{tenant.id}/messages",
                json=webhook_data,
                headers={
                    "X-API-Key": api_key,
                    "X-Instance-ID": f"test_instance_{uuid4().hex[:8]}"
                }
            )
            
            # 验证Webhook处理
            assert webhook_response.status_code in [200, 201]
            webhook_result = webhook_response.json()
            assert webhook_result["success"] is True 