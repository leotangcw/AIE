#!/usr/bin/env python3
"""AIE 依赖检查脚本

检查所有必需和可选模块的安装状态。
运行: python check_dependencies.py
"""

import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class Dependency:
    """依赖项定义"""
    name: str
    package: str
    required: bool = True
    description: str = ""
    import_name: Optional[str] = None

    def get_import_name(self) -> str:
        return self.import_name or self.package.replace("-", "_").split("[")[0]


# 所有依赖项定义
DEPENDENCIES = [
    # 核心依赖
    Dependency("FastAPI", "fastapi", True, "Web 框架"),
    Dependency("Uvicorn", "uvicorn", True, "ASGI 服务器"),
    Dependency("SQLAlchemy", "sqlalchemy", True, "ORM"),
    Dependency("Pydantic", "pydantic", True, "数据验证"),
    Dependency("Loguru", "loguru", True, "日志"),
    Dependency("LiteLLM", "litellm", True, "LLM 统一接口"),
    Dependency("Tiktoken", "tiktoken", True, "Tokenizer"),
    Dependency("OpenAI", "openai", True, "OpenAI SDK"),
    Dependency("Tenacity", "tenacity", True, "重试机制"),
    Dependency("Croniter", "croniter", True, "定时任务"),

    # 渠道 SDK
    Dependency("QQ Bot", "qq-botpy", False, "QQ 机器人"),
    Dependency("DingTalk", "dingtalk-stream", False, "钉钉"),
    Dependency("Lark", "lark-oapi", False, "飞书"),
    Dependency("Telegram", "python-telegram-bot", False, "Telegram"),

    # 知识库
    Dependency("Sentence Transformers", "sentence-transformers", False, "向量嵌入"),
    Dependency("NumPy", "numpy", True, "数值计算"),

    # GraphRAG (LightRAG)
    Dependency("LightRAG", "lightrag-hku", False, "知识图谱 RAG", "lightrag"),
    Dependency("NetworkX", "networkx", False, "图计算"),
    Dependency("Nano VectorDB", "nano-vectordb", False, "向量数据库"),
    Dependency("JSON Repair", "json_repair", False, "JSON 修复"),
    Dependency("PyPinyin", "pypinyin", False, "拼音转换"),
    Dependency("Pandas", "pandas", True, "数据处理"),

    # 多模态
    Dependency("PyPDF", "pypdf", False, "PDF 读取"),
    Dependency("Pillow", "Pillow", False, "图像处理"),
    Dependency("OpenCV", "opencv-python-headless", False, "图像处理", "cv2"),
]


def check_dependency(dep: Dependency) -> tuple[bool, str]:
    """检查单个依赖

    Returns:
        (是否安装, 状态消息)
    """
    try:
        module = __import__(dep.get_import_name())
        version = getattr(module, "__version__", "未知版本")
        return True, f"✓ 已安装 ({version})"
    except ImportError:
        if dep.required:
            return False, "✗ 未安装 (必需)"
        return False, "- 未安装 (可选)"


def main():
    print("=" * 60)
    print("AIE 依赖检查")
    print("=" * 60)
    print()

    installed = 0
    missing_required = 0
    missing_optional = 0

    # 按类别分组检查
    categories = {
        "核心依赖": [d for d in DEPENDENCIES if d.required and d.package not in [
            "qq-botpy", "dingtalk-stream", "lark-oapi", "python-telegram-bot",
            "sentence-transformers", "lightrag-hku", "networkx", "nano-vectordb",
            "json_repair", "pypinyin", "pypdf", "Pillow", "opencv-python-headless"
        ]],
        "渠道 SDK": [d for d in DEPENDENCIES if d.package in [
            "qq-botpy", "dingtalk-stream", "lark-oapi", "python-telegram-bot"
        ]],
        "知识库": [d for d in DEPENDENCIES if d.package in [
            "sentence-transformers", "numpy"
        ]],
        "GraphRAG (LightRAG)": [d for d in DEPENDENCIES if d.package in [
            "lightrag-hku", "networkx", "nano-vectordb", "json_repair", "pypinyin"
        ]],
        "多模态": [d for d in DEPENDENCIES if d.package in [
            "pypdf", "Pillow", "opencv-python-headless"
        ]],
    }

    for category, deps in categories.items():
        print(f"【{category}】")
        for dep in deps:
            ok, status = check_dependency(dep)
            print(f"  {dep.name}: {status}")

            if ok:
                installed += 1
            elif dep.required:
                missing_required += 1
            else:
                missing_optional += 1
        print()

    # 总结
    print("=" * 60)
    print("检查结果:")
    print(f"  已安装: {installed}")
    print(f"  缺失必需: {missing_required}")
    print(f"  缺失可选: {missing_optional}")
    print()

    if missing_required > 0:
        print("⚠️  存在缺失的必需依赖，请运行:")
        print("    pip install -r requirements.txt")
        return 1
    else:
        print("✓ 所有必要依赖已安装！")
        if missing_optional > 0:
            print("ℹ️  部分可选功能未安装，如需使用请手动安装对应依赖。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
