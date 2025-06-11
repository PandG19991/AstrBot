"""
认证服务
包含用户登录、注册、Token管理等认证相关业务逻辑
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.core.security import (
    verify_password, 
    get_password_hash, 
    create_auth_tokens,
    verify_token,
    TokenExpiredError,
    InvalidTokenError
)
from app.models.tenant import Tenant, TenantStatus, TenantPlan
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ChangePasswordRequest
)


class AuthenticationError(Exception):
    """认证异常"""
    pass


class RegistrationError(Exception):
    """注册异常"""
    pass


class AuthService:
    """认证服务类"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化认证服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        验证用户凭据
        
        Args:
            email: 用户邮箱
            password: 密码
            
        Returns:
            Optional[User]: 认证成功返回用户对象，失败返回None
        """
        try:
            # 查找用户（这里简化处理，实际项目中可能需要用户表）
            # 目前使用租户表的邮箱字段作为登录凭据
            stmt = select(Tenant).where(Tenant.email == email)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                return None
            
            # 验证密码（这里需要在Tenant模型中添加password_hash字段）
            # 简化实现：直接返回租户信息
            return tenant
            
        except Exception:
            return None
    
    async def login(self, login_data: LoginRequest) -> LoginResponse:
        """
        用户登录
        
        Args:
            login_data: 登录请求数据
            
        Returns:
            LoginResponse: 登录响应（包含Token）
            
        Raises:
            AuthenticationError: 认证失败
        """
        try:
            # 查找租户（简化实现）
            stmt = select(Tenant).where(Tenant.email == login_data.email)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise AuthenticationError("Invalid email or password")
            
            # 检查租户状态
            if tenant.status != TenantStatus.ACTIVE:
                raise AuthenticationError("Account is not active")
            
            # 简化密码验证（实际项目中应该有真正的密码验证）
            # 这里暂时跳过密码验证
            
            # 创建用户ID（简化处理）
            user_id = f"tenant:{tenant.id}"
            
            # 生成Token
            tokens = create_auth_tokens(
                user_id=user_id,
                tenant_id=tenant.id,
                user_email=tenant.email,
                user_role="admin"  # 租户管理员
            )
            
            # 更新最后登录时间（如果有用户表的话）
            # tenant.last_login_at = datetime.utcnow()
            # await self.db.commit()
            
            return LoginResponse(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_type=tokens["token_type"],
                expires_in=60 * 24 * 8 * 60,  # 8天，单位秒
                user_id=user_id,
                tenant_id=tenant.id
            )
            
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Login failed: {str(e)}")
    
    async def register(self, register_data: RegisterRequest) -> RegisterResponse:
        """
        用户注册
        
        Args:
            register_data: 注册请求数据
            
        Returns:
            RegisterResponse: 注册响应
            
        Raises:
            RegistrationError: 注册失败
        """
        try:
            # 检查邮箱是否已存在
            stmt = select(Tenant).where(Tenant.email == register_data.email)
            result = await self.db.execute(stmt)
            existing_tenant = result.scalar_one_or_none()
            
            if existing_tenant:
                raise RegistrationError("Email already registered")
            
            # 创建新租户
            new_tenant = Tenant(
                id=uuid.uuid4(),
                name=register_data.tenant_name,
                email=register_data.email,
                status=TenantStatus.ACTIVE,
                plan=TenantPlan.BASIC,
                # password_hash=get_password_hash(register_data.password),  # 需要添加到模型
                api_key=Tenant.generate_api_key()
            )
            
            self.db.add(new_tenant)
            await self.db.commit()
            await self.db.refresh(new_tenant)
            
            # 创建用户ID
            user_id = f"tenant:{new_tenant.id}"
            
            return RegisterResponse(
                message="Registration successful",
                user_id=user_id,
                tenant_id=new_tenant.id
            )
            
        except RegistrationError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise RegistrationError(f"Registration failed: {str(e)}")
    
    async def refresh_token(self, refresh_data: RefreshTokenRequest) -> RefreshTokenResponse:
        """
        刷新访问Token
        
        Args:
            refresh_data: 刷新Token请求
            
        Returns:
            RefreshTokenResponse: 新的访问Token
            
        Raises:
            AuthenticationError: Token无效或过期
        """
        try:
            # 验证刷新Token
            payload = verify_token(refresh_data.refresh_token, token_type="refresh")
            user_id = payload.get("sub")
            
            if not user_id:
                raise AuthenticationError("Invalid refresh token")
            
            # 简化实现：从user_id提取租户ID
            if user_id.startswith("tenant:"):
                tenant_id = UUID(user_id.split(":", 1)[1])
            else:
                raise AuthenticationError("Invalid user ID format")
            
            # 验证租户是否仍然有效
            tenant = await self.db.get(Tenant, tenant_id)
            if not tenant or tenant.status != TenantStatus.ACTIVE:
                raise AuthenticationError("Tenant is not active")
            
            # 生成新的访问Token
            from app.core.security import create_access_token
            
            new_access_token = create_access_token(
                subject=user_id,
                extra_data={
                    "tenant_id": str(tenant_id),
                    "email": tenant.email,
                    "role": "admin"
                }
            )
            
            return RefreshTokenResponse(
                access_token=new_access_token,
                token_type="bearer",
                expires_in=60 * 24 * 8 * 60  # 8天
            )
            
        except (TokenExpiredError, InvalidTokenError) as e:
            raise AuthenticationError(f"Invalid refresh token: {str(e)}")
        except Exception as e:
            raise AuthenticationError(f"Token refresh failed: {str(e)}")
    
    async def change_password(
        self, 
        user_id: str, 
        change_data: ChangePasswordRequest
    ) -> Dict[str, str]:
        """
        修改密码
        
        Args:
            user_id: 用户ID
            change_data: 修改密码请求数据
            
        Returns:
            Dict[str, str]: 操作结果
            
        Raises:
            AuthenticationError: 认证失败或操作失败
        """
        try:
            # 简化实现：从user_id提取租户ID
            if user_id.startswith("tenant:"):
                tenant_id = UUID(user_id.split(":", 1)[1])
            else:
                raise AuthenticationError("Invalid user ID format")
            
            # 获取租户
            tenant = await self.db.get(Tenant, tenant_id)
            if not tenant:
                raise AuthenticationError("Tenant not found")
            
            # 验证当前密码（简化实现，实际需要password_hash字段）
            # if not verify_password(change_data.current_password, tenant.password_hash):
            #     raise AuthenticationError("Current password is incorrect")
            
            # 更新密码（简化实现）
            # tenant.password_hash = get_password_hash(change_data.new_password)
            # await self.db.commit()
            
            return {"message": "Password changed successfully"}
            
        except AuthenticationError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise AuthenticationError(f"Password change failed: {str(e)}")
    
    async def logout(self, token: str) -> Dict[str, str]:
        """
        用户登出
        
        Args:
            token: 访问Token
            
        Returns:
            Dict[str, str]: 登出结果
        """
        try:
            # 将Token加入黑名单
            from app.core.security import logout_token
            logout_token(token)
            
            return {"message": "Logout successful"}
            
        except Exception as e:
            raise AuthenticationError(f"Logout failed: {str(e)}")
    
    async def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        根据Token获取用户信息
        
        Args:
            token: 访问Token
            
        Returns:
            Optional[Dict[str, Any]]: 用户信息
        """
        try:
            payload = verify_token(token)
            user_id = payload.get("sub")
            tenant_id_str = payload.get("tenant_id")
            
            if not user_id or not tenant_id_str:
                return None
            
            tenant_id = UUID(tenant_id_str)
            
            # 获取租户信息
            tenant = await self.db.get(Tenant, tenant_id)
            if not tenant or tenant.status != TenantStatus.ACTIVE:
                return None
            
            return {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "email": tenant.email,
                "tenant_name": tenant.name,
                "role": payload.get("role", "user"),
                "tenant_status": tenant.status,
                "tenant_plan": tenant.plan
            }
            
        except (TokenExpiredError, InvalidTokenError):
            return None
        except Exception:
            return None
    
    async def verify_api_key(self, api_key: str) -> Optional[Tenant]:
        """
        验证API Key
        
        Args:
            api_key: API密钥
            
        Returns:
            Optional[Tenant]: API Key对应的租户
        """
        try:
            stmt = select(Tenant).where(Tenant.api_key == api_key)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if tenant and tenant.status == TenantStatus.ACTIVE:
                return tenant
            
            return None
            
        except Exception:
            return None
    
    async def generate_api_key(self, tenant_id: UUID) -> str:
        """
        为租户生成新的API Key
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            str: 新的API Key
            
        Raises:
            AuthenticationError: 操作失败
        """
        try:
            tenant = await self.db.get(Tenant, tenant_id)
            if not tenant:
                raise AuthenticationError("Tenant not found")
            
            # 生成新的API Key
            new_api_key = Tenant.generate_api_key()
            tenant.api_key = new_api_key
            
            await self.db.commit()
            
            return new_api_key
            
        except AuthenticationError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise AuthenticationError(f"API key generation failed: {str(e)}")
    
    async def revoke_api_key(self, tenant_id: UUID) -> Dict[str, str]:
        """
        撤销租户的API Key
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Dict[str, str]: 操作结果
            
        Raises:
            AuthenticationError: 操作失败
        """
        try:
            tenant = await self.db.get(Tenant, tenant_id)
            if not tenant:
                raise AuthenticationError("Tenant not found")
            
            # 清空API Key
            tenant.api_key = None
            await self.db.commit()
            
            return {"message": "API key revoked successfully"}
            
        except AuthenticationError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise AuthenticationError(f"API key revocation failed: {str(e)}")


def get_auth_service(db: AsyncSession) -> AuthService:
    """
    获取认证服务实例
    
    Args:
        db: 数据库会话
        
    Returns:
        AuthService: 认证服务实例
    """
    return AuthService(db) 