"""初始化 Agent Teams 示例数据"""

import asyncio
import uuid

from backend.database import AsyncSessionLocal
from backend.models.agent_team import AgentTeam


async def init_sample_teams():
    """初始化示例 Agent Teams"""

    sample_teams = [
        {
            "name": "代码审查团队",
            "description": "多阶段代码审查工作流 - 先分析代码，再进行审查，最后生成报告",
            "mode": "pipeline",
            "agents": [
                {
                    "id": "analyzer",
                    "role": "Code Analyzer",
                    "task": "Analyze the provided code for structure, complexity, and potential issues. Identify key functions and their purposes.",
                    "depends_on": []
                },
                {
                    "id": "reviewer",
                    "role": "Code Reviewer",
                    "task": "Review the code for bugs, security issues, performance problems, and best practices violations. Provide detailed feedback.",
                    "depends_on": ["analyzer"]
                },
                {
                    "id": "reporter",
                    "role": "Report Generator",
                    "task": "Compile a comprehensive review report based on the analysis and review findings.",
                    "depends_on": ["reviewer"]
                }
            ],
            "is_active": True,
            "cross_review": False,
            "enable_skills": False
        },
        {
            "name": "研究分析团队",
            "description": "依赖图模式 - 并行执行不同角度的研究，最后汇总",
            "mode": "graph",
            "agents": [
                {
                    "id": "market",
                    "role": "Market Analyst",
                    "task": "Research the market aspects of the given topic. Analyze trends, competitors, and opportunities.",
                    "depends_on": []
                },
                {
                    "id": "tech",
                    "role": "Tech Analyst",
                    "task": "Research the technical aspects. Analyze technologies, frameworks, and technical feasibility.",
                    "depends_on": []
                },
                {
                    "id": "risk",
                    "role": "Risk Analyst",
                    "task": "Analyze potential risks and challenges. Consider technical, market, and operational risks.",
                    "depends_on": []
                },
                {
                    "id": "synthesizer",
                    "role": "Synthesizer",
                    "task": "Combine all analysis into a comprehensive research report with actionable recommendations.",
                    "depends_on": ["market", "tech", "risk"]
                }
            ],
            "is_active": True,
            "cross_review": False,
            "enable_skills": False
        },
        {
            "name": "决策咨询委员会",
            "description": "多视角评审模式 - 不同立场的人对问题进行分析和辩论",
            "mode": "council",
            "agents": [
                {
                    "id": "pro",
                    "perspective": "支持方 - 乐观激进",
                    "role": "Progressive Advocate",
                    "task": "Argue for the benefits and opportunities. Take an optimistic, forward-thinking stance.",
                    "depends_on": []
                },
                {
                    "id": "con",
                    "perspective": "反对方 - 保守谨慎",
                    "role": "Conservative Critic",
                    "task": "Argue against the proposal. Identify risks, problems, and valid concerns.",
                    "depends_on": []
                },
                {
                    "id": "neutral",
                    "perspective": "中立分析 - 客观理性",
                    "role": "Neutral Analyst",
                    "task": "Provide balanced, objective analysis. Consider both benefits and risks fairly.",
                    "depends_on": []
                }
            ],
            "is_active": True,
            "cross_review": True,
            "enable_skills": False
        }
    ]

    async with AsyncSessionLocal() as session:
        for team_data in sample_teams:
            team = AgentTeam(
                id=str(uuid.uuid4()),
                **team_data
            )
            session.add(team)

        await session.commit()
        print(f"✓ 已创建 {len(sample_teams)} 个示例 Agent Teams")


async def main():
    print("初始化 Agent Teams 示例数据...")
    await init_sample_teams()
    print("完成!")


if __name__ == "__main__":
    asyncio.run(main())
