"""
访客统计模块 - 记录独立IP数和查询次数，持久化到JSON文件
"""
import json
import os
import threading

from config import DATABASE_PATH

# stats.json 存放在与数据库相同的目录下，Docker volume 自动持久化
STATS_FILE = os.path.join(os.path.dirname(DATABASE_PATH), "stats.json")

# 线程锁，避免并发写入冲突
_lock = threading.Lock()


def load_stats() -> dict:
    """加载统计数据"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"unique_ips": [], "query_count": 0}


def save_stats(stats: dict):
    """保存统计数据"""
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)


def record_visit(ip: str):
    """记录访客IP（去重）"""
    with _lock:
        stats = load_stats()
        if ip and ip not in stats["unique_ips"]:
            stats["unique_ips"].append(ip)
            save_stats(stats)


def record_query():
    """记录查询次数"""
    with _lock:
        stats = load_stats()
        stats["query_count"] = stats.get("query_count", 0) + 1
        save_stats(stats)


def get_stats() -> dict:
    """获取统计摘要"""
    stats = load_stats()
    return {
        "visitor_count": len(stats.get("unique_ips", [])),
        "query_count": stats.get("query_count", 0),
    }
