#!/usr/bin/env python3
"""AIE 应用启动脚本"""

import os
import sys
import subprocess
import hashlib

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 设置 AIE 环境变量默认值
os.environ.setdefault("AIE_APP_NAME", "AIE")
os.environ.setdefault("AIE_API_PORT", "21000")
os.environ.setdefault("AIE_WS_PORT", "20000")
os.environ.setdefault("AIE_WEB_PORT", "22000")


def get_file_hash(filepath: str) -> str:
    """计算文件内容的 MD5 哈希"""
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def needs_frontend_build() -> bool:
    """检查是否需要构建前端"""
    frontend_dir = os.path.join(project_root, "frontend")
    dist_dir = os.path.join(frontend_dir, "dist")

    # dist 目录不存在，需要构建
    if not os.path.exists(dist_dir):
        return True

    # 检查 src 目录是否有变动（比对比最后修改时间）
    src_dir = os.path.join(frontend_dir, "src")
    if os.path.exists(src_dir):
        # 比较 src 目录和 dist 目录的修改时间
        src_mtime = max(
            os.path.getmtime(os.path.join(root, f))
            for root, _, files in os.walk(src_dir)
            for f in files
        )
        dist_mtime = os.path.getmtime(dist_dir)

        if src_mtime > dist_mtime:
            return True

    return False


def build_frontend():
    """构建前端"""
    frontend_dir = os.path.join(project_root, "frontend")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"

    print(f"\n{'='*60}")
    print("首次运行，正在构建前端...")
    print(f"{'='*60}")

    # 检查 node_modules
    node_modules = os.path.join(frontend_dir, "node_modules")
    if not os.path.exists(node_modules):
        print("安装前端依赖...")
        subprocess.run([npm_cmd, "install"], cwd=frontend_dir, check=True)

    # 构建前端
    print("构建前端...")
    result = subprocess.run(
        [npm_cmd, "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"前端构建失败: {result.stderr}")
        return False

    print("前端构建完成!")
    return True


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    # 加载 .env 文件
    load_dotenv()

    # 从 backend.app 导入 app 实例
    from backend.app import app

    port = int(os.getenv("AIE_API_PORT", "21000"))
    host = os.getenv("AIE_HOST", "0.0.0.0")

    # 检查并构建前端
    if needs_frontend_build():
        if not build_frontend():
            print("警告: 前端构建失败，将尝试启动后端...")

    print(f"\n{'='*60}")
    print(f"AIE 启动中...")
    print(f"访问地址: http://localhost:{port}")
    print(f"{'='*60}\n")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )
