#!/usr/bin/env python3
"""AIE 应用启动脚本"""

import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 设置 AIE 环境变量默认值
os.environ.setdefault("AIE_APP_NAME", "AIE")
os.environ.setdefault("AIE_API_PORT", "21000")
os.environ.setdefault("AIE_WS_PORT", "20000")
os.environ.setdefault("AIE_WEB_PORT", "22000")

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    # 加载 .env 文件
    load_dotenv()

    # 从 backend.app 导入 app 实例
    from backend.app import app

    port = int(os.getenv("AIE_API_PORT", "21000"))
    host = os.getenv("AIE_HOST", "0.0.0.0")

    print(f"Starting AIE on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )
