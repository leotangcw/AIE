#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发送 AI 论文速递邮件
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime

# 邮件配置
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
        "title": "OS-Themis: A Scalable Critic Framework for Generalist GUI Rewards",
        "arxiv": "2603.19191",
        "direction": "强化学习 · GUI 智能体",
        "summary": "提出了 OS-Themis，一个可扩展且准确的多智能体批评框架，用于改进 GUI 智能体的强化学习训练。通过将轨迹分解为可验证的里程碑并采用审查机制，在 AndroidWorld 实验中实现了 10.3% 的性能提升。"
    },
    {
        "title": "Box Maze: A Process-Control Architecture for Reliable LLM Reasoning",
        "arxiv": "2603.19182",
        "direction": "LLM 安全 · 推理可靠性",
        "summary": "提出了 Box Maze 框架，将 LLM 推理分解为三个显式层：记忆基础、结构化推理和边界执行。在对抗性场景下，将边界失败率从 40% 降低到 1% 以下，显著提升推理可靠性。"
    },
    {
        "title": "cuGenOpt: A GPU-Accelerated General-Purpose Metaheuristic Framework for Combinatorial Optimization",
        "arxiv": "2603.19163",
        "direction": "组合优化 · GPU 加速",
        "summary": "提出了 cuGenOpt，一个 GPU 加速的通用元启发式框架。采用「一个块演化一个解」的 CUDA 架构，在 TSP-442 问题上 30 秒内达到 4.73% 间隙，比通用 MIP 求解器快数个数量级。"
    },
    {
        "title": "D5P4: Partition Determinantal Point Process for Diversity in Parallel Discrete Diffusion Decoding",
        "arxiv": "2603.19146",
        "direction": "扩散模型 · 文本生成",
        "summary": "提出了 D5P4，一种基于行列式点过程的并行离散扩散解码方法。通过 MAP 推理实现显式的多样性 - 概率权衡，在自由形式生成和问答任务中显著提升多样性。"
    },
    {
        "title": "Implicit Patterns in LLM-Based Binary Analysis",
        "arxiv": "2603.19138",
        "direction": "LLM 应用 · 二进制分析",
        "summary": "首次大规模研究了 LLM 在二进制漏洞分析中的隐式推理模式。分析了 521 个二进制文件和 99,563 个推理步骤，识别出四种主导模式：早期剪枝、路径依赖锁定、针对性回溯和知识引导优先级。"
    },
    {
        "title": "How Uncertainty Estimation Scales with Sampling in Reasoning Models",
        "arxiv": "2603.19118",
        "direction": "不确定性估计 · 推理模型",
        "summary": "研究了推理模型中不确定性估计如何随采样规模变化。发现混合估计器仅需 2 个样本即可提升 AUROC 达 12%，在数学领域表现最佳，展示了信号组合的强大效果。"
    },
    {
        "title": "LuMamba: Latent Unified Mamba for Electrode Topology-Invariant and Efficient EEG Modeling",
        "arxiv": "2603.19100",
        "direction": "脑机接口 · 高效架构",
        "summary": "提出了 LuMamba，结合拓扑不变编码和线性复杂度状态空间建模的 EEG 基础模型。仅需 4.6M 参数，在 TUAB 上达到 80.99% 平衡准确率，计算量比 SOTA 减少 377 倍。"
    },
    {
        "title": "Serendipity by Design: Evaluating the Impact of Cross-domain Mappings on Human and LLM Creativity",
        "arxiv": "2603.19087",
        "direction": "创造力研究 · 人机对比",
        "summary": "评估了跨领域映射对人类和 LLM 创造力的影响。发现人类 reliably 受益于随机跨领域映射，而 LLM 平均生成更原创的想法但对干预不敏感，揭示了人机创造力的系统性差异。"
    },
    {
        "title": "Man and machine: artificial intelligence and judicial decision making",
        "arxiv": "2603.19042",
        "direction": "AI 伦理 · 司法决策",
        "summary": "综述了 AI 在司法决策中的应用，特别是风险评估工具。指出当前证据表明 AI 决策辅助工具对判决影响有限，呼吁加强跨学科研究和人机交互理解。"
    },
    {
        "title": "Behavioral Fingerprints for LLM Endpoint Stability and Identity",
        "arxiv": "2603.19022",
        "direction": "LLM 运维 · 稳定性监控",
        "summary": "提出了 Stability Monitor，一个黑盒稳定性监控系统。通过行为指纹检测端点变化，可识别模型家族、版本、推理栈、量化等变更，在真实场景中观察到显著的提供商间稳定性差异。"
    }
]

