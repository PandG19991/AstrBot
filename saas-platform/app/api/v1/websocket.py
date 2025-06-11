"""WebSocket实时通信模块

提供客服和用户之间的实时消息通信，支持多租户隔离
"""
import asyncio
import json
import logging
from typing import Dict, List, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_from_token, get_db
from app.models.tenant import Tenant
from app.models.session import Session
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.schemas.message import MessageCreate, MessageType

# 配置日志
logger = logging.getLogger(__name__)

# WebSocket连接管理器
class ConnectionManager:
    """管理WebSocket连接的全局管理器，支持租户隔离"""
    
    def __init__(self):
        # 存储活跃连接: {tenant_id: {connection_id: websocket}}
        self.active_connections: Dict[UUID, Dict[str, WebSocket]] = {}
        # 存储会话连接映射: {session_id: {connection_id: websocket}}
        self.session_connections: Dict[UUID, Dict[str, WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, tenant_id: UUID, connection_id: str):
        """接受WebSocket连接并注册到租户"""
        await websocket.accept()
        
        # 初始化租户连接字典
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = {}
            
        self.active_connections[tenant_id][connection_id] = websocket
        logger.info("websocket_connected", 
                   tenant_id=tenant_id, 
                   connection_id=connection_id,
                   total_connections=len(self.active_connections[tenant_id]))
    
    def disconnect(self, tenant_id: UUID, connection_id: str):
        """断开连接并清理"""
        if tenant_id in self.active_connections:
            self.active_connections[tenant_id].pop(connection_id, None)
            
            # 如果租户没有活跃连接，清理租户记录
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]
                
        # 清理会话连接映射
        for session_id, connections in list(self.session_connections.items()):
            connections.pop(connection_id, None)
            if not connections:
                del self.session_connections[session_id]
                
        logger.info("websocket_disconnected", 
                   tenant_id=tenant_id, 
                   connection_id=connection_id)
    
    def subscribe_to_session(self, session_id: UUID, connection_id: str, websocket: WebSocket):
        """订阅会话消息"""
        if session_id not in self.session_connections:
            self.session_connections[session_id] = {}
            
        self.session_connections[session_id][connection_id] = websocket
        logger.info("session_subscribed", 
                   session_id=session_id, 
                   connection_id=connection_id)
    
    def unsubscribe_from_session(self, session_id: UUID, connection_id: str):
        """取消订阅会话消息"""
        if session_id in self.session_connections:
            self.session_connections[session_id].pop(connection_id, None)
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]
                
        logger.info("session_unsubscribed", 
                   session_id=session_id, 
                   connection_id=connection_id)
    
    async def broadcast_to_tenant(self, tenant_id: UUID, message: dict):
        """向租户的所有连接广播消息"""
        if tenant_id not in self.active_connections:
            return
            
        disconnected_connections = []
        for connection_id, websocket in self.active_connections[tenant_id].items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error("broadcast_failed", 
                           tenant_id=tenant_id, 
                           connection_id=connection_id, 
                           error=str(e))
                disconnected_connections.append(connection_id)
        
        # 清理失效连接
        for connection_id in disconnected_connections:
            self.disconnect(tenant_id, connection_id)
    
    async def broadcast_to_session(self, session_id: UUID, message: dict):
        """向会话的所有连接广播消息"""
        if session_id not in self.session_connections:
            return
            
        disconnected_connections = []
        for connection_id, websocket in self.session_connections[session_id].items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error("session_broadcast_failed", 
                           session_id=session_id, 
                           connection_id=connection_id, 
                           error=str(e))
                disconnected_connections.append(connection_id)
        
        # 清理失效连接
        for connection_id in disconnected_connections:
            self.unsubscribe_from_session(session_id, connection_id)

# 全局连接管理器实例
manager = ConnectionManager()

