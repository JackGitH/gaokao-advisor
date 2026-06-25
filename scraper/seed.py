"""
高考志愿推荐系统 - 种子数据生成模块
在爬虫无法获取真实数据时，生成合理的模拟数据作为fallback
数据基于真实数据分布，覆盖约100所代表性学校
"""
import random
import json
import os
import math
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_DIR, DATABASE_PATH
from database.db import (
    get_connection, init_db,
    insert_school, insert_major, insert_admission_record,
    insert_score_line, insert_ranking, bulk_insert_rankings
)

# ==================== 学校数据定义 ====================
# 格式: (学校名, 省份, 城市, 类型, 等级, 特色, 位次范围(min, max))
SCHOOLS_DATA = [
    # 顶尖985
    ("清华大学", "北京", "北京", "985", "本科一批", "C9联盟,双一流A类", 50, 150),
    ("北京大学", "北京", "北京", "985", "本科一批", "C9联盟,双一流A类", 50, 180),
    ("复旦大学", "上海", "上海", "985", "本科一批", "C9联盟,双一流A类", 200, 500),
    ("上海交通大学", "上海", "上海", "985", "本科一批", "C9联盟,双一流A类", 200, 550),
    ("浙江大学", "浙江", "杭州", "985", "本科一批", "C9联盟,双一流A类", 300, 700),
    ("中国科学技术大学", "安徽", "合肥", "985", "本科一批", "C9联盟,双一流A类", 400, 800),
    ("南京大学", "江苏", "南京", "985", "本科一批", "C9联盟,双一流A类", 500, 1000),
    ("中国人民大学", "北京", "北京", "985", "本科一批", "双一流A类", 400, 900),
    # 中上985
    ("北京航空航天大学", "北京", "北京", "985", "本科一批", "双一流A类", 1000, 2500),
    ("同济大学", "上海", "上海", "985", "本科一批", "双一流A类", 1200, 3000),
    ("武汉大学", "湖北", "武汉", "985", "本科一批", "双一流A类", 1500, 3500),
    ("华中科技大学", "湖北", "武汉", "985", "本科一批", "双一流A类", 2000, 4000),
    ("西安交通大学", "陕西", "西安", "985", "本科一批", "C9联盟,双一流A类", 2000, 4500),
    ("哈尔滨工业大学", "黑龙江", "哈尔滨", "985", "本科一批", "C9联盟,双一流A类", 2000, 5000),
    ("中山大学", "广东", "广州", "985", "本科一批", "双一流A类", 2500, 5500),
    ("东南大学", "江苏", "南京", "985", "本科一批", "双一流A类", 3000, 6000),
    ("天津大学", "天津", "天津", "985", "本科一批", "双一流A类", 3500, 7000),
    ("北京理工大学", "北京", "北京", "985", "本科一批", "双一流A类", 3000, 6500),
    ("厦门大学", "福建", "厦门", "985", "本科一批", "双一流A类", 3000, 6000),
    ("四川大学", "四川", "成都", "985", "本科一批", "双一流A类", 4000, 9000),
    # 中985
    ("南开大学", "天津", "天津", "985", "本科一批", "双一流A类", 3500, 7500),
    ("电子科技大学", "四川", "成都", "985", "本科一批", "双一流A类", 3000, 7000),
    ("北京师范大学", "北京", "北京", "985", "本科一批", "双一流A类", 2500, 5000),
    ("华南理工大学", "广东", "广州", "985", "本科一批", "双一流A类", 5000, 10000),
    ("大连理工大学", "辽宁", "大连", "985", "本科一批", "双一流A类", 6000, 12000),
    ("吉林大学", "吉林", "长春", "985", "本科一批", "双一流A类", 7000, 14000),
    ("湖南大学", "湖南", "长沙", "985", "本科一批", "双一流A类", 7000, 13000),
    ("重庆大学", "重庆", "重庆", "985", "本科一批", "双一流A类", 8000, 15000),
    # 山东省内重点（985/211）
    ("山东大学", "山东", "济南", "985", "本科一批", "双一流A类", 5000, 15000),
    ("中国海洋大学", "山东", "青岛", "985", "本科一批", "双一流A类", 10000, 25000),
    ("中国石油大学(华东)", "山东", "青岛", "211", "本科一批", "双一流", 18000, 40000),
    ("山东大学威海分校", "山东", "威海", "985", "本科一批", "双一流A类", 12000, 28000),
    # 顶尖211
    ("北京邮电大学", "北京", "北京", "211", "本科一批", "双一流", 4000, 8000),
    ("上海财经大学", "上海", "上海", "211", "本科一批", "双一流", 3000, 6000),
    ("中央财经大学", "北京", "北京", "211", "本科一批", "双一流", 4000, 8000),
    ("对外经济贸易大学", "北京", "北京", "211", "本科一批", "双一流", 4500, 9000),
    ("西安电子科技大学", "陕西", "西安", "211", "本科一批", "双一流", 8000, 16000),
    ("南京航空航天大学", "江苏", "南京", "211", "本科一批", "双一流", 10000, 20000),
    ("南京理工大学", "江苏", "南京", "211", "本科一批", "双一流", 10000, 22000),
    ("北京交通大学", "北京", "北京", "211", "本科一批", "双一流", 8000, 17000),
    ("华东理工大学", "上海", "上海", "211", "本科一批", "双一流", 12000, 24000),
    ("河海大学", "江苏", "南京", "211", "本科一批", "双一流", 15000, 30000),
    ("苏州大学", "江苏", "苏州", "211", "本科一批", "双一流", 12000, 25000),
    ("中南财经政法大学", "湖北", "武汉", "211", "本科一批", "双一流", 12000, 25000),
    ("武汉理工大学", "湖北", "武汉", "211", "本科一批", "双一流", 14000, 28000),
    ("西南财经大学", "四川", "成都", "211", "本科一批", "双一流", 13000, 26000),
    ("华北电力大学", "北京", "北京", "211", "本科一批", "双一流", 12000, 24000),
    ("中国政法大学", "北京", "北京", "211", "本科一批", "双一流", 5000, 11000),
    ("北京科技大学", "北京", "北京", "211", "本科一批", "双一流", 10000, 20000),
    ("北京外国语大学", "北京", "北京", "211", "本科一批", "双一流", 5000, 12000),
    ("上海外国语大学", "上海", "上海", "211", "本科一批", "双一流", 6000, 14000),
    ("暨南大学", "广东", "广州", "211", "本科一批", "双一流", 13000, 27000),
    ("兰州大学", "甘肃", "兰州", "985", "本科一批", "双一流A类", 10000, 22000),
    ("东北大学", "辽宁", "沈阳", "985", "本科一批", "双一流A类", 10000, 20000),
    # 普通211/双一流
    ("中国地质大学(武汉)", "湖北", "武汉", "211", "本科一批", "双一流", 20000, 40000),
    ("中国矿业大学", "江苏", "徐州", "211", "本科一批", "双一流", 22000, 42000),
    ("长安大学", "陕西", "西安", "211", "本科一批", "双一流", 22000, 45000),
    ("合肥工业大学", "安徽", "合肥", "211", "本科一批", "双一流", 18000, 35000),
    ("福州大学", "福建", "福州", "211", "本科一批", "双一流", 18000, 36000),
    ("南昌大学", "江西", "南昌", "211", "本科一批", "双一流", 20000, 42000),
    ("郑州大学", "河南", "郑州", "211", "本科一批", "双一流", 20000, 43000),
    ("哈尔滨工程大学", "黑龙江", "哈尔滨", "211", "本科一批", "双一流", 16000, 32000),
    ("太原理工大学", "山西", "太原", "211", "本科一批", "双一流", 30000, 55000),
    ("海南大学", "海南", "海口", "211", "本科一批", "双一流", 30000, 60000),
    # 山东省内重点本科
    ("山东师范大学", "山东", "济南", "普通本科", "本科一批", "省属重点", 30000, 65000),
    ("青岛大学", "山东", "青岛", "普通本科", "本科一批", "省属重点", 35000, 70000),
    ("山东科技大学", "山东", "青岛", "普通本科", "本科一批", "省属重点", 50000, 100000),
    ("济南大学", "山东", "济南", "普通本科", "本科一批", "省属重点", 55000, 110000),
    ("山东财经大学", "山东", "济南", "普通本科", "本科一批", "省属重点", 45000, 90000),
    ("青岛科技大学", "山东", "青岛", "普通本科", "本科一批", "省属重点", 55000, 105000),
    ("山东理工大学", "山东", "淄博", "普通本科", "本科一批", "省属", 70000, 130000),
    ("曲阜师范大学", "山东", "曲阜", "普通本科", "本科一批", "省属", 60000, 120000),
    ("烟台大学", "山东", "烟台", "普通本科", "本科一批", "省属", 65000, 125000),
    ("鲁东大学", "山东", "烟台", "普通本科", "本科一批", "省属", 80000, 145000),
    # 省外普通本科/双一流
    ("南京信息工程大学", "江苏", "南京", "双一流", "本科一批", "双一流", 25000, 50000),
    ("上海大学", "上海", "上海", "211", "本科一批", "双一流", 12000, 25000),
    ("深圳大学", "广东", "深圳", "普通本科", "本科一批", "高水平大学", 20000, 42000),
    ("杭州电子科技大学", "浙江", "杭州", "普通本科", "本科一批", "省属重点", 30000, 55000),
    ("南京邮电大学", "江苏", "南京", "双一流", "本科一批", "双一流", 25000, 48000),
    ("成都理工大学", "四川", "成都", "双一流", "本科一批", "双一流", 35000, 65000),
    ("浙江工业大学", "浙江", "杭州", "普通本科", "本科一批", "省属重点", 32000, 60000),
    ("广东工业大学", "广东", "广州", "普通本科", "本科一批", "省属重点", 40000, 80000),
    ("重庆邮电大学", "重庆", "重庆", "普通本科", "本科一批", "省属重点", 35000, 70000),
    ("西安邮电大学", "陕西", "西安", "普通本科", "本科一批", "省属", 45000, 85000),
    # 更多普通本科
    ("天津工业大学", "天津", "天津", "双一流", "本科一批", "双一流", 35000, 68000),
    ("湖南师范大学", "湖南", "长沙", "211", "本科一批", "双一流", 15000, 30000),
    ("华南师范大学", "广东", "广州", "211", "本科一批", "双一流", 15000, 32000),
    ("陕西师范大学", "陕西", "西安", "211", "本科一批", "双一流", 14000, 28000),
    ("东北师范大学", "吉林", "长春", "211", "本科一批", "双一流", 15000, 30000),
    ("西北大学", "陕西", "西安", "211", "本科一批", "双一流", 15000, 32000),
    ("北京化工大学", "北京", "北京", "211", "本科一批", "双一流", 16000, 33000),
    ("中国农业大学", "北京", "北京", "985", "本科一批", "双一流A类", 8000, 16000),
    ("西北农林科技大学", "陕西", "杨凌", "985", "本科一批", "双一流A类", 15000, 35000),
    ("中国传媒大学", "北京", "北京", "211", "本科一批", "双一流", 8000, 18000),
    ("北京中医药大学", "北京", "北京", "211", "本科一批", "双一流", 18000, 38000),
    ("南京师范大学", "江苏", "南京", "211", "本科一批", "双一流", 14000, 28000),
    ("江南大学", "江苏", "无锡", "211", "本科一批", "双一流", 18000, 36000),
    ("西南大学", "重庆", "重庆", "211", "本科一批", "双一流", 14000, 28000),
    ("安徽大学", "安徽", "合肥", "211", "本科一批", "双一流", 22000, 44000),
    ("辽宁大学", "辽宁", "沈阳", "211", "本科一批", "双一流", 22000, 45000),
    # 普通本科补充
    ("山东建筑大学", "山东", "济南", "普通本科", "本科一批", "省属", 80000, 140000),
    ("齐鲁工业大学", "山东", "济南", "普通本科", "本科一批", "省属", 75000, 135000),
    ("山东农业大学", "山东", "泰安", "普通本科", "本科一批", "省属", 85000, 150000),
    ("临沂大学", "山东", "临沂", "普通本科", "本科二批", "省属", 120000, 180000),
    ("潍坊学院", "山东", "潍坊", "普通本科", "本科二批", "省属", 140000, 200000),
    # 低分段普通本科/民办本科，补齐一段线附近到二段线上部推荐
    ("山东女子学院", "山东", "济南", "普通本科", "本科二批", "省属", 160000, 240000),
    ("山东青年政治学院", "山东", "济南", "普通本科", "本科二批", "省属", 170000, 250000),
    ("山东管理学院", "山东", "济南", "普通本科", "本科二批", "省属", 170000, 260000),
    ("山东协和学院", "山东", "济南", "普通本科", "本科二批", "民办", 190000, 300000),
    ("烟台南山学院", "山东", "烟台", "普通本科", "本科二批", "民办", 210000, 320000),
    ("青岛滨海学院", "山东", "青岛", "普通本科", "本科二批", "民办", 230000, 350000),
    ("潍坊科技学院", "山东", "潍坊", "普通本科", "本科二批", "民办", 230000, 360000),
    ("齐鲁医药学院", "山东", "淄博", "普通本科", "本科二批", "民办", 180000, 300000),
    ("青岛黄海学院", "山东", "青岛", "普通本科", "本科二批", "民办", 260000, 390000),
    ("山东英才学院", "山东", "济南", "普通本科", "本科二批", "民办", 270000, 410000),
    ("青岛工学院", "山东", "青岛", "普通本科", "本科二批", "民办", 280000, 430000),
    ("泰山科技学院", "山东", "泰安", "普通本科", "本科二批", "民办", 300000, 450000),
    ("齐鲁理工学院", "山东", "济南", "普通本科", "本科二批", "民办", 290000, 440000),
    ("山东华宇工学院", "山东", "德州", "普通本科", "本科二批", "民办", 320000, 470000),
    # 山东高职专科，补齐普通类二段线附近推荐
    ("山东商业职业技术学院", "山东", "济南", "高职专科", "专科批", "双高计划", 300000, 500000),
    ("淄博职业学院", "山东", "淄博", "高职专科", "专科批", "双高计划", 320000, 520000),
    ("日照职业技术学院", "山东", "日照", "高职专科", "专科批", "双高计划", 350000, 560000),
    ("山东职业学院", "山东", "济南", "高职专科", "专科批", "省属高职", 340000, 540000),
    ("青岛职业技术学院", "山东", "青岛", "高职专科", "专科批", "省属高职", 330000, 530000),
    ("威海职业学院", "山东", "威海", "高职专科", "专科批", "省属高职", 380000, 580000),
    ("烟台职业学院", "山东", "烟台", "高职专科", "专科批", "省属高职", 390000, 600000),
    ("潍坊职业学院", "山东", "潍坊", "高职专科", "专科批", "省属高职", 420000, 630000),
    ("济南职业学院", "山东", "济南", "高职专科", "专科批", "省属高职", 410000, 620000),
    ("山东科技职业学院", "山东", "潍坊", "高职专科", "专科批", "省属高职", 430000, 650000),
    ("山东畜牧兽医职业学院", "山东", "潍坊", "高职专科", "专科批", "省属高职", 450000, 660000),
    ("山东交通职业学院", "山东", "潍坊", "高职专科", "专科批", "省属高职", 460000, 665000),
]

