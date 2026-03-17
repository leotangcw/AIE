#!/usr/bin/env python3
"""发送今日 AI 论文邮件"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
smtp_server = 'smtp.163.com'
smtp_port = 465
sender_email = 'leotangbot@163.com'
sender_password = 'SWdqGSFtw34fRnie'
receiver_email = 'tangchengwen@163.com'

subject = '📊 今日 AI 论文速递 - 2026-03-12'

html_content = """
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #1a73e8; color: white; padding: 20px; }
        .section { margin: 20px 0; }
        .paper { border-left: 4px solid #1a73e8; padding: 15px; margin: 15px 0; background: #f9f9f9; }
        .title { font-size: 16px; font-weight: bold; color: #1a73e8; }
        .desc { color: #555; margin: 8px 0; }
        .directions { background: #e8f4fd; padding: 15px; border-radius: 5px; }
        .footer { background: #f5f5f5; padding: 15px; text-align: center; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 今日 AI 论文速递</h1>
        <p>日期：2026-03-12</p>
    </div>
    <div style="padding: 20px;">
        <div class="section">
            <h2>📄 今日论文 (5 篇)</h2>
            <div class="paper">
                <div class="title">1. Boosting deep RL using pretraining with Logical Options</div>
                <div class="desc">H²RL 混合框架，用逻辑选项预训练策略引导 RL 智能体，避免短期奖励循环，提升长程决策能力</div>
            </div>
            <div class="paper">
                <div class="title">2. A recipe for scalable attention-based MLIPs</div>
                <div class="desc">AllScAIP 模型，基于注意力的机器学习原子势，扩展到 1 亿训练样本，用全连接节点注意力捕捉长程相互作用</div>
            </div>
            <div class="paper">
                <div class="title">3. Causal Interpretation of Neural Network computations with Contribution Decomposition</div>
                <div class="desc">CODEC 方法，用稀疏自编码器分解神经网络隐藏神经元贡献，揭示因果过程，支持因果操纵和可解释可视化</div>
            </div>
            <div class="paper">
                <div class="title">4. Talk Freely, Execute Strictly: Schema-Gated Agentic AI</div>
                <div class="desc">模式门控编排架构，分离对话灵活性和执行确定性，解决科学工作流中 LLM 的可重复性问题</div>
            </div>
            <div class="paper">
                <div class="title">5. Hierarchical Industrial Demand Forecasting with Temporal and Uncertainty Explanations</div>
                <div class="desc">层次化时间序列预测的可解释性方法，解释变量对预测和不确定性的影响，应用于工业供应链场景</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🎯 研究方向总结</h2>
            <div class="directions">
                <ul>
                    <li><strong>可解释 AI</strong> (2 篇) - 神经元因果分解、预测不确定性解释</li>
                    <li><strong>强化学习</strong> (1 篇) - 逻辑选项预训练 + 深度 RL</li>
                    <li><strong>科学 AI</strong> (2 篇) - 分子动力学原子势、科学工作流自动化</li>
                    <li><strong>AI Agent</strong> (1 篇) - 模式门控编排架构</li>
                    <li><strong>时间序列预测</strong> (1 篇) - 工业需求预测</li>
                </ul>
            </div>
        </div>
        
        <div class="section">
            <h2>🔥 核心趋势</h2>
            <p><strong>可解释性</strong>和<strong>科学领域落地</strong>是今日研究热点。</p>
        </div>
    </div>
    <div class="footer">
        <p>此邮件由 AIE 智能助手自动生成</p>
        <p>发送时间：2026-03-12 11:25</p>
    </div>
</body>
</html>
"""

# 发送邮件
msg = MIMEMultipart('alternative')
msg['Subject'] = subject
msg['From'] = sender_email
msg['To'] = receiver_email

html_part = MIMEText(html_content, 'html', 'utf-8')
msg.attach(html_part)

server = smtplib.SMTP_SSL(smtp_server, smtp_port)
server.login(sender_email, sender_password)
server.sendmail(sender_email, [receiver_email], msg.as_string())
server.quit()

print('✅ 邮件发送成功！')
print(f'收件人：{receiver_email}')
print(f'主题：{subject}')
