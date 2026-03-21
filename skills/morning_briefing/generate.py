#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🌅 AIE Morning Briefing Generator
生成每日晨报：天气 + 新闻 + AI 论文 + TTS 语音
"""

import smtplib
import ssl
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import json
import subprocess

# ============ 配置 ============
SMTP_SERVER = "smtp.163.com"
SMTP_PORT = 465
SENDER_EMAIL = "leotangbot@163.com"
SENDER_PASSWORD = "SWdqGSFtw34fRnie"
RECEIVER_EMAIL = "tangchengwen@163.com"

# API 端点
WEATHER_API = "https://wttr.in/Beijing?format=j1"
ARXIV_API = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=10"
NEWS_RSS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
]

# ============ 天气获取 ============
def get_weather():
    """获取北京天气"""
    try:
        resp = requests.get(WEATHER_API, timeout=5)
        data = resp.json()
        
        current = data['current_condition'][0]
        today = data['weather'][0]
        
        weather_info = {
            'temp_c': current['temp_C'],
            'temp_f': current['temp_F'],
            'desc_zh': current['lang_zh'][0]['value'],
            'desc_en': current['weatherDesc'][0]['value'],
            'humidity': current['humidity'],
            'wind': f"{current['windspeedKmph']} km/h {current['winddir16Point']}",
            'max_temp': today['maxtempC'],
            'min_temp': today['mintempC'],
        }
        return weather_info
    except Exception as e:
        return {'error': str(e)}

# ============ AI 论文获取 ============
def get_arxiv_papers():
    """获取最新 AI 论文"""
    import feedparser
    
    try:
        feed = feedparser.parse(ARXIV_API)
        papers = []
        
        for entry in feed.entries[:10]:
            paper = {
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary[:200] + '...' if len(entry.summary) > 200 else entry.summary,
                'published': entry.published[:10] if 'published' in entry else 'N/A',
            }
            papers.append(paper)
        
        return papers
    except Exception as e:
        return [{'title': f'获取失败：{str(e)}'}]

# ============ 新闻获取 ============
def get_tech_news():
    """获取科技新闻"""
    import feedparser
    
    news_list = []
    for rss_url in NEWS_RSS[:1]:  # 只取一个源避免超时
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:5]:
                news = {
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published[:10] if 'published' in entry else 'N/A',
                }
                news_list.append(news)
        except:
            continue
    
    return news_list[:5]

# ============ HTML 邮件生成 ============
def generate_html_email(weather, papers, news):
    """生成 HTML 格式邮件"""
    today = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")
    
    # 天气图标
    weather_icon = "☀️" if 'Sunny' in weather.get('desc_en', '') else "☁️" if 'Cloud' in weather.get('desc_en', '') else "🌧️"
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header p {{ margin: 10px 0 0; opacity: 0.9; }}
        .section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; }}
        .section h2 {{ color: #667eea; margin-top: 0; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        .weather-box {{ display: flex; justify-content: space-around; text-align: center; }}
        .weather-item {{ padding: 10px; }}
        .weather-icon {{ font-size: 48px; }}
        .paper-item, .news-item {{ background: white; padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 4px solid #667eea; }}
        .paper-item h3, .news-item h3 {{ margin: 0 0 8px; font-size: 16px; color: #333; }}
        .paper-item a, .news-item a {{ color: #667eea; text-decoration: none; }}
        .paper-item a:hover, .news-item a:hover {{ text-decoration: underline; }}
        .meta {{ color: #888; font-size: 13px; margin-top: 8px; }}
        .summary {{ color: #555; font-size: 14px; }}
        .trend {{ background: #e8f4fd; padding: 15px; border-radius: 6px; }}
        .trend ul {{ margin: 10px 0; padding-left: 20px; }}
        .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌅 早安 · Morning Briefing</h1>
        <p>{today} | {weekday} | 北京</p>
    </div>
    
    <div class="section">
        <h2>🌤️ 今日天气</h2>
        <div class="weather-box">
            <div class="weather-item">
                <div class="weather-icon">{weather_icon}</div>
                <div><strong>{weather.get('desc_zh', 'N/A')}</strong></div>
                <div>{weather.get('temp_c', 'N/A')}°C / {weather.get('temp_f', 'N/A')}°F</div>
            </div>
            <div class="weather-item">
                <div class="weather-icon">🌡️</div>
                <div>最高 {weather.get('max_temp', 'N/A')}°C</div>
                <div>最低 {weather.get('min_temp', 'N/A')}°C</div>
            </div>
            <div class="weather-item">
                <div class="weather-icon">💧</div>
                <div>湿度 {weather.get('humidity', 'N/A')}%</div>
                <div>{weather.get('wind', 'N/A')}</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>📊 AI 论文速递 (arXiv)</h2>
"""
    
    for i, paper in enumerate(papers[:5], 1):
        html += f"""
        <div class="paper-item">
            <h3>{i}. <a href="{paper.get('link', '#')}">{paper.get('title', 'N/A')}</a></h3>
            <div class="summary">{paper.get('summary', 'N/A')}</div>
            <div class="meta">📅 {paper.get('published', 'N/A')}</div>
        </div>
"""
    
    html += """
    </div>
    
    <div class="section">
        <h2>📰 科技新闻</h2>
"""
    
    for i, news in enumerate(news[:5], 1):
        html += f"""
        <div class="news-item">
            <h3>{i}. <a href="{news.get('link', '#')}">{news.get('title', 'N/A')}</a></h3>
            <div class="meta">📅 {news.get('published', 'N/A')}</div>
        </div>
"""
    
    html += f"""
    </div>
    
    <div class="section trend">
        <h2>🔮 今日趋势</h2>
        <ul>
            <li>多模态模型持续优化，推理效率提升</li>
            <li>Agent 工程化加速，自主性增强</li>
            <li>边缘 AI 部署方案成熟</li>
            <li>AI 安全与对齐研究深化</li>
        </ul>
    </div>
    
    <div class="footer">
        <p>Generated by AIE Morning Briefing Skill</p>
        <p>🤖 Automated Daily Briefing for tangchengwen@163.com</p>
    </div>
</body>
</html>
"""
    
    return html

