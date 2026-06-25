"""
高考志愿推荐系统 - 爬虫模块

主要组件：
- BaseScraper: 爬虫基类
- ZhangshangScraper: 掌上高考数据爬虫
- ShandongEduScraper: 山东教育考试院爬虫
- generate_seed_data: 种子数据生成函数
"""
from scraper.base import BaseScraper
from scraper.zhangshang import ZhangshangScraper
from scraper.shandong_edu import ShandongEduScraper
from scraper.seed import generate_seed_data

__all__ = [
    "BaseScraper",
    "ZhangshangScraper",
    "ShandongEduScraper",
    "generate_seed_data",
]
