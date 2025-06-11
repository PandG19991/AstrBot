"""
数据分析相关的Pydantic模式

定义用于数据统计与分析的请求和响应模型：
- 过滤条件模型
- 统计响应模型
- 时间序列数据模型
- 实时监控指标模型
"""
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsFilter(BaseModel):
    """数据分析过滤条件"""
    
    start_date: Optional[datetime] = Field(
        None, 
        description="开始时间"
    )
    end_date: Optional[datetime] = Field(
        None, 
        description="结束时间"
    )
    status: Optional[List[str]] = Field(
        None, 
        description="会话状态过滤"
    )
    message_types: Optional[List[str]] = Field(
        None, 
        description="消息类型过滤"
    )
    user_ids: Optional[List[str]] = Field(
        None, 
        description="用户ID过滤"
    )


class TimeSeriesData(BaseModel):
    """时间序列数据点"""
    
    timestamp: datetime = Field(description="时间戳")
    value: int = Field(description="数值")


class SessionStatsResponse(BaseModel):
    """会话统计响应"""
    
    total_sessions: int = Field(description="总会话数")
    status_distribution: Dict[str, int] = Field(
        description="状态分布统计"
    )
    avg_duration_seconds: float = Field(
        description="平均会话时长(秒)"
    )
    time_series: List[TimeSeriesData] = Field(
        description="时间序列数据"
    )


class MessageStatsResponse(BaseModel):
    """消息统计响应"""
    
    total_messages: int = Field(description="总消息数")
    type_distribution: Dict[str, int] = Field(
        description="消息类型分布"
    )
    avg_response_time_seconds: float = Field(
        description="平均响应时间(秒)"
    )
    time_series: List[TimeSeriesData] = Field(
        description="时间序列数据"
    )
    top_active_sessions: List[Dict[str, Any]] = Field(
        description="最活跃的会话列表"
    )


class RealtimeMetrics(BaseModel):
    """实时监控指标"""
    
    active_sessions: int = Field(description="当前活跃会话数")
    new_sessions_last_hour: int = Field(
        description="过去1小时新会话数"
    )
    messages_last_hour: int = Field(
        description="过去1小时消息数"
    )
    avg_response_time_seconds: float = Field(
        description="平均响应时间(秒)"
    )
    timestamp: datetime = Field(description="数据时间戳")


class TrendAnalysis(BaseModel):
    """趋势分析结果"""
    
    period_days: int = Field(description="分析周期(天)")
    sessions_change_percent: float = Field(
        description="会话数变化百分比"
    )
    messages_change_percent: float = Field(
        description="消息数变化百分比"
    )
    hourly_activity_distribution: Dict[int, int] = Field(
        description="24小时活动分布"
    )
    analysis_date: datetime = Field(description="分析时间")


class CustomReportRequest(BaseModel):
    """自定义报表请求"""
    
    report_name: str = Field(description="报表名称")
    metrics: List[str] = Field(description="指标列表")
    dimensions: List[str] = Field(description="维度列表")
    filters: AnalyticsFilter = Field(description="过滤条件")
    group_by: Optional[str] = Field(None, description="分组字段")
    sort_by: Optional[str] = Field(None, description="排序字段")
    limit: Optional[int] = Field(10, description="结果限制")


class CustomReportResponse(BaseModel):
    """自定义报表响应"""
    
    report_name: str = Field(description="报表名称")
    generated_at: datetime = Field(description="生成时间")
    data: List[Dict[str, Any]] = Field(description="报表数据")
    summary: Dict[str, Any] = Field(description="汇总信息")
    metadata: Dict[str, Any] = Field(description="元数据")


class DashboardOverview(BaseModel):
    """仪表板概览"""
    
    tenant_id: UUID = Field(description="租户ID")
    period_start: datetime = Field(description="统计开始时间")
    period_end: datetime = Field(description="统计结束时间")
    
    # 核心指标
    total_sessions: int = Field(description="总会话数")
    total_messages: int = Field(description="总消息数")
    active_sessions: int = Field(description="活跃会话数")
    avg_response_time: float = Field(description="平均响应时间")
    
    # 趋势数据
    sessions_trend: List[TimeSeriesData] = Field(description="会话趋势")
    messages_trend: List[TimeSeriesData] = Field(description="消息趋势")
    
    # 分布统计
    session_status_distribution: Dict[str, int] = Field(
        description="会话状态分布"
    )
    message_type_distribution: Dict[str, int] = Field(
        description="消息类型分布"
    )
    hourly_activity: Dict[int, int] = Field(
        description="24小时活动分布"
    )
    
    # 性能指标
    peak_concurrent_sessions: int = Field(description="峰值并发会话数")
    resolution_rate: float = Field(description="问题解决率")
    customer_satisfaction: Optional[float] = Field(
        None, description="客户满意度"
    )


class ExportRequest(BaseModel):
    """数据导出请求"""
    
    export_type: str = Field(description="导出类型: csv, excel, json")
    data_type: str = Field(
        description="数据类型: sessions, messages, analytics"
    )
    filters: AnalyticsFilter = Field(description="过滤条件")
    include_details: bool = Field(
        default=True, description="是否包含详细数据"
    )
    format_options: Optional[Dict[str, Any]] = Field(
        None, description="格式选项"
    )


class ExportResponse(BaseModel):
    """数据导出响应"""
    
    export_id: UUID = Field(description="导出任务ID")
    status: str = Field(description="导出状态")
    download_url: Optional[str] = Field(None, description="下载链接")
    file_size: Optional[int] = Field(None, description="文件大小")
    expires_at: Optional[datetime] = Field(None, description="链接过期时间")
    created_at: datetime = Field(description="创建时间") 