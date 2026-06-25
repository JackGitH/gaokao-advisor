"""
高考志愿推荐系统 - 配置文件
"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== 数据库配置 ====================
DATABASE_PATH = os.path.join(BASE_DIR, "database", "gaokao.db")

# ==================== 爬虫配置 ====================
SCRAPER_CONFIG = {
    # User-Agent 列表，随机轮换防止被封
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ],
    # 请求间隔（秒），避免频率过高被封
    "request_interval": 2.0,
    # 最大重试次数
    "max_retries": 3,
    # 请求超时时间（秒）
    "timeout": 30,
    # 并发数
    "concurrency": 3,
}

# ==================== API 配置 ====================
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": True,
    "title": "高考志愿推荐系统",
    "description": "基于历年录取数据的智能志愿推荐API",
    "version": "1.0.0",
}

# ==================== 推荐算法配置 ====================
ALGORITHM_CONFIG = {
    # 冲稳保比例
    "rush_ratio": 0.3,      # 冲一冲
    "stable_ratio": 0.4,    # 稳一稳
    "safe_ratio": 0.3,      # 保一保
    # 排名浮动范围
    "rush_rank_offset": 5000,    # 冲：排名前5000
    "stable_rank_offset": 2000,  # 稳：排名前后2000
    "safe_rank_offset": 5000,    # 保：排名后5000
    # 默认分析年份范围
    "default_years": [2022, 2023, 2024, 2025],
}

# ==================== 山东高考配置 ====================
SHANDONG_CONFIG = {
    "province": "山东",
    "exam_type": "新高考",  # 3+3模式
    "total_score": 750,
    "batches": ["普通类一段", "普通类二段", "艺术类", "体育类"],
}
