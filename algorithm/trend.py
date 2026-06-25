"""
高考志愿推荐系统 - 热门/冷门趋势分析
分析历年录取分数和位次的变化趋势，识别专业热度变化
"""
import os
import sys
import math
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_connection, query_admission_by_school
from config import ALGORITHM_CONFIG


class TrendAnalyzer:
    """专业热度趋势分析"""

    def __init__(self, years: List[int] = None):
        """
        初始化趋势分析器

        Args:
            years: 分析的年份范围
        """
        self.years = years or ALGORITHM_CONFIG.get("default_years", [2022, 2023, 2024, 2025])

    def analyze_major_trend(self, major_id: int) -> dict:
        """
        分析单个专业的趋势

        Args:
            major_id: 专业ID

        Returns:
            {
                "trend": "热门上升" | "热门稳定" | "平稳" | "冷门下降" | "冷门稳定",
                "score_change": float,  # 3年分数变化率
                "rank_change": float,   # 3年位次变化率
                "prediction": str       # 趋势预测
            }
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT year, AVG(min_score) as avg_score, AVG(min_rank) as avg_rank
                   FROM admission_records
                   WHERE major_id = ? AND year IN ({})
                   GROUP BY year
                   ORDER BY year ASC""".format(",".join("?" * len(self.years))),
                [major_id] + self.years
            ).fetchall()

            records = [dict(row) for row in rows]
        finally:
            conn.close()

        if len(records) < 2:
            return {
                "trend": "数据不足",
                "score_change": 0.0,
                "rank_change": 0.0,
                "prediction": "数据不足，无法预测",
            }

        # 计算位次变化率
        ranks = [(r["year"], r["avg_rank"]) for r in records if r["avg_rank"] is not None]
        scores = [(r["year"], r["avg_score"]) for r in records if r["avg_score"] is not None]

        rank_change_rate = 0.0
        if len(ranks) >= 2:
            first_rank = ranks[0][1]
            last_rank = ranks[-1][1]
            if first_rank > 0:
                rank_change_rate = (last_rank - first_rank) / first_rank

        score_change_rate = 0.0
        if len(scores) >= 2:
            first_score = scores[0][1]
            last_score = scores[-1][1]
            if first_score > 0:
                score_change_rate = (last_score - first_score) / first_score

        # 判定趋势
        trend = self._determine_trend(ranks, rank_change_rate)

        # 预测
        prediction = self._make_prediction(trend, rank_change_rate, score_change_rate)

        return {
            "trend": trend,
            "score_change": round(score_change_rate, 4),
            "rank_change": round(rank_change_rate, 4),
            "prediction": prediction,
        }

    def analyze_school_trend(self, school_id: int) -> Dict[str, Any]:
        """
        分析某学校录取趋势

        Args:
            school_id: 学校ID

        Returns:
            趋势分析结果，包含方向(上升/下降/平稳)和幅度
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT year, AVG(min_score) as avg_score, AVG(min_rank) as avg_rank,
                          MIN(min_rank) as best_rank, MAX(min_rank) as worst_rank
                   FROM admission_records
                   WHERE school_id = ? AND year IN ({})
                   GROUP BY year
                   ORDER BY year ASC""".format(",".join("?" * len(self.years))),
                [school_id] + self.years
            ).fetchall()

            records = [dict(row) for row in rows]
        finally:
            conn.close()

        if len(records) < 2:
            return {
                "direction": "数据不足",
                "magnitude": 0,
                "years_data": records,
                "volatility": 0,
            }

        # 计算变化
        ranks = [r["avg_rank"] for r in records if r["avg_rank"] is not None]
        scores = [r["avg_score"] for r in records if r["avg_score"] is not None]

        direction = "平稳"
        magnitude = 0.0

        if len(ranks) >= 2:
            rank_change = (ranks[-1] - ranks[0]) / ranks[0] if ranks[0] else 0
            magnitude = abs(rank_change)

            if rank_change < -0.1:
                direction = "上升"  # 位次变小=变好
            elif rank_change > 0.1:
                direction = "下降"  # 位次变大=变差
            else:
                direction = "平稳"

        # 波动性
        volatility = self._calculate_volatility(ranks)

        return {
            "direction": direction,
            "magnitude": round(magnitude, 4),
            "years_data": records,
            "volatility": round(volatility, 4),
        }

    def batch_analyze(self) -> list:
        """
        批量分析所有专业趋势，更新数据库中的 hot_trend 字段

        Returns:
            分析结果列表
        """
        conn = get_connection()
        try:
            # 获取所有专业
            majors = conn.execute("SELECT id, name, category FROM majors").fetchall()
            majors = [dict(row) for row in majors]
        finally:
            conn.close()

        results = []
        for major in majors:
            trend_info = self.analyze_major_trend(major["id"])
            trend_label = trend_info["trend"]

            # 更新数据库
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE majors SET hot_trend = ? WHERE id = ?",
                    (trend_label, major["id"])
                )
                conn.commit()
            finally:
                conn.close()

            results.append({
                "major_id": major["id"],
                "major_name": major["name"],
                "category": major.get("category"),
                **trend_info,
            })

        return results

    def get_hot_majors(self, top_n: int = 20) -> list:
        """
        获取当前最热门的N个专业

        按分数线上涨幅度（位次下降幅度）排序

        Args:
            top_n: 返回数量

        Returns:
            热门专业列表
        """
        conn = get_connection()
        try:
            # 查询有多年数据的专业
            rows = conn.execute(
                """SELECT m.id, m.name, m.category,
                          GROUP_CONCAT(ar.year || ':' || ar.min_rank) as rank_history
                   FROM majors m
                   JOIN admission_records ar ON m.id = ar.major_id
                   WHERE ar.year IN ({})
                   GROUP BY m.id
                   HAVING COUNT(DISTINCT ar.year) >= 2
                   """.format(",".join("?" * len(self.years))),
                self.years
            ).fetchall()

            majors = [dict(row) for row in rows]
        finally:
            conn.close()

        # 计算每个专业的热度变化
        hot_list = []
        for major in majors:
            rank_history = self._parse_rank_history(major.get("rank_history", ""))
            if len(rank_history) < 2:
                continue

            sorted_years = sorted(rank_history.keys())
            first_rank = rank_history[sorted_years[0]]
            last_rank = rank_history[sorted_years[-1]]

            if first_rank > 0:
                change_rate = (last_rank - first_rank) / first_rank
                # 位次变小（负值）= 变热门
                if change_rate < 0:
                    hot_list.append({
                        "major_id": major["id"],
                        "major_name": major["name"],
                        "category": major.get("category"),
                        "rank_change_rate": round(change_rate, 4),
                        "heat_score": round(abs(change_rate) * 100, 2),
                    })

        # 按热度排序（位次下降幅度越大越热）
        hot_list.sort(key=lambda x: x["rank_change_rate"])
        return hot_list[:top_n]

    def get_cold_majors(self, top_n: int = 20) -> list:
        """
        获取当前最冷门的N个专业

        按分数线下降幅度（位次上升幅度）排序

        Args:
            top_n: 返回数量

        Returns:
            冷门专业列表
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT m.id, m.name, m.category,
                          GROUP_CONCAT(ar.year || ':' || ar.min_rank) as rank_history
                   FROM majors m
                   JOIN admission_records ar ON m.id = ar.major_id
                   WHERE ar.year IN ({})
                   GROUP BY m.id
                   HAVING COUNT(DISTINCT ar.year) >= 2
                   """.format(",".join("?" * len(self.years))),
                self.years
            ).fetchall()

            majors = [dict(row) for row in rows]
        finally:
            conn.close()

        cold_list = []
        for major in majors:
            rank_history = self._parse_rank_history(major.get("rank_history", ""))
            if len(rank_history) < 2:
                continue

            sorted_years = sorted(rank_history.keys())
            first_rank = rank_history[sorted_years[0]]
            last_rank = rank_history[sorted_years[-1]]

            if first_rank > 0:
                change_rate = (last_rank - first_rank) / first_rank
                # 位次变大（正值）= 变冷门
                if change_rate > 0:
                    cold_list.append({
                        "major_id": major["id"],
                        "major_name": major["name"],
                        "category": major.get("category"),
                        "rank_change_rate": round(change_rate, 4),
                        "cold_score": round(change_rate * 100, 2),
                    })

        # 按冷门程度排序（位次上升幅度越大越冷）
        cold_list.sort(key=lambda x: x["rank_change_rate"], reverse=True)
        return cold_list[:top_n]

    def get_trend_summary(self) -> dict:
        """
        获取整体趋势摘要

        Returns:
            {
                "hot_categories": [...],   # 热门学科门类
                "cold_categories": [...],  # 冷门学科门类
                "rising_majors": [...],    # 上升最快的专业
                "falling_majors": [...],   # 下降最快的专业
            }
        """
        hot_majors = self.get_hot_majors(20)
        cold_majors = self.get_cold_majors(20)

        # 统计热门学科门类
        hot_categories = {}
        for m in hot_majors:
            cat = m.get("category", "其他")
            if cat:
                hot_categories[cat] = hot_categories.get(cat, 0) + 1

        cold_categories = {}
        for m in cold_majors:
            cat = m.get("category", "其他")
            if cat:
                cold_categories[cat] = cold_categories.get(cat, 0) + 1

        # 按出现次数排序
        hot_cats_sorted = sorted(hot_categories.items(), key=lambda x: x[1], reverse=True)
        cold_cats_sorted = sorted(cold_categories.items(), key=lambda x: x[1], reverse=True)

        return {
            "hot_categories": [{"category": c, "count": n} for c, n in hot_cats_sorted[:10]],
            "cold_categories": [{"category": c, "count": n} for c, n in cold_cats_sorted[:10]],
            "rising_majors": hot_majors[:10],
            "falling_majors": cold_majors[:10],
        }

    def predict_next_year(self, school_id: int, major_id: int) -> Optional[Tuple[int, int]]:
        """
        预测下一年的录取分数和位次

        使用线性回归简单预测

        Args:
            school_id: 学校ID
            major_id: 专业ID

        Returns:
            (预测分数, 预测位次) 或 None
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT year, min_score, min_rank
                   FROM admission_records
                   WHERE school_id = ? AND major_id = ? AND year IN ({})
                   ORDER BY year ASC""".format(",".join("?" * len(self.years))),
                [school_id, major_id] + self.years
            ).fetchall()

            records = [dict(row) for row in rows]
        finally:
            conn.close()

        if len(records) < 2:
            return None

        # 简单线性回归预测
        years = [r["year"] for r in records]
        scores = [r["min_score"] for r in records if r["min_score"] is not None]
        ranks = [r["min_rank"] for r in records if r["min_rank"] is not None]

        next_year = max(years) + 1

        predicted_score = None
        if len(scores) >= 2:
            score_years = [r["year"] for r in records if r["min_score"] is not None]
            predicted_score = self._linear_predict(score_years, scores, next_year)

        predicted_rank = None
        if len(ranks) >= 2:
            rank_years = [r["year"] for r in records if r["min_rank"] is not None]
            predicted_rank = self._linear_predict(rank_years, ranks, next_year)

        if predicted_score is None and predicted_rank is None:
            return None

        return (
            int(predicted_score) if predicted_score else None,
            int(predicted_rank) if predicted_rank else None,
        )

    def get_volatility(self, school_id: int, major_id: int) -> float:
        """
        计算录取分数波动性

        波动性越大说明该院校专业录取分数不稳定

        Args:
            school_id: 学校ID
            major_id: 专业ID

        Returns:
            波动系数 (0-1)
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT min_rank FROM admission_records
                   WHERE school_id = ? AND major_id = ? AND min_rank IS NOT NULL
                   ORDER BY year ASC""",
                (school_id, major_id)
            ).fetchall()

            ranks = [row["min_rank"] for row in rows]
        finally:
            conn.close()

        return self._calculate_volatility(ranks)

    # ==================== 内部辅助方法 ====================

    def _determine_trend(self, ranks: list, rank_change_rate: float) -> str:
        """
        根据位次数据判定趋势

        规则：
        - 连续3年位次下降（数值变小）> 10%：热门上升
        - 连续3年位次上升（数值变大）> 10%：冷门下降
        - 波动 < 5%：平稳
        - 其他：根据最近2年趋势判断
        """
        if len(ranks) < 2:
            return "数据不足"

        # 检查是否连续变化
        if len(ranks) >= 3:
            # 检查连续下降（变热门）
            all_decreasing = all(
                ranks[i][1] < ranks[i - 1][1] for i in range(1, len(ranks))
            )
            # 检查连续上升（变冷门）
            all_increasing = all(
                ranks[i][1] > ranks[i - 1][1] for i in range(1, len(ranks))
            )

            if all_decreasing and rank_change_rate < -0.1:
                return "热门上升"
            elif all_increasing and rank_change_rate > 0.1:
                return "冷门下降"

        # 非连续变化，看总体变化率
        if abs(rank_change_rate) < 0.05:
            return "平稳"
        elif rank_change_rate < -0.1:
            return "热门上升"
        elif rank_change_rate < -0.05:
            return "热门稳定"
        elif rank_change_rate > 0.1:
            return "冷门下降"
        elif rank_change_rate > 0.05:
            return "冷门稳定"
        else:
            return "平稳"

    def _make_prediction(self, trend: str, rank_change: float, score_change: float) -> str:
        """生成趋势预测文字"""
        if trend == "热门上升":
            return f"该专业持续升温，预计明年分数线继续上涨，位次可能再降{abs(rank_change)*50:.0f}%左右"
        elif trend == "冷门下降":
            return f"该专业热度持续走低，预计明年分数线可能继续降低，是捡漏的好机会"
        elif trend == "热门稳定":
            return "该专业热度较高但趋于稳定，分数线波动不大"
        elif trend == "冷门稳定":
            return "该专业热度较低且稳定，录取难度不大"
        elif trend == "平稳":
            return "该专业录取趋势平稳，可参考往年数据填报"
        else:
            return "数据不足，建议参考近一年数据"

    def _calculate_volatility(self, ranks: list) -> float:
        """
        计算波动系数 (0-1)

        Args:
            ranks: 位次列表

        Returns:
            波动系数，0为最稳定，1为最不稳定
        """
        valid_ranks = [r for r in ranks if r is not None]
        if len(valid_ranks) < 2:
            return 0.5

        mean = sum(valid_ranks) / len(valid_ranks)
        if mean == 0:
            return 0.5

        variance = sum((r - mean) ** 2 for r in valid_ranks) / len(valid_ranks)
        std = math.sqrt(variance)
        cv = std / mean

        # 归一化到 0-1
        return min(1.0, round(cv / 0.3, 4))

    def _parse_rank_history(self, history_str: str) -> dict:
        """
        解析 GROUP_CONCAT 的排名历史字符串

        格式: "2022:5000,2023:4800,2024:4500"

        Returns:
            {year: avg_rank}
        """
        if not history_str:
            return {}

        result = {}
        pairs = history_str.split(",")
        year_ranks = {}  # year -> [ranks]

        for pair in pairs:
            try:
                parts = pair.strip().split(":")
                if len(parts) == 2:
                    year = int(parts[0])
                    rank = int(float(parts[1]))
                    if year not in year_ranks:
                        year_ranks[year] = []
                    year_ranks[year].append(rank)
            except (ValueError, IndexError):
                continue

        # 对同一年的多个排名取平均
        for year, ranks in year_ranks.items():
            result[year] = int(sum(ranks) / len(ranks))

        return result

    def _linear_predict(self, x_vals: list, y_vals: list, target_x: int) -> Optional[float]:
        """
        简单线性回归预测

        Args:
            x_vals: x 值列表（年份）
            y_vals: y 值列表（分数或位次）
            target_x: 预测目标年份

        Returns:
            预测值或 None
        """
        n = len(x_vals)
        if n < 2 or n != len(y_vals):
            return None

        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        # 计算斜率和截距
        numerator = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n))
        denominator = sum((x_vals[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return y_mean

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        predicted = slope * target_x + intercept
        return max(0, predicted)  # 确保非负
