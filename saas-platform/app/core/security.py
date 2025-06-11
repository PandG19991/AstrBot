"""
安全相关工具函数
包含JWT token创建、验证和密码处理
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import settings


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityError(Exception):
    """安全相关异常基类"""
    pass


class TokenExpiredError(SecurityError):
    """Token过期异常"""
    pass


class InvalidTokenError(SecurityError):
    """无效Token异常"""
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        bool: 密码是否正确
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    生成密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        str: 哈希密码
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, UUID], 
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    创建访问Token
    
    Args:
        subject: Token主题（通常是用户ID）
        expires_delta: 过期时间间隔
        extra_data: 额外数据（如租户ID）
        
    Returns:
        str: JWT Token字符串
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    
    # 构建Token载荷
    to_encode = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "sub": str(subject),
        "type": "access"
    }
    
    # 添加额外数据
    if extra_data:
        to_encode.update(extra_data)
    
    # 编码JWT
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm=settings.algorithm
    )
    
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, UUID],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新Token
    
    Args:
        subject: Token主题（用户ID）
        expires_delta: 过期时间间隔
        
    Returns:
        str: 刷新Token字符串
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
    
    to_encode = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "sub": str(subject),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm=settings.algorithm
    )
    
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """
    验证JWT Token
    
    Args:
        token: JWT Token字符串
        token_type: Token类型（access/refresh）
        
    Returns:
        Dict[str, Any]: Token载荷数据
        
    Raises:
        TokenExpiredError: Token已过期
        InvalidTokenError: Token无效
    """
    try:
        # 解码JWT
        payload = jwt.decode(
            token, 
            settings.secret_key, 
            algorithms=[settings.algorithm]
        )
        
        # 验证Token类型
        if payload.get("type") != token_type:
            raise InvalidTokenError(f"Invalid token type: expected {token_type}")
        
        # 验证过期时间
        exp = payload.get("exp")
        if not exp:
            raise InvalidTokenError("Token missing expiration")
        
        if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise TokenExpiredError("Token has expired")
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise InvalidTokenError(f"Token verification failed: {str(e)}")


def get_subject_from_token(token: str) -> str:
    """
    从Token中获取主题（用户ID）
    
    Args:
        token: JWT Token
        
    Returns:
        str: 用户ID
        
    Raises:
        InvalidTokenError: Token无效或缺少主题
    """
    payload = verify_token(token)
    subject = payload.get("sub")
    
    if not subject:
        raise InvalidTokenError("Token missing subject")
    
    return subject


def get_tenant_id_from_token(token: str) -> Optional[UUID]:
    """
    从Token中获取租户ID
    
    Args:
        token: JWT Token
        
    Returns:
        Optional[UUID]: 租户ID，如果不存在返回None
    """
    try:
        payload = verify_token(token)
        tenant_id_str = payload.get("tenant_id")
        
        if tenant_id_str:
            return UUID(tenant_id_str)
        return None
        
    except (InvalidTokenError, TokenExpiredError, ValueError):
        return None


def create_auth_tokens(
    user_id: Union[str, UUID], 
    tenant_id: UUID,
    user_email: str,
    user_role: str = "user"
) -> Dict[str, str]:
    """
    创建完整的认证Token对
    
    Args:
        user_id: 用户ID
        tenant_id: 租户ID
        user_email: 用户邮箱
        user_role: 用户角色
        
    Returns:
        Dict[str, str]: 包含access_token和refresh_token的字典
    """
    # 构建额外数据
    extra_data = {
        "tenant_id": str(tenant_id),
        "email": user_email,
        "role": user_role
    }
    
    # 创建访问Token
    access_token = create_access_token(
        subject=user_id,
        extra_data=extra_data
    )
    
    # 创建刷新Token
    refresh_token = create_refresh_token(subject=user_id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """
    使用刷新Token获取新的访问Token
    
    Args:
        refresh_token: 刷新Token
        
    Returns:
        Dict[str, str]: 新的Token对
        
    Raises:
        InvalidTokenError: 刷新Token无效
        TokenExpiredError: 刷新Token已过期
    """
    # 验证刷新Token
    payload = verify_token(refresh_token, token_type="refresh")
    user_id = payload.get("sub")
    
    if not user_id:
        raise InvalidTokenError("Refresh token missing subject")
    
    # 这里应该从数据库获取用户最新信息
    # 简化实现，实际项目中需要查询数据库
    # TODO: 从数据库获取用户和租户信息
    
    # 创建新的访问Token（简化版）
    new_access_token = create_access_token(subject=user_id)
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


def generate_api_key(prefix: str = "ak") -> str:
    """
    生成API密钥
    
    Args:
        prefix: API密钥前缀
        
    Returns:
        str: API密钥
    """
    import secrets
    import string
    
    # 生成32字符的随机字符串
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    return f"{prefix}_{'live' if settings.environment == 'production' else 'test'}_{random_part}"


def validate_api_key_format(api_key: str) -> bool:
    """
    验证API密钥格式
    
    Args:
        api_key: API密钥
        
    Returns:
        bool: 格式是否正确
    """
    if not api_key:
        return False
    
    parts = api_key.split('_')
    
    # 格式: prefix_env_randompart
    if len(parts) != 3:
        return False
    
    prefix, env, random_part = parts
    
    # 验证前缀
    if prefix not in ['ak', 'sk']:
        return False
    
    # 验证环境
    if env not in ['live', 'test']:
        return False
    
    # 验证随机部分长度
    if len(random_part) != 32:
        return False
    
    return True


class TokenBlacklist:
    """Token黑名单管理（简化实现）"""
    
    def __init__(self):
        # 实际项目中应该使用Redis或数据库
        self._blacklisted_tokens = set()
    
    def add_token(self, token: str) -> None:
        """将Token加入黑名单"""
        self._blacklisted_tokens.add(token)
    
    def is_blacklisted(self, token: str) -> bool:
        """检查Token是否在黑名单中"""
        return token in self._blacklisted_tokens
    
    def remove_expired_tokens(self) -> None:
        """清理过期Token（定期清理任务）"""
        # TODO: 实现过期Token清理逻辑
        pass


# 全局Token黑名单实例
token_blacklist = TokenBlacklist()


def logout_token(token: str) -> None:
    """
    登出Token（加入黑名单）
    
    Args:
        token: 要登出的Token
    """
    token_blacklist.add_token(token)


def is_token_valid(token: str) -> bool:
    """
    检查Token是否有效（未过期且未被注销）
    
    Args:
        token: JWT Token
        
    Returns:
        bool: Token是否有效
    """
    # 检查黑名单
    if token_blacklist.is_blacklisted(token):
        return False
    
    try:
        # 验证Token格式和过期时间
        verify_token(token)
        return True
    except (TokenExpiredError, InvalidTokenError):
        return False


def extract_token_from_header(authorization: str) -> str:
    """
    从Authorization头中提取Token
    
    Args:
        authorization: Authorization头值（格式：Bearer <token>）
        
    Returns:
        str: JWT Token
        
    Raises:
        InvalidTokenError: 头格式无效
    """
    if not authorization:
        raise InvalidTokenError("Missing authorization header")
    
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidTokenError("Invalid authorization header format")
    
    return parts[1] 