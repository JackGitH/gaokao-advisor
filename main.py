"""
高考志愿推荐系统 - FastAPI 应用入口
"""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from config import API_CONFIG, BASE_DIR
from database.db import init_db, get_connection
from api.routes import router

app = FastAPI(
    title=API_CONFIG["title"],
    description=API_CONFIG["description"],
    version=API_CONFIG["version"],
)

# 注册API路由
app.include_router(router)

# 挂载静态文件
static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """返回前端首页"""
    index_path = os.path.join(BASE_DIR, "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "高考志愿填报助手 API 已启动，请访问 /docs 查看接口文档"}


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库，检查是否需要加载种子数据"""
    # 初始化数据库表结构
    init_db()

    # 检查数据库是否为空，为空则加载种子数据
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM schools").fetchone()
        school_count = row["cnt"] if row else 0
    finally:
        conn.close()

    if school_count == 0:
        print("数据库为空，正在加载种子数据...")
        try:
            from scraper.seed import generate_seed_data
            generate_seed_data(save_to_db=True, save_json=False)
            print("种子数据加载完成")
        except Exception as e:
            print(f"种子数据加载失败: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG["debug"],
    )
