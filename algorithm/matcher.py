"""
高考志愿推荐系统 - 核心匹配算法
基于排名的学校匹配引擎，支持冲/稳/保三档推荐
"""
import os
import sys
import math
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import (
    get_connection,
    get_rank_by_score,
    get_score_by_rank,
    query_schools_by_rank_range,
    query_admission_by_school,
)
from config import DATABASE_PATH, ALGORITHM_CONFIG
from algorithm.ranker import SchoolRanker


class SchoolMatcher:
    """基于排名的学校匹配引擎"""

    def __init__(self, db_path: str = None):
        """
        初始化匹配器

        Args:
            db_path: 数据库路径（可选，默认使用 config 中配置）
        """
        self.db_path = db_path or DATABASE_PATH
        self.ranker = SchoolRanker()
        self.years = ALGORITHM_CONFIG.get("default_years", [2022, 2023, 2024, 2025])

    # ==================== 分数/排名转换 ====================

    def score_to_rank(self, score: int, year: int = 2025) -> int:
        """
        分数转排名：查询一分一段表

        如果精确分数不存在，做线性插值

        Args:
            score: 高考分数
            year: 年份

        Returns:
            对应排名（位次）
        """
        # 先尝试精确匹配
        rank = get_rank_by_score(score, year)
        if rank is not None:
            return rank

        # 精确匹配失败，线性插值
        conn = get_connection()
        try:
            # 找到分数上下两个最近的记录
            higher = conn.execute(
                """SELECT score, cumulative_count FROM ranking_table
                   WHERE year = ? AND score > ? ORDER BY score ASC LIMIT 1""",
                (year, score)
            ).fetchone()

            lower = conn.execute(
                """SELECT score, cumulative_count FROM ranking_table
                   WHERE year = ? AND score < ? ORDER BY score DESC LIMIT 1""",
                (year, score)
            ).fetchone()

            if higher and lower:
                # 线性插值
                s1, r1 = lower["score"], lower["cumulative_count"]
                s2, r2 = higher["score"], higher["cumulative_count"]
                # 分数越高排名越小（数值越小）
                interpolated = r1 + (r2 - r1) * (score - s1) / (s2 - s1)
                return int(round(interpolated))
            elif higher:
                return higher["cumulative_count"]
            elif lower:
                return lower["cumulative_count"]
            else:
                # 无数据，返回一个保守估计
                return score * 100  # 粗略估算
        finally:
            conn.close()

    def rank_to_score(self, rank: int, year: int = 2025) -> int:
        """
        排名转分数：查询一分一段表

        Args:
            rank: 全省排名
            year: 年份

        Returns:
            对应分数
        """
        score = get_score_by_rank(rank, year)
        if score is not None:
            return score

        # 精确匹配失败，线性插值
        conn = get_connection()
        try:
            # 找排名上下两个最近的记录（注意：排名越小分数越高）
            better = conn.execute(
                """SELECT score, cumulative_count FROM ranking_table
                   WHERE year = ? AND cumulative_count < ? ORDER BY cumulative_count DESC LIMIT 1""",
                (year, rank)
            ).fetchone()

            worse = conn.execute(
                """SELECT score, cumulative_count FROM ranking_table
                   WHERE year = ? AND cumulative_count > ? ORDER BY cumulative_count ASC LIMIT 1""",
                (year, rank)
            ).fetchone()

            if better and worse:
                r1, s1 = better["cumulative_count"], better["score"]
                r2, s2 = worse["cumulative_count"], worse["score"]
                interpolated = s1 + (s2 - s1) * (rank - r1) / (r2 - r1)
                return int(round(interpolated))
            elif better:
                return better["score"]
            elif worse:
                return worse["score"]
            else:
                return 0
        finally:
            conn.close()

    # ==================== 排名区间计算 ====================

    def get_rank_ranges(self, user_rank: int) -> dict:
        """
        计算冲/稳/保的排名区间

        冲一冲：历年最低位次比用户排名高10-20%（数值更小）
        稳一稳：位次相近 ±5%
        保一保：位次更低20-40%（数值更大）

        Args:
            user_rank: 用户排名

        Returns:
            {"reach": (min, max), "match": (min, max), "safety": (min, max)}
        """
        reach_min = int(user_rank * 0.8)
        reach_max = int(user_rank * 0.9)
        match_min = int(user_rank * 0.95)
        match_max = int(user_rank * 1.05)
        safety_min = int(user_rank * 1.2)
        safety_max = int(user_rank * 1.4)

        return {
            "reach": (reach_min, reach_max),
            "match": (match_min, match_max),
            "safety": (safety_min, safety_max),
        }

    # ==================== 主匹配方法 ====================

    def match(self, score: int = None, rank: int = None,
              filters: dict = None, sort_by: str = "match_score") -> dict:
        """
        主匹配方法

        Args:
            score: 高考分数（与rank二选一）
            rank: 全省排名（与score二选一）
            filters: 筛选条件 {
                "school_type": ["985", "211", ...],
                "province": "省内" | "省外" | None,
                "batch": "本科批" | None,
                "major_category": "工学" | None
            }

        Returns:
            包含三档推荐结果的字典
        """
        if score is None and rank is None:
            raise ValueError("score 和 rank 必须至少提供一个")

        # 1. 分数排名互转
        if rank is None:
            user_rank = self.score_to_rank(score)
        else:
            user_rank = rank

        if score is None:
            user_score = self.rank_to_score(user_rank)
        else:
            user_score = score

        # 2. 计算三档排名区间
        ranges = self.get_rank_ranges(user_rank)

        # 3. 查询各档学校（综合多年数据）
        reach_schools = self._query_schools_multi_year(
            ranges["reach"][0], ranges["reach"][1]
        )
        match_schools = self._query_schools_multi_year(
            ranges["match"][0], ranges["match"][1]
        )
        safety_schools = self._query_schools_multi_year(
            ranges["safety"][0], ranges["safety"][1]
        )

        # 4. 应用筛选条件
        if filters:
            reach_schools = self._apply_filters(reach_schools, filters)
            match_schools = self._apply_filters(match_schools, filters)
            safety_schools = self._apply_filters(safety_schools, filters)

        # 5. 使用 ranker 排序
        reach_schools = self.ranker.rank_schools(reach_schools, user_rank, sort_by=sort_by)
        match_schools = self.ranker.rank_schools(match_schools, user_rank, sort_by=sort_by)
        safety_schools = self.ranker.rank_schools(safety_schools, user_rank, sort_by=sort_by)

        # 6. 统计
        all_schools = reach_schools + match_schools + safety_schools
        in_province = sum(1 for s in all_schools if s.get("province") == "山东")
        out_province = len(all_schools) - in_province

        return {
            "user_rank": user_rank,
            "user_score": user_score,
            "reach": reach_schools,
            "match": match_schools,
            "safety": safety_schools,
            "statistics": {
                "total": len(all_schools),
                "in_province": in_province,
                "out_province": out_province,
            },
        }

    # ==================== 学校详情 ====================

    def get_school_detail(self, school_id: int) -> dict:
        """
        获取学校详细录取信息（含各专业）

        Args:
            school_id: 学校ID

        Returns:
            学校详情字典，包含各专业录取数据和趋势
        """
        # 查询该校所有年份的录取记录
        records = query_admission_by_school(school_id)
        if not records:
            return {"school_id": school_id, "majors": [], "years_data": {}}

        # 获取学校基本信息
        conn = get_connection()
        try:
            school_row = conn.execute(
                "SELECT * FROM schools WHERE id = ?", (school_id,)
            ).fetchone()
            school_info = dict(school_row) if school_row else {}
        finally:
            conn.close()

        # 按专业分组
        majors_data = {}
        for record in records:
            major_name = record.get("major_name", "未知专业")
            if major_name not in majors_data:
                majors_data[major_name] = {
                    "major_id": record.get("major_id"),
                    "major_name": major_name,
                    "category": record.get("category"),
                    "years": {},
                }
            majors_data[major_name]["years"][record["year"]] = {
                "min_score": record.get("min_score"),
                "min_rank": record.get("min_rank"),
                "avg_score": record.get("avg_score"),
                "plan_count": record.get("plan_count"),
                "actual_count": record.get("actual_count"),
            }

        # 计算每个专业的趋势
        for major_name, data in majors_data.items():
            data["trend"] = self._calculate_major_trend(data["years"])

        return {
            "school_id": school_id,
            "school_info": school_info,
            "majors": list(majors_data.values()),
        }

    def get_school_majors(self, school_id: int) -> list:
        """
        获取学校所有专业的录取详情

        Args:
            school_id: 学校ID

        Returns:
            专业列表，含各年录取数据
        """
        detail = self.get_school_detail(school_id)
        return detail.get("majors", [])

    # ==================== 内部辅助方法 ====================

    def _query_schools_multi_year(self, min_rank: int, max_rank: int) -> list:
        """
        综合多年数据查询匹配学校

        使用最近3年数据的中位数作为参考

        Args:
            min_rank: 最小排名
            max_rank: 最大排名

        Returns:
            去重后的学校列表，附带多年数据统计
        """
        schools_map = {}  # school_id -> aggregated data

        for year in self.years[-3:]:  # 使用最近3年
            schools = query_schools_by_rank_range(min_rank, max_rank, year)
            for school in schools:
                sid = school["id"]
                if sid not in schools_map:
                    schools_map[sid] = {
                        "id": sid,
                        "name": school["name"],
                        "province": school.get("province"),
                        "city": school.get("city"),
                        "type": school.get("type"),
                        "level": school.get("level"),
                        "features": school.get("features"),
                        "min_ranks": [],
                        "min_scores": [],
                        "years_matched": [],
                        "major_categories": set(),
                    }
                schools_map[sid]["min_ranks"].append(school.get("min_rank"))
                schools_map[sid]["min_scores"].append(school.get("min_score"))
                schools_map[sid]["years_matched"].append(school.get("year", year))
                categories = school.get("major_categories") or ""
                schools_map[sid]["major_categories"].update(
                    c for c in categories.split(",") if c
                )

        # 计算统计值
        result = []
        for sid, data in schools_map.items():
            valid_ranks = [r for r in data["min_ranks"] if r is not None]
            valid_scores = [s for s in data["min_scores"] if s is not None]

            if valid_ranks:
                sorted_ranks = sorted(valid_ranks)
                data["avg_rank"] = int(sum(valid_ranks) / len(valid_ranks))
                data["median_rank"] = sorted_ranks[len(sorted_ranks) // 2]
            else:
                data["avg_rank"] = 0
                data["median_rank"] = 0

            if valid_scores:
                data["avg_score"] = int(sum(valid_scores) / len(valid_scores))
            else:
                data["avg_score"] = 0

            data["data_years"] = len(data["years_matched"])
            data["major_categories"] = sorted(data["major_categories"])
            result.append(data)

        return result

    def _apply_filters(self, schools: list, filters: dict) -> list:
        """
        应用筛选条件

        Args:
            schools: 学校列表
            filters: 筛选条件字典

        Returns:
            筛选后的学校列表
        """
        filtered = schools

        # 学校类型筛选
        school_types = filters.get("school_type")
        if school_types:
            filtered = [
                s for s in filtered
                if s.get("type") in school_types
            ]

        # 省份筛选
        province = filters.get("province")
        if province == "省内":
            filtered = [s for s in filtered if s.get("province") == "山东"]
        elif province == "省外":
            filtered = [s for s in filtered if s.get("province") != "山东"]

        # 批次筛选（需要查询录取记录）
        batch = filters.get("batch")
        if batch:
            # 批次信息在录取记录中，这里简单跳过，后续可扩展
            pass

        # 专业门类筛选
        major_category = filters.get("major_category")
        if major_category:
            filtered = [
                s for s in filtered
                if major_category in (s.get("major_categories") or [])
            ]

        return filtered

    def _calculate_major_trend(self, years_data: dict) -> dict:
        """
        计算单个专业的趋势

        Args:
            years_data: {year: {min_score, min_rank, ...}}

        Returns:
            趋势信息字典
        """
        sorted_years = sorted(years_data.keys())
        if len(sorted_years) < 2:
            return {"trend": "数据不足", "score_change": 0, "rank_change": 0}

        # 计算位次变化率
        ranks = []
        for y in sorted_years:
            r = years_data[y].get("min_rank")
            if r is not None:
                ranks.append((y, r))

        if len(ranks) < 2:
            return {"trend": "数据不足", "score_change": 0, "rank_change": 0}

        first_rank = ranks[0][1]
        last_rank = ranks[-1][1]
        rank_change_rate = (last_rank - first_rank) / first_rank if first_rank else 0

        # 计算分数变化率
        scores = []
        for y in sorted_years:
            s = years_data[y].get("min_score")
            if s is not None:
                scores.append((y, s))

        score_change_rate = 0
        if len(scores) >= 2:
            first_score = scores[0][1]
            last_score = scores[-1][1]
            score_change_rate = (last_score - first_score) / first_score if first_score else 0

        # 判定趋势
        # 位次变小 = 变热门，位次变大 = 变冷门
        if rank_change_rate < -0.1:
            trend = "热门上升"
        elif rank_change_rate > 0.1:
            trend = "冷门下降"
        elif abs(rank_change_rate) < 0.05:
            trend = "平稳"
        elif rank_change_rate < 0:
            trend = "热门稳定"
        else:
            trend = "冷门稳定"

        return {
            "trend": trend,
            "score_change": round(score_change_rate, 4),
            "rank_change": round(rank_change_rate, 4),
        }


# ==================== 兼容旧接口 ====================

class VolunteerMatcher:
    """志愿匹配器（兼容旧接口，内部使用 SchoolMatcher）"""

    def __init__(self, score: int, rank: int, year: int):
        self.score = score
        self.rank = rank
        self.year = year
        self._matcher = SchoolMatcher()

    def match_rush(self, rank_offset: int = 5000) -> List[Dict[str, Any]]:
        """匹配"冲一冲"的院校"""
        min_rank = max(1, self.rank - rank_offset)
        max_rank = self.rank
        return self._matcher._query_schools_multi_year(min_rank, max_rank)

    def match_stable(self, rank_offset: int = 2000) -> List[Dict[str, Any]]:
        """匹配"稳一稳"的院校"""
        min_rank = max(1, self.rank - rank_offset)
        max_rank = self.rank + rank_offset
        return self._matcher._query_schools_multi_year(min_rank, max_rank)

    def match_safe(self, rank_offset: int = 5000) -> List[Dict[str, Any]]:
        """匹配"保一保"的院校"""
        min_rank = self.rank
        max_rank = self.rank + rank_offset
        return self._matcher._query_schools_multi_year(min_rank, max_rank)

    def get_recommendations(self, count: int = 30,
                            preferred_provinces: List[str] = None,
                            preferred_majors: List[str] = None,
                            school_types: List[str] = None) -> Dict[str, List]:
        """获取完整推荐结果"""
        filters = {}
        if school_types:
            filters["school_type"] = school_types
        if preferred_provinces:
            filters["preferred_provinces"] = preferred_provinces

        result = self._matcher.match(
            score=self.score, rank=self.rank, filters=filters if filters else None
        )
        return {
            "rush": result["reach"][:count // 3],
            "stable": result["match"][:count // 3],
            "safe": result["safety"][:count // 3],
        }
