"""
FastAPI依赖注入模块
提供认证、授权和数据库会话相关的依赖函数
"""
from typing import Generator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.tenant import Tenant
from app.utils.logging import get_logger

# 设置日志记录器
logger = get_logger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_db_session() -> AsyncSession:
    """获取数据库会话"""
    async with get_db() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    获取当前认证用户
    
    Args:
        credentials: HTTP Authorization Bearer token
        db: 数据库会话
        
    Returns:
        User: 当前认证用户
        
    Raises:
        HTTPException: 401 认证失败或token无效
    """
    try:
        # 解析JWT token
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # 从token中获取用户ID
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("Token中缺少用户ID")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token无效",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 从数据库获取用户信息
        user = await db.get(User, UUID(user_id))
        if user is None:
            logger.warning(f"用户不存在: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 检查用户是否激活
        if not user.is_active:
            logger.warning(f"用户已被禁用: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户已被禁用",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"用户认证成功: {user.email}")
        return user
        
    except InvalidTokenError as e:
        logger.warning(f"Token验证失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"认证过程发生异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="认证服务异常"
        )


async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Tenant:
    """
    获取当前用户的租户
    
    Args:
        current_user: 当前认证用户
        db: 数据库会话
        
    Returns:
        Tenant: 当前用户所属的租户
        
    Raises:
        HTTPException: 404 租户不存在或403 无权限访问
    """
    try:
        # 获取用户的租户信息
        tenant = await db.get(Tenant, current_user.tenant_id)
        if tenant is None:
            logger.error(f"租户不存在: {current_user.tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        # 检查租户是否激活
        if not tenant.is_active:
            logger.warning(f"租户已被禁用: {tenant.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="租户已被禁用"
            )
        
        logger.info(f"获取租户信息成功: {tenant.name}")
        return tenant
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取租户信息异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取租户信息失败"
        )


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取管理员用户依赖 (需要管理员权限)
    
    Args:
        current_user: 当前登录的用户
        
    Returns:
        User: 验证后的管理员用户
        
    Raises:
        HTTPException: 用户不是管理员时
    """
    try:
        # 检查用户是否为系统管理员或租户管理员
        if not current_user.has_permission("admin", "access"):
            logger.warning(
                "用户尝试访问管理员功能但权限不足",
                user_id=current_user.id,
                tenant_id=str(current_user.tenant_id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限"
            )
        
        logger.info(
            "管理员用户认证成功",
            user_id=current_user.id,
            tenant_id=str(current_user.tenant_id)
        )
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("管理员认证失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="认证验证失败"
        )


async def get_current_tenant_from_token(
    token: str
) -> Tenant:
    """
    从token获取当前租户 (用于WebSocket认证)
    
    Args:
        token: JWT访问令牌
        
    Returns:
        Tenant: 验证后的租户
        
    Raises:
        HTTPException: token无效或租户不存在时
    """
    try:
        # 验证JWT token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # 提取用户信息
        user_id: str = payload.get("sub")
        tenant_id_str: str = payload.get("tenant_id")
        
        if not user_id or not tenant_id_str:
            logger.warning("token中缺少必要信息")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token信息不完整"
            )
        
        # 验证token类型
        token_type: str = payload.get("type", "")
        if token_type != "access":
            logger.warning(f"错误的token类型: {token_type}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的token类型"
            )
        
        # 验证租户ID格式
        try:
            tenant_uuid = UUID(tenant_id_str)
        except ValueError:
            logger.warning(f"无效的租户ID格式: {tenant_id_str}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的租户ID"
            )
        
        # 获取数据库会话
        async with get_db_session() as db:
            # 查询租户
            tenant = await db.get(Tenant, tenant_uuid)
            if not tenant:
                logger.warning(f"租户不存在: {tenant_uuid}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="租户不存在"
                )
            
            # 检查租户状态
            if not tenant.is_active:
                logger.warning(
                    f"租户已停用: {tenant_uuid}, 状态: {tenant.status}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="租户已停用"
                )
            
            logger.info(
                "WebSocket租户认证成功",
                tenant_id=str(tenant.id),
                tenant_name=tenant.name
            )
            return tenant
        
    except JWTError as e:
        logger.warning(f"JWT token验证失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebSocket认证异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="认证验证失败"
        )


# 可选的租户权限验证
async def get_tenant_admin_user(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant)
) -> User:
    """
    验证用户是否具有租户管理员权限
    
    Args:
        current_user: 当前认证用户
        current_tenant: 当前租户
        
    Returns:
        User: 具有租户管理员权限的用户
        
    Raises:
        HTTPException: 403 权限不足
    """
    try:
        # 检查用户是否是超级管理员
        if current_user.is_superuser:
            return current_user
        
        # 检查用户是否是租户管理员
        # TODO: 这里需要根据实际的权限模型来实现
        # 目前简化为检查用户是否属于当前租户
        if current_user.tenant_id != current_tenant.id:
            logger.warning(
                f"租户权限验证失败: 用户 {current_user.email} 不属于租户 {current_tenant.name}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限管理此租户"
            )
        
        logger.info(f"租户管理员权限验证通过: {current_user.email}")
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"租户权限验证异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限验证失败"
        )
