#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发送今日 AI 论文速递邮件
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import ssl

# 配置信息
SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465
SENDER_EMAIL = "leotangbot@163.com"
SENDER_PASSWORD = "SWdqGSFtw34fRnie"
RECEIVER_EMAIL = "tangchengwen@163.com"

# 今日日期
TODAY = datetime.now().strftime("%Y-%m-%d")

# 论文数据
papers = [
    {
        "title": "PhysMoDPO: Physically-Plausible Humanoid Motion with Preference Optimization",
        "summary": "提出 PhysMoDPO，一种直接偏好优化框架，用于生成符合物理规律的人形机器人运动。通过将全身控制器（WBC）集成到训练流程中，优化扩散模型使输出既符合物理规律又符合文本指令。在仿真机器人和真实 G1 人形机器人上展示了显著改进。",
        "category": "机器人学习/运动控制",
        "link": "https://arxiv.org/abs/2603.13228"
    },
    {
        "title": "Representation Learning for Spatiotemporal Physical Systems",
        "summary": "研究时空物理系统的表示学习，发现潜在空间学习方法（如 JEPA）在下游科学任务上优于像素级预测方法。由 Yann LeCun 等作者完成，发表于 ICLR 2026 Workshop。",
        "category": "表示学习/科学 AI",
        "link": "https://arxiv.org/abs/2603.13227"
    },
    {
        "title": "Visual-ERM: Reward Modeling for Visual Equivalence",
        "summary": "提出视觉等价奖励模型（Visual-ERM），为视觉到代码任务提供细粒度、可解释的反馈。在图表转代码任务上提升 Qwen3-VL-8B-Instruct 达 +8.4 分，并引入 VC-RewardBench 基准测试。",
        "category": "视觉语言模型/强化学习",
        "link": "https://arxiv.org/abs/2603.13224"
    },
    {
        "title": "Out of Sight, Out of Mind? Evaluating State Evolution in Video World Models",
        "summary": "提出 STEVO-Bench 基准，评估视频世界模型能否在不可见情况下正确模拟状态演化（如水倾倒、冰融化）。揭示了当前视频世界模型在解耦状态演化与观测方面的局限性。",
        "category": "视频理解/世界模型",
        "link": "https://arxiv.org/abs/2603.13215"
    },
    {
        "title": "Neuron-Aware Data Selection In Instruction Tuning For Large Language Models",
        "summary": "提出 NAIT 框架，通过分析神经元激活模式相似性来选择指令微调数据。实验表明，使用 NAIT 选择的 10% Alpaca-GPT4 数据子集训练，效果优于使用外部高级模型或不确定性特征的方法。",
        "category": "大语言模型/指令微调",
        "link": "https://arxiv.org/abs/2603.13201"
    },
    {
        "title": "From Experiments to Expertise: Scientific Knowledge Consolidation for AI-Driven Computational Research",
        "summary": "提出 QMatSuite 平台，使 AI 代理能够记录发现、检索知识并在反思会话中纠正错误。在量子力学模拟工作流中，累积知识将推理开销降低 67%，准确率从 47% 偏差提升至 3%。",
        "category": "AI for Science/智能代理",
        "link": "https://arxiv.org/abs/2603.13191"
    },
    {
        "title": "LLM Constitutional Multi-Agent Governance",
        "summary": "提出宪制多智能体治理（CMAG）框架，结合硬约束过滤和软惩罚效用优化，平衡合作潜力与操纵风险。实验表明 CMAG 在保持自主性（0.985）和完整性（0.995）的同时，实现伦理合作分数 0.741。",
        "category": "多智能体系统/AI 治理",
        "link": "https://arxiv.org/abs/2603.13189"
    },
    {
        "title": "Learnability and Privacy Vulnerability are Entangled in a Few Critical Weights",
        "summary": "发现隐私漏洞仅存在于极小部分权重中，但这些权重也关键影响效用性能。提出仅重绕关键权重的方法，在保持效用的同时有效抵抗成员推断攻击。发表于 ICLR 2026。",
        "category": "机器学习隐私/安全",
        "link": "https://arxiv.org/abs/2603.13186"
    },
    {
        "title": "DiT-IC: Aligned Diffusion Transformer for Efficient Image Compression",
        "summary": "提出 DiT-IC，一种对齐扩散 Transformer 用于图像压缩。通过三步对齐机制实现单步扩散，解码速度提升 30 倍，可在 16GB 笔记本 GPU 上重建 2048x2048 图像。",
        "category": "图像压缩/扩散模型",
        "link": "https://arxiv.org/abs/2603.13162"
    },
    {
        "title": "ESG-Bench: Benchmarking Long-Context ESG Reports for Hallucination Mitigation",
        "summary": "推出 ESG-Bench 基准数据集，用于评估大语言模型在 ESG 报告理解中的幻觉问题。提出任务特定的思维链（CoT）提示策略，显著减少幻觉，并可将改进迁移到其他 QA 基准。",
        "category": "长上下文/幻觉缓解",
        "link": "https://arxiv.org/abs/2603.13154"
    }
]

