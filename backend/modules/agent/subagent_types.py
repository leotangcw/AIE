"""Subagent Types - 子代理类型定义"""

from enum import Enum
from typing import Optional


class SubagentType(Enum):
    """子代理类型"""

    GENERAL = "general"     # 通用任务
    EXPLORE = "explore"    # 探索代码库
    RESEARCH = "research"   # 研究/调研
    DEBUG = "debug"         # 调试任务
    REVIEW = "review"       # 代码审查
    BUILD = "build"        # 构建/测试


class SubagentDefaults:
    """子代理默认配置"""

    # 每个类型默认超时时间（秒）
    DEFAULT_TIMEOUTS = {
        SubagentType.EXPLORE: 300,    # 5分钟 - 代码探索需要更多时间
        SubagentType.RESEARCH: 600,   # 10分钟 - 研究调研可能需要更久
        SubagentType.DEBUG: 180,       # 3分钟 - 调试需要快速响应
        SubagentType.REVIEW: 120,      # 2分钟 - 代码审查相对快速
        SubagentType.BUILD: 300,       # 5分钟 - 构建测试可能需要较久
        SubagentType.GENERAL: 180,     # 3分钟 - 默认
    }

    # 每个类型的系统提示
    SYSTEM_PROMPTS = {
        SubagentType.EXPLORE: """你是一个代码库探索专家。
你的任务是深入理解代码库的结构和功能。
- 先了解整体目录结构
- 找到相关的核心文件和模块
- 分析代码逻辑和依赖关系
- 用简洁清晰的方式总结你的发现""",

        SubagentType.RESEARCH: """你是一个研究专家。
你的任务是深入研究给定的主题。
- 收集相关信息和资料
- 分析不同来源的观点
- 提供全面准确的调研报告
- 标注信息来源和可信度""",

        SubagentType.DEBUG: """你是一个调试专家。
你的任务是帮助定位和解决问题。
- 首先理解问题的表现
- 分析错误信息和日志
- 定位可能的根本原因
- 提供具体的修复建议
- 验证修复方案的有效性""",

        SubagentType.REVIEW: """你是一个代码审查专家。
你的任务是审查代码并提供改进建议。
- 检查代码的正确性和完整性
- 识别潜在的安全风险
- 评估代码性能和可维护性
- 提供具体的改进建议
- 按照严重程度分类问题""",

        SubagentType.BUILD: """你是一个构建和测试专家。
你的任务是执行构建和测试任务。
- 按照要求执行构建命令
- 运行相关测试
- 分析构建和测试结果
- 报告成功/失败以及原因
- 提供错误排查建议""",

        SubagentType.GENERAL: """你是一个助手。
你的任务是完成用户指定的任务。
- 理解用户的需求
- 采取适当的行动
- 提供清晰准确的结果
- 如果遇到问题，说明原因""",
    }

    @classmethod
    def get_timeout(cls, subagent_type: SubagentType) -> int:
        """获取类型的默认超时时间"""
        return cls.DEFAULT_TIMEOUTS.get(subagent_type, 180)

    @classmethod
    def get_system_prompt(cls, subagent_type: SubagentType) -> str:
        """获取类型的系统提示"""
        return cls.SYSTEM_PROMPTS.get(subagent_type, cls.SYSTEM_PROMPTS[SubagentType.GENERAL])

    @classmethod
    def from_string(cls, type_str: str) -> SubagentType:
        """从字符串获取类型"""
        type_str = type_str.lower().strip()
        for t in SubagentType:
            if t.value == type_str:
                return t
        return SubagentType.GENERAL
