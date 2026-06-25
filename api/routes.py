"""
高考志愿推荐系统 - API路由
提供推荐、学校详情、专业、排名表、批次线、趋势等接口
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from algorithm.matcher import SchoolMatcher
from algorithm.trend import TrendAnalyzer
from database.db import get_connection

router = APIRouter(prefix="/api")

# 初始化全局实例
matcher = SchoolMatcher()
trend_analyzer = TrendAnalyzer()


def success_response(data):
    """统一成功响应格式"""
    return {"success": True, "data": data}


def error_response(code: int, message: str):
    """统一错误响应格式"""
    return {"success": False, "error": {"code": code, "message": message}}


# ==================== 1. 核心推荐接口 ====================

@router.get("/convert")
async def convert_score_rank(
    score: Optional[int] = Query(None, ge=0, le=750, description="高考分数"),
    rank: Optional[int] = Query(None, ge=1, description="全省排名"),
):
    """分数和位次互转，用于前端输入联动。"""
    if score is None and rank is None:
        raise HTTPException(status_code=400, detail="score 和 rank 至少需要提供一个")

    try:
        converted_score = score
        converted_rank = rank
        if score is not None:
            converted_rank = matcher.score_to_rank(score)
        if rank is not None:
            converted_score = matcher.rank_to_score(rank)

        return success_response({
            "score": converted_score,
            "rank": converted_rank,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分数位次转换失败: {str(e)}")


@router.get("/recommend")
async def recommend(
    score: Optional[int] = Query(None, ge=0, le=750, description="高考分数"),
    rank: Optional[int] = Query(None, ge=1, description="全省排名"),
    school_type: Optional[str] = Query(None, description="学校类型筛选：985,211,双一流,普通本科,高职专科"),
    province: Optional[str] = Query(None, description="省内/省外"),
    major_category: Optional[str] = Query(None, description="专业类别"),
    sort_by: str = Query(
        "match_score",
        pattern="^(match_score|school_level|stability|probability)$",
        description="排序方式：match_score,school_level,stability,probability",
    ),
):
    """根据分数或排名推荐学校，返回冲/稳/保三档推荐"""
    # 参数校验：score 和 rank 至少传一个
    if score is None and rank is None:
        raise HTTPException(status_code=400, detail="score 和 rank 至少需要提供一个")

    try:
        # 构建筛选条件
        filters = {}
        if school_type:
            filters["school_type"] = [t.strip() for t in school_type.split(",")]
        if province:
            filters["province"] = province
        if major_category:
            filters["major_category"] = major_category

        # 调用匹配算法
        result = matcher.match(
            score=score,
            rank=rank,
            filters=filters if filters else None,
            sort_by=sort_by,
        )

        # 格式化输出
        def format_school(s):
            return {
                "school_id": s.get("id"),
                "school_name": s.get("name"),
                "province": s.get("province"),
                "city": s.get("city"),
                "type": s.get("type"),
                "match_score": s.get("match_score", 0),
                "probability": s.get("probability", 0),
                "stability": s.get("stability", 0),
                "school_level_score": s.get("school_level_score", 0),
                "avg_rank": s.get("avg_rank", 0),
                "avg_score": s.get("avg_score", 0),
                "major_categories": s.get("major_categories", []),
                "suggested_majors": s.get("suggested_majors", []),
                "history": [
                    {"year": y, "min_score": sc, "min_rank": rk}
                    for y, sc, rk in zip(
                        s.get("years_matched", []),
                        s.get("min_scores", []),
                        s.get("min_ranks", []),
                    )
                ],
            }

        reach = [format_school(s) for s in result.get("reach", [])]
        match_list = [format_school(s) for s in result.get("match", [])]
        safety = [format_school(s) for s in result.get("safety", [])]

        stats = result.get("statistics", {})

        return success_response({
            "user_input": {
                "score": result.get("user_score", score),
                "rank": result.get("user_rank", rank),
            },
            "recommendations": {
                "reach": reach,
                "match": match_list,
                "safety": safety,
            },
            "statistics": {
                "total": stats.get("total", 0),
                "in_province": stats.get("in_province", 0),
                "out_province": stats.get("out_province", 0),
                "reach_count": len(reach),
                "match_count": len(match_list),
                "safety_count": len(safety),
            },
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐服务异常: {str(e)}")


# ==================== 2. 学校详情 ====================

@router.get("/school/{school_id}")
async def school_detail(school_id: int):
    """获取学校详细信息及历年录取情况"""
    try:
        detail = matcher.get_school_detail(school_id)
        school_info = detail.get("school_info", {})

        if not school_info:
            raise HTTPException(status_code=404, detail=f"未找到ID为{school_id}的学校")

        return success_response({
            "school_id": school_id,
            "school_name": school_info.get("name"),
            "province": school_info.get("province"),
            "city": school_info.get("city"),
            "type": school_info.get("type"),
            "level": school_info.get("level"),
            "features": school_info.get("features"),
            "majors_count": len(detail.get("majors", [])),
            "majors": [
                {
                    "major_name": m.get("major_name"),
                    "category": m.get("category"),
                    "trend": m.get("trend", {}).get("trend", "数据不足"),
                    "years": m.get("years", {}),
                }
                for m in detail.get("majors", [])
            ],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询学校详情失败: {str(e)}")


# ==================== 3. 学校专业列表 ====================

@router.get("/school/{school_id}/majors")
async def school_majors(school_id: int):
    """获取学校各专业录取详情"""
    try:
        # 先确认学校存在
        conn = get_connection()
        try:
            school_row = conn.execute(
                "SELECT name FROM schools WHERE id = ?", (school_id,)
            ).fetchone()
        finally:
            conn.close()

        if not school_row:
            raise HTTPException(status_code=404, detail=f"未找到ID为{school_id}的学校")

        majors = matcher.get_school_majors(school_id)

        return success_response({
            "school_name": school_row["name"],
            "majors": [
                {
                    "major_name": m.get("major_name"),
                    "category": m.get("category"),
                    "hot_trend": m.get("trend", {}).get("trend", "数据不足"),
                    "history": [
                        {"year": year, "min_score": data.get("min_score"), "min_rank": data.get("min_rank")}
                        for year, data in sorted(m.get("years", {}).items(), reverse=True)
                    ],
                }
                for m in majors
            ],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询专业列表失败: {str(e)}")


# ==================== 4. 一分一段表 ====================

@router.get("/ranking-table")
async def ranking_table(year: int = Query(2025, description="年份")):
    """获取指定年份一分一段表"""
    try:
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT score, same_score_count, cumulative_count
                   FROM ranking_table
                   WHERE year = ?
                   ORDER BY score DESC""",
                (year,)
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return success_response({"year": year, "total": 0, "records": []})

        records = [
            {
                "score": row["score"],
                "same_score_count": row["same_score_count"],
                "cumulative_count": row["cumulative_count"],
            }
            for row in rows
        ]

        return success_response({
            "year": year,
            "total": len(records),
            "records": records,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询一分一段表失败: {str(e)}")


# ==================== 5. 历年批次线 ====================

@router.get("/score-lines")
async def score_lines():
    """获取近3年批次线数据"""
    try:
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT year, batch, score, rank
                   FROM score_lines
                   ORDER BY year DESC, batch ASC"""
            ).fetchall()
        finally:
            conn.close()

        # 按年份分组
        by_year = {}
        for row in rows:
            year = row["year"]
            if year not in by_year:
                by_year[year] = []
            by_year[year].append({
                "batch": row["batch"],
                "score": row["score"],
                "rank": row["rank"],
            })

        return success_response({
            "years": [
                {"year": year, "lines": lines}
                for year, lines in sorted(by_year.items(), reverse=True)
            ]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询批次线失败: {str(e)}")


# ==================== 6. 热门专业排行 ====================

@router.get("/hot-majors")
async def hot_majors(top_n: int = Query(20, description="返回数量", ge=1, le=100)):
    """获取热门/冷门专业排行"""
    try:
        hot = trend_analyzer.get_hot_majors(top_n)
        cold = trend_analyzer.get_cold_majors(top_n)

        return success_response({
            "hot_majors": hot,
            "cold_majors": cold,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询热门专业失败: {str(e)}")


# ==================== 7. 趋势摘要 ====================

@router.get("/trend-summary")
async def trend_summary():
    """获取专业趋势总览"""
    try:
        summary = trend_analyzer.get_trend_summary()
        return success_response(summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询趋势摘要失败: {str(e)}")


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    """健康检查"""
    return {"success": True, "status": "ok", "message": "高考志愿推荐系统运行正常"}
