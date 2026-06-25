"""
高考志愿推荐系统 - 数据库操作封装
提供连接管理和CRUD操作
"""
import sqlite3
import os
from typing import List, Optional, Tuple, Dict, Any

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_PATH
from database.schema import init_db as _init_schema


def get_connection() -> sqlite3.Connection:
    """
    获取数据库连接
    
    Returns:
        sqlite3.Connection 对象
    """
    # 确保数据库目录存在
    db_dir = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # 使查询结果可以按列名访问
    conn.execute("PRAGMA foreign_keys = ON")  # 开启外键约束
    return conn


def init_db():
    """初始化数据库（创建所有表和索引）"""
    conn = get_connection()
    try:
        _init_schema(conn)
    finally:
        conn.close()


# ==================== 学校相关操作 ====================

def insert_school(name: str, province: str = None, city: str = None,
                  type_: str = None, level: str = None, features: str = None) -> int:
    """
    插入学校记录
    
    Returns:
        新插入记录的ID
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO schools (name, province, city, type, level, features) VALUES (?, ?, ?, ?, ?, ?)",
            (name, province, city, type_, level, features)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_major(name: str, category: str = None, hot_trend: str = None) -> int:
    """
    插入专业记录
    
    Returns:
        新插入记录的ID
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO majors (name, category, hot_trend) VALUES (?, ?, ?)",
            (name, category, hot_trend)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_admission_record(year: int, school_id: int, major_id: int,
                            batch: str = None, min_score: int = None,
                            min_rank: int = None, avg_score: int = None,
                            plan_count: int = None, actual_count: int = None) -> int:
    """
    插入录取记录
    
    Returns:
        新插入记录的ID
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO admission_records 
               (year, school_id, major_id, batch, min_score, min_rank, avg_score, plan_count, actual_count) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (year, school_id, major_id, batch, min_score, min_rank, avg_score, plan_count, actual_count)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_score_line(year: int, batch: str, score: int, rank: int = None) -> int:
    """
    插入分数线记录
    
    Returns:
        新插入记录的ID
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO score_lines (year, batch, score, rank) VALUES (?, ?, ?, ?)",
            (year, batch, score, rank)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_ranking(year: int, score: int, same_score_count: int = None,
                   cumulative_count: int = None) -> int:
    """
    插入一分一段记录
    
    Returns:
        新插入记录的ID
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO ranking_table (year, score, same_score_count, cumulative_count) VALUES (?, ?, ?, ?)",
            (year, score, same_score_count, cumulative_count)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ==================== 查询操作 ====================

def query_schools_by_rank_range(min_rank: int, max_rank: int, year: int) -> List[Dict[str, Any]]:
    """
    根据位次范围查询学校
    
    Args:
        min_rank: 最小位次（排名靠前）
        max_rank: 最大位次（排名靠后）
        year: 年份
        
    Returns:
        符合条件的学校列表
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT DISTINCT s.*, ar.min_rank, ar.min_score
               FROM schools s
               JOIN admission_records ar ON s.id = ar.school_id
               WHERE ar.year = ? AND ar.min_rank BETWEEN ? AND ?
               ORDER BY ar.min_rank ASC""",
            (year, min_rank, max_rank)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def query_admission_by_school(school_id: int, year: int = None) -> List[Dict[str, Any]]:
    """
    查询某学校的录取记录
    
    Args:
        school_id: 学校ID
        year: 年份（可选，不传则查所有年份）
        
    Returns:
        录取记录列表
    """
    conn = get_connection()
    try:
        if year:
            rows = conn.execute(
                """SELECT ar.*, m.name as major_name, m.category
                   FROM admission_records ar
                   JOIN majors m ON ar.major_id = m.id
                   WHERE ar.school_id = ? AND ar.year = ?
                   ORDER BY ar.min_rank ASC""",
                (school_id, year)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ar.*, m.name as major_name, m.category
                   FROM admission_records ar
                   JOIN majors m ON ar.major_id = m.id
                   WHERE ar.school_id = ?
                   ORDER BY ar.year DESC, ar.min_rank ASC""",
                (school_id,)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_rank_by_score(score: int, year: int) -> Optional[int]:
    """
    分数转位次：根据分数查询对应位次
    
    Args:
        score: 高考分数
        year: 年份
        
    Returns:
        对应的位次，找不到返回None
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT cumulative_count FROM ranking_table WHERE year = ? AND score = ?",
            (year, score)
        ).fetchone()
        return row["cumulative_count"] if row else None
    finally:
        conn.close()


def get_score_by_rank(rank: int, year: int) -> Optional[int]:
    """
    位次转分数：根据位次查询对应分数
    
    Args:
        rank: 位次
        year: 年份
        
    Returns:
        对应的分数，找不到返回最接近的分数
    """
    conn = get_connection()
    try:
        # 精确匹配
        row = conn.execute(
            "SELECT score FROM ranking_table WHERE year = ? AND cumulative_count >= ? ORDER BY cumulative_count ASC LIMIT 1",
            (year, rank)
        ).fetchone()
        return row["score"] if row else None
    finally:
        conn.close()


# ==================== 批量操作 ====================

def bulk_insert_schools(schools: List[Dict[str, Any]]) -> int:
    """
    批量插入学校
    
    Args:
        schools: 学校字典列表
        
    Returns:
        插入的记录数
    """
    conn = get_connection()
    try:
        cursor = conn.executemany(
            "INSERT INTO schools (name, province, city, type, level, features) VALUES (:name, :province, :city, :type, :level, :features)",
            schools
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def bulk_insert_rankings(rankings: List[Dict[str, Any]]) -> int:
    """
    批量插入一分一段表数据
    
    Args:
        rankings: 排名字典列表
        
    Returns:
        插入的记录数
    """
    conn = get_connection()
    try:
        cursor = conn.executemany(
            "INSERT INTO ranking_table (year, score, same_score_count, cumulative_count) VALUES (:year, :score, :same_score_count, :cumulative_count)",
            rankings
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
