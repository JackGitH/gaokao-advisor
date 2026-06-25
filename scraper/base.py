"""
高考志愿推荐系统 - 爬虫基类
所有数据源爬虫的基类，提供通用能力
"""
import time
import random
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SCRAPER_CONFIG, DATABASE_PATH
from scraper.utils import (
    get_random_ua, get_headers, get_random_delay,
    save_response_cache, load_response_cache
)


class BaseScraper(ABC):
    """爬虫基类"""
    
    def __init__(self, db_path: str = None):
        self.session = requests.Session()
        self.config = SCRAPER_CONFIG
        self.db_path = db_path or DATABASE_PATH
        self._last_request_time = 0
    
    def _rate_limit(self):
        """请求频率控制"""
        elapsed = time.time() - self._last_request_time
        interval = get_random_delay(self.config["request_interval"])
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_time = time.time()
    
    def fetch(self, url: str, params: Dict = None, use_cache: bool = True) -> Optional[str]:
        """
        发起HTTP GET请求并返回响应文本
        
        Args:
            url: 请求URL
            params: 请求参数
            use_cache: 是否使用缓存
            
        Returns:
            响应文本，失败返回None
        """
        # 尝试从缓存读取
        cache_key = url + (json.dumps(params, sort_keys=True) if params else "")
        if use_cache:
            cached = load_response_cache(cache_key)
            if cached is not None:
                print(f"[缓存命中] {url}")
                return cached
        
        self._rate_limit()
        
        for attempt in range(self.config["max_retries"]):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=get_headers(),
                    timeout=self.config["timeout"],
                )
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                text = response.text
                
                # 保存缓存
                if use_cache:
                    save_response_cache(cache_key, text)
                
                return text
            except requests.RequestException as e:
                print(f"[GET请求失败] (尝试 {attempt + 1}/{self.config['max_retries']}): {url} - {e}")
                time.sleep(self.config["request_interval"] * (attempt + 1))
        
        return None
    
    def fetch_json(self, url: str, params: Dict = None, use_cache: bool = True) -> Optional[Any]:
        """
        发起HTTP GET请求并返回JSON数据
        
        Args:
            url: 请求URL
            params: 请求参数
            use_cache: 是否使用缓存
            
        Returns:
            JSON数据，失败返回None
        """
        cache_key = url + (json.dumps(params, sort_keys=True) if params else "")
        if use_cache:
            cached = load_response_cache(cache_key)
            if cached is not None:
                print(f"[缓存命中] {url}")
                if isinstance(cached, str):
                    try:
                        return json.loads(cached)
                    except json.JSONDecodeError:
                        return cached
                return cached
        
        self._rate_limit()
        
        for attempt in range(self.config["max_retries"]):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=get_headers(),
                    timeout=self.config["timeout"],
                )
                response.raise_for_status()
                data = response.json()
                
                if use_cache:
                    save_response_cache(cache_key, data)
                
                return data
            except requests.RequestException as e:
                print(f"[GET-JSON请求失败] (尝试 {attempt + 1}/{self.config['max_retries']}): {url} - {e}")
                time.sleep(self.config["request_interval"] * (attempt + 1))
            except json.JSONDecodeError as e:
                print(f"[JSON解析失败]: {url} - {e}")
                return None
        
        return None
    
    def post(self, url: str, data: Dict = None, json_data: Dict = None,
             use_cache: bool = True) -> Optional[Any]:
        """
        发起HTTP POST请求
        
        Args:
            url: 请求URL
            data: 表单数据
            json_data: JSON数据
            use_cache: 是否使用缓存
            
        Returns:
            响应JSON数据，失败返回None
        """
        cache_key = url + json.dumps(data or json_data or {}, sort_keys=True)
        if use_cache:
            cached = load_response_cache(cache_key)
            if cached is not None:
                print(f"[缓存命中] POST {url}")
                return cached
        
        self._rate_limit()
        
        headers = get_headers()
        if data:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        for attempt in range(self.config["max_retries"]):
            try:
                response = self.session.post(
                    url,
                    data=data,
                    json=json_data,
                    headers=headers,
                    timeout=self.config["timeout"],
                )
                response.raise_for_status()
                result = response.json()
                
                if use_cache:
                    save_response_cache(cache_key, result)
                
                return result
            except requests.RequestException as e:
                print(f"[POST请求失败] (尝试 {attempt + 1}/{self.config['max_retries']}): {url} - {e}")
                time.sleep(self.config["request_interval"] * (attempt + 1))
            except json.JSONDecodeError as e:
                print(f"[JSON解析失败]: {url} - {e}")
                return None
        
        return None
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """解析HTML"""
        return BeautifulSoup(html, "html.parser")
    
    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        执行爬取，子类必须实现
        
        Returns:
            爬取到的数据列表
        """
        pass
    
    @abstractmethod
    def save(self, data: List[Dict[str, Any]]):
        """
        保存数据到数据库，子类必须实现
        
        Args:
            data: 要保存的数据列表
        """
        pass
    
    def run(self, years: List[int] = None):
        """
        主执行流程：爬取 -> 保存
        
        Args:
            years: 年份列表，默认 [2023, 2024, 2025]
        """
        if years is None:
            years = [2023, 2024, 2025]
        
        print(f"[{self.__class__.__name__}] 开始爬取，年份: {years}")
        
        try:
            data = self.scrape()
            if data:
                self.save(data)
                print(f"[{self.__class__.__name__}] 完成，共保存 {len(data)} 条记录")
            else:
                print(f"[{self.__class__.__name__}] 未获取到数据，尝试使用种子数据...")
                self._use_seed_data()
        except Exception as e:
            print(f"[{self.__class__.__name__}] 爬取失败: {e}，切换到种子数据...")
            self._use_seed_data()
    
    def _use_seed_data(self):
        """使用种子数据作为fallback"""
        from scraper.seed import generate_seed_data
        generate_seed_data()
        print(f"[{self.__class__.__name__}] 种子数据已写入数据库")
