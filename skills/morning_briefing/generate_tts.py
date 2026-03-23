#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🗣️ AIE Morning Briefing TTS Generator
使用 Edge TTS 生成中文语音晨报
"""

import asyncio
import edge_tts
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.header import Header
from datetime import datetime
import requests
import feedparser

# ============ 配置 ============
import os

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.163.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "your_email@163.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL", "recipient@example.com")

# TTS 配置
TTS_VOICE = "zh-CN-YunyangNeural"  # 新闻播报风格
TTS_OUTPUT = "/mnt/d/deploy_knowledge/morning_briefing_audio.mp3"

# API 端点
WEATHER_API = "https://wttr.in/Beijing?format=j1"
ARXIV_API = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=5"
NEWS_RSS = "https://techcrunch.com/feed/"


# ============ 数据获取 ============
def get_weather():
    """获取北京天气"""
    try:
        resp = requests.get(WEATHER_API, timeout=5)
        data = resp.json()
        current = data['current_condition'][0]
        today = data['weather'][0]
        return {
            'temp_c': current['temp_C'],
            'desc_zh': current['lang_zh'][0]['value'],
            'humidity': current['humidity'],
            'wind': f"{current['windspeedKmph']} km/h {current['winddir16Point']}",
            'max_temp': today['maxtempC'],
            'min_temp': today['mintempC'],
        }
    except Exception as e:
        return {'error': str(e)}


def get_arxiv_papers():
    """获取最新 AI 论文"""
    try:
        feed = feedparser.parse(ARXIV_API)
        papers = []
        for entry in feed.entries[:5]:
            papers.append({
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary[:100] + '...' if len(entry.summary) > 100 else entry.summary,
            })
        return papers
    except Exception as e:
        return [{'title': f'获取失败：{str(e)}'}]


def get_tech_news():
    """获取科技新闻"""
    try:
        feed = feedparser.parse(NEWS_RSS)
        news = []
        for entry in feed.entries[:5]:
            news.append({
                'title': entry.title,
                'link': entry.link,
            })
        return news
    except:
        return []


# ============ TTS 生成 ============
async def generate_tts_audio(text, output_file):
    """使用 Edge TTS 生成语音"""
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(output_file)
    return True


def build_tts_text(weather, papers, news):
    """构建 TTS 播报文本"""
    today = datetime.now().strftime("%Y 年%m 月%d 日")
    weekday = datetime.now().strftime("%A")
    
    text = f"""
早上好！今天是{today}，{weekday}。欢迎收听 AIE 晨报。

【天气】北京今天{weather.get('desc_zh', '未知')}，温度{weather.get('temp_c', '未知')}摄氏度，最高{weather.get('max_temp', '未知')}度，最低{weather.get('min_temp', '未知')}度。湿度{weather.get('humidity', '未知')}%，{weather.get('wind', '未知')}。

【AI 论文速递】
"""
    for i, paper in enumerate(papers[:3], 1):
        title = paper.get('title', '未知标题')
        # 简化标题，去掉技术细节
        if len(title) > 50:
            title = title[:50] + "等"
        text += f"{i}. {title}。\n"
    
    text += "\n【科技新闻】\n"
    for i, n in enumerate(news[:2], 1):
        title = n.get('title', '未知新闻')
        if len(title) > 40:
            title = title[:40] + "等"
        text += f"{i}. {title}。\n"
    
    text += """
【今日趋势】多模态模型持续优化，Agent 工程化加速，边缘 AI 部署成熟，AI 安全研究深化。