# ==================== 专业数据定义 ====================
MAJORS_DATA = [
    # (专业名, 学科门类, 热门趋势)
    ("计算机科学与技术", "工学", "热门"),
    ("软件工程", "工学", "热门"),
    ("人工智能", "工学", "热门"),
    ("数据科学与大数据技术", "工学", "热门"),
    ("电子信息工程", "工学", "热门"),
    ("通信工程", "工学", "热门"),
    ("自动化", "工学", "热门"),
    ("电气工程及其自动化", "工学", "热门"),
    ("机械工程", "工学", "平稳"),
    ("土木工程", "工学", "冷门"),
    ("建筑学", "工学", "平稳"),
    ("临床医学", "医学", "热门"),
    ("口腔医学", "医学", "热门"),
    ("金融学", "经济学", "热门"),
    ("会计学", "管理学", "平稳"),
    ("法学", "法学", "热门"),
    ("英语", "文学", "平稳"),
    ("汉语言文学", "文学", "平稳"),
    ("数学与应用数学", "理学", "平稳"),
    ("物理学", "理学", "平稳"),
    ("化学", "理学", "平稳"),
    ("生物科学", "理学", "冷门"),
    ("经济学", "经济学", "热门"),
    ("工商管理", "管理学", "平稳"),
    ("材料科学与工程", "工学", "平稳"),
    ("环境工程", "工学", "冷门"),
    ("食品科学与工程", "工学", "平稳"),
    ("车辆工程", "工学", "平稳"),
    ("网络空间安全", "工学", "热门"),
    ("信息安全", "工学", "热门"),
    ("统计学", "理学", "热门"),
    ("国际经济与贸易", "经济学", "平稳"),
    ("新闻学", "文学", "平稳"),
    ("心理学", "教育学", "平稳"),
    ("药学", "医学", "平稳"),
]

