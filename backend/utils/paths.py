"""统一路径管理 - 跨平台兼容 AIE 版本"""

import os
import sys
from pathlib import Path

# AIE 应用名称
APP_NAME = "AIE"


def get_application_root() -> Path:
    """获取应用程序根目录

    编译版: 使用可执行文件所在目录
    开发版: 使用项目根目录
    """
    if getattr(sys, "frozen", False):
        # 编译版: _internal 目录包含所有资源
        if sys.platform == "darwin":
            # macOS onedir: AIE.app/Contents/MacOS/AIE -> 使用 _internal
            exe_dir = Path(sys.executable).parent
            if (exe_dir / "_internal").exists():
                root = exe_dir / "_internal"
            else:
                # BUNDLE 模式: Contents/MacOS/AIE -> Contents/Resources/
                root = exe_dir.parent / "Resources"
        else:
            # Windows/Linux onedir: AIE.exe 旁边的 _internal
            exe_dir = Path(sys.executable).parent
            root = exe_dir / "_internal" if (exe_dir / "_internal").exists() else exe_dir
    else:
        # 开发版: 项目根目录
        root = Path(__file__).parent.parent.parent

    return root.resolve()


def get_data_dir() -> Path:
    """获取数据目录（数据库、日志）"""
    # 优先使用环境变量
    custom_path = os.getenv("AIE_DATA_DIR")
    if custom_path:
        data_dir = Path(custom_path)
    else:
        data_dir = get_application_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_workspace_dir() -> Path:
    """获取工作区目录"""
    # 优先使用环境变量
    custom_path = os.getenv("AIE_WORKSPACE_DIR")
    if custom_path:
        return Path(custom_path)
    return get_application_root()


def get_config_dir() -> Path:
    """获取配置目录"""
    # 优先使用环境变量
    custom_path = os.getenv("AIE_CONFIG_DIR")
    if custom_path:
        config_dir = Path(custom_path)
    else:
        config_dir = get_application_root() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_memory_dir() -> Path:
    """获取记忆存储目录"""
    custom_path = os.getenv("AIE_MEMORY_DIR")
    if custom_path:
        memory_dir = Path(custom_path)
    else:
        memory_dir = get_application_root() / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def get_skills_dir() -> Path:
    """获取技能目录"""
    custom_path = os.getenv("AIE_SKILLS_DIR")
    if custom_path:
        skills_dir = Path(custom_path)
    else:
        skills_dir = get_application_root() / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


# 导出路径常量
APPLICATION_ROOT = get_application_root()
DATA_DIR = get_data_dir()
WORKSPACE_DIR = get_workspace_dir()
CONFIG_DIR = get_config_dir()
MEMORY_DIR = get_memory_dir()
SKILLS_DIR = get_skills_dir()


if __name__ == "__main__":
    print("=" * 70)
    print("AIE 路径配置")
    print("=" * 70)
    print(f"运行模式: {'编译版' if getattr(sys, 'frozen', False) else '开发版'}")
    print(f"平台: {sys.platform}")
    print(f"\n应用程序根目录: {APPLICATION_ROOT}")
    print(f"数据目录: {DATA_DIR}")
    print(f"工作区目录: {WORKSPACE_DIR}")
    print(f"配置目录: {CONFIG_DIR}")
    print(f"记忆目录: {MEMORY_DIR}")
    print(f"技能目录: {SKILLS_DIR}")
    print("=" * 70)
