"""
高考志愿推荐系统 - Pydantic 数据模型
定义API请求和响应的数据结构
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ==================== 基础模型 ====================

class SchoolInfo(BaseModel):
    """学校信息"""
    id: Optional[int] = None
    name: str
    province: Optional[str] = None
    city: Optional[str] = None
    type: Optional[str] = Field(None, description="985/211/双一流/普通本科")
    level: Optional[str] = Field(None, description="本科一批/本科二批")
    features: Optional[str] = None


class MajorInfo(BaseModel):
    """专业信息"""
    id: Optional[int] = None
    name: str
    category: Optional[str] = Field(None, description="学科门类")
    hot_trend: Optional[str] = Field(None, description="热门/冷门/平稳")


class AdmissionRecord(BaseModel):
    """录取记录"""
    id: Optional[int] = None
    year: int
    school_id: int
    school_name: Optional[str] = None
    major_id: int
    major_name: Optional[str] = None
    batch: Optional[str] = None
    min_score: Optional[int] = None
    min_rank: Optional[int] = None
    avg_score: Optional[int] = None
    plan_count: Optional[int] = None
    actual_count: Optional[int] = None


class RankingEntry(BaseModel):
    """一分一段表条目"""
    year: int
    score: int
    same_score_count: Optional[int] = None
    cumulative_count: Optional[int] = None


# ==================== 请求模型 ====================

class RecommendRequest(BaseModel):
    """志愿推荐请求"""
    score: int = Field(..., description="高考分数", ge=0, le=750)
    year: int = Field(..., description="高考年份")
    rank: Optional[int] = Field(None, description="位次，如不提供则自动根据分数查询")
    preferred_provinces: Optional[List[str]] = Field(None, description="意向省份列表")
    preferred_majors: Optional[List[str]] = Field(None, description="意向专业类别")
    school_types: Optional[List[str]] = Field(None, description="学校类型筛选：985/211/双一流")
    count: int = Field(default=30, description="推荐数量", ge=1, le=96)


class ScoreQueryRequest(BaseModel):
    """分数查询请求"""
    score: int = Field(..., description="高考分数")
    year: int = Field(..., description="年份")


# ==================== 响应模型 ====================

class RecommendItem(BaseModel):
    """单条推荐结果"""
    school: SchoolInfo
    major: MajorInfo
    admission: AdmissionRecord
    category: str = Field(..., description="冲/稳/保")
    confidence: float = Field(..., description="录取概率估计", ge=0, le=1)


class RecommendResponse(BaseModel):
    """志愿推荐响应"""
    score: int
    rank: int
    total_count: int
    recommendations: List[RecommendItem]
    rush: List[RecommendItem] = Field(default_factory=list, description="冲一冲")
    stable: List[RecommendItem] = Field(default_factory=list, description="稳一稳")
    safe: List[RecommendItem] = Field(default_factory=list, description="保一保")


class RankResponse(BaseModel):
    """位次查询响应"""
    score: int
    year: int
    rank: Optional[int] = None
    same_score_count: Optional[int] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    detail: Optional[str] = None