# ==================== 批次线数据 ====================
SCORE_LINES_DATA = {
    2023: [
        ("普通类一段", 443, 308701),
        ("普通类二段", 150, 662199),
        ("特殊类型招生控制线", 520, 98957),
    ],
    2024: [
        ("普通类一段", 444, 307432),
        ("普通类二段", 150, 659800),
        ("特殊类型招生控制线", 520, 99051),
    ],
    2025: [
        ("普通类一段", 443, 310256),
        ("普通类二段", 150, 665321),
        ("特殊类型招生控制线", 521, 97823),
    ],
}


def _generate_ranking_table(year: int) -> list:
    """
    生成一分一段表（基于正态分布）
    
    山东高考总分750，考生约60-70万
    分数分布近似正态：均值约450，标准差约90
    """
    rankings = []
    
    # 参数微调每年略有不同
    year_offset = {2023: 0, 2024: 1, 2025: -0.5}
    mean = 450 + year_offset.get(year, 0)
    std = 88
    total_students = {2023: 662199, 2024: 659800, 2025: 665321}[year]
    
    cumulative = 0
    for score in range(750, 149, -1):
        # 使用正态分布PDF估算每分人数
        z = (score - mean) / std
        pdf = math.exp(-0.5 * z * z) / (std * math.sqrt(2 * math.pi))
        same_count = max(1, int(pdf * total_students))
        
        # 高分段和低分段微调
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


