"""
高考志愿推荐系统 - 多维度排序算法
对匹配结果进行综合排序，支持多种排序策略
"""
import math
from typing import List, Dict, Any


class SchoolRanker:
    """多维度排序器"""

    # 学校层次权重
    SCHOOL_TYPE_WEIGHTS = {
        "985": 100,
        "211": 80,
        "双一流": 60,
        "省属重点": 40,
        "普通本科": 20,
    }

    def __init__(self):
        """初始化排序器"""
        # 排序权重配置
        self.weights = {
            "rank_match": 0.4,      # 位次匹配度
            "stability": 0.2,       # 稳定性
            "school_level": 0.2,    # 学校层次
            "probability": 0.2,     # 录取概率
        }

    def calculate_match_score(self, school_records: dict, user_rank: int) -> float:
        """
        计算匹配度分数 (0-100)

        考虑因素：
        1. 位次差距（越近分越高）
        2. 稳定性（3年波动越小分越高）
        3. 录取概率估算

        Args:
            school_records: 学校记录字典（包含 avg_rank, min_ranks, type 等）
            user_rank: 用户排名

        Returns:
            匹配度分数 0-100
        """
        avg_rank = school_records.get("avg_rank") or school_records.get("median_rank", 0)
        if avg_rank == 0 or user_rank == 0:
            return 0.0

        # 基础分：位次越接近分越高
        rank_diff_ratio = abs(user_rank - avg_rank) / user_rank
        base_score = max(0, 100 - rank_diff_ratio * 100)

        # 稳定性加分
        min_ranks = school_records.get("min_ranks", [])
        stability = self.calculate_stability(min_ranks)
        stability_bonus = stability * 10

        # 学校层次加分
        school_type = school_records.get("type", "普通本科")
        level_weight = self.SCHOOL_TYPE_WEIGHTS.get(school_type, 20)
        level_bonus = level_weight / 10

        # 最终分数
        final_score = base_score + stability_bonus + level_bonus
        return min(100.0, max(0.0, round(final_score, 2)))

    def calculate_stability(self, records: list) -> float:
        """
        计算学校录取位次的稳定性 (0-1)

        基于多年数据的标准差/均值比（变异系数）
        标准差越小越稳定，返回值越接近1

        Args:
            records: 多年最低位次列表

        Returns:
            稳定性分数 0-1（1为最稳定）
        """
        valid_ranks = [r for r in records if r is not None]
        if len(valid_ranks) < 2:
            return 0.5  # 数据不足时返回中间值

        mean = sum(valid_ranks) / len(valid_ranks)
        if mean == 0:
            return 0.5

        # 计算标准差
        variance = sum((r - mean) ** 2 for r in valid_ranks) / len(valid_ranks)
        std = math.sqrt(variance)

        # 变异系数（CV）：std/mean，CV 越小越稳定
        cv = std / mean

        # 将 CV 转换为 0-1 的稳定性分数
        # CV < 0.05 非常稳定 -> 接近 1
        # CV > 0.3 非常不稳定 -> 接近 0
        stability = max(0, min(1, 1 - cv / 0.3))
        return round(stability, 4)

    def calculate_admission_probability(self, user_rank: int,
                                         school_min_ranks: list) -> float:
        """
        估算录取概率

        使用 Sigmoid 函数模型：
        P = 1 / (1 + exp(k * (user_rank - avg_min_rank) / std_rank))

        基于历年数据：
        - 用户排名 < 所有年份最低位次：概率 > 90%
        - 用户排名 在最低位次范围内：概率 50-90%
        - 用户排名 > 所有年份最低位次：概率 < 50%

        Args:
            user_rank: 用户排名
            school_min_ranks: 该校历年最低录取位次列表

        Returns:
            录取概率 0-1
        """
        valid_ranks = [r for r in school_min_ranks if r is not None]
        if not valid_ranks:
            return 0.5

        avg_min_rank = sum(valid_ranks) / len(valid_ranks)

        # 计算标准差
        if len(valid_ranks) >= 2:
            variance = sum((r - avg_min_rank) ** 2 for r in valid_ranks) / len(valid_ranks)
            std_rank = math.sqrt(variance)
        else:
            std_rank = avg_min_rank * 0.1  # 单年数据，假设10%波动

        if std_rank == 0:
            std_rank = avg_min_rank * 0.05  # 避免除零

        # Sigmoid 模型
        # 当 user_rank < avg_min_rank 时（排名更好），概率高
        # 当 user_rank > avg_min_rank 时（排名更差），概率低
        # k 为调节系数，控制曲线陡度
        k = 3.0
        x = (user_rank - avg_min_rank) / std_rank
        exponent = k * x
        if exponent > 50:
            probability = 0.0
        elif exponent < -50:
            probability = 1.0
        else:
            probability = 1.0 / (1.0 + math.exp(exponent))

        return round(min(0.99, max(0.01, probability)), 4)

    def rank_schools(self, schools: list, user_rank: int,
                     sort_by: str = "match_score") -> list:
        """
        对学校列表进行综合排序

        Args:
            schools: 学校列表
            user_rank: 用户排名
            sort_by: 排序方式
                - "match_score": 综合匹配度（默认）
                - "school_level": 学校层次优先
                - "stability": 稳定性优先
                - "probability": 录取概率优先

        Returns:
            排序后的学校列表（附带各维度分数）
        """
        if not schools:
            return []

        for school in schools:
            min_ranks = school.get("min_ranks", [])

            # 计算各项分数
            school["match_score"] = self.calculate_match_score(school, user_rank)
            school["stability"] = self.calculate_stability(min_ranks)
            school["probability"] = self.calculate_admission_probability(user_rank, min_ranks)
            school["school_level_score"] = self.SCHOOL_TYPE_WEIGHTS.get(
                school.get("type", "普通本科"), 20
            )

        # 根据 sort_by 排序
        if sort_by == "match_score":
            schools.sort(key=lambda s: s.get("match_score", 0), reverse=True)
        elif sort_by == "school_level":
            schools.sort(key=lambda s: s.get("school_level_score", 0), reverse=True)
        elif sort_by == "stability":
            schools.sort(key=lambda s: s.get("stability", 0), reverse=True)
        elif sort_by == "probability":
            schools.sort(key=lambda s: s.get("probability", 0), reverse=True)
        else:
            schools.sort(key=lambda s: s.get("match_score", 0), reverse=True)

        return schools

    def diversify_results(self, ranked_list: List[Dict[str, Any]],
                          max_same_school: int = 3) -> List[Dict[str, Any]]:
        """
        结果多样化：限制同一学校出现次数

        Args:
            ranked_list: 排序后的列表
            max_same_school: 同一学校最大出现次数

        Returns:
            多样化后的列表
        """
        if not ranked_list:
            return []

        school_count = {}
        diversified = []

        for item in ranked_list:
            school_id = item.get("id") or item.get("school_id")
            if school_id is None:
                diversified.append(item)
                continue

            count = school_count.get(school_id, 0)
            if count < max_same_school:
                diversified.append(item)
                school_count[school_id] = count + 1

        return diversified

    def calculate_confidence(self, student_rank: int, school_min_rank: int) -> float:
        """
        计算录取置信度（兼容旧接口）

        Args:
            student_rank: 考生位次
            school_min_rank: 学校最低录取位次

        Returns:
            0-1之间的置信度
        """
        return self.calculate_admission_probability(student_rank, [school_min_rank])
