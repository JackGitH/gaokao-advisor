"""
高考志愿推荐系统 - 算法模块

核心组件：
- SchoolMatcher: 基于排名的学校匹配引擎（冲/稳/保三档推荐）
- SchoolRanker: 多维度排序器（匹配度/稳定性/录取概率）
- TrendAnalyzer: 专业热度趋势分析
- VolunteerMatcher: 兼容旧接口的匹配器
"""
from .ranker import SchoolRanker
from .trend import TrendAnalyzer
from .matcher import SchoolMatcher, VolunteerMatcher

__all__ = ["SchoolMatcher", "VolunteerMatcher", "SchoolRanker", "TrendAnalyzer"]
"""
高考志愿推荐系统 - 算法模块
"""
from .matcher import VolunteerMatcher
from .ranker import SchoolRanker
from .trend import TrendAnalyzer