# 创建路由
router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    connection_id: str = "default",
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket连接端点
    
    Query参数:
    - token: JWT访问令牌
    - connection_id: 连接标识符（用于多连接管理）
    """
    try:
        # 验证token并获取租户信息
        tenant = await get_current_tenant_from_token(token, db)
        if not tenant:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        # 建立连接
        await manager.connect(websocket, tenant.id, connection_id)
        
        # 初始化服务
        message_service = MessageService(db)
        session_service = SessionService(db)
        
        try:
            while True:
                # 接收客户端消息
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # 处理消息
                await handle_websocket_message(
                    message_data, 
                    tenant.id, 
                    connection_id,
                    message_service,
                    session_service
                )
                
        except WebSocketDisconnect:
            logger.info("websocket_disconnected_normally", 
                       tenant_id=tenant.id, 
                       connection_id=connection_id)
        except Exception as e:
            logger.error("websocket_error", 
                        tenant_id=tenant.id, 
                        connection_id=connection_id, 
                        error=str(e))
        finally:
            manager.disconnect(tenant.id, connection_id)
            
    except Exception as e:
        logger.error("websocket_connection_error", error=str(e))
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

async def handle_websocket_message(
    message_data: dict, 
    tenant_id: UUID, 
    connection_id: str,
    message_service: MessageService,
    session_service: SessionService
):
    """处理WebSocket接收到的消息"""
    try:
        message_type = message_data.get("type")
        
        if message_type == "subscribe_session":
            # 订阅会话消息
            session_id = UUID(message_data["session_id"])
            
            # 验证会话属于当前租户
            session = await session_service.get_session(session_id, tenant_id)
            if not session:
                logger.warning("subscribe_unauthorized_session", 
                             tenant_id=tenant_id, 
                             session_id=session_id)
                return
                
            websocket = manager.active_connections[tenant_id][connection_id]
            manager.subscribe_to_session(session_id, connection_id, websocket)
            
            # 发送订阅确认
            await websocket.send_text(json.dumps({
                "type": "subscription_confirmed",
                "session_id": str(session_id)
            }))
            
        elif message_type == "unsubscribe_session":
            # 取消订阅会话消息
            session_id = UUID(message_data["session_id"])
            manager.unsubscribe_from_session(session_id, connection_id)
            
        elif message_type == "send_message":
            # 发送消息
            session_id = UUID(message_data["session_id"])
            content = message_data["content"]
            msg_type = MessageType(message_data.get("message_type", "agent"))
            
            # 验证会话权限
            session = await session_service.get_session(session_id, tenant_id)
            if not session:
                logger.warning("send_message_unauthorized_session", 
                             tenant_id=tenant_id, 
                             session_id=session_id)
                return
            
            # 创建消息
            message_create = MessageCreate(
                session_id=session_id,
                content=content,
                message_type=msg_type,
                user_id=message_data.get("user_id", "system")
            )
            
            message = await message_service.store_message(message_create, tenant_id)
            
            # 广播消息到会话订阅者
            await manager.broadcast_to_session(session_id, {
                "type": "new_message",
                "message": {
                    "id": str(message.id),
                    "session_id": str(session_id),
                    "content": content,
                    "message_type": msg_type.value,
                    "user_id": message_data.get("user_id", "system"),
                    "created_at": message.created_at.isoformat()
                }
            })
            
        else:
            logger.warning("unknown_message_type", 
                         tenant_id=tenant_id, 
                         message_type=message_type)
            
    except Exception as e:
        logger.error("handle_websocket_message_error", 
                    tenant_id=tenant_id, 
                    error=str(e))

# 消息广播工具函数
async def broadcast_message_to_session(session_id: UUID, message_data: dict):
    """向指定会话广播消息（供外部服务调用）"""
    await manager.broadcast_to_session(session_id, message_data)

async def broadcast_notification_to_tenant(tenant_id: UUID, notification: dict):
    """向指定租户广播通知（供外部服务调用）"""
    await manager.broadcast_to_tenant(tenant_id, notification)

def get_session_connections_count(session_id: UUID) -> int:
    """获取会话当前连接数"""
    return len(manager.session_connections.get(session_id, {}))

def get_tenant_connections_count(tenant_id: UUID) -> int:
    """获取租户当前连接数"""
    return len(manager.active_connections.get(tenant_id, {})) 