def _get_majors_for_school(school_type: str) -> list:
    """根据学校类型选择适当的专业列表"""
    all_majors = list(range(len(MAJORS_DATA)))
    
    if school_type == "985":
        count = random.randint(10, 15)
    elif school_type == "211":
        count = random.randint(8, 12)
    elif school_type == "双一流":
        count = random.randint(6, 10)
    elif school_type == "高职专科":
        count = random.randint(4, 7)
    else:
        count = random.randint(5, 8)
    
    return random.sample(all_majors, min(count, len(all_majors)))


def _generate_admission_score(base_rank: int, year: int, major_trend: str) -> tuple:
    """
    根据学校基础位次和专业热门程度生成录取分/位次
    
    Returns:
        (min_score, min_rank, avg_score)
    """
    # 热门专业位次更靠前
    trend_offset = {"热门": -0.15, "平稳": 0, "冷门": 0.2}
    offset = trend_offset.get(major_trend, 0)
    
    # 年份波动
    year_jitter = random.uniform(-0.05, 0.05)
    
    rank = int(base_rank * (1 + offset + year_jitter))
    rank = max(1, rank + random.randint(-int(base_rank * 0.1), int(base_rank * 0.1)))
    
    # 位次转分数（近似映射）
    if rank <= 100:
        score = random.randint(685, 700)
    elif rank <= 500:
        score = random.randint(665, 685)
    elif rank <= 1000:
        score = random.randint(655, 668)
    elif rank <= 2000:
        score = random.randint(643, 658)
    elif rank <= 5000:
        score = random.randint(625, 645)
    elif rank <= 10000:
        score = random.randint(605, 628)
    elif rank <= 20000:
        score = random.randint(585, 608)
    elif rank <= 30000:
        score = random.randint(570, 588)
    elif rank <= 50000:
        score = random.randint(550, 572)
    elif rank <= 80000:
        score = random.randint(525, 553)
    elif rank <= 120000:
        score = random.randint(490, 528)
    elif rank <= 160000:
        score = random.randint(460, 493)
    elif rank <= 220000:
        score = random.randint(430, 465)
    elif rank <= 300000:
        score = random.randint(400, 445)
    elif rank <= 400000:
        score = random.randint(350, 420)
    elif rank <= 520000:
        score = random.randint(270, 380)
    else:
        score = random.randint(150, 320)
    
    avg_score = score + random.randint(2, 8)
    
    return score, rank, avg_score


