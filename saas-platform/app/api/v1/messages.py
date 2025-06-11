"""
消息管理API端点
提供消息的发送、接收、搜索和统计功能
参考：cursor doc/功能说明.md 3.2 会话与消息管理
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db_session
from app.models.tenant import Tenant
from app.models.message import MessageType, MessageStatus
from app.schemas.message import (
    MessageCreate, 
    MessageRead, 
    IncomingMessageData,
    MessageSearchParams
)
from app.schemas.common import StandardResponse, PaginatedResponse
from app.services.message_service import MessageService, get_message_service
from app.utils.logging import get_logger

# 创建路由器
router = APIRouter(prefix="/messages", tags=["消息管理"])
logger = get_logger(__name__)


@router.post(
    "",
    response_model=StandardResponse[MessageRead],
    status_code=status.HTTP_201_CREATED,
    summary="发送消息",
    description="发送新消息到指定会话"
)
async def send_message(
    message_data: MessageCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    message_service: MessageService = Depends(get_message_service)
) -> StandardResponse[MessageRead]:
    """
    发送消息
    
    - **session_id**: 目标会话ID
    - **message_type**: 消息类型（text/image/voice/file/system）
    - **content**: 消息内容
    - **sender_type**: 发送者类型（user/agent/system/bot）
    - **sender_id**: 发送者ID
    - **sender_name**: 发送者名称
    - **attachments**: 附件信息（可选）
    - **metadata**: 额外元数据（可选）
    """
    try:
        logger.info(
            "开始发送消息",
            session_id=str(message_data.session_id),
            message_type=message_data.message_type.value,
            sender_type=message_data.sender_type.value,
            tenant_id=str(current_tenant.id)
        )
        
        # 存储消息
        message = await message_service.store_message(message_data, current_tenant.id)
        
        logger.info(
            "消息发送成功",
            message_id=str(message.id),
            session_id=str(message_data.session_id),
            tenant_id=str(current_tenant.id)
        )
        
        return StandardResponse(
            success=True,
            message="消息发送成功",
            data=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "发送消息异常",
            session_id=str(message_data.session_id),
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="发送消息失败，请稍后重试"
        )


@router.post(
    "/incoming",
    response_model=StandardResponse[MessageRead],
    status_code=status.HTTP_201_CREATED,
    summary="处理incoming消息",
    description="处理来自IM平台的用户消息（内部接口）"
)
async def process_incoming_message(
    incoming_data: IncomingMessageData,
    current_tenant: Tenant = Depends(get_current_tenant),
    message_service: MessageService = Depends(get_message_service)
) -> StandardResponse[MessageRead]:
    """
    处理incoming消息（供AstrBot实例调用）
    
    - **user_id**: 用户ID（平台唯一标识）
    - **platform**: IM平台类型
    - **message_type**: 消息类型
    - **content**: 消息内容
    - **sender_name**: 发送者名称
    - **session_data**: 会话创建数据（可选）
    
    处理流程：
    1. 黑名单检查
    2. 会话创建/更新
    3. 消息存储
    4. 通知推送
    """
    try:
        logger.info(
            "开始处理incoming消息",
            user_id=incoming_data.user_id,
            platform=incoming_data.platform,
            message_type=incoming_data.message_type.value,
            tenant_id=str(current_tenant.id)
        )
        
        # 处理incoming消息
        message = await message_service.process_incoming_message(
            incoming_data, 
            current_tenant.id
        )
        
        logger.info(
            "incoming消息处理成功",
            message_id=str(message.id),
            user_id=incoming_data.user_id,
            tenant_id=str(current_tenant.id)
        )
        
        return StandardResponse(
            success=True,
            message="消息处理成功",
            data=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "处理incoming消息异常",
            user_id=incoming_data.user_id,
            platform=incoming_data.platform,
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="消息处理失败，请稍后重试"
        )


@router.get(
    "/sessions/{session_id}",
    response_model=PaginatedResponse[MessageRead],
    summary="获取会话消息",
    description="分页获取指定会话的消息列表"
)
async def get_session_messages(
    session_id: UUID,
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(50, ge=1, le=100, description="每页记录数"),
    message_type: Optional[MessageType] = Query(None, description="按消息类型过滤"),
    before_time: Optional[datetime] = Query(None, description="时间范围过滤（之前）"),
    after_time: Optional[datetime] = Query(None, description="时间范围过滤（之后）"),
    current_tenant: Tenant = Depends(get_current_tenant),
    message_service: MessageService = Depends(get_message_service)
) -> PaginatedResponse[MessageRead]:
    """
    获取会话消息列表
    
    - **session_id**: 会话唯一标识
    - **skip**: 跳过的记录数（分页）
    - **limit**: 每页记录数（1-100）
    - **message_type**: 按消息类型过滤
    - **before_time**: 获取此时间之前的消息
    - **after_time**: 获取此时间之后的消息
    
    结果按创建时间倒序排列（最新消息在前）
    """
    try:
        logger.info(
            "获取会话消息",
            session_id=str(session_id),
            tenant_id=str(current_tenant.id),
            skip=skip,
            limit=limit
        )
        
        messages = await message_service.get_session_messages(
            session_id=session_id,
            tenant_id=current_tenant.id,
            skip=skip,
            limit=limit,
            message_type=message_type,
            before_time=before_time,
            after_time=after_time
        )
        
        # 简化版本的总数计算
        total = len(messages) + skip
        
        logger.info(
            "会话消息获取成功",
            session_id=str(session_id),
            tenant_id=str(current_tenant.id),
            returned_count=len(messages)
        )
        
        return PaginatedResponse(
            success=True,
            message="获取会话消息成功",
            data=messages,
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "获取会话消息异常",
            session_id=str(session_id),
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话消息失败"
        )


@router.get(
    "/search",
    response_model=PaginatedResponse[MessageRead],
    summary="搜索消息",
    description="根据关键词搜索消息，支持多种过滤条件"
)
async def search_messages(
    search_query: str = Query(..., min_length=1, description="搜索关键词"),
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(50, ge=1, le=100, description="每页记录数"),
    session_id: Optional[UUID] = Query(None, description="限制在特定会话"),
    user_id: Optional[str] = Query(None, description="按发送用户过滤"),
    start_time: Optional[datetime] = Query(None, description="搜索开始时间"),
    end_time: Optional[datetime] = Query(None, description="搜索结束时间"),
    current_tenant: Tenant = Depends(get_current_tenant),
    message_service: MessageService = Depends(get_message_service)
) -> PaginatedResponse[MessageRead]:
    """
    搜索消息
    
    - **search_query**: 搜索关键词（必填）
    - **skip**: 跳过的记录数（分页）
    - **limit**: 每页记录数（1-100）
    - **session_id**: 限制在特定会话中搜索
    - **user_id**: 按发送用户过滤
    - **start_time**: 搜索时间范围开始
    - **end_time**: 搜索时间范围结束
    
    在消息内容中进行全文搜索，支持多种过滤条件
    """
    try:
        logger.info(
            "开始搜索消息",
            search_query=search_query,
            tenant_id=str(current_tenant.id),
            session_id=str(session_id) if session_id else None,
            user_id=user_id
        )
        
        messages = await message_service.search_messages(
            tenant_id=current_tenant.id,
            search_query=search_query,
            session_id=session_id,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            skip=skip,
            limit=limit
        )
        
        # 简化版本的总数计算
        total = len(messages) + skip
        
        logger.info(
            "消息搜索完成",
            search_query=search_query,
            tenant_id=str(current_tenant.id),
            returned_count=len(messages)
        )
        
        return PaginatedResponse(
            success=True,
            message="消息搜索成功",
            data=messages,
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "消息搜索异常",
            search_query=search_query,
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="消息搜索失败"
        )


@router.put(
    "/{message_id}/status",
    response_model=StandardResponse[MessageRead],
    summary="更新消息状态",
    description="更新消息的状态（如已读、已送达等）"
)
async def update_message_status(
    message_id: UUID,
    new_status: MessageStatus,
    current_tenant: Tenant = Depends(get_current_tenant),
    message_service: MessageService = Depends(get_message_service)
) -> StandardResponse[MessageRead]:
    """
    更新消息状态
    
    - **message_id**: 消息唯一标识
    - **new_status**: 新状态（sent/delivered/read/failed）
    
    用于更新消息的发送状态或已读状态
    """
    try:
        logger.info(
            "更新消息状态",
            message_id=str(message_id),
            new_status=new_status.value,
            tenant_id=str(current_tenant.id)
        )
        
        updated_message = await message_service.update_message_status(
            message_id=message_id,
            tenant_id=current_tenant.id,
            new_status=new_status
        )
        
        logger.info(
            "消息状态更新成功",
            message_id=str(message_id),
            new_status=new_status.value,
            tenant_id=str(current_tenant.id)
        )
        
        return StandardResponse(
            success=True,
            message="消息状态更新成功",
            data=updated_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "消息状态更新异常",
            message_id=str(message_id),
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="消息状态更新失败"
        )


@router.get(
    "/stats",
    response_model=StandardResponse[dict],
    summary="获取消息统计",
    description="获取租户的消息统计信息"
)
async def get_message_statistics(
    start_time: Optional[datetime] = Query(None, description="统计开始时间"),
    end_time: Optional[datetime] = Query(None, description="统计结束时间"),
    current_tenant: Tenant = Depends(get_current_tenant),
    message_service: MessageService = Depends(get_message_service)
) -> StandardResponse[dict]:
    """
    获取消息统计信息
    
    - **start_time**: 统计时间范围开始（可选）
    - **end_time**: 统计时间范围结束（可选）
    
    返回统计数据：
    - 总消息数量
    - 按类型分布
    - 按发送者类型分布
    - 时间范围信息
    """
    try:
        logger.info(
            "获取消息统计",
            tenant_id=str(current_tenant.id),
            start_time=start_time.isoformat() if start_time else None,
            end_time=end_time.isoformat() if end_time else None
        )
        
        statistics = await message_service.get_message_statistics(
            tenant_id=current_tenant.id,
            start_time=start_time,
            end_time=end_time
        )
        
        logger.info(
            "消息统计获取成功",
            tenant_id=str(current_tenant.id),
            total_messages=statistics.get("total_messages", 0)
        )
        
        return StandardResponse(
            success=True,
            message="获取消息统计成功",
            data=statistics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "获取消息统计异常",
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取消息统计失败"
        ) 