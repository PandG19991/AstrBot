"""
会话总结分析器

负责用户行为分析和服务质量评估
"""
import logging
from typing import Dict, Any, List
from uuid import UUID

from app.services.llm.base_provider import BaseLLMProvider, LLMMessage
from app.schemas.message import MessageRead

# 配置日志
logger = logging.getLogger(__name__)


class SessionAnalyzer:
    """会话分析器"""
    
    def __init__(self):
        """初始化分析器"""
        pass
    
    async def analyze_user_behavior(
        self, 
        messages: List[MessageRead], 
        tenant_id: UUID,
        llm_provider: BaseLLMProvider
    ) -> Dict[str, Any]:
        """
        分析用户行为
        
        Args:
            messages: 消息列表
            tenant_id: 租户ID
            llm_provider: LLM提供商
            
        Returns:
            Dict[str, Any]: 用户行为分析结果
        """
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        
        if not user_messages:
            return {"analysis": "无用户消息", "patterns": {}}
        
        # 分析回复模式
        response_pattern = self._analyze_response_pattern(messages)
        
        # 检测情感指标
        emotion_analysis = await self._detect_emotion_indicators(
            user_messages, tenant_id, llm_provider
        )
        
        # 评估紧急程度
        urgency_level = self._assess_urgency_level(user_messages)
        
        # 确定交互风格
        interaction_style = self._determine_interaction_style(user_messages)
        
        return {
            "response_pattern": response_pattern,
            "emotion_analysis": emotion_analysis,
            "urgency_level": urgency_level,
            "interaction_style": interaction_style,
            "user_message_count": len(user_messages),
            "analysis_timestamp": messages[-1].created_at.isoformat() if messages else None
        }
    
    def _analyze_response_pattern(self, messages: List[MessageRead]) -> str:
        """分析用户回复模式"""
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        agent_messages = [msg for msg in messages if msg.message_type == "agent"]
        
        if not user_messages:
            return "无用户消息"
        
        # 分析连续提问、快速回复等模式
        quick_responses = 0
        for i in range(1, len(user_messages)):
            time_diff = (user_messages[i].created_at - user_messages[i-1].created_at).total_seconds()
            if time_diff < 30:  # 30秒内的快速回复
                quick_responses += 1
        
        if quick_responses > len(user_messages) * 0.3:
            return "急切型 - 用户回复较为急切"
        elif len(user_messages) > len(agent_messages) * 1.5:
            return "健谈型 - 用户主动交流较多"
        else:
            return "正常型 - 用户交流模式正常"
    
    async def _detect_emotion_indicators(
        self, 
        user_messages: List[MessageRead], 
        tenant_id: UUID,
        llm_provider: BaseLLMProvider
    ) -> Dict[str, Any]:
        """检测情感指标"""
        # 关键词分析
        positive_keywords = ["谢谢", "感谢", "好的", "满意", "不错", "棒", "赞"]
        negative_keywords = ["不满", "投诉", "问题", "错误", "失望", "糟糕", "差"]
        
        positive_count = 0
        negative_count = 0
        
        for message in user_messages:
            content = message.content.lower()
            positive_count += sum(1 for keyword in positive_keywords if keyword in content)
            negative_count += sum(1 for keyword in negative_keywords if keyword in content)
        
        # 使用LLM进行深度情感分析
        overall_tone = "neutral"
        confidence = 0.5
        
        if len(user_messages) > 0:
            try:
                # 构建情感分析提示
                messages_text = "\n".join([f"用户: {msg.content}" for msg in user_messages[-3:]])
                
                llm_messages = [
                    LLMMessage(role="system", content="你是一个情感分析专家。请分析用户消息的整体情感倾向。"),
                    LLMMessage(role="user", content=f"请分析以下用户消息的情感倾向，返回 positive/negative/neutral 之一：\n{messages_text}")
                ]
                
                response = await llm_provider.generate_response(llm_messages)
                if response and response.content:
                    if "positive" in response.content.lower():
                        overall_tone = "positive"
                        confidence = 0.8
                    elif "negative" in response.content.lower():
                        overall_tone = "negative"
                        confidence = 0.8
                        
            except Exception as e:
                logger.warning("emotion_analysis_llm_error", error=str(e))
        
        # 基于关键词确定整体基调
        if positive_count > negative_count:
            keyword_tone = "positive"
        elif negative_count > positive_count:
            keyword_tone = "negative"
        else:
            keyword_tone = "neutral"
        
        return {
            "overall_tone": overall_tone,
            "keyword_tone": keyword_tone,
            "positive_indicators": positive_count,
            "negative_indicators": negative_count,
            "confidence": confidence
        }
    
    def _assess_urgency_level(self, user_messages: List[MessageRead]) -> str:
        """评估紧急程度"""
        if not user_messages:
            return "low"
        
        # 检查紧急关键词
        urgent_keywords = ["紧急", "急", "立即", "马上", "赶快", "urgent", "asap"]
        urgent_count = 0
        
        for message in user_messages:
            content = message.content.lower()
            urgent_count += sum(1 for keyword in urgent_keywords if keyword in content)
        
        # 检查感叹号和问号频率
        punctuation_count = sum(
            msg.content.count('!') + msg.content.count('？') + msg.content.count('?')
            for msg in user_messages
        )
        
        if urgent_count > 0 or punctuation_count > len(user_messages) * 1.5:
            return "high"
        elif punctuation_count > len(user_messages):
            return "medium"
        else:
            return "low"
    
    def _determine_interaction_style(self, user_messages: List[MessageRead]) -> str:
        """确定交互风格"""
        if not user_messages:
            return "unknown"
        
        # 分析消息长度
        avg_length = sum(len(msg.content) for msg in user_messages) / len(user_messages)
        
        # 分析礼貌用词
        polite_words = ["请", "谢谢", "麻烦", "不好意思", "打扰", "please", "thank"]
        polite_count = sum(
            sum(1 for word in polite_words if word in msg.content.lower())
            for msg in user_messages
        )
        
        if avg_length > 50 and polite_count > 0:
            return "formal"  # 正式
        elif avg_length < 20:
            return "casual"  # 随意
        elif polite_count > len(user_messages) * 0.5:
            return "polite"  # 礼貌
        else:
            return "direct"  # 直接
    
    async def assess_service_quality(
        self, 
        messages: List[MessageRead], 
        tenant_id: UUID,
        llm_provider: BaseLLMProvider
    ) -> Dict[str, Any]:
        """
        评估服务质量
        
        Args:
            messages: 消息列表
            tenant_id: 租户ID
            llm_provider: LLM提供商
            
        Returns:
            Dict[str, Any]: 服务质量评估结果
        """
        agent_messages = [msg for msg in messages if msg.message_type == "agent"]
        
        if not agent_messages:
            return {"rating": 0, "analysis": "无客服回复"}
        
        # 计算平均响应时间
        avg_response_time = self._calculate_avg_response_time(messages)
        
        # 评估响应及时性
        timeliness = self._rate_response_timeliness(avg_response_time)
        
        # 评估回复完整性
        completeness = self._assess_response_completeness(agent_messages)
        
        # 评估专业语调
        professional_tone = await self._assess_professional_tone(
            agent_messages, tenant_id, llm_provider
        )
        
        # 评估问题解决情况
        problem_resolution = self._assess_problem_resolution(messages)
        
        # 计算总体评分
        overall_rating = self._calculate_overall_rating({
            "timeliness": timeliness,
            "completeness": completeness,
            "professional_tone": professional_tone,
            "problem_resolution": problem_resolution
        })
        
        return {
            "overall_rating": overall_rating,
            "timeliness": timeliness,
            "completeness": completeness,
            "professional_tone": professional_tone,
            "problem_resolution": problem_resolution,
            "agent_message_count": len(agent_messages)
        }
    
    def _calculate_avg_response_time(self, messages: List[MessageRead]) -> float:
        """计算平均响应时间"""
        if len(messages) < 2:
            return 0
        
        response_times = []
        for i in range(1, len(messages)):
            if (messages[i-1].message_type == "user" and 
                messages[i].message_type == "agent"):
                time_diff = (messages[i].created_at - messages[i-1].created_at).total_seconds()
                response_times.append(time_diff)
        
        return sum(response_times) / len(response_times) if response_times else 0
    
    def _rate_response_timeliness(self, avg_response_time: float) -> Dict[str, Any]:
        """评估响应及时性"""
        if avg_response_time <= 30:
            rating = "excellent"
            score = 5
        elif avg_response_time <= 60:
            rating = "good"
            score = 4
        elif avg_response_time <= 120:
            rating = "average"
            score = 3
        elif avg_response_time <= 300:
            rating = "slow"
            score = 2
        else:
            rating = "very_slow"
            score = 1
        
        return {
            "rating": rating,
            "score": score,
            "avg_time_seconds": avg_response_time
        }
    
    def _assess_response_completeness(self, agent_messages: List[MessageRead]) -> Dict[str, Any]:
        """评估回复完整性"""
        if not agent_messages:
            return {"score": 0, "analysis": "无客服回复"}
        
        # 分析回复长度
        avg_length = sum(len(msg.content) for msg in agent_messages) / len(agent_messages)
        
        # 检查是否包含常见的完整回复要素
        helpful_phrases = [
            "为您", "帮助", "解决", "处理", "联系", "咨询", 
            "感谢", "不客气", "还有什么", "其他问题"
        ]
        
        helpful_count = sum(
            sum(1 for phrase in helpful_phrases if phrase in msg.content)
            for msg in agent_messages
        )
        
        if avg_length > 30 and helpful_count > len(agent_messages) * 0.3:
            score = 5
            analysis = "回复完整详细"
        elif avg_length > 20 and helpful_count > 0:
            score = 4
            analysis = "回复较为完整"
        elif avg_length > 10:
            score = 3
            analysis = "回复一般"
        else:
            score = 2
            analysis = "回复过于简短"
        
        return {
            "score": score,
            "analysis": analysis,
            "avg_length": avg_length,
            "helpful_phrases_count": helpful_count
        }
    
    async def _assess_professional_tone(
        self, 
        agent_messages: List[MessageRead], 
        tenant_id: UUID,
        llm_provider: BaseLLMProvider
    ) -> Dict[str, Any]:
        """评估专业语调"""
        if not agent_messages:
            return {"score": 0, "analysis": "无客服回复"}
        
        # 关键词分析
        professional_words = ["您好", "请", "谢谢", "为您服务", "很抱歉", "理解"]
        unprofessional_words = ["哎", "额", "嗯", "啊", "哦"]
        
        professional_count = sum(
            sum(1 for word in professional_words if word in msg.content)
            for msg in agent_messages
        )
        
        unprofessional_count = sum(
            sum(1 for word in unprofessional_words if word in msg.content)
            for msg in agent_messages
        )
        
        # 基本评分
        if professional_count > unprofessional_count and professional_count > 0:
            score = 4
            analysis = "语调专业"
        elif unprofessional_count == 0:
            score = 3
            analysis = "语调中性"
        else:
            score = 2
            analysis = "语调不够专业"
        
        return {
            "score": score,
            "analysis": analysis,
            "professional_indicators": professional_count,
            "unprofessional_indicators": unprofessional_count
        }
    
    def _assess_problem_resolution(self, messages: List[MessageRead]) -> Dict[str, Any]:
        """评估问题解决情况"""
        if not messages:
            return {"score": 0, "status": "unknown"}
        
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        
        # 检查最后几条用户消息的情感
        last_user_messages = user_messages[-2:] if len(user_messages) >= 2 else user_messages
        
        satisfied_indicators = ["谢谢", "解决了", "明白了", "好的", "满意"]
        unsatisfied_indicators = ["还是不行", "没解决", "不明白", "还有问题"]
        
        satisfied_count = sum(
            sum(1 for indicator in satisfied_indicators if indicator in msg.content)
            for msg in last_user_messages
        )
        
        unsatisfied_count = sum(
            sum(1 for indicator in unsatisfied_indicators if indicator in msg.content)
            for msg in last_user_messages
        )
        
        if satisfied_count > 0 and unsatisfied_count == 0:
            return {"score": 5, "status": "resolved", "confidence": "high"}
        elif satisfied_count > unsatisfied_count:
            return {"score": 4, "status": "likely_resolved", "confidence": "medium"}
        elif unsatisfied_count > 0:
            return {"score": 2, "status": "unresolved", "confidence": "high"}
        else:
            return {"score": 3, "status": "unknown", "confidence": "low"}
    
    def _calculate_overall_rating(self, assessment: Dict[str, Any]) -> float:
        """计算总体评分"""
        weights = {
            "timeliness": 0.3,
            "completeness": 0.25,
            "professional_tone": 0.25,
            "problem_resolution": 0.2
        }
        
        total_score = 0
        total_weight = 0
        
        for dimension, weight in weights.items():
            if dimension in assessment and "score" in assessment[dimension]:
                total_score += assessment[dimension]["score"] * weight
                total_weight += weight
        
        return round(total_score / total_weight if total_weight > 0 else 0, 2) 