# 研究方向总结
research_directions = """
<h3>🔬 研究方向分布</h3>
<table style="width:100%; border-collapse: collapse; margin: 20px 0;">
    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
        <th style="padding: 12px; text-align: left; color: white;">研究方向</th>
        <th style="padding: 12px; text-align: center; color: white;">论文数量</th>
        <th style="padding: 12px; text-align: left; color: white;">占比</th>
    </tr>
    <tr style="background: #f8f9fa;">
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">🤖 机器人与具身智能</td>
        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #dee2e6;">2</td>
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">20%</td>
    </tr>
    <tr>
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">👁️ 视觉与多模态</td>
        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #dee2e6;">3</td>
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">30%</td>
    </tr>
    <tr style="background: #f8f9fa;">
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">🧠 大语言模型</td>
        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #dee2e6;">3</td>
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">30%</td>
    </tr>
    <tr>
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">🔒 隐私与安全</td>
        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #dee2e6;">1</td>
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">10%</td>
    </tr>
    <tr style="background: #f8f9fa;">
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">🔬 AI for Science</td>
        <td style="padding: 10px; text-align: center; border-bottom: 1px solid #dee2e6;">1</td>
        <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">10%</td>
    </tr>
</table>
"""

# 核心趋势
core_trends = """
<h3>📈 核心趋势洞察</h3>
<div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 20px; border-radius: 10px; margin: 20px 0;">
    <div style="margin-bottom: 15px;">
        <strong style="color: #667eea;">1️⃣ 具身智能爆发</strong>
        <p style="margin: 8px 0 0 0; color: #555;">人形机器人运动控制、世界模型、开放世界具身代理成为热点，AI 正从纯软件走向物理世界交互。</p>
    </div>
    <div style="margin-bottom: 15px;">
        <strong style="color: #667eea;">2️⃣ 视觉 - 语言深度融合</strong>
        <p style="margin: 8px 0 0 0; color: #555;">视觉奖励建模、多模态概念瓶颈模型、视觉到代码任务表明 VLM 正在向更细粒度、更可靠的方向发展。</p>
    </div>
    <div style="margin-bottom: 15px;">
        <strong style="color: #667eea;">3️⃣ 高效训练与推理</strong>
        <p style="margin: 8px 0 0 0; color: #555;">神经元感知数据选择、扩散 Transformer 图像压缩、MXNorm 归一化等技术追求更高效率。</p>
    </div>
    <div style="margin-bottom: 15px;">
        <strong style="color: #667eea;">4️⃣ AI 安全与治理</strong>
        <p style="margin: 8px 0 0 0; color: #555;">多智能体治理框架、隐私漏洞分析、幻觉缓解等研究反映 AI 安全日益受到重视。</p>
    </div>
    <div>
        <strong style="color: #667eea;">5️⃣ 科学 AI 实用化</strong>
        <p style="margin: 8px 0 0 0; color: #555;">从实验到专家的知识积累系统、物理系统表示学习等表明 AI for Science 正走向成熟应用。</p>
    </div>
</div>
"""

# 构建 HTML 邮件内容
html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 今日 AI 论文速递 - {TODAY}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f7fa;
        }}
        .container {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .paper-card {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 0 10px 10px 0;
            transition: transform 0.2s;
        }}
        .paper-card:hover {{
            transform: translateX(5px);
        }}
        .paper-title {{
            font-size: 18px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 10px;
        }}
        .paper-title a {{
            color: #667eea;
            text-decoration: none;
        }}
        .paper-title a:hover {{
            text-decoration: underline;
        }}
        .paper-category {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 10px;
        }}
        .paper-summary {{
            color: #555;
            font-size: 14px;
            line-height: 1.7;
        }}
        h2 {{
            color: #2d3748;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-top: 30px;
        }}
        h3 {{
            color: #4a5568;
            margin-top: 25px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
            color: #718096;
            font-size: 12px;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
        }}
        .stat-item {{
            text-align: center;
            color: white;
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 今日 AI 论文速递</h1>
            <p>{TODAY} | arXiv 24 小时最新论文精选</p>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number">10</div>
                <div class="stat-label">精选论文</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">5</div>
                <div class="stat-label">研究方向</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">24h</div>
                <div class="stat-label">时间范围</div>
            </div>
        </div>

        <h2>📚 论文精选</h2>
"""

# 添加论文卡片
for i, paper in enumerate(papers, 1):
    html_content += f"""
        <div class="paper-card">
            <span class="paper-category">{paper['category']}</span>
            <div class="paper-title">
                <a href="{paper['link']}">{i}. {paper['title']}</a>
            </div>
            <div class="paper-summary">
                {paper['summary']}
            </div>
        </div>
"""

# 添加研究方向和趋势
html_content += research_directions
html_content += core_trends

# 添加页脚
html_content += f"""
        <div class="footer">
            <p>数据来源：arXiv.org | 自动生成于 {TODAY}</p>
            <p>🤖 AI 论文速递机器人 | leotangbot@163.com</p>
        </div>
    </div>
</body>
</html>
"""

# 创建邮件
msg = MIMEMultipart('alternative')
msg['Subject'] = Header(f"📊 今日 AI 论文速递 - {TODAY}", 'utf-8')
msg['From'] = SENDER_EMAIL
msg['To'] = RECEIVER_EMAIL

# 添加 HTML 内容
html_part = MIMEText(html_content, 'html', 'utf-8')
msg.attach(html_part)

# 发送邮件
try:
    # 创建 SSL 上下文
    context = ssl.create_default_context()
    
    # 连接 SMTP 服务器
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    
    print(f"✅ 邮件发送成功！")
    print(f"📧 收件人：{RECEIVER_EMAIL}")
    print(f"📅 日期：{TODAY}")
    print(f"📄 论文数量：{len(papers)}")
except Exception as e:
    print(f"❌ 邮件发送失败：{e}")
    raise
