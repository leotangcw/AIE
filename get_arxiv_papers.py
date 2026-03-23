#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取 arxiv 最新 AI 论文并发送邮件 - 带重试机制
"""

import arxiv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import time
import requests

# 配置
SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465
SENDER_EMAIL = "leotangbot@163.com"
SENDER_PASSWORD = "SWdqGSFtw34fRnie"
RECEIVER_EMAIL = "tangchengwen@163.com"

def get_latest_papers_arxiv_api(max_results=10):
    """使用 arxiv API 获取最新论文（带重试）"""
    papers = []
    seen_titles = set()
    
    # 使用不同的查询来获取不同领域的论文
    queries = [
        "cat:cs.AI",
        "cat:cs.LG", 
        "cat:cs.CV",
        "cat:cs.CL"
    ]
    
    client = arxiv.Client(
        page_size=5,
        delay_seconds=3.0  # 增加延迟避免限流
    )
    
    for query in queries:
        if len(papers) >= max_results:
            break
            
        try:
            search = arxiv.Search(
                query=query,
                max_results=5,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            for result in client.results(search):
                if len(papers) >= max_results:
                    break
                if result.title not in seen_titles:
                    seen_titles.add(result.title)
                    papers.append({
                        'title': result.title,
                        'summary': result.summary,
                        'published': result.published,
                        'authors': [str(a) for a in result.authors],
                        'categories': result.categories,
                        'pdf_url': result.pdf_url,
                        'arxiv_url': result.entry_id
                    })
            
            time.sleep(2)  # 查询间延迟
            
        except Exception as e:
            print(f"查询 {query} 出错：{e}")
            time.sleep(5)
            continue
    
    papers.sort(key=lambda x: x['published'], reverse=True)
    return papers

def analyze_research_directions(papers):
    """分析研究方向"""
    directions = {}
    
    keywords_map = {
        "大语言模型": ["llm", "large language model", "gpt", "transformer", "language model"],
        "计算机视觉": ["vision", "image", "visual", "cnn", "object detection", "segmentation"],
        "强化学习": ["reinforcement learning", "rl", "policy", "reward", "agent"],
        "生成模型": ["generative", "diffusion", "gan", "vae", "text-to-image"],
        "多模态": ["multimodal", "vision-language", "clip", "image-text"],
        "自然语言处理": ["nlp", "text", "language", "translation", "sentiment"],
        "机器人": ["robot", "robotics", "control", "manipulation"],
        "优化算法": ["optimization", "gradient", "training", "convergence"],
        "其他": []
    }
    
    for paper in papers:
        text = (paper['title'] + " " + paper['summary']).lower()
        categorized = False
        
        for direction, keywords in keywords_map.items():
            if direction == "其他":
                continue
            for keyword in keywords:
                if keyword.lower() in text:
                    if direction not in directions:
                        directions[direction] = 0
                    directions[direction] += 1
                    categorized = True
                    break
            if categorized:
                break
        
        if not categorized:
            if "其他" not in directions:
                directions["其他"] = 0
            directions["其他"] += 1
    
    return directions

def generate_html_email(papers, directions):
    """生成 HTML 格式的邮件内容"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    sorted_directions = sorted(directions.items(), key=lambda x: x[1], reverse=True)
    trends_html = ""
    for direction, count in sorted_directions[:5]:
        percentage = (count / len(papers)) * 100 if papers else 0
        bar_width = int(percentage * 2)
        trends_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{direction}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                <div style="background: #e0e0e0; border-radius: 4px; height: 20px; width: 200px;">
                    <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                                border-radius: 4px; height: 100%; width: {bar_width}px;"></div>
                </div>
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{count}篇 ({percentage:.1f}%)</td>
        </tr>
        """
    
    papers_html = ""
    for i, paper in enumerate(papers, 1):
        text = (paper['title'] + " " + paper['summary']).lower()
        direction = "📌 综合 AI"
        keywords_map = {
            "🤖 大语言模型": ["llm", "large language model", "gpt", "transformer", "language model"],
            "👁️ 计算机视觉": ["vision", "image", "visual", "cnn", "object detection", "segmentation"],
            "🎮 强化学习": ["reinforcement learning", "rl", "policy", "reward", "agent"],
            "🎨 生成模型": ["generative", "diffusion", "gan", "vae", "text-to-image"],
            "🔀 多模态": ["multimodal", "vision-language", "clip", "image-text"],
            "📝 自然语言处理": ["nlp", "text", "language", "translation", "sentiment"],
            "🦾 机器人": ["robot", "robotics", "control", "manipulation"],
        }
        
        for dir_name, keywords in keywords_map.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    direction = dir_name
                    break
            if direction != "📌 综合 AI":
                break
        
        papers_html += f"""
        <div style="background: #f8f9fa; border-left: 4px solid #667eea; 
                    padding: 15px; margin: 15px 0; border-radius: 0 8px 8px 0;">
            <h3 style="margin: 0 0 10px 0; color: #333; font-size: 16px;">
                {i}. {paper['title']}
            </h3>
            <p style="margin: 0 0 10px 0; color: #666; font-size: 13px; line-height: 1.6;">
                {paper['summary'][:300]}{'...' if len(paper['summary']) > 300 else ''}
            </p>
            <div style="font-size: 12px; color: #888;">
                <span style="background: #667eea; color: white; padding: 2px 8px; 
                            border-radius: 12px; margin-right: 8px;">{direction}</span>
                <span>📅 {paper['published'].strftime('%Y-%m-%d %H:%M')}</span>
                <span style="margin-left: 10px;">🔗 <a href="{paper['arxiv_url']}" 
                           style="color: #667eea; text-decoration: none;">查看论文</a></span>
            </div>
        </div>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
                     'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; 
                     max-width: 800px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
            .section {{ margin: 30px 0; }}
            .section h2 {{ color: #667eea; border-bottom: 2px solid #667eea; 
                         padding-bottom: 10px; }}
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; 
                    margin: 20px 0; }}
            .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; 
                        text-align: center; }}
            .stat-number {{ font-size: 32px; font-weight: bold; color: #667eea; }}
            .stat-label {{ color: #666; margin-top: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: #667eea; color: white; padding: 12px; text-align: left; }}
            .footer {{ background: #f8f9fa; padding: 20px; border-radius: 8px; 
                    margin-top: 30px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 今日 AI 论文速递</h1>
            <p>{today} | arXiv 24 小时内最新 AI 研究</p>
        </div>
        
        <div class="section">
            <h2>📈 研究概况</h2>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(papers)}</div>
                    <div class="stat-label">今日论文数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(set(d for p in papers for d in p['categories']))}</div>
                    <div class="stat-label">涉及领域</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(directions)}</div>
                    <div class="stat-label">研究方向</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>🎯 核心趋势</h2>
            <table>
                <tr>
                    <th>研究方向</th>
                    <th>热度</th>
                    <th>占比</th>
                </tr>
                {trends_html}
            </table>
        </div>
        
        <div class="section">
            <h2>📚 论文列表</h2>
            {papers_html}
        </div>
        
        <div class="footer">
            <p>📧 本邮件由 AI 论文速递机器人自动生成</p>
            <p>数据来源：arXiv.org | 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    
    return html_content

def send_email(subject, html_content):
    """发送邮件"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    
    html_part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(html_part)
    
    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        server.quit()
        print("✅ 邮件发送成功！")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")
        return False

def main():
    print("🔍 正在获取最新 AI 论文...")
    papers = get_latest_papers_arxiv_api(max_results=10)
    
    print(f"📄 获取到 {len(papers)} 篇论文")
    
    if not papers:
        print("❌ 无法获取论文，退出")
        return
    
    print("🔬 正在分析研究方向...")
    directions = analyze_research_directions(papers)
    
    print("📧 正在生成邮件...")
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"📊 今日 AI 论文速递 - {today}"
    html_content = generate_html_email(papers, directions)
    
    print("🚀 正在发送邮件...")
    success = send_email(subject, html_content)
    
    if success:
        print(f"\n✅ 完成！邮件已发送至 {RECEIVER_EMAIL}")
        print(f"📅 日期：{today}")
        print(f"📊 论文数量：{len(papers)}")
    else:
        print("\n❌ 发送失败，请检查配置")

if __name__ == "__main__":
    main()