# ============ 邮件发送 ============
def send_email(html_content, subject):
    """发送邮件"""
    msg = MIMEMultipart("alternative")
    msg["From"] = Header(f"AIE 晨报 <{SENDER_EMAIL}>", "utf-8")
    msg["To"] = Header(RECEIVER_EMAIL, "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    
    # 纯文本备用
    text_content = f"""
🌅 早安 · Morning Briefing
{datetime.now().strftime('%Y-%m-%d %A')}

🌤️ 天气：查看 HTML 版本
📊 AI 论文：5 篇最新 arXiv 论文
📰 科技新闻：5 条最新资讯

详情请查看 HTML 版本邮件。
    """
    
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        return True, "发送成功"
    except Exception as e:
        return False, str(e)

# ============ TTS 语音生成 ============
def generate_tts(text, output_file="morning_briefing.mp3"):
    """使用 sherpa-onnx 生成 TTS 语音"""
    try:
        # 检查 sherpa-onnx 是否可用
        result = subprocess.run(
            ["which", "sherpa-onnx-tts"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return False, "sherpa-onnx-tts 未安装"
        
        # 生成语音（简化版，实际需要模型路径）
        cmd = f"""
        sherpa-onnx-tts \\
          --vits-model=/path/to/model \\
          --vits-lexicon=/path/to/lexicon \\
          --vits-tokens=/path/to/tokens \\
          --vits-data-dir=/path/to/data \\
          --text="{text[:100]}" \\
          --output-filename="{output_file}"
        """
        # 注：实际使用需要配置模型路径
        return False, "TTS 模型未配置（需下载 sherpa-onnx 中文模型）"
        
    except Exception as e:
        return False, str(e)

# ============ 主函数 ============
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="🌅 AIE Morning Briefing")
    parser.add_argument("--send", action="store_true", help="发送邮件")
    parser.add_argument("--tts", action="store_true", help="生成 TTS 语音")
    parser.add_argument("--preview", action="store_true", help="预览 HTML")
    args = parser.parse_args()
    
    print("🌅 正在生成晨报...")
    
    # 获取数据
    print("📊 获取天气...")
    weather = get_weather()
    
    print("📄 获取 AI 论文...")
    papers = get_arxiv_papers()
    
    print("📰 获取新闻...")
    news = get_tech_news()
    
    # 生成 HTML
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"🌅 早安晨报 - {today}"
    html_content = generate_html_email(weather, papers, news)
    
    # 预览
    if args.preview:
        with open("morning_briefing_preview.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("✅ 预览已保存：morning_briefing_preview.html")
    
    # 发送邮件
    if args.send:
        print("📧 发送邮件...")
        success, msg = send_email(html_content, subject)
        if success:
            print(f"✅ {msg}")
        else:
            print(f"❌ {msg}")
    
    # 生成 TTS
    if args.tts:
        print("🗣️ 生成 TTS...")
        tts_text = f"早上好，今天是{today}。北京天气{weather.get('desc_zh', '未知')}，温度{weather.get('temp_c', '未知')}摄氏度。"
        success, msg = generate_tts(tts_text)
        print(f"{'✅' if success else '⚠️'} {msg}")
    
    print("🎉 完成！")

if __name__ == "__main__":
    main()
