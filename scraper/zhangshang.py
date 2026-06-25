"""
高考志愿推荐系统 - 掌上高考数据爬虫
数据源：掌上高考 (gaokao.cn) & 教育在线 API (api.eol.cn)

策略：
1. 先通过 school_code.json 获取全国高校ID映射表
2. 使用 requests 尝试直接请求数据接口
3. 如果请求失败，自动切换到种子数据作为fallback
"""
import json
import time
import random
from typing import List, Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.base import BaseScraper
from database.db import (
    get_connection, init_db,
    insert_school, insert_major, insert_admission_record
)


class ZhangshangScraper(BaseScraper):
    """掌上高考爬虫 - 获取高校录取数据"""
    
    # 高校ID映射表
    SCHOOL_CODE_URL = "https://static-data.gaokao.cn/www/2.0/school/school_code.json"
    # 教育在线API - 高校列表
    EOL_SCHOOL_LIST_URL = "https://api.eol.cn/gkcx/api/"
    # 掌上高考院校分数线接口（尝试直接请求）
    PROVINCE_LINE_URL = "https://static-data.gaokao.cn/www/2.0/schoolprovincescore/{school_id}/37/{year}.json"
    # 山东省代码
    SHANDONG_CODE = "37"
    
    def __init__(self, db_path: str = None):
        super().__init__(db_path)
        self.school_map = {}  # name -> school_id mapping
        self.years = [2023, 2024, 2025]
    
    def fetch_school_list(self) -> Dict[str, Any]:
        """
        获取学校ID映射表
        
        Returns:
            学校编码字典 {school_id: school_info}
        """
        print("[掌上高考] 正在获取学校编码表...")
        data = self.fetch_json(self.SCHOOL_CODE_URL)
        
        if data and isinstance(data, dict):
            # 解析响应格式: 可能是 {"code": "0", "data": {...}} 或直接的学校字典
            if "data" in data and isinstance(data["data"], dict):
                school_data = data["data"]
                print(f"[掌上高考] 获取到学校编码表，共 {len(school_data)} 条")
                return school_data
            elif "data" in data and isinstance(data["data"], list):
                # 列表格式，转换为字典
                school_data = {}
                for item in data["data"]:
                    sid = str(item.get("school_id", item.get("id", "")))
                    if sid:
                        school_data[sid] = item
                print(f"[掌上高考] 获取到学校编码表，共 {len(school_data)} 条")
                return school_data
            else:
                # 可能是其他格式，过滤掉API元数据字段
                meta_keys = {"code", "message", "msg", "status", "success"}
                school_data = {k: v for k, v in data.items() if k not in meta_keys}
                if school_data:
                    print(f"[掌上高考] 获取到学校编码表，共 {len(school_data)} 条")
                    return school_data
        
        # 尝试教育在线API
        print("[掌上高考] 编码表获取失败，尝试教育在线API...")
        return self._fetch_from_eol()
    
    def _fetch_from_eol(self) -> Dict[str, Any]:
        """
        通过教育在线API获取学校列表
        POST请求 Content-Type: application/x-www-form-urlencoded
        """
        all_schools = {}
        page = 1
        max_pages = 5  # 限制页数避免过多请求
        
        while page <= max_pages:
            params = {
                "access_token": "",
                "page": page,
                "size": 20,
                "sort": "view_total",
                "uri": "apidata/api/gk/school/lists",
            }
            
            result = self.post(self.EOL_SCHOOL_LIST_URL, data=params)
            
            if not result:
                break
            
            # 解析返回数据
            data = result.get("data", {})
            items = data.get("item", [])
            
            if not items:
                break
            
            for item in items:
                school_id = str(item.get("school_id", ""))
                if school_id:
                    all_schools[school_id] = {
                        "name": item.get("name", ""),
                        "province_name": item.get("province_name", ""),
                        "city_name": item.get("city_name", ""),
                        "type_name": item.get("type_name", ""),
                        "level_name": item.get("level_name", ""),
                    }
            
            page += 1
            time.sleep(self.config["request_interval"])
        
        print(f"[教育在线] 获取到 {len(all_schools)} 所学校")
        return all_schools
    
    def fetch_province_line(self, school_id: str, year: int = 2025) -> Optional[Dict]:
        """
        获取某学校在山东省的录取分数线
        
        Args:
            school_id: 学校ID
            year: 年份
            
        Returns:
            录取数据字典，失败返回None
        """
        url = self.PROVINCE_LINE_URL.format(school_id=school_id, year=year)
        data = self.fetch_json(url, use_cache=True)
        
        if data and isinstance(data, dict):
            return data.get("data", data)
        
        return None
    
    def scrape(self) -> List[Dict[str, Any]]:
        """
        执行完整爬取流程：
        1. 获取学校列表
        2. 逐个获取山东省录取线
        3. 返回所有录取记录
        """
        all_records = []
        
        # Step 1: 获取学校列表
        school_data = self.fetch_school_list()
        
        if not school_data:
            print("[掌上高考] 无法获取学校列表，将使用种子数据")
            return []
        
        # Step 2: 遍历学校获取分数线
        processed = 0
        failed = 0
        max_schools = 20  # 限制爬取数量避免被封
        max_consecutive_failures = 5  # 连续失赥次数阀值
        
        for school_id, info in list(school_data.items())[:max_schools]:
            school_name = info.get("name", "") if isinstance(info, dict) else str(info)
            
            if not school_name or school_name in ("code", "message", "msg"):
                continue
            
            got_data = False
            for year in self.years:
                score_data = self.fetch_province_line(school_id, year)
                
                if score_data:
                    records = self._parse_score_data(school_name, score_data, year)
                    all_records.extend(records)
                    got_data = True
            
            if not got_data:
                failed += 1
            else:
                failed = 0  # 重置连续失败计数
            
            processed += 1
            
            # 如果连续多次失败，提前结束
            if failed >= max_consecutive_failures:
                print(f"[掌上高考] 连续 {failed} 次获取失败，停止爬取")
                break
            
            if processed % 10 == 0:
                print(f"[掌上高考] 已处理 {processed} 所学校...")
        
        print(f"[掌上高考] 共获取 {len(all_records)} 条录取记录")
        return all_records
    
    def _parse_score_data(self, school_name: str, data: Any, year: int) -> List[Dict]:
        """解析分数线数据为标准格式"""
        records = []
        
        if isinstance(data, dict):
            items = data.get("item", []) or data.get("data", [])
            if isinstance(items, list):
                for item in items:
                    record = {
                        "school_name": school_name,
                        "year": year,
                        "major_name": item.get("spname", item.get("major_name", "未知专业")),
                        "batch": item.get("batch", "普通类一段"),
                        "min_score": item.get("min", item.get("min_score")),
                        "min_rank": item.get("min_section", item.get("min_rank")),
                        "avg_score": item.get("average", item.get("avg_score")),
                        "plan_count": item.get("num", item.get("plan_count")),
                    }
                    records.append(record)
        elif isinstance(data, list):
            for item in data:
                record = {
                    "school_name": school_name,
                    "year": year,
                    "major_name": item.get("spname", item.get("major_name", "未知专业")),
                    "batch": item.get("batch", "普通类一段"),
                    "min_score": item.get("min", item.get("min_score")),
                    "min_rank": item.get("min_section", item.get("min_rank")),
                    "avg_score": item.get("average", item.get("avg_score")),
                    "plan_count": item.get("num", item.get("plan_count")),
                }
                records.append(record)
        
        return records
    
    def save(self, data: List[Dict[str, Any]]):
        """
        保存爬取数据到数据库
        """
        init_db()
        conn = get_connection()
        
        # 缓存已存在的学校和专业ID
        school_cache = {}
        major_cache = {}
        
        try:
            for record in data:
                school_name = record.get("school_name", "")
                major_name = record.get("major_name", "")
                
                # 获取或创建学校
                if school_name not in school_cache:
                    row = conn.execute(
                        "SELECT id FROM schools WHERE name = ?", (school_name,)
                    ).fetchone()
                    if row:
                        school_cache[school_name] = row["id"]
                    else:
                        cursor = conn.execute(
                            "INSERT INTO schools (name) VALUES (?)", (school_name,)
                        )
                        school_cache[school_name] = cursor.lastrowid
                        conn.commit()
                
                # 获取或创建专业
                if major_name not in major_cache:
                    row = conn.execute(
                        "SELECT id FROM majors WHERE name = ?", (major_name,)
                    ).fetchone()
                    if row:
                        major_cache[major_name] = row["id"]
                    else:
                        cursor = conn.execute(
                            "INSERT INTO majors (name) VALUES (?)", (major_name,)
                        )
                        major_cache[major_name] = cursor.lastrowid
                        conn.commit()
                
                school_id = school_cache[school_name]
                major_id = major_cache[major_name]
                
                # 插入录取记录
                try:
                    conn.execute(
                        """INSERT INTO admission_records 
                           (year, school_id, major_id, batch, min_score, min_rank, avg_score, plan_count)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            record.get("year"),
                            school_id,
                            major_id,
                            record.get("batch", "普通类一段"),
                            record.get("min_score"),
                            record.get("min_rank"),
                            record.get("avg_score"),
                            record.get("plan_count"),
                        )
                    )
                except Exception as e:
                    pass  # 跳过重复记录
            
            conn.commit()
            print(f"[掌上高考] 数据保存完成")
        finally:
            conn.close()
    
    def run(self, years: List[int] = None):
        """
        主执行入口
        
        Args:
            years: 年份列表
        """
        if years:
            self.years = years
        
        print(f"[掌上高考] 开始爬取，目标年份: {self.years}")
        
        try:
            data = self.scrape()
            if data:
                self.save(data)
                print(f"[掌上高考] 爬取完成，共 {len(data)} 条记录")
            else:
                print("[掌上高考] 未获取到在线数据，切换到种子数据...")
                self._use_seed_data()
        except Exception as e:
            print(f"[掌上高考] 爬取异常: {e}，切换到种子数据...")
            self._use_seed_data()


if __name__ == "__main__":
    scraper = ZhangshangScraper()
    scraper.run()
