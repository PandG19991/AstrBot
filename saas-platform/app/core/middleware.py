"""
应用中间件
包含租户上下文、请求日志、错误处理等中间件
"""
import time
import uuid
from typing import Callable
from uuid import UUID

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.core.security import (
    get_tenant_id_from_token, 
    extract_token_from_header,
    TokenExpiredError,
    InvalidTokenError
)
from app.api.deps import tenant_context


logger = structlog.get_logger()


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    租户上下文中间件
    
    从JWT Token中提取租户ID并设置到上下文中，
    确保后续的业务逻辑可以获取当前租户信息
    """
    
    # 不需要租户验证的路径
    EXCLUDED_PATHS = [
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/webhooks",  # 使用API Key认证
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，设置租户上下文
        
        Args:
            request: HTTP请求
            call_next: 下一个处理器
            
        Returns:
            Response: HTTP响应
        """
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 记录请求开始
        start_time = time.time()
        
        try:
            # 检查是否需要租户验证
            if self._should_skip_tenant_check(request.url.path):
                logger.info(
                    "request_start",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    skip_tenant_check=True
                )
                response = await call_next(request)
            else:
                # 提取租户ID并设置上下文
                tenant_id = await self._extract_and_set_tenant_context(request)
                
                logger.info(
                    "request_start",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    tenant_id=str(tenant_id) if tenant_id else None
                )
                
                # 执行后续处理
                response = await call_next(request)
            
            # 记录请求完成
            process_time = time.time() - start_time
            logger.info(
                "request_complete",
                request_id=request_id,
                status_code=response.status_code,
                process_time=f"{process_time:.4f}s"
            )
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            
            return response
            
        except HTTPException as e:
            # 处理HTTP异常
            process_time = time.time() - start_time
            logger.warning(
                "request_http_exception",
                request_id=request_id,
                status_code=e.status_code,
                detail=e.detail,
                process_time=f"{process_time:.4f}s"
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "detail": e.detail,
                    "request_id": request_id,
                    "error_type": "http_exception"
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Process-Time": f"{process_time:.4f}"
                }
            )
            
        except Exception as e:
            # 处理未捕获的异常
            process_time = time.time() - start_time
            logger.error(
                "request_unhandled_exception",
                request_id=request_id,
                error=str(e),
                process_time=f"{process_time:.4f}s",
                exc_info=True
            )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                    "error_type": "internal_error"
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Process-Time": f"{process_time:.4f}"
                }
            )
            
        finally:
            # 清理租户上下文
            tenant_context.clear()
    
    def _should_skip_tenant_check(self, path: str) -> bool:
        """
        检查是否应该跳过租户验证
        
        Args:
            path: 请求路径
            
        Returns:
            bool: 是否跳过
        """
        # 精确匹配
        if path in self.EXCLUDED_PATHS:
            return True
        
        # 前缀匹配
        for excluded_path in self.EXCLUDED_PATHS:
            if path.startswith(excluded_path.rstrip('/') + '/'):
                return True
        
        return False
    
    async def _extract_and_set_tenant_context(
        self, 
        request: Request
    ) -> UUID | None:
        """
        从请求中提取租户ID并设置上下文
        
        Args:
            request: HTTP请求
            
        Returns:
            UUID | None: 租户ID
            
        Raises:
            HTTPException: 认证失败或租户信息缺失
        """
        tenant_id = None
        
        try:
            # 优先从Authorization头获取JWT Token
            authorization = request.headers.get("Authorization")
            if authorization:
                token = extract_token_from_header(authorization)
                tenant_id = get_tenant_id_from_token(token)
                
                if tenant_id:
                    tenant_context.set_tenant_id(tenant_id)
                    return tenant_id
            
            # 备选：从API Key获取租户信息
            api_key = request.headers.get("X-API-Key")
            if api_key:
                # TODO: 从数据库根据API Key查找租户
                # 这里需要数据库查询，简化实现先跳过
                pass
            
            # 如果没有找到租户信息，抛出认证异常
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )
            
        except (TokenExpiredError, InvalidTokenError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "tenant_context_extraction_failed",
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract tenant context"
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全头中间件
    
    添加安全相关的HTTP响应头
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，添加安全头
        
        Args:
            request: HTTP请求
            call_next: 下一个处理器
            
        Returns:
            Response: 带安全头的HTTP响应
        """
        response = await call_next(request)
        
        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # 如果是HTTPS，添加HSTS头
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件
    
    简化实现，实际项目中应该使用Redis等存储
    """
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        """
        初始化速率限制中间件
        
        Args:
            app: FastAPI应用
            calls: 允许的调用次数
            period: 时间窗口（秒）
        """
        super().__init__(app)
        self.calls = calls
        self.period = period
        self._requests = {}  # 简化实现，生产环境应使用Redis
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，检查速率限制
        
        Args:
            request: HTTP请求
            call_next: 下一个处理器
            
        Returns:
            Response: HTTP响应
            
        Raises:
            HTTPException: 超过速率限制
        """
        # 获取客户端标识（简化实现）
        client_id = self._get_client_id(request)
        
        # 检查速率限制
        if self._is_rate_limited(client_id):
            logger.warning(
                "rate_limit_exceeded",
                client_id=client_id,
                path=request.url.path
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        # 记录请求
        self._record_request(client_id)
        
        return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """
        获取客户端标识
        
        Args:
            request: HTTP请求
            
        Returns:
            str: 客户端标识
        """
        # 优先使用租户ID（如果已设置）
        tenant_id = tenant_context.get_tenant_id()
        if tenant_id:
            return f"tenant:{tenant_id}"
        
        # 备选：使用IP地址
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _is_rate_limited(self, client_id: str) -> bool:
        """
        检查是否超过速率限制
        
        Args:
            client_id: 客户端标识
            
        Returns:
            bool: 是否超过限制
        """
        now = time.time()
        
        # 获取客户端请求记录
        if client_id not in self._requests:
            return False
        
        requests = self._requests[client_id]
        
        # 清理过期记录
        requests = [req_time for req_time in requests if now - req_time < self.period]
        self._requests[client_id] = requests
        
        # 检查是否超过限制
        return len(requests) >= self.calls
    
    def _record_request(self, client_id: str) -> None:
        """
        记录请求
        
        Args:
            client_id: 客户端标识
        """
        now = time.time()
        
        if client_id not in self._requests:
            self._requests[client_id] = []
        
        self._requests[client_id].append(now)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    
    记录详细的请求和响应信息
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，记录日志
        
        Args:
            request: HTTP请求
            call_next: 下一个处理器
            
        Returns:
            Response: HTTP响应
        """
        # 获取请求信息
        request_info = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
        }
        
        # 过滤敏感信息
        if "authorization" in request_info["headers"]:
            request_info["headers"]["authorization"] = "Bearer [REDACTED]"
        
        if "x-api-key" in request_info["headers"]:
            request_info["headers"]["x-api-key"] = "[REDACTED]"
        
        # 记录请求开始
        logger.debug("request_details", **request_info)
        
        # 执行请求
        response = await call_next(request)
        
        # 记录响应信息
        response_info = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
        }
        
        logger.debug("response_details", **response_info)
        
        return response 