"""
通用数据模式定义
包含标准响应格式、分页响应、错误处理等
"""

from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field

# 泛型类型变量
T = TypeVar('T')


class StandardResponse(BaseModel, Generic[T]):
    """
    标准API响应格式
    
    提供统一的API响应结构，包含成功状态、消息和数据
    """
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    
    class Config:
        """Pydantic配置"""
        json_encoders = {
            # 自定义编码器可以在这里添加
        }
        schema_extra = {
            "example": {
                "success": True,
                "message": "操作成功",
                "data": {}
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    分页响应格式
    
    扩展StandardResponse，增加分页信息
    """
    success: bool = Field(True, description="请求是否成功")
    message: str = Field("", description="响应消息")
    data: List[T] = Field([], description="响应数据列表")
    total: int = Field(0, description="总记录数")
    skip: int = Field(0, description="跳过的记录数")
    limit: int = Field(20, description="每页记录数")
    has_next: bool = Field(False, description="是否有下一页")
    has_prev: bool = Field(False, description="是否有上一页")
    
    def __init__(self, **data):
        """初始化分页响应，自动计算分页状态"""
        super().__init__(**data)
        # 自动计算分页状态
        self.has_next = (self.skip + self.limit) < self.total
        self.has_prev = self.skip > 0
    
    class Config:
        """Pydantic配置"""
        schema_extra = {
            "example": {
                "success": True,
                "message": "查询成功",
                "data": [],
                "total": 100,
                "skip": 0,
                "limit": 20,
                "has_next": True,
                "has_prev": False
            }
        }


class ErrorResponse(BaseModel):
    """
    错误响应格式
    
    用于API错误情况的标准响应
    """
    success: bool = Field(False, description="请求是否成功")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(None, description="错误代码")
    details: Optional[dict] = Field(None, description="详细错误信息")
    
    class Config:
        """Pydantic配置"""
        schema_extra = {
            "example": {
                "success": False,
                "message": "请求失败",
                "error_code": "VALIDATION_ERROR",
                "details": {
                    "field": "email",
                    "issue": "格式不正确"
                }
            }
        }


class HealthCheck(BaseModel):
    """
    健康检查响应
    """
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="API版本")
    timestamp: Optional[str] = Field(None, description="检查时间")
    
    class Config:
        """Pydantic配置"""
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "v1.0.0",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }


# 通用查询参数
class PaginationParams(BaseModel):
    """
    分页查询参数
    """
    skip: int = Field(0, ge=0, description="跳过的记录数")
    limit: int = Field(20, ge=1, le=100, description="每页记录数")
    
    class Config:
        """Pydantic配置"""
        schema_extra = {
            "example": {
                "skip": 0,
                "limit": 20
            }
        }


class SearchParams(PaginationParams):
    """
    搜索查询参数
    """
    search: Optional[str] = Field(None, min_length=1, max_length=100, description="搜索关键词")
    
    class Config:
        """Pydantic配置"""
        schema_extra = {
            "example": {
                "skip": 0,
                "limit": 20,
                "search": "关键词"
            }
        } 