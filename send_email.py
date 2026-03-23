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
import ssl

# 邮件配置
SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465
SENDER_EMAIL = "leotangbot@163.com"
SENDER_PASSWORD = "SWdqGSFtw34fRnie"
RECEIVER_EMAIL = "tangchengwen@163.com"

# 获取今天日期
today = datetime.now().strftime("%Y-%m-%d")
SUBJECT = f"📊 今日 AI 论文速递 - {today}"

# 读取 HTML 内容
with open("ai_paper_digest.html", "r", encoding="utf-8") as f:
    html_content = f.read()

# 创建邮件
msg = MIMEMultipart("alternative")
msg["From"] = Header("AI 论文速递机器人 <leotangbot@163.com>", "utf-8")
msg["To"] = Header("tangchengwen@163.com", "utf-8")
msg["Subject"] = Header(SUBJECT, "utf-8")

# 添加纯文本版本（备用）
text_content = f"""
📊 今日 AI 论文速递 - {today}

精选 10 篇 arXiv 最新 AI 论文：

1. Do Metrics for Counterfactual Explanations Align with User Perception?
   - 可解释 AI/人机交互

2. OpenSeeker: Democratizing Frontier Search Agents
   - AI Agent/开源

3. Computational Concept of the Psyche
   - AGI/认知架构

4. Are Dilemmas and Conflicts in LLM Alignment Solvable?
   - LLM 对齐/AI 安全

5. Understanding Reasoning in LLMs through Strategic Information Allocation
   - LLM 推理/信息论

6. Talk, Evaluate, Diagnose: User-aware Agent Evaluation
   - Agent 评估/自动化测试

7. Agent Lifecycle Toolkit (ALTK)
   - Agent 工程/中间件

8. Unlocking the Value of Text for Time Series Forecasting
   - 时间序列/多模态

9. Listening to the Echo: User-Reaction Aware Policy Optimization
   - 情感对话/强化学习

10. Why AI systems don't learn and what to do about it
    - 自主学习/认知科学

核心趋势：
- Agent 工程化加速
- 人类对齐深度探索
- 认知科学启发 AGI
- 评估范式革新
- 多模态融合深化

详情请查看 HTML 版本邮件。
"""

# 附加纯文本和 HTML 版本
msg.attach(MIMEText(text_content, "plain", "utf-8"))
msg.attach(MIMEText(html_content, "html", "utf-8"))

# 发送邮件
try:
    print(f"正在连接 SMTP 服务器：{SMTP_SERVER}:{SMTP_PORT}...")
    
    # 创建 SSL 上下文
    context = ssl.create_default_context()
    
    # 连接服务器并发送邮件
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        print("登录邮箱...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        print(f"发送邮件至 {RECEIVER_EMAIL}...")
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        
    print("✅ 邮件发送成功！")
    print(f"📧 收件人：{RECEIVER_EMAIL}")
    print(f"📝 主题：{SUBJECT}")
    
except smtplib.SMTPAuthenticationError as e:
    print(f"❌ 认证失败：{e}")
except smtplib.SMTPConnectError as e:
    print(f"❌ 连接失败：{e}")
except Exception as e:
    print(f"❌ 发送失败：{e}")
