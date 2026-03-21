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
today = datetime.now().strftime("%Y-%m-%d")

# 论文数据（从 arxiv 获取的最新论文）
papers = [
    {
        "title": "MultihopSpatial: Multi-hop Compositional Spatial Reasoning Benchmark for Vision-Language Model",
        "summary": "针对视觉语言模型（VLMs）的空间推理能力，提出了 MultihopSpatial 基准测试。该基准专注于多跳组合空间推理，包含 1-3 跳复杂查询，并提出了 Acc@50IoU 新评估指标。对 37 个最先进 VLM 的评估揭示了组合空间推理仍是重大挑战。",
        "category": "计算机视觉 / 视觉语言模型",
        "authors": "Youngwan Lee et al."
    },
    {
        "title": "PromptHub: Enhancing Multi-Prompt Visual In-Context Learning with Locality-Aware Fusion",
        "summary": "提出了 PromptHub 框架，通过位置感知融合、集中和对齐来增强多提示视觉上下文学习。该方法利用空间先验捕获更丰富的上下文信息，在三个基本视觉任务上展示了优越性，并验证了其在分布外设置中的通用性和鲁棒性。",
        "category": "计算机视觉 / 上下文学习",
        "authors": "Tianci Luo et al."
    },
    {
        "title": "Reasoning over Mathematical Objects: On-Policy Reward Modeling and Test Time Aggregation",
        "summary": "针对数学对象推理能力，发布了 Principia 训练数据集和基准测试。提出了强 LLM 评判者和验证器的训练方案，展示了 on-policy 评判训练可提升性能，并通过聚合扩展测试时计算能力。",
        "category": "大语言模型 / 数学推理",
        "authors": "Pranjal Aggarwal et al."
    },
    {
        "title": "DriftGuard: Mitigating Asynchronous Data Drift in Federated Learning",
        "summary": "提出了 DriftGuard 联邦持续学习框架，有效应对异步数据漂移问题。采用混合专家（MoE）架构分离共享参数和局部参数，实现全局和群体两种互补的重训练策略，在多个数据集上减少重训练成本高达 83%。",
        "category": "联邦学习 / 持续学习",
        "authors": "Yizhou Han et al."
    },
    {
        "title": "Bridging Network Fragmentation: A Semantic-Augmented DRL Framework for UAV-aided VANETs",
        "summary": "提出了语义增强深度强化学习（SA-DRL）框架，用于无人机辅助车联网。通过将 LLM 的语义推理能力注入策略作为先验，有效引导智能体朝向关键路口。仅用 26.6% 的训练回合即可达到基线性能， connectivity 指标提升 13.2%-23.5%。",
        "category": "强化学习 / 无线网络",
        "authors": "Gaoxiang Cao et al."
    },
    {
        "title": "Through the Looking-Glass: AI-Mediated Video Communication Reduces Interpersonal Trust",
        "summary": "通过两项预注册在线实验（N=2000）研究 AI 中介视频通信对人际信任的影响。发现 AI 中介视频（如修图、背景替换、虚拟形象）会降低感知信任和判断信心，但实际判断准确性保持不变。",
        "category": "人机交互 / AI 伦理",
        "authors": "Nelson Navajas Fernández et al."
    },
    {
        "title": "RewardFlow: Topology-Aware Reward Propagation on State Graphs for Agentic RL with LLMs",
        "summary": "提出了 RewardFlow 方法，用于代理强化学习中的状态级奖励估计。通过构建状态图并利用拓扑结构进行图传播，量化状态对成功的贡献。在四个代理推理基准测试上显著优于 prior RL 基线。",
        "category": "强化学习 / 大语言模型",
        "authors": "Xiao Feng et al."
    },
    {
        "title": "Why Better Cross-Lingual Alignment Fails for Better Cross-Lingual Transfer: Case of Encoders",
        "summary": "揭示了更好的跨语言对齐并不总能带来更好的跨语言迁移。通过表示分析发现：嵌入距离 alone 是不可靠的性能预测指标，对齐和任务梯度通常接近正交。提供了结合跨语言对齐与任务特定微调的实用指南。",
        "category": "自然语言处理 / 跨语言学习",
        "authors": "Yana Veitsman et al."
    },
    {
        "title": "A Human-in/on-the-Loop Framework for Accessible Text Generation",
        "summary": "提出了混合框架，将人类参与明确整合到基于 LLM 的无障碍文本生成中。Human-in-the-Loop 指导生成过程中的调整，Human-on-the-Loop 确保系统化的生成后审查。建立了可追踪、可重现、可审计的无障碍文本创建流程。",
        "category": "自然语言处理 / 无障碍技术",
        "authors": "Lourdes Moreno et al."
    },
    {
        "title": "RadioDiff-FS: Physics-Informed Manifold Alignment in Few-Shot Diffusion Models for Radio Map Construction",
        "summary": "提出了 RadioDiff-FS 少样本扩散框架，用于高保真无线电地图构建。基于多路径无线电地图的理论分解，引入方向一致性损失约束扩散分数更新。在静态和动态无线电地图上分别减少 NMSE 59.5% 和 74.0%。",
        "category": "扩散模型 / 无线通信",
        "authors": "Xiucheng Wang et al."
    }
]