# 研究方向统计
direction_stats = {
    "强化学习与智能体": 1,
    "LLM 安全与可靠性": 2,
    "高效架构与优化": 2,
    "生成模型": 1,
    "科学 AI (脑机接口)": 1,
    "AI 伦理与社会影响": 2,
    "LLM 分析与理解": 1
}

# 核心趋势
trends = """
<ol>
    <li><strong>效率优先</strong>：多篇论文聚焦计算效率优化，如 LuMamba 的线性复杂度架构、cuGenOpt 的 GPU 加速框架</li>
    <li><strong>可靠性与安全</strong>：LLM 推理可靠性（Box Maze）和端点稳定性监控（Behavioral Fingerprints）成为研究热点</li>
    <li><strong>多模态与具身智能</strong>：GUI 智能体（OS-Themis）和脑电信号处理（LuMamba）显示 AI 向物理世界延伸</li>
    <li><strong>人机协作理解</strong>：创造力对比研究和司法决策综述反映对人机交互深层理解的重视</li>
    <li><strong>生成模型创新</strong>：离散扩散解码（D5P4）探索自回归之外的生成范式</li>
</ol>
"""

# 生成 HTML 内容
html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>今日 AI 论文速递</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: #ffffff;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            font-size: 24px;
        }}
        h2 {{
            color: #34495e;
            font-size: 18px;
            margin-top: 25px;
        }}
        .paper {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            color: white;
        }}
        .paper:nth-child(even) {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .paper-title {{
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .paper-arxiv {{
            font-size: 12px;
            opacity: 0.9;
            margin-bottom: 10px;
        }}
        .paper-direction {{
            font-size: 13px;
            background: rgba(255,255,255,0.2);
            padding: 3px 8px;
            border-radius: 4px;
            display: inline-block;
            margin-bottom: 10px;
        }}
        .paper-summary {{
            font-size: 14px;
            line-height: 1.7;
            opacity: 0.95;
        }}
        .stats {{
            background-color: #ecf0f1;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }}
        .stat-item {{
            background: white;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
            border-left: 4px solid #3498db;
        }}
        .stat-number {{
            font-size: 24px;
            font-weight: bold;
            color: #3498db;
        }}
        .stat-label {{
            font-size: 12px;
            color: #7f8c8d;
            margin-top: 5px;
        }}
        .trends {{
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .trends h3 {{
            color: #856404;
            margin-top: 0;
        }}
        .trends li {{
            margin: 10px 0;
            color: #856404;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            color: #95a5a6;
            font-size: 12px;
        }}
        .arxiv-link {{
            color: #3498db;
            text-decoration: none;
        }}
        .arxiv-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 今日 AI 论文速递 - {TODAY}</h1>
        
        <p style="color: #7f8c8d; font-size: 14px;">
            精选 arXiv 24 小时内提交的 10 篇 AI 领域最新论文，涵盖强化学习、LLM 安全、高效架构、生成模型等前沿方向。
        </p>

        <h2>📄 精选论文</h2>
"""

# 添加论文列表
for i, paper in enumerate(papers, 1):
    html_content += f"""
        <div class="paper">
            <div class="paper-title">{i}. {paper['title']}</div>
            <div class="paper-arxiv">arXiv:{paper['arxiv']} | <a href="https://arxiv.org/abs/{paper['arxiv']}" class="arxiv-link" style="color: white;">查看原文</a></div>
            <div class="paper-direction">🏷️ {paper['direction']}</div>
            <div class="paper-summary">{paper['summary']}</div>
        </div>
"""

# 添加研究方向统计
html_content += """
        <h2>📈 研究方向分布</h2>
        <div class="stats">
            <div class="stats-grid">
"""

for direction, count in direction_stats.items():
    html_content += f"""
                <div class="stat-item">
                    <div class="stat-number">{count}</div>
                    <div class="stat-label">{direction}</div>
                </div>
"""

html_content += f"""
            </div>
        </div>

        <h2>🔮 核心趋势</h2>
        <div class="trends">
            <h3>今日 AI 研究五大趋势</h3>
            {trends}
        </div>

        <div class="footer">
            <p>📧 本邮件由 AI 自动生成 | 数据来源：arXiv.org</p>
            <p>如有疑问请联系：leotangbot@163.com</p>
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
    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    server.quit()
    print(f"✅ 邮件发送成功！")
    print(f"📧 收件人：{RECEIVER_EMAIL}")
    print(f"📅 日期：{TODAY}")
    print(f"📄 论文数量：{len(papers)}")
except Exception as e:
    print(f"❌ 邮件发送失败：{e}")
