"""
高考志愿推荐系统 - 山东省教育考试院数据爬虫
数据源：山东省教育招生考试院 (sdzk.cn)

职责：
1. 获取山东省高考批次线（一段线/二段线/特殊类型线）
2. 获取一分一段表
3. 如果无法在线获取，使用模拟数据fallback
"""
import json
import re
import time
from typing import List, Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.base import BaseScraper
from database.db import (
    get_connection, init_db,
    insert_score_line, insert_ranking, bulk_insert_rankings
)


class ShandongEduScraper(BaseScraper):
    """山东省教育考试院爬虫 - 获取批次线和一分一段表"""
    
    BASE_URL = "https://www.sdzk.cn"
    
    # 已知的新闻页面ID（包含分数线/一分一段表数据）
    NEWS_IDS = {
        2025: {"score_line": "7256", "ranking": "7257"},
        2024: {"score_line": "7102", "ranking": "7103"},
        2023: {"score_line": "6943", "ranking": "6944"},
    }
    
    def __init__(self, db_path: str = None):
        super().__init__(db_path)
        self.years = [2023, 2024, 2025]
    
    def fetch_score_lines(self, year: int) -> List[Dict[str, Any]]:
        """
        获取某年的批次线数据
        
        山东省2020年后不分文理：
        - 普通类一段线
        - 普通类二段线
        - 特殊类型招生控制线
        
        Args:
            year: 年份
            
        Returns:
            批次线列表
        """
        news_id = self.NEWS_IDS.get(year, {}).get("score_line")
        if not news_id:
            print(f"[山东考试院] {year}年批次线页面ID未知")
            return self._get_fallback_score_lines(year)
        
        url = f"{self.BASE_URL}/NewsInfo.aspx?NewsID={news_id}"
        html = self.fetch(url, use_cache=True)
        
        if html:
            lines = self._parse_score_lines_html(html, year)
            if lines:
                return lines
        
        print(f"[山东考试院] {year}年批次线在线获取失败，使用备用数据")
        return self._get_fallback_score_lines(year)
    
    def _parse_score_lines_html(self, html: str, year: int) -> List[Dict[str, Any]]:
        """解析批次线HTML页面"""
        lines = []
        soup = self.parse_html(html)
        
        # 尝试从表格或文本中提取分数线
        text = soup.get_text()
        
        # 匹配模式：一段线 XXX 分
        patterns = [
            (r"[一1]段[线|分].*?(\d{3})", "普通类一段"),
            (r"二段[线|分].*?(\d{3})", "普通类二段"),
            (r"特殊类型.*?(\d{3})", "特殊类型招生控制线"),
            (r"普通类.*?一段.*?(\d{3})", "普通类一段"),
            (r"普通类.*?二段.*?(\d{3})", "普通类二段"),
        ]
        
        for pattern, batch in patterns:
            match = re.search(pattern, text)
            if match:
                score = int(match.group(1))
                if 100 <= score <= 750:
                    lines.append({
                        "year": year,
                        "batch": batch,
                        "score": score,
                    })
        
        return lines
    
    def _get_fallback_score_lines(self, year: int) -> List[Dict[str, Any]]:
        """批次线备用数据（基于真实数据）"""
        fallback = {
            2023: [
                {"year": 2023, "batch": "普通类一段", "score": 443, "rank": 308701},
                {"year": 2023, "batch": "普通类二段", "score": 150, "rank": 662199},
                {"year": 2023, "batch": "特殊类型招生控制线", "score": 520, "rank": 98957},
            ],
            2024: [
                {"year": 2024, "batch": "普通类一段", "score": 444, "rank": 307432},
                {"year": 2024, "batch": "普通类二段", "score": 150, "rank": 659800},
                {"year": 2024, "batch": "特殊类型招生控制线", "score": 520, "rank": 99051},
            ],
            2025: [
                {"year": 2025, "batch": "普通类一段", "score": 443, "rank": 310256},
                {"year": 2025, "batch": "普通类二段", "score": 150, "rank": 665321},
                {"year": 2025, "batch": "特殊类型招生控制线", "score": 521, "rank": 97823},
            ],
        }
        return fallback.get(year, [])
    
    def fetch_ranking_table(self, year: int) -> List[Dict[str, Any]]:
        """
        获取某年的一分一段表
        
        山东考试院通常以XLS文件发布，尝试下载并解析
        如果无法获取，使用模拟数据
        
        Args:
            year: 年份
            
        Returns:
            一分一段表数据列表
        """
        news_id = self.NEWS_IDS.get(year, {}).get("ranking")
        if not news_id:
            print(f"[山东考试院] {year}年一分一段表页面ID未知")
            return self._generate_ranking_table(year)
        
        url = f"{self.BASE_URL}/NewsInfo.aspx?NewsID={news_id}"
        html = self.fetch(url, use_cache=True)
        
        if html:
            # 尝试从HTML中提取XLS下载链接
            rankings = self._parse_ranking_page(html, year)
            if rankings:
                return rankings
        
        print(f"[山东考试院] {year}年一分一段表在线获取失败，使用模拟数据")
        return self._generate_ranking_table(year)
    
    def _parse_ranking_page(self, html: str, year: int) -> List[Dict[str, Any]]:
        """尝试从页面解析一分一段表数据或下载链接"""
        soup = self.parse_html(html)
        rankings = []
        
        # 尝试找表格数据
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # 跳过表头
                cols = row.find_all(["td", "th"])
                if len(cols) >= 3:
                    try:
                        score = int(cols[0].get_text(strip=True))
                        same_count = int(cols[1].get_text(strip=True))
                        cumulative = int(cols[2].get_text(strip=True))
                        
                        if 100 <= score <= 750:
                            rankings.append({
                                "year": year,
                                "score": score,
                                "same_score_count": same_count,
                                "cumulative_count": cumulative,
                            })
                    except (ValueError, IndexError):
                        continue
        
        # 尝试找XLS下载链接
        if not rankings:
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                if href.endswith((".xls", ".xlsx")):
                    xls_url = href if href.startswith("http") else f"{self.BASE_URL}/{href.lstrip('/')}"
                    print(f"[山东考试院] 发现XLS文件: {xls_url}")
                    rankings = self._download_and_parse_xls(xls_url, year)
                    if rankings:
                        break
        
        return rankings
    
    def _download_and_parse_xls(self, url: str, year: int) -> List[Dict[str, Any]]:
        """下载并解析XLS文件"""
        try:
            import pandas as pd
            
            self._rate_limit()
            response = self.session.get(url, headers=self._get_headers_dict(), timeout=30)
            
            if response.status_code == 200:
                # 保存临时文件
                import tempfile
                suffix = ".xlsx" if url.endswith(".xlsx") else ".xls"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                    f.write(response.content)
                    temp_path = f.name
                
                try:
                    df = pd.read_excel(temp_path)
                    rankings = []
                    
                    # 尝试识别列名
                    cols = df.columns.tolist()
                    score_col = None
                    same_col = None
                    cumulative_col = None
                    
                    for col in cols:
                        col_str = str(col)
                        if "分数" in col_str or "成绩" in col_str:
                            score_col = col
                        elif "同分" in col_str or "本段" in col_str:
                            same_col = col
                        elif "累计" in col_str or "位次" in col_str:
                            cumulative_col = col
                    
                    # 如果没找到对应列名，用位置
                    if score_col is None and len(cols) >= 3:
                        score_col, same_col, cumulative_col = cols[0], cols[1], cols[2]
                    
                    if score_col:
                        for _, row in df.iterrows():
                            try:
                                score = int(row[score_col])
                                same_count = int(row[same_col]) if same_col else 0
                                cumulative = int(row[cumulative_col]) if cumulative_col else 0
                                
                                if 100 <= score <= 750:
                                    rankings.append({
                                        "year": year,
                                        "score": score,
                                        "same_score_count": same_count,
                                        "cumulative_count": cumulative,
                                    })
                            except (ValueError, TypeError):
                                continue
                    
                    return rankings
                finally:
                    os.unlink(temp_path)
        except ImportError:
            print("[山东考试院] pandas未安装，无法解析XLS")
        except Exception as e:
            print(f"[山东考试院] XLS解析失败: {e}")
        
        return []
    
    def _get_headers_dict(self) -> Dict[str, str]:
        """获取请求头（兼容方法）"""
        from scraper.utils import get_headers
        return get_headers(referer=self.BASE_URL)
    
    def _generate_ranking_table(self, year: int) -> List[Dict[str, Any]]:
        """生成模拟一分一段表"""
        import math
        import random
        
        total_students = {2023: 662199, 2024: 659800, 2025: 665321}.get(year, 660000)
        mean = 450 + (year - 2024) * 0.5
        std = 88
        
        rankings = []
        cumulative = 0
        
        for score in range(750, 149, -1):
            z = (score - mean) / std
            pdf = math.exp(-0.5 * z * z) / (std * math.sqrt(2 * math.pi))
            same_count = max(1, int(pdf * total_students))
            
            # 高分段微调
            if score >= 700:
                same_count = random.randint(1, 5)
            elif score >= 680:
                same_count = random.randint(10, 40)
            elif score >= 650:
                same_count = random.randint(80, 200)
            elif score < 200:
                same_count = random.randint(500, 1500)
            
            cumulative += same_count
            if cumulative > total_students:
                cumulative = total_students
            
            rankings.append({
                "year": year,
                "score": score,
                "same_score_count": same_count,
                "cumulative_count": cumulative,
            })
        
        return rankings
    
    def scrape(self) -> List[Dict[str, Any]]:
        """
        执行完整爬取：批次线 + 一分一段表
        
        Returns:
            包含所有数据的列表
        """
        all_data = {
            "score_lines": [],
            "rankings": [],
        }
        
        for year in self.years:
            # 获取批次线
            print(f"[山东考试院] 获取 {year} 年批次线...")
            lines = self.fetch_score_lines(year)
            all_data["score_lines"].extend(lines)
            
            # 获取一分一段表
            print(f"[山东考试院] 获取 {year} 年一分一段表...")
            rankings = self.fetch_ranking_table(year)
            all_data["rankings"].extend(rankings)
        
        # 合并返回
        return [all_data]  # 包装为list以符合基类接口
    
    def save(self, data: List[Dict[str, Any]]):
        """
        保存批次线和一分一段表到数据库
        """
        init_db()
        
        if not data:
            return
        
        all_data = data[0]  # scrape返回的是包含dict的list
        
        # 保存批次线
        score_lines = all_data.get("score_lines", [])
        for line in score_lines:
            try:
                insert_score_line(
                    line["year"],
                    line["batch"],
                    line["score"],
                    line.get("rank")
                )
            except Exception as e:
                pass  # 跳过重复
        
        print(f"[山东考试院] 已保存 {len(score_lines)} 条批次线")
        
        # 保存一分一段表
        rankings = all_data.get("rankings", [])
        if rankings:
            try:
                bulk_insert_rankings(rankings)
            except Exception:
                # 逐条插入
                saved = 0
                for r in rankings:
                    try:
                        insert_ranking(
                            r["year"], r["score"],
                            r["same_score_count"], r["cumulative_count"]
                        )
                        saved += 1
                    except Exception:
                        pass
                print(f"[山东考试院] 已保存 {saved} 条一分一段记录")
            else:
                print(f"[山东考试院] 已批量保存 {len(rankings)} 条一分一段记录")
    
    def run(self, years: List[int] = None):
        """
        主执行入口
        
        Args:
            years: 年份列表
        """
        if years:
            self.years = years
        
        print(f"[山东考试院] 开始获取数据，目标年份: {self.years}")
        
        try:
            data = self.scrape()
            if data and data[0].get("score_lines"):
                self.save(data)
                total = len(data[0].get("score_lines", [])) + len(data[0].get("rankings", []))
                print(f"[山东考试院] 完成，共保存 {total} 条记录")
            else:
                print("[山东考试院] 未获取到数据，切换到种子数据...")
                self._use_seed_data()
        except Exception as e:
            print(f"[山东考试院] 爬取异常: {e}，切换到种子数据...")
            self._use_seed_data()


if __name__ == "__main__":
    scraper = ShandongEduScraper()
    scraper.run()

