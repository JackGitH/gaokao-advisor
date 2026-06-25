# 山东高考志愿填报助手

基于近3年(2023-2025)录取数据的智能志愿填报辅助系统，面向山东省高考考生。

## 功能特性

- **智能匹配**：输入分数或排名，自动推荐"冲一冲/稳一稳/保一保"三档院校
- **数据丰富**：内置131所代表性院校种子数据（985/211/双一流/普通本科/高职专科），可通过爬虫扩展真实数据
- **专业分析**：热门/冷门专业动态标注，基于3年分数线变化趋势自动识别
- **多维排序**：综合匹配度、学校层次、录取概率、稳定性多维度排序
- **数据可视化**：批次线对比、分数趋势折线图、热门专业排行图表
- **自适应页面**：PC/平板/手机全设备适配

## 技术架构

```
数据爬取层 → 数据清洗/存储(SQLite) → 匹配算法引擎 → FastAPI后端 → 自适应前端
```

## 快速启动

```bash
# 安装依赖
pip3 install -r requirements.txt

# 启动服务
python3 main.py

# 访问页面
open http://localhost:8000
```

首次启动自动初始化数据库并加载种子数据（131所学校 × 近3年录取数据）。

## 核心算法

- **排名优先原则**：排名比分数更稳定，以位次为核心匹配依据
- **三档推荐**：冲(位次80%-90%)、稳(±5%)、保(120%-140%)
- **录取概率模型**：基于Sigmoid函数，结合3年数据估算录取概率
- **稳定性评估**：基于变异系数评估院校录取位次波动

## API接口

| 接口 | 说明 |
|------|------|
| GET /api/recommend?score=600 | 按分数推荐 |
| GET /api/recommend?rank=1000 | 按排名推荐 |
| GET /api/school/{id} | 学校详情 |
| GET /api/school/{id}/majors | 学校专业录取详情 |
| GET /api/ranking-table?year=2025 | 一分一段表 |
| GET /api/score-lines | 历年批次线 |
| GET /api/hot-majors | 热门专业排行 |

## 项目结构

```
├── main.py              # FastAPI 入口
├── config.py            # 系统配置
├── database/            # 数据库层
│   ├── schema.py        # 表结构定义
│   └── db.py            # 数据库操作
├── scraper/             # 数据爬取
│   ├── base.py          # 爬虫基类
│   ├── zhangshang.py    # 掌上高考爬虫
│   ├── shandong_edu.py  # 山东教育考试院爬虫
│   ├── seed.py          # 种子数据生成
│   └── utils.py         # 反爬工具
├── algorithm/           # 匹配算法
│   ├── matcher.py       # 核心匹配引擎
│   ├── ranker.py        # 多维度排序
│   └── trend.py         # 趋势分析
├── api/                 # API路由
│   ├── routes.py        # 路由定义
│   └── schemas.py       # 数据模型
└── static/              # 前端页面
    ├── index.html
    ├── css/style.css
    └── js/
```

## 数据来源

- 掌上高考 (gaokao.cn)
- 山东省教育招生考试院 (sdzk.cn)
- 内置种子数据（基于真实数据分布模拟）

## 部署

支持 nginx 反向代理部署，通过 `/gk` 路径前缀区分服务；本地根路径 `/` 也可直接访问。

## 技术栈

- **后端**：Python 3 + FastAPI + SQLite
- **算法**：pandas + numpy + 自研匹配引擎
- **前端**：HTML + CSS + JavaScript + Chart.js
- **爬虫**：requests + BeautifulSoup

## 免责声明

本系统数据仅供参考，实际填报请以各省教育考试院官方发布数据为准。
