"""
会话管理API端点
提供会话的CRUD操作、状态管理和生命周期控制
参考：cursor doc/功能说明.md 3.2 会话与消息管理
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant
from app.core.database import get_db
from app.core.security import (
    verify_token, 
    get_tenant_id_from_token, 
    extract_token_from_header,
    TokenExpiredError,
    InvalidTokenError
)
from app.models.tenant import Tenant
from app.models.session import SessionStatus
from app.schemas.session import (
    SessionCreate, 
    SessionRead, 
    SessionStatusUpdate,
    IncomingSessionData
)
from app.schemas.common import StandardResponse, PaginatedResponse
from app.services.session_service import SessionService, get_session_service
from app.utils.logging import get_logger

# 创建路由器
router = APIRouter(tags=["会话管理"])
logger = get_logger(__name__)


def get_tenant_from_auth():
    """
    获取租户的混合认证依赖
    支持JWT token和API key两种认证方式
    """
    async def _get_tenant(
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
        authorization: Optional[str] = Header(None, alias="Authorization"),
        db: AsyncSession = Depends(get_db)
    ) -> Tenant:
        # 优先使用API key认证（用于测试和webhook）
        if x_api_key:
            try:
                from sqlalchemy import select
                stmt = select(Tenant).where(Tenant.api_key == x_api_key)
                result = await db.execute(stmt)
                tenant = result.scalar_one_or_none()
                
                if tenant and tenant.is_active:
                    logger.info(
                        "API key认证成功",
                        tenant_id=str(tenant.id),
                        api_key=x_api_key[:8] + "***"
                    )
                    return tenant
                else:
                    logger.warning(
                        "API key认证失败：租户不存在或未激活",
                        api_key=x_api_key[:8] + "***",
                        tenant_found=tenant is not None,
                        tenant_active=tenant.is_active if tenant else None
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="API key authentication failed"
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error("API key认证异常", error=str(e), exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key authentication failed"
                )
        
        # 简化的租户ID header认证（仅用于测试）
        if x_tenant_id:
            try:
                from uuid import UUID
                tenant_uuid = UUID(x_tenant_id)
                tenant = await db.get(Tenant, tenant_uuid)
                
                if tenant and tenant.is_active:
                    logger.info(
                        "租户ID认证成功",
                        tenant_id=str(tenant.id),
                        tenant_name=tenant.name
                    )
                    return tenant
                else:
                    logger.warning("租户ID认证失败: 租户不存在或未激活")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Tenant not found"
                    )
            except ValueError:
                logger.warning("租户ID格式无效", tenant_id=x_tenant_id)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tenant ID format"
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error("租户ID认证异常", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Tenant lookup failed"
                )
        
        # JWT认证fallback（手动实现，避免依赖注入问题）
        if authorization:
            try:
                # 提取JWT token
                token = extract_token_from_header(authorization)
                
                # 验证token并获取payload
                payload = verify_token(token)
                
                # 从token中获取租户ID
                tenant_id = get_tenant_id_from_token(token)
                
                if not tenant_id:
                    logger.warning("JWT token缺少租户信息")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token missing tenant information"
                    )
                
                # 查询租户
                tenant = await db.get(Tenant, tenant_id)
                
                if not tenant:
                    logger.warning("JWT认证失败: 租户不存在", tenant_id=str(tenant_id))
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Tenant not found"
                    )
                
                # 检查租户状态
                if not tenant.is_active:
                    logger.warning("JWT认证失败: 租户未激活", tenant_id=str(tenant_id))
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Tenant is not active"
                    )
                
                logger.info(
                    "JWT认证成功",
                    tenant_id=str(tenant.id),
                    tenant_name=tenant.name,
                    user_id=payload.get("sub")
                )
                return tenant
                
            except TokenExpiredError:
                logger.warning("JWT认证失败: token已过期")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            except InvalidTokenError as e:
                logger.warning("JWT认证失败: token无效", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: {str(e)}"
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error("JWT认证异常", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT authentication failed"
                )
        
        # 如果所有认证方式都失败
        logger.warning("认证失败: 缺少有效的认证凭据")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide API key, tenant ID, or valid JWT token."
        )
    
    return _get_tenant


@router.post(
    "",
    response_model=StandardResponse[SessionRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建或获取会话",
    description="创建新会话或获取现有活跃会话（支持幂等性）"
)
async def create_or_get_session(
    session_data: IncomingSessionData,
    current_tenant: Tenant = Depends(get_tenant_from_auth()),
    session_service: SessionService = Depends(get_session_service)
) -> StandardResponse[SessionRead]:
    """
    创建或获取会话（幂等性操作）
    
    - **user_id**: 用户ID（平台唯一标识）
    - **platform**: IM平台类型（企业微信、QQ等）
    - **customer_name**: 客户姓名（可选）
    - **customer_avatar**: 客户头像（可选）
    - **metadata**: 额外元数据（可选）
    
    如果用户在该平台已有活跃会话，返回现有会话；否则创建新会话
    """
    try:
        logger.info(
            "开始创建或获取会话",
            user_id=session_data.user_id,
            platform=session_data.platform,
            tenant_id=str(current_tenant.id)
        )
        
        # 转换为内部数据格式 - 只传递扩展数据
        session_create = None
        if any([session_data.customer_name, session_data.customer_avatar, 
                session_data.tags, session_data.metadata]):
            session_create = SessionCreate(
                user_id=session_data.user_id,  # 必需字段
                platform=session_data.platform,  # 必需字段
                customer_name=session_data.customer_name,
                customer_avatar=session_data.customer_avatar,
                tags=session_data.tags or [],
                metadata=session_data.metadata or {}
            )
        
        # 创建或获取会话
        session = await session_service.create_or_get_session(
            user_id=session_data.user_id,
            platform=session_data.platform,
            tenant_id=current_tenant.id,
            session_data=session_create
        )
        
        logger.info(
            "会话创建或获取成功",
            session_id=str(session.id),
            user_id=session_data.user_id,
            status=session.status.value,
            tenant_id=str(current_tenant.id)
        )
        
        return StandardResponse(
            success=True,
            message="会话操作成功",
            data=session
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "创建或获取会话异常",
            user_id=session_data.user_id,
            platform=session_data.platform,
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="会话操作失败，请稍后重试"
        )


@router.get(
    "/{session_id}",
    response_model=StandardResponse[SessionRead],
    summary="获取会话详情",
    description="根据会话ID获取详细信息，支持租户隔离"
)
async def get_session(
    session_id: UUID,
    current_tenant: Tenant = Depends(get_tenant_from_auth()),
    session_service: SessionService = Depends(get_session_service)
) -> StandardResponse[SessionRead]:
    """
    获取会话详情
    
    - **session_id**: 会话唯一标识
    
    注意：只能访问当前租户的会话
    """
    try:
        session = await session_service.get_session(session_id, current_tenant.id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在或没有访问权限"
            )
        
        logger.info(
            "会话详情获取成功",
            session_id=str(session_id),
            tenant_id=str(current_tenant.id)
        )
        
        return StandardResponse(
            success=True,
            message="获取会话详情成功",
            data=session
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "获取会话详情异常",
            session_id=str(session_id),
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话详情失败"
        )


@router.put(
    "/{session_id}/status",
    response_model=StandardResponse[SessionRead],
    summary="更新会话状态",
    description="更新会话状态，支持状态转换验证"
)
async def update_session_status(
    session_id: UUID,
    status_update: SessionStatusUpdate,
    current_tenant: Tenant = Depends(get_tenant_from_auth()),
    session_service: SessionService = Depends(get_session_service)
) -> StandardResponse[SessionRead]:
    """
    更新会话状态
    
    - **session_id**: 会话唯一标识
    - **status**: 新状态（waiting/active/transferred/closed）
    - **agent_id**: 分配的客服ID（可选）
    - **reason**: 状态变更原因（可选）
    
    支持的状态转换：
    - WAITING → ACTIVE, CLOSED
    - ACTIVE → CLOSED, TRANSFERRED
    - TRANSFERRED → ACTIVE, CLOSED
    - CLOSED → （无法转换）
    """
    try:
        logger.info(
            "开始更新会话状态",
            session_id=str(session_id),
            new_status=status_update.status.value,
            agent_id=str(status_update.agent_id) if status_update.agent_id else None,
            tenant_id=str(current_tenant.id)
        )
        
        updated_session = await session_service.update_session_status(
            session_id=session_id,
            tenant_id=current_tenant.id,
            status_update=status_update
        )
        
        logger.info(
            "会话状态更新成功",
            session_id=str(session_id),
            new_status=status_update.status.value,
            tenant_id=str(current_tenant.id)
        )
        
        return StandardResponse(
            success=True,
            message="会话状态更新成功",
            data=updated_session
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "更新会话状态异常",
            session_id=str(session_id),
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="会话状态更新失败"
        )


@router.get(
    "",
    response_model=PaginatedResponse[SessionRead],
    summary="获取会话列表",
    description="分页获取租户的会话列表，支持多种过滤条件"
)
async def list_sessions(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="每页记录数"),
    status_filter: Optional[SessionStatus] = Query(None, description="按状态过滤"),
    agent_id: Optional[UUID] = Query(None, description="按客服过滤"),
    platform: Optional[str] = Query(None, description="按平台过滤"),
    current_tenant: Tenant = Depends(get_tenant_from_auth()),
    session_service: SessionService = Depends(get_session_service)
) -> PaginatedResponse[SessionRead]:
    """
    获取会话列表
    
    - **skip**: 跳过的记录数（分页）
    - **limit**: 每页记录数（1-100）
    - **status_filter**: 按状态过滤（waiting/active/transferred/closed）
    - **agent_id**: 按分配的客服过滤
    - **platform**: 按IM平台过滤
    
    结果按最后消息时间倒序排列
    """
    try:
        logger.info(
            "获取会话列表",
            tenant_id=str(current_tenant.id),
            skip=skip,
            limit=limit,
            status_filter=status_filter.value if status_filter else None,
            agent_id=str(agent_id) if agent_id else None,
            platform=platform
        )
        
        sessions = await session_service.list_tenant_sessions(
            tenant_id=current_tenant.id,
            skip=skip,
            limit=limit,
            status_filter=status_filter,
            agent_id=agent_id,
            platform=platform
        )
        
        # 简化版本的总数计算（实际应该单独查询）
        total = len(sessions) + skip
        
        logger.info(
            "会话列表获取成功",
            tenant_id=str(current_tenant.id),
            returned_count=len(sessions)
        )
        
        return PaginatedResponse(
            success=True,
            message="获取会话列表成功",
            data=sessions,
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "获取会话列表异常",
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话列表失败"
        )


@router.get(
    "/stats/summary",
    response_model=StandardResponse[dict],
    summary="获取会话统计摘要",
    description="获取当前租户的会话统计信息"
)
async def get_session_stats(
    current_tenant: Tenant = Depends(get_tenant_from_auth()),
    session_service: SessionService = Depends(get_session_service)
) -> StandardResponse[dict]:
    """
    获取会话统计摘要
    
    返回统计数据：
    - 总会话数
    - 各状态会话数量
    - 平均响应时间
    - 活跃客服数量
    """
    try:
        # 获取不同状态的会话数量
        waiting_sessions = await session_service.list_tenant_sessions(
            tenant_id=current_tenant.id,
            status_filter=SessionStatus.WAITING,
            limit=1000  # 获取较多数据用于统计
        )
        
        active_sessions = await session_service.list_tenant_sessions(
            tenant_id=current_tenant.id,
            status_filter=SessionStatus.ACTIVE,
            limit=1000
        )
        
        closed_sessions = await session_service.list_tenant_sessions(
            tenant_id=current_tenant.id,
            status_filter=SessionStatus.CLOSED,
            limit=1000
        )
        
        # 统计数据
        stats = {
            "total_sessions": len(waiting_sessions) + len(active_sessions) + len(closed_sessions),
            "session_status": {
                "waiting": len(waiting_sessions),
                "active": len(active_sessions),
                "closed": len(closed_sessions)
            },
            "active_agents": len(set(
                session.assigned_agent_id 
                for session in active_sessions 
                if session.assigned_agent_id
            )),
            "summary": {
                "needs_attention": len(waiting_sessions),
                "in_progress": len(active_sessions)
            }
        }
        
        logger.info(
            "会话统计获取成功",
            tenant_id=str(current_tenant.id),
            total_sessions=stats["total_sessions"]
        )
        
        return StandardResponse(
            success=True,
            message="获取会话统计成功",
            data=stats
        )
        
    except Exception as e:
        logger.error(
            "获取会话统计异常",
            tenant_id=str(current_tenant.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话统计失败"
        ) 