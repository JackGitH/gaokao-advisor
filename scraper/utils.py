"""
高考志愿推荐系统 - 反爬工具集
提供UA轮换、频率控制、重试机制、响应缓存等能力
"""
import random
import time
import hashlib
import json
import os
import functools
from typing import Dict, Optional, Any, Callable

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SCRAPER_CONFIG, BASE_DIR


# ==================== 缓存目录 ====================
DEFAULT_CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")


def get_random_ua() -> str:
    """从配置中随机选取一个User-Agent"""
    return random.choice(SCRAPER_CONFIG["user_agents"])


def get_headers(referer: str = None) -> Dict[str, str]:
    """
    构造带随机UA的请求头
    
    Args:
        referer: 可选的Referer头
        
    Returns:
        请求头字典
    """
    headers = {
        "User-Agent": get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def rate_limit(seconds: float = None):
    """
    请求频率控制装饰器
    
    Args:
        seconds: 最小请求间隔（秒），默认使用配置值
    """
    if seconds is None:
        seconds = SCRAPER_CONFIG["request_interval"]
    
    def decorator(func: Callable) -> Callable:
        last_call_time = [0.0]
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call_time[0]
            if elapsed < seconds:
                # 加入随机抖动
                sleep_time = seconds - elapsed + random.uniform(0, 0.5)
                time.sleep(sleep_time)
            result = func(*args, **kwargs)
            last_call_time[0] = time.time()
            return result
        
        return wrapper
    return decorator


def retry(max_retries: int = None, backoff_factor: float = 1.0):
    """
    指数退避重试装饰器
    
    Args:
        max_retries: 最大重试次数，默认使用配置值
        backoff_factor: 退避因子
    """
    if max_retries is None:
        max_retries = SCRAPER_CONFIG["max_retries"]
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"[重试失败] {func.__name__} 经过 {max_retries} 次尝试后仍失败: {e}")
                        raise
                    wait_time = backoff_factor * (2 ** attempt) + random.uniform(0, 1)
                    print(f"[重试] {func.__name__} 第 {attempt + 1}/{max_retries} 次失败，等待 {wait_time:.1f}s: {e}")
                    time.sleep(wait_time)
        return wrapper
    return decorator


def _url_to_cache_key(url: str) -> str:
    """将URL转为缓存文件名"""
    return hashlib.md5(url.encode()).hexdigest()


def save_response_cache(url: str, data: Any, cache_dir: str = None):
    """
    缓存响应数据到本地文件
    
    Args:
        url: 请求URL（作为缓存key）
        data: 要缓存的数据（JSON可序列化）
        cache_dir: 缓存目录，默认使用 data/cache
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = _url_to_cache_key(url)
    cache_path = os.path.join(cache_dir, f"{cache_key}.json")
    
    cache_entry = {
        "url": url,
        "timestamp": time.time(),
        "data": data,
    }
    
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_entry, f, ensure_ascii=False, indent=2)


def load_response_cache(url: str, cache_dir: str = None, max_age: int = 86400) -> Optional[Any]:
    """
    从缓存读取响应数据
    
    Args:
        url: 请求URL
        cache_dir: 缓存目录
        max_age: 缓存最大有效期（秒），默认24小时
        
    Returns:
        缓存的数据，不存在或过期返回None
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    
    cache_key = _url_to_cache_key(url)
    cache_path = os.path.join(cache_dir, f"{cache_key}.json")
    
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_entry = json.load(f)
        
        # 检查是否过期
        if time.time() - cache_entry.get("timestamp", 0) > max_age:
            return None
        
        return cache_entry.get("data")
    except (json.JSONDecodeError, IOError):
        return None


def get_random_delay(base_interval: float = None) -> float:
    """
    获取随机延迟时间，加入随机抖动
    
    Args:
        base_interval: 基础间隔，默认使用配置值
        
    Returns:
        随机延迟秒数
    """
    if base_interval is None:
        base_interval = SCRAPER_CONFIG["request_interval"]
    jitter = base_interval * random.uniform(-0.5, 0.5)
    return max(0.5, base_interval + jitter)


def rotate_proxy(proxy_list: list = None) -> Optional[Dict[str, str]]:
    """
    轮换代理IP
    
    Args:
        proxy_list: 代理列表
        
    Returns:
        代理字典
    """
    if not proxy_list:
        return None
    proxy = random.choice(proxy_list)
    return {"http": proxy, "https": proxy}