感谢收听 AIE 晨报，祝您今天工作顺利！
"""
    return text


# ============ 邮件发送 ============
def send_email_with_audio(html_content, audio_file, subject):
    """发送带音频附件的邮件"""
    msg = MIMEMultipart("mixed")
    msg["From"] = Header(f"AIE 晨报 <{SENDER_EMAIL}>", "utf-8")
    msg["To"] = Header(RECEIVER_EMAIL, "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    
    # HTML 正文
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    
    # 音频附件
    with open(audio_file, "rb") as f:
        part = MIMEBase("audio", "mpeg")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {datetime.now().strftime('%Y%m%d')}_morning_briefing.mp3"
        )
        msg.attach(part)
    
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        return True, "发送成功"
    except Exception as e:
        return False, str(e)


# ============ HTML 邮件 ============
def generate_html_email(weather, papers, news):
    """生成 HTML 邮件"""
    today = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header p {{ margin: 10px 0 0; opacity: 0.9; }}
        .section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; }}
        .section h2 {{ color: #667eea; margin-top: 0; border-bottom: 2px solid #667eea; padding-bottom: 10px; font-size: 18px; }}
        .weather-box {{ display: flex; justify-content: space-around; text-align: center; }}
        .weather-item {{ padding: 10px; }}
        .weather-icon {{ font-size: 48px; }}
        .paper-item, .news-item {{ background: white; padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 4px solid #667eea; }}
        .paper-item h3, .news-item h3 {{ margin: 0 0 8px; font-size: 16px; color: #333; }}
        .paper-item a, .news-item a {{ color: #667eea; text-decoration: none; }}
        .meta {{ color: #888; font-size: 13px; margin-top: 8px; }}
        .audio-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0; }}
        .audio-box h3 {{ margin: 0 0 10px; }}
        .audio-box p {{ margin: 0; opacity: 0.9; font-size: 14px; }}
        .trend {{ background: #e8f4fd; padding: 15px; border-radius: 6px; }}
        .trend ul {{ margin: 10px 0; padding-left: 20px; }}
        .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌅 早安 · Morning Briefing</h1>
            <p>{today} | {weekday} | 北京</p>
        </div>
        
        <div class="audio-box">
            <h3>🗣️ 语音播报已就绪</h3>
            <p>音频文件已附加到本邮件，请下载收听</p>
            <p style="margin-top: 10px; font-size: 12px;">📁 {datetime.now().strftime('%Y%m%d')}_morning_briefing.mp3</p>
        </div>
        
        <div class="section">
            <h2>🌤️ 今日天气</h2>
            <div class="weather-box">
                <div class="weather-item">
                    <div class="weather-icon">☀️</div>
                    <div><strong>{weather.get('desc_zh', 'N/A')}</strong></div>
                    <div>{weather.get('temp_c', 'N/A')}°C</div>
                </div>
                <div class="weather-item">
                    <div>🌡️ 最高 {weather.get('max_temp', 'N/A')}°C</div>
                    <div>💧 湿度 {weather.get('humidity', 'N/A')}%</div>
                    <div>💨 {weather.get('wind', 'N/A')}</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 AI 论文速递</h2>
"""
    for i, paper in enumerate(papers[:5], 1):
        html += f"""
            <div class="paper-item">
                <h3>{i}. <a href="{paper.get('link', '#')}">{paper.get('title', 'N/A')}</a></h3>
            </div>
"""
    
    html += """
        </div>
        
        <div class="section">
            <h2>📰 科技新闻</h2>
"""
    for i, n in enumerate(news[:5], 1):
        html += f"""
            <div class="news-item">
                <h3>{i}. <a href="{n.get('link', '#')}">{n.get('title', 'N/A')}</a></h3>
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
            <p>🤖 AIE Morning Briefing | Generated by AIE</p>
            <p>📧 tangchengwen@163.com</p>
        </div>
    </div>
</body>
</html>
"""
    return html


# ============ 主函数 ============
async def main():
    print("🌅 正在生成语音晨报...")
    
    # 获取数据
    print("📊 获取天气...")
    weather = get_weather()
    
    print("📄 获取 AI 论文...")
    papers = get_arxiv_papers()
    
    print("📰 获取新闻...")
    news = get_tech_news()
    
    # 构建 TTS 文本
    print("📝 构建播报文本...")
    tts_text = build_tts_text(weather, papers, news)
    print(f"   文本长度：{len(tts_text)} 字符")
    
    # 生成 TTS
    print(f"🗣️ 生成语音 ({TTS_VOICE})...")
    try:
        await generate_tts_audio(tts_text, TTS_OUTPUT)
        print(f"✅ 语音已保存：{TTS_OUTPUT}")
    except Exception as e:
        print(f"❌ TTS 生成失败：{e}")
        return
    
    # 生成 HTML
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"🌅 早安晨报 (含语音) - {today}"
    html_content = generate_html_email(weather, papers, news)
    
    # 发送邮件
    print("📧 发送邮件...")
    success, msg = send_email_with_audio(html_content, TTS_OUTPUT, subject)
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
    
    print("🎉 完成！")


if __name__ == "__main__":
    asyncio.run(main())
