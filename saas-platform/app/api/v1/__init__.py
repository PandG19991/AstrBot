"""
API v1 路由模块

统一管理所有API v1版本的路由：
- 租户管理
- 用户管理  
- 会话管理
- 消息管理
- WebSocket通信
- LLM服务
- AI功能
- Webhook
- 实例管理
- RBAC权限
- 用户角色
- 数据分析
"""

from fastapi import APIRouter
from datetime import datetime

from .tenants import router as tenants_router
# from .users import router as users_router  # TODO: 创建users.py模块 ，测试时注释，正式环境启用
from .sessions import router as sessions_router
from .messages import router as messages_router
from .websocket import router as websocket_router
from .ai_features import router as ai_features_router
from .webhooks import router as webhooks_router
from .instances import router as instances_router
from .rbac import router as rbac_router
from .user_roles import router as user_roles_router
from .analytics import router as analytics_router

# 创建主路由器
api_router = APIRouter()

# 注册所有子路由
api_router.include_router(
    tenants_router, 
    prefix="/tenants", 
    tags=["租户管理"]
)

api_router.include_router(
    sessions_router, 
    prefix="/sessions", 
    tags=["会话管理"]
)

api_router.include_router(
    messages_router, 
    prefix="/messages", 
    tags=["消息管理"]
)

api_router.include_router(
    websocket_router, 
    prefix="/ws", 
    tags=["WebSocket通信"]
)

api_router.include_router(
    ai_features_router, 
    prefix="/ai", 
    tags=["AI功能"]
)

api_router.include_router(
    webhooks_router, 
    prefix="/webhooks", 
    tags=["Webhook接收"]
)

api_router.include_router(
    instances_router, 
    prefix="/instances", 
    tags=["实例管理"]
)

api_router.include_router(
    rbac_router, 
    prefix="/rbac", 
    tags=["权限管理"]
)

api_router.include_router(
    user_roles_router, 
    prefix="/user-roles", 
    tags=["用户角色"]
)

api_router.include_router(
    analytics_router, 
    prefix="/analytics", 
    tags=["数据分析"]
)

# 健康检查端点
@api_router.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy", 
        "version": "v1",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "tenant_management": "active",
            "session_management": "active", 
            "message_management": "active"
        }
    }
