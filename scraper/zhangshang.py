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
    init_db,
    insert_school, insert_major, insert_admission_record
)


class ZhangshangScraper(BaseScraper):
    """掌上高考爬虫 - 获取高校录取数据"""
    
    # 高校ID映射表
    SCHOOL_CODE_URL = "https://static-data.gaokao.cn/www/2.0/school/school_code.json"
    # 教育在线API - 高校列表
    EOL_SCHOOL_LIST_URL = "https://api.eol.cn/gkcx/api/"
    # 掌上高考院校专业分数线接口
    SCHOOL_SPECIAL_SCORE_URL = "https://static-data.gaokao.cn/www/2.0/schoolspecialscore/{school_id}/{year}/37.json"
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
        url = self.SCHOOL_SPECIAL_SCORE_URL.format(school_id=school_id, year=year)
        data = self.fetch_json(url, use_cache=True)
        
        if data and isinstance(data, dict):
            return data.get("data", data)
        
        return None

    def _extract_school_meta(self, info: Any) -> Dict[str, Any]:
        """Extract school metadata from gaokao.cn/EOL school list rows."""
        if not isinstance(info, dict):
            return {}

        features = []
        if str(info.get("f985", info.get("is_985", ""))) in ("1", "True", "true"):
            school_type = "985"
            features.append("985")
        elif str(info.get("f211", info.get("is_211", ""))) in ("1", "True", "true"):
            school_type = "211"
            features.append("211")
        elif str(info.get("is_dual_class", info.get("dual_class", ""))) in ("1", "True", "true"):
            school_type = "双一流"
            features.append("双一流")
        else:
            school_type = info.get("school_level")

        return {
            "province": info.get("province_name") or info.get("province"),
            "city": info.get("city_name") or info.get("city"),
            "type": school_type,
            "level": info.get("level_name") or info.get("level"),
            "features": ",".join(features) if features else None,
        }
    
    def scrape(
        self,
        school_names: Optional[List[str]] = None,
        max_schools: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
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
        
        # Step 2: 遍历学校获取专业分数线
        processed = 0
        failed = 0
        wanted_names = set(school_names or [])
        candidates = []
        for raw_school_id, info in school_data.items():
            if not isinstance(info, dict):
                continue
            school_name = info.get("name", "")
            gaokao_school_id = str(info.get("school_id") or raw_school_id)
            if not school_name or school_name in ("code", "message", "msg"):
                continue
            if wanted_names and school_name not in wanted_names:
                continue
            candidates.append((gaokao_school_id, info))

        if max_schools is None:
            max_schools = len(candidates) if wanted_names else 20

        max_consecutive_failures = 5  # 连续失赥次数阀值
        
        for school_id, info in candidates[:max_schools]:
            school_name = info.get("name", "")
            school_meta = self._extract_school_meta(info)
            
            got_data = False
            for year in self.years:
                score_data = self.fetch_province_line(school_id, year)
                
                if score_data:
                    records = self._parse_score_data(school_name, score_data, year)
                    for record in records:
                        record.update(school_meta)
                    all_records.extend(records)
                    got_data = True
            
            if not got_data:
                failed += 1
            else:
                failed = 0  # 重置连续失败计数
            
            processed += 1
            
            # 如果连续多次失败，提前结束
            if not wanted_names and failed >= max_consecutive_failures:
                print(f"[掌上高考] 连续 {failed} 次获取失败，停止爬取")
                break
            
            if processed % 10 == 0:
                print(f"[掌上高考] 已处理 {processed} 所学校...")
        
        print(f"[掌上高考] 共获取 {len(all_records)} 条录取记录")
        return all_records
    
    def _parse_score_data(self, school_name: str, data: Any, year: int) -> List[Dict]:
        """解析分数线数据为标准格式"""
        records = []

        for item in self._iter_score_items(data):
            major_name = item.get("spname") or item.get("sp_name") or item.get("major_name") or "未知专业"
            record = {
                "school_name": school_name,
                "year": year,
                "major_name": major_name,
                "category": item.get("level2_name") or item.get("category"),
                "batch": item.get("local_batch_name") or item.get("batch") or "普通类一段",
                "min_score": self._to_int(item.get("min", item.get("min_score"))),
                "min_rank": self._to_int(item.get("min_section", item.get("min_rank"))),
                "avg_score": self._to_int(item.get("average", item.get("avg_score"))),
                "plan_count": self._to_int(item.get("lq_num", item.get("num", item.get("plan_count")))),
                "data_source": "gaokao.cn",
            }
            if record["min_score"] is not None or record["min_rank"] is not None:
                records.append(record)
        
        return records

    def _iter_score_items(self, data: Any) -> List[Dict]:
        """Flatten gaokao.cn score payload blocks into item rows."""
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if not isinstance(data, dict):
            return []

        items = data.get("item")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]

        nested = data.get("data")
        if nested is not None and nested is not data:
            return self._iter_score_items(nested)

        flattened = []
        for block in data.values():
            if isinstance(block, dict):
                block_items = block.get("item")
                if isinstance(block_items, list):
                    flattened.extend(item for item in block_items if isinstance(item, dict))
            elif isinstance(block, list):
                flattened.extend(item for item in block if isinstance(item, dict))
        return flattened

    def _to_int(self, value) -> Optional[int]:
        if value in (None, "", "-"):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    
    def save(self, data: List[Dict[str, Any]]):
        """
        保存爬取数据到数据库
        """
        init_db()

        # 缓存已存在的学校和专业ID
        school_cache = {}
        major_cache = {}

        for record in data:
            school_name = record.get("school_name", "")
            major_name = record.get("major_name", "")
            if not school_name or not major_name:
                continue

            if school_name not in school_cache:
                school_cache[school_name] = insert_school(
                    school_name,
                    record.get("province"),
                    record.get("city"),
                    record.get("type"),
                    record.get("level"),
                    record.get("features"),
                )

            if major_name not in major_cache:
                major_cache[major_name] = insert_major(
                    major_name,
                    record.get("category"),
                    record.get("hot_trend"),
                )

            insert_admission_record(
                record.get("year"),
                school_cache[school_name],
                major_cache[major_name],
                record.get("batch", "普通类一段"),
                record.get("min_score"),
                record.get("min_rank"),
                record.get("avg_score"),
                record.get("plan_count"),
                record.get("actual_count"),
                record.get("data_source", "gaokao.cn"),
            )

        print(f"[掌上高考] 数据保存完成")
    
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
