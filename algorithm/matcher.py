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
        reach_schools, match_schools, safety_schools = self._dedupe_recommendation_buckets(
            reach_schools,
            match_schools,
            safety_schools,
            sort_by,
        )

        if not (reach_schools or match_schools or safety_schools):
            fallback_schools = self._query_nearest_schools(user_rank, limit=200)
            if filters:
                fallback_schools = self._apply_filters(fallback_schools, filters)
            match_schools = self.ranker.rank_schools(
                fallback_schools[:30], user_rank, sort_by=sort_by
            )
            if sort_by == "match_score":
                match_schools.sort(key=lambda s: abs((s.get("avg_rank") or 0) - user_rank))

        self._attach_suggested_majors(reach_schools, user_rank)
        self._attach_suggested_majors(match_schools, user_rank)
        self._attach_suggested_majors(safety_schools, user_rank)

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

    def _append_school_row(self, schools_map: dict, school: dict, year: int = None):
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

    def _finalize_schools(self, schools_map: dict) -> list:
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
                self._append_school_row(schools_map, school, year)

        return self._finalize_schools(schools_map)

    def _query_nearest_schools(self, user_rank: int, limit: int = 60) -> list:
        """When no bucket matches exactly, return schools closest to the user rank."""
        years = self.years[-3:]
        placeholders = ",".join("?" * len(years))
        conn = get_connection()
        try:
            rows = conn.execute(
                f"""WITH real_years AS (
                       SELECT school_id, year
                       FROM admission_records
                       WHERE COALESCE(data_source, 'seed') != 'seed'
                       GROUP BY school_id, year
                   )
                   SELECT s.*,
                          ar.year as year,
                          CAST(AVG(ar.min_rank) AS INTEGER) as min_rank,
                          CAST(AVG(ar.min_score) AS INTEGER) as min_score,
                          GROUP_CONCAT(DISTINCT m.category) as major_categories
                   FROM schools s
                   JOIN admission_records ar ON s.id = ar.school_id
                   JOIN majors m ON ar.major_id = m.id
                   LEFT JOIN real_years ry ON ry.school_id = ar.school_id AND ry.year = ar.year
                   WHERE ar.year IN ({placeholders})
                     AND (ry.school_id IS NULL OR COALESCE(ar.data_source, 'seed') != 'seed')
                   GROUP BY s.id, ar.year
                   ORDER BY ABS(CAST(AVG(ar.min_rank) AS INTEGER) - ?) ASC
                   LIMIT ?""",
                [*years, user_rank, limit * 3],
            ).fetchall()
        finally:
            conn.close()

        schools_map = {}
        for row in rows:
            self._append_school_row(schools_map, dict(row), row["year"])

        schools = self._finalize_schools(schools_map)
        schools.sort(key=lambda s: abs((s.get("avg_rank") or 0) - user_rank))
        return schools[:limit]

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

    def _dedupe_recommendation_buckets(
        self,
        reach_schools: list,
        match_schools: list,
        safety_schools: list,
        sort_by: str,
    ) -> Tuple[list, list, list]:
        """Ensure each school appears in only one risk bucket."""
        bucket_order = [
            ("reach", reach_schools),
            ("match", match_schools),
            ("safety", safety_schools),
        ]
        bucket_priority = {"match": 2, "safety": 1, "reach": 0}
        best_by_school = {}

        for bucket_name, schools in bucket_order:
            for index, school in enumerate(schools):
                sid = school.get("id")
                if sid is None:
                    continue

                current = best_by_school.get(sid)
                candidate_score = (
                    school.get("match_score", 0),
                    bucket_priority.get(bucket_name, 0),
                    -index,
                )
                if current is None or candidate_score > current["score"]:
                    best_by_school[sid] = {
                        "bucket": bucket_name,
                        "school": school,
                        "score": candidate_score,
                    }

        deduped = {"reach": [], "match": [], "safety": []}
        for item in best_by_school.values():
            deduped[item["bucket"]].append(item["school"])

        return (
            self._sort_ranked_schools(deduped["reach"], sort_by),
            self._sort_ranked_schools(deduped["match"], sort_by),
            self._sort_ranked_schools(deduped["safety"], sort_by),
        )

    def _sort_ranked_schools(self, schools: list, sort_by: str) -> list:
        """Sort already-ranked schools without recalculating scores."""
        sort_fields = {
            "match_score": "match_score",
            "school_level": "school_level_score",
            "stability": "stability",
            "probability": "probability",
        }
        field = sort_fields.get(sort_by, "match_score")
        schools.sort(key=lambda s: s.get(field, 0), reverse=True)
        return schools

    def _attach_suggested_majors(self, schools: list, user_rank: int):
        """Add major-level suggestions to school cards."""
        for school in schools:
            school["suggested_majors"] = self._get_suggested_majors(
                school.get("id"),
                user_rank,
            )

    def _get_suggested_majors(self, school_id: int, user_rank: int, limit: int = 5) -> list:
        """Recommend majors in a school based on recent major admission ranks."""
        if not school_id or not user_rank:
            return []

        years = self.years[-3:]
        placeholders = ",".join("?" * len(years))
        conn = get_connection()
        try:
            rows = conn.execute(
                f"""WITH real_years AS (
                       SELECT school_id, year
                       FROM admission_records
                       WHERE COALESCE(data_source, 'seed') != 'seed'
                       GROUP BY school_id, year
                   )
                   SELECT m.id as major_id,
                          m.name as major_name,
                          m.category as category,
                          ar.year as year,
                          ar.min_score as min_score,
                          ar.min_rank as min_rank,
                          ar.avg_score as avg_score,
                          ar.plan_count as plan_count
                   FROM admission_records ar
                   JOIN majors m ON ar.major_id = m.id
                   LEFT JOIN real_years ry ON ry.school_id = ar.school_id AND ry.year = ar.year
                   WHERE ar.school_id = ?
                     AND ar.year IN ({placeholders})
                     AND ar.min_rank IS NOT NULL
                     AND (ry.school_id IS NULL OR COALESCE(ar.data_source, 'seed') != 'seed')
                   ORDER BY m.id, ar.year DESC""",
                [school_id, *years],
            ).fetchall()
        finally:
            conn.close()

        majors_map = {}
        for row in rows:
            major_id = row["major_id"]
            if major_id not in majors_map:
                majors_map[major_id] = {
                    "major_id": major_id,
                    "major_name": row["major_name"],
                    "category": row["category"],
                    "ranks": [],
                    "scores": [],
                    "history": [],
                }

            data = majors_map[major_id]
            data["ranks"].append(row["min_rank"])
            if row["min_score"] is not None:
                data["scores"].append(row["min_score"])
            data["history"].append({
                "year": row["year"],
                "min_score": row["min_score"],
                "min_rank": row["min_rank"],
                "plan_count": row["plan_count"],
            })

        suggestions = []
        for data in majors_map.values():
            valid_ranks = [r for r in data["ranks"] if r is not None]
            if not valid_ranks:
                continue

            avg_rank = int(sum(valid_ranks) / len(valid_ranks))
            avg_score = int(sum(data["scores"]) / len(data["scores"])) if data["scores"] else None
            probability = self.ranker.calculate_admission_probability(user_rank, valid_ranks)
            proximity = max(0, 1 - abs(user_rank - avg_rank) / max(user_rank, 1))

            if probability >= 0.8:
                fit_label = "稳"
            elif probability >= 0.45:
                fit_label = "可报"
            elif probability >= 0.18:
                fit_label = "可冲"
            else:
                fit_label = "风险高"

            latest_history = sorted(
                data["history"],
                key=lambda item: item["year"],
                reverse=True,
            )

            suggestions.append({
                "major_id": data["major_id"],
                "major_name": data["major_name"],
                "category": data["category"],
                "fit_label": fit_label,
                "probability": probability,
                "avg_rank": avg_rank,
                "avg_score": avg_score,
                "latest_year": latest_history[0]["year"] if latest_history else None,
                "latest_score": latest_history[0]["min_score"] if latest_history else None,
                "latest_rank": latest_history[0]["min_rank"] if latest_history else None,
                "history": latest_history,
                "_sort_score": proximity * 0.55 + probability * 0.45,
            })

        suggestions.sort(
            key=lambda item: (
                item["_sort_score"],
                item["probability"],
                -abs(user_rank - item["avg_rank"]),
            ),
            reverse=True,
        )

        for item in suggestions:
            item.pop("_sort_score", None)

        return suggestions[:limit]

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
