"""
数据统计与分析服务

提供多维度的数据统计分析功能，支持：
- 会话统计分析
- 消息统计分析
- 实时监控数据
- 业务报表生成
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import func, and_, or_, case, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session import Session
from app.models.message import Message
from app.models.user import User
from app.schemas.analytics import (
    SessionStatsResponse,
    MessageStatsResponse,
    TimeSeriesData,
    RealtimeMetrics,
    TrendAnalysis,
    AnalyticsFilter
)

# 配置日志
logger = logging.getLogger(__name__)


class AnalyticsService:
    """数据分析服务类"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化分析服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def get_session_stats(
        self,
        tenant_id: UUID,
        filters: AnalyticsFilter
    ) -> SessionStatsResponse:
        """
        获取会话统计数据
        
        Args:
            tenant_id: 租户ID
            filters: 过滤条件
            
        Returns:
            会话统计响应
        """
        try:
            # 构建基础查询
            query = self.db.query(Session).filter(Session.tenant_id == tenant_id)
            
            # 应用时间过滤
            if filters.start_date:
                query = query.filter(Session.created_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(Session.created_at <= filters.end_date)
            
            # 应用状态过滤
            if filters.status:
                query = query.filter(Session.status.in_(filters.status))
            
            # 总会话数
            total_sessions = await query.count()
            
            # 状态分布统计
            status_stats = await self.db.query(
                Session.status,
                func.count(Session.id).label('count')
            ).filter(
                Session.tenant_id == tenant_id,
                Session.created_at >= filters.start_date if filters.start_date else True,
                Session.created_at <= filters.end_date if filters.end_date else True
            ).group_by(Session.status).all()
            
            # 平均会话时长
            avg_duration = await self.db.query(
                func.avg(
                    extract('epoch', Session.updated_at - Session.created_at)
                ).label('avg_duration')
            ).filter(
                Session.tenant_id == tenant_id,
                Session.status == 'closed',
                Session.created_at >= filters.start_date if filters.start_date else True,
                Session.created_at <= filters.end_date if filters.end_date else True
            ).scalar()
            
            # 按时间分组的会话数
            time_series = await self._get_sessions_time_series(tenant_id, filters)
            
            logger.info(
                "session_stats_retrieved",
                tenant_id=str(tenant_id),
                total_sessions=total_sessions,
                time_range=f"{filters.start_date} to {filters.end_date}"
            )
            
            return SessionStatsResponse(
                total_sessions=total_sessions,
                status_distribution={stat.status: stat.count for stat in status_stats},
                avg_duration_seconds=avg_duration or 0,
                time_series=time_series
            )
            
        except Exception as e:
            logger.error(
                "session_stats_failed",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise
    
    async def get_message_stats(
        self,
        tenant_id: UUID,
        filters: AnalyticsFilter
    ) -> MessageStatsResponse:
        """
        获取消息统计数据
        
        Args:
            tenant_id: 租户ID
            filters: 过滤条件
            
        Returns:
            消息统计响应
        """
        try:
            # 构建基础查询
            query = self.db.query(Message).filter(Message.tenant_id == tenant_id)
            
            # 应用时间过滤
            if filters.start_date:
                query = query.filter(Message.created_at >= filters.start_date)
            if filters.end_date:
                query = query.filter(Message.created_at <= filters.end_date)
            
            # 应用类型过滤
            if filters.message_types:
                query = query.filter(Message.type.in_(filters.message_types))
            
            # 总消息数
            total_messages = await query.count()
            
            # 消息类型分布
            type_stats = await self.db.query(
                Message.type,
                func.count(Message.id).label('count')
            ).filter(
                Message.tenant_id == tenant_id,
                Message.created_at >= filters.start_date if filters.start_date else True,
                Message.created_at <= filters.end_date if filters.end_date else True
            ).group_by(Message.type).all()
            
            # 平均响应时间（仅适用于客服回复）
            avg_response_time = await self._calculate_avg_response_time(tenant_id, filters)
            
            # 按时间分组的消息数
            time_series = await self._get_messages_time_series(tenant_id, filters)
            
            # 最活跃的会话
            top_sessions = await self._get_top_active_sessions(tenant_id, filters)
            
            logger.info(
                "message_stats_retrieved",
                tenant_id=str(tenant_id),
                total_messages=total_messages,
                time_range=f"{filters.start_date} to {filters.end_date}"
            )
            
            return MessageStatsResponse(
                total_messages=total_messages,
                type_distribution={stat.type: stat.count for stat in type_stats},
                avg_response_time_seconds=avg_response_time,
                time_series=time_series,
                top_active_sessions=top_sessions
            )
            
        except Exception as e:
            logger.error(
                "message_stats_failed",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise
    
    async def get_realtime_metrics(self, tenant_id: UUID) -> RealtimeMetrics:
        """
        获取实时监控指标
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            实时指标数据
        """
        try:
            now = datetime.utcnow()
            one_hour_ago = now - timedelta(hours=1)
            
            # 活跃会话数
            active_sessions = await self.db.query(Session).filter(
                Session.tenant_id == tenant_id,
                Session.status == 'active'
            ).count()
            
            # 过去1小时新会话数
            new_sessions_hour = await self.db.query(Session).filter(
                Session.tenant_id == tenant_id,
                Session.created_at >= one_hour_ago
            ).count()
            
            # 过去1小时消息数
            messages_hour = await self.db.query(Message).filter(
                Message.tenant_id == tenant_id,
                Message.created_at >= one_hour_ago
            ).count()
            
            # 过去1小时平均响应时间
            avg_response_time = await self._calculate_avg_response_time(
                tenant_id,
                AnalyticsFilter(start_date=one_hour_ago, end_date=now)
            )
            
            logger.info(
                "realtime_metrics_retrieved",
                tenant_id=str(tenant_id),
                active_sessions=active_sessions,
                new_sessions_hour=new_sessions_hour
            )
            
            return RealtimeMetrics(
                active_sessions=active_sessions,
                new_sessions_last_hour=new_sessions_hour,
                messages_last_hour=messages_hour,
                avg_response_time_seconds=avg_response_time,
                timestamp=now
            )
            
        except Exception as e:
            logger.error(
                "realtime_metrics_failed",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise
    
    async def get_trend_analysis(
        self,
        tenant_id: UUID,
        days: int = 7
    ) -> TrendAnalysis:
        """
        获取趋势分析数据
        
        Args:
            tenant_id: 租户ID
            days: 分析天数
            
        Returns:
            趋势分析结果
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # 获取两个时间段的数据进行对比
            current_period = AnalyticsFilter(start_date=start_date, end_date=end_date)
            previous_period = AnalyticsFilter(
                start_date=start_date - timedelta(days=days),
                end_date=start_date
            )
            
            # 当前期间统计
            current_sessions = await self._count_sessions_in_period(tenant_id, current_period)
            current_messages = await self._count_messages_in_period(tenant_id, current_period)
            
            # 前期统计
            previous_sessions = await self._count_sessions_in_period(tenant_id, previous_period)
            previous_messages = await self._count_messages_in_period(tenant_id, previous_period)
            
            # 计算变化率
            sessions_change = self._calculate_change_rate(previous_sessions, current_sessions)
            messages_change = self._calculate_change_rate(previous_messages, current_messages)
            
            # 按小时分组的活动分布
            hourly_distribution = await self._get_hourly_activity_distribution(
                tenant_id, current_period
            )
            
            logger.info(
                "trend_analysis_retrieved",
                tenant_id=str(tenant_id),
                days=days,
                sessions_change=sessions_change,
                messages_change=messages_change
            )
            
            return TrendAnalysis(
                period_days=days,
                sessions_change_percent=sessions_change,
                messages_change_percent=messages_change,
                hourly_activity_distribution=hourly_distribution,
                analysis_date=end_date
            )
            
        except Exception as e:
            logger.error(
                "trend_analysis_failed",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise
    
    async def _get_sessions_time_series(
        self,
        tenant_id: UUID,
        filters: AnalyticsFilter
    ) -> List[TimeSeriesData]:
        """获取会话时间序列数据"""
        try:
            # 按日期分组统计
            results = await self.db.query(
                func.date(Session.created_at).label('date'),
                func.count(Session.id).label('count')
            ).filter(
                Session.tenant_id == tenant_id,
                Session.created_at >= filters.start_date if filters.start_date else True,
                Session.created_at <= filters.end_date if filters.end_date else True
            ).group_by(func.date(Session.created_at)).order_by('date').all()
            
            return [
                TimeSeriesData(timestamp=result.date, value=result.count)
                for result in results
            ]
            
        except Exception as e:
            logger.error("sessions_time_series_failed", error=str(e))
            return []
    
    async def _get_messages_time_series(
        self,
        tenant_id: UUID,
        filters: AnalyticsFilter
    ) -> List[TimeSeriesData]:
        """获取消息时间序列数据"""
        try:
            # 按日期分组统计
            results = await self.db.query(
                func.date(Message.created_at).label('date'),
                func.count(Message.id).label('count')
            ).filter(
                Message.tenant_id == tenant_id,
                Message.created_at >= filters.start_date if filters.start_date else True,
                Message.created_at <= filters.end_date if filters.end_date else True
            ).group_by(func.date(Message.created_at)).order_by('date').all()
            
            return [
                TimeSeriesData(timestamp=result.date, value=result.count)
                for result in results
            ]
            
        except Exception as e:
            logger.error("messages_time_series_failed", error=str(e))
            return []
    
    async def _calculate_avg_response_time(
        self,
        tenant_id: UUID,
        filters: AnalyticsFilter
    ) -> float:
        """计算平均响应时间"""
        try:
            # 查找用户消息和紧随其后的客服回复
            user_messages = self.db.query(Message).filter(
                Message.tenant_id == tenant_id,
                Message.type == 'incoming',
                Message.created_at >= filters.start_date if filters.start_date else True,
                Message.created_at <= filters.end_date if filters.end_date else True
            ).subquery()
            
            agent_responses = self.db.query(Message).filter(
                Message.tenant_id == tenant_id,
                Message.type == 'outgoing',
                Message.created_at >= filters.start_date if filters.start_date else True,
                Message.created_at <= filters.end_date if filters.end_date else True
            ).subquery()
            
            # 计算响应时间差
            avg_response = await self.db.query(
                func.avg(
                    extract('epoch', agent_responses.c.created_at - user_messages.c.created_at)
                ).label('avg_response_time')
            ).join(
                agent_responses,
                and_(
                    user_messages.c.session_id == agent_responses.c.session_id,
                    agent_responses.c.created_at > user_messages.c.created_at
                )
            ).scalar()
            
            return avg_response or 0.0
            
        except Exception as e:
            logger.error("avg_response_time_calculation_failed", error=str(e))
            return 0.0
    
    async def _get_top_active_sessions(
        self,
        tenant_id: UUID,
        filters: AnalyticsFilter,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取最活跃的会话"""
        try:
            results = await self.db.query(
                Message.session_id,
                func.count(Message.id).label('message_count'),
                func.min(Message.created_at).label('first_message'),
                func.max(Message.created_at).label('last_message')
            ).filter(
                Message.tenant_id == tenant_id,
                Message.created_at >= filters.start_date if filters.start_date else True,
                Message.created_at <= filters.end_date if filters.end_date else True
            ).group_by(
                Message.session_id
            ).order_by(
                func.count(Message.id).desc()
            ).limit(limit).all()
            
            return [
                {
                    'session_id': str(result.session_id),
                    'message_count': result.message_count,
                    'first_message': result.first_message,
                    'last_message': result.last_message,
                    'duration_seconds': (result.last_message - result.first_message).total_seconds()
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error("top_active_sessions_failed", error=str(e))
            return []
    
    async def _count_sessions_in_period(
        self,
        tenant_id: UUID,
        period: AnalyticsFilter
    ) -> int:
        """统计指定时间段的会话数"""
        try:
            count = await self.db.query(Session).filter(
                Session.tenant_id == tenant_id,
                Session.created_at >= period.start_date,
                Session.created_at <= period.end_date
            ).count()
            
            return count
            
        except Exception as e:
            logger.error("count_sessions_failed", error=str(e))
            return 0
    
    async def _count_messages_in_period(
        self,
        tenant_id: UUID,
        period: AnalyticsFilter
    ) -> int:
        """统计指定时间段的消息数"""
        try:
            count = await self.db.query(Message).filter(
                Message.tenant_id == tenant_id,
                Message.created_at >= period.start_date,
                Message.created_at <= period.end_date
            ).count()
            
            return count
            
        except Exception as e:
            logger.error("count_messages_failed", error=str(e))
            return 0
    
    def _calculate_change_rate(self, previous: int, current: int) -> float:
        """计算变化率"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return ((current - previous) / previous) * 100.0
    
    async def _get_hourly_activity_distribution(
        self,
        tenant_id: UUID,
        period: AnalyticsFilter
    ) -> Dict[int, int]:
        """获取按小时分布的活动统计"""
        try:
            results = await self.db.query(
                extract('hour', Message.created_at).label('hour'),
                func.count(Message.id).label('count')
            ).filter(
                Message.tenant_id == tenant_id,
                Message.created_at >= period.start_date,
                Message.created_at <= period.end_date
            ).group_by(extract('hour', Message.created_at)).all()
            
            # 初始化24小时的字典
            hourly_dist = {hour: 0 for hour in range(24)}
            
            # 填充实际数据
            for result in results:
                hourly_dist[int(result.hour)] = result.count
            
            return hourly_dist
            
        except Exception as e:
            logger.error("hourly_distribution_failed", error=str(e))
            return {hour: 0 for hour in range(24)}