"""
高考志愿推荐系统 - 数据库表结构定义
包含5张核心表：schools, majors, admission_records, score_lines, ranking_table
"""

# ==================== 建表 DDL ====================

CREATE_SCHOOLS_TABLE = """
CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    province TEXT,
    city TEXT,
    type TEXT,          -- 985/211/双一流/普通本科
    level TEXT,         -- 本科一批/本科二批等
    features TEXT       -- 学校特色，逗号分隔
);
"""

CREATE_MAJORS_TABLE = """
CREATE TABLE IF NOT EXISTS majors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,      -- 学科门类：工学/理学/文学等
    hot_trend TEXT      -- 热门/冷门/平稳
);
"""

CREATE_ADMISSION_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS admission_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    school_id INTEGER NOT NULL,
    major_id INTEGER NOT NULL,
    batch TEXT,              -- 批次：普通类一段/普通类二段等
    min_score INTEGER,       -- 最低录取分
    min_rank INTEGER,        -- 最低录取位次
    avg_score INTEGER,       -- 平均录取分
    plan_count INTEGER,      -- 计划招生人数
    actual_count INTEGER,    -- 实际录取人数
    data_source TEXT DEFAULT 'seed', -- 数据来源：seed/gaokao.cn等
    FOREIGN KEY (school_id) REFERENCES schools(id),
    FOREIGN KEY (major_id) REFERENCES majors(id)
);
"""

CREATE_SCORE_LINES_TABLE = """
CREATE TABLE IF NOT EXISTS score_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    batch TEXT NOT NULL,     -- 批次
    score INTEGER NOT NULL,  -- 分数线
    rank INTEGER             -- 对应位次
);
"""

CREATE_RANKING_TABLE = """
CREATE TABLE IF NOT EXISTS ranking_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    score INTEGER NOT NULL,
    same_score_count INTEGER,    -- 同分人数
    cumulative_count INTEGER     -- 累计人数（即位次）
);
"""

# 所有建表语句列表
ALL_TABLES = [
    CREATE_SCHOOLS_TABLE,
    CREATE_MAJORS_TABLE,
    CREATE_ADMISSION_RECORDS_TABLE,
    CREATE_SCORE_LINES_TABLE,
    CREATE_RANKING_TABLE,
]

# ==================== 索引 ====================

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_admission_year ON admission_records(year);",
    "CREATE INDEX IF NOT EXISTS idx_admission_school ON admission_records(school_id);",
    "CREATE INDEX IF NOT EXISTS idx_admission_major ON admission_records(major_id);",
    "CREATE INDEX IF NOT EXISTS idx_admission_rank ON admission_records(min_rank);",
    "CREATE INDEX IF NOT EXISTS idx_ranking_year_score ON ranking_table(year, score);",
    "CREATE INDEX IF NOT EXISTS idx_score_lines_year ON score_lines(year, batch);",
    "CREATE INDEX IF NOT EXISTS idx_schools_type ON schools(type);",
]


def init_db(connection):
    """
    初始化数据库：创建所有表和索引
    
    Args:
        connection: sqlite3 数据库连接对象
    """
    cursor = connection.cursor()
    
    # 创建表
    for ddl in ALL_TABLES:
        cursor.execute(ddl)
    
    # 创建索引
    for index_sql in CREATE_INDEXES:
        cursor.execute(index_sql)
    
    connection.commit()
    print("数据库初始化完成：5张表和索引已创建")