def generate_seed_data(save_to_db: bool = True, save_json: bool = True, force: bool = False):
    """
    生成种子数据并存入数据库和JSON文件
    
    Args:
        save_to_db: 是否写入数据库
        save_json: 是否保存为JSON文件
        force: 是否强制重新生成（即使数据已存在）
    """
    print("[种子数据] 开始生成模拟数据...")
    
    # 初始化数据库
    if save_to_db:
        init_db()
        
        # 检查是否已有数据
        if force:
            conn = get_connection()
            try:
                for table in [
                    "admission_records",
                    "score_lines",
                    "ranking_table",
                    "schools",
                    "majors",
                ]:
                    conn.execute(f"DELETE FROM {table}")
                conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('admission_records', 'score_lines', 'ranking_table', 'schools', 'majors')")
                conn.commit()
            finally:
                conn.close()

        if not force:
            conn = get_connection()
            count = conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
            conn.close()
            if count >= len(SCHOOLS_DATA):
                print(f"[种子数据] 数据库已有 {count} 所学校，跳过生成（使用 force=True 强制重新生成）")
                return {"schools": count, "skipped": True}
            if count > 0:
                print(f"[种子数据] 数据库已有 {count} 所学校，将增量补齐至 {len(SCHOOLS_DATA)} 所")
    
    # 存储生成的数据
    all_schools = []
    all_majors = []
    all_admission_records = []
    all_score_lines = []
    all_rankings = []
    
    # ===== 1. 生成学校数据 =====
    school_ids = {}  # name -> db_id
    for idx, school_info in enumerate(SCHOOLS_DATA):
        name, province, city, type_, level, features, rank_min, rank_max = school_info
        school_dict = {
            "name": name,
            "province": province,
            "city": city,
            "type": type_,
            "level": level,
            "features": features,
        }
        all_schools.append(school_dict)
        
        if save_to_db:
            try:
                sid = insert_school(name, province, city, type_, level, features)
                school_ids[name] = sid
            except Exception:
                # 可能已存在
                conn = get_connection()
                row = conn.execute("SELECT id FROM schools WHERE name = ?", (name,)).fetchone()
                if row:
                    school_ids[name] = row["id"]
                conn.close()
    
    print(f"[种子数据] 已生成 {len(all_schools)} 所学校")
    
    # ===== 2. 生成专业数据 =====
    major_ids = {}  # name -> db_id
    for idx, major_info in enumerate(MAJORS_DATA):
        name, category, hot_trend = major_info
        major_dict = {
            "name": name,
            "category": category,
            "hot_trend": hot_trend,
        }
        all_majors.append(major_dict)
        
        if save_to_db:
            try:
                mid = insert_major(name, category, hot_trend)
                major_ids[name] = mid
            except Exception:
                conn = get_connection()
                row = conn.execute("SELECT id FROM majors WHERE name = ?", (name,)).fetchone()
                if row:
                    major_ids[name] = row["id"]
                conn.close()
    
    print(f"[种子数据] 已生成 {len(all_majors)} 个专业")
    
    # ===== 3. 生成录取记录 =====
    years = [2023, 2024, 2025]
    existing_admission_keys = set()
    if save_to_db:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT year, school_id, major_id, IFNULL(batch, '') as batch FROM admission_records"
            ).fetchall()
            existing_admission_keys = {
                (row["year"], row["school_id"], row["major_id"], row["batch"])
                for row in rows
            }
        finally:
            conn.close()

    for school_info in SCHOOLS_DATA:
        name, province, city, type_, level, features, rank_min, rank_max = school_info
        school_id = school_ids.get(name)
        if not school_id:
            continue
        
        # 为该校选择专业
        major_indices = _get_majors_for_school(type_)
        base_rank = (rank_min + rank_max) // 2
        
        for year in years:
            for mi in major_indices:
                major_name = MAJORS_DATA[mi][0]
                major_trend = MAJORS_DATA[mi][2]
                major_id = major_ids.get(major_name)
                if not major_id:
                    continue
                
                min_score, min_rank, avg_score = _generate_admission_score(
                    base_rank, year, major_trend
                )
                
                plan_count = random.randint(2, 15)
                actual_count = plan_count + random.randint(-1, 2)
                actual_count = max(1, actual_count)
                
                batch = "普通类二段" if type_ == "高职专科" else "普通类一段"
                admission_key = (year, school_id, major_id, batch)
                if admission_key in existing_admission_keys:
                    continue

                record = {
                    "year": year,
                    "school_id": school_id,
                    "school_name": name,
                    "major_id": major_id,
                    "major_name": major_name,
                    "batch": batch,
                    "min_score": min_score,
                    "min_rank": min_rank,
                    "avg_score": avg_score,
                    "plan_count": plan_count,
                    "actual_count": actual_count,
                }
                all_admission_records.append(record)
                
                if save_to_db:
                    try:
                        insert_admission_record(
                            year, school_id, major_id,
                            batch, min_score, min_rank,
                            avg_score, plan_count, actual_count
                        )
                        existing_admission_keys.add(admission_key)
                    except Exception:
                        pass
    
    print(f"[种子数据] 已生成 {len(all_admission_records)} 条录取记录")
    
    # ===== 4. 生成批次线 =====
    for year, lines in SCORE_LINES_DATA.items():
        for batch, score, rank in lines:
            line_dict = {
                "year": year,
                "batch": batch,
                "score": score,
                "rank": rank,
            }
            all_score_lines.append(line_dict)
            
            if save_to_db:
                try:
                    insert_score_line(year, batch, score, rank)
                except Exception:
                    pass
    
    print(f"[种子数据] 已生成 {len(all_score_lines)} 条批次线")
    
    # ===== 5. 生成一分一段表 =====
    for year in years:
        rankings = _generate_ranking_table(year)
        all_rankings.extend(rankings)
        
        if save_to_db:
            try:
                bulk_insert_rankings(rankings)
            except Exception:
                # 逐条插入
                for r in rankings:
                    try:
                        insert_ranking(r["year"], r["score"],
                                      r["same_score_count"], r["cumulative_count"])
                    except Exception:
                        pass
    
    print(f"[种子数据] 已生成 {len(all_rankings)} 条一分一段记录")
    
    # ===== 6. 保存为JSON =====
    if save_json:
        json_data = {
            "description": "高考志愿推荐系统种子数据（模拟）",
            "generated_by": "scraper.seed.generate_seed_data",
            "schools": all_schools,
            "majors": all_majors,
            "score_lines": all_score_lines,
            "admission_records_count": len(all_admission_records),
            "ranking_table_count": len(all_rankings),
        }
        
        json_path = os.path.join(BASE_DIR, "data", "seed_data.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"[种子数据] JSON文件已保存至 {json_path}")
    
    print("[种子数据] 生成完毕！")
    return {
        "schools": len(all_schools),
        "majors": len(all_majors),
        "admission_records": len(all_admission_records),
        "score_lines": len(all_score_lines),
        "rankings": len(all_rankings),
    }


if __name__ == "__main__":
    result = generate_seed_data()
    print(f"\n生成统计: {result}")