# 研究方向总结
research_summary = """
<h3>📈 研究方向总结</h3>
<ul>
    <li><strong>视觉语言模型 (VLM)</strong>: 空间推理基准测试、视觉上下文学习</li>
    <li><strong>大语言模型推理</strong>: 数学推理、代理强化学习、奖励建模</li>
    <li><strong>联邦学习</strong>: 异步数据漂移缓解、持续学习</li>
    <li><strong>人机交互</strong>: AI 中介通信对信任的影响、无障碍文本生成</li>
    <li><strong>跨语言学习</strong>: 跨语言对齐与迁移的理论与实践</li>
    <li><strong>扩散模型应用</strong>: 物理信息引导的少样本学习</li>
</ul>
"""

# 核心趋势
core_trends = """
<h3>🔮 核心趋势洞察</h3>
<ol>
    <li><strong>多模态推理深化</strong>: VLM 研究从基础感知向复杂组合推理演进，空间推理成为新焦点</li>
    <li><strong>RL + LLM 融合</strong>: 强化学习与大语言模型结合，解决代理推理中的奖励稀疏问题</li>
    <li><strong>高效学习范式</strong>: 联邦学习、少样本学习、持续学习受到关注，强调计算效率</li>
    <li><strong>人本 AI 设计</strong>: 人机交互、无障碍技术、AI 伦理研究增多，关注 AI 对社会的影响</li>
    <li><strong>领域专业化</strong>: 通用模型向专业领域（地理、通信、语言学习）深度适配</li>
</ol>
"""

# 构建 HTML 邮件内容
html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>今日 AI 论文速递 - {today}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: #ffffff;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            text-align: center;
        }}
        h2 {{
            color: #2980b9;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}
        h3 {{
            color: #27ae60;
        }}
        .paper {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .paper-title {{
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .paper-summary {{
            font-size: 14px;
            opacity: 0.95;
            margin-bottom: 10px;
        }}
        .paper-meta {{
            font-size: 12px;
            opacity: 0.8;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
        }}
        .tag {{
            background-color: rgba(255,255,255,0.2);
            padding: 3px 10px;
            border-radius: 15px;
            display: inline-block;
            margin: 3px;
        }}
        ul, ol {{
            padding-left: 20px;
        }}
        li {{
            margin: 8px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
        }}
        .highlight {{
            background-color: #fff3cd;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #ffc107;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 今日 AI 论文速递 - {today}</h1>
        
        <div class="highlight">
            <strong>📌 本期概要：</strong> 精选 arxiv 24 小时内提交的 10 篇 AI 领域最新论文，涵盖视觉语言模型、大语言模型推理、联邦学习、人机交互等前沿方向。
        </div>

        <h2>📚 精选论文</h2>
"""

# 添加论文列表
for i, paper in enumerate(papers, 1):
    html_content += f"""
        <div class="paper">
            <div class="paper-title">#{i} {paper['title']}</div>
            <div class="paper-summary">{paper['summary']}</div>
            <div class="paper-meta">
                <span class="tag">🏷️ {paper['category']}</span>
                <span class="tag">✍️ {paper['authors']}</span>
            </div>
        </div>
"""

html_content += research_summary + core_trends

html_content += f"""
        <div class="footer">
            <p>📧 本邮件由 AI 自动整理发送 | 数据来源：arxiv.org</p>
            <p>🔗 论文原文链接请访问 <a href="https://arxiv.org" style="color: #3498db;">arxiv.org</a></p>
            <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>
"""

# 创建邮件
msg = MIMEMultipart('alternative')
msg['Subject'] = Header(f"📊 今日 AI 论文速递 - {today}", 'utf-8')
msg['From'] = Header("Leo AI Bot <leotangbot@163.com>", 'utf-8')
msg['To'] = Header("tangchengwen@163.com", 'utf-8')

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
    print(f"📅 日期：{today}")
    print(f"📄 论文数量：{len(papers)} 篇")
except Exception as e:
    print(f"❌ 邮件发送失败：{e}")
    raise
