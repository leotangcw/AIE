#!/usr/bin/env python3
"""
Arxiv Daily AI Paper Report
Fetches AI-related papers from arxiv API and sends email report
"""

import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime, timedelta
import urllib.parse
import re
import ssl
import time

# Arxiv API configuration
ARXIV_API_URL = "http://export.arxiv.org/api/query"

# AI-related categories
AI_CATEGORIES = [
    "cs.AI",      # Artificial Intelligence
    "cs.LG",      # Machine Learning
    "cs.CL",      # Computation and Language
    "cs.CV",      # Computer Vision
    "cs.NE",      # Neural and Evolutionary Computing
    "stat.ML",    # Machine Learning (Statistics)
]

# Email configuration
import os

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.163.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL", "")

def fetch_arxiv_papers(max_papers=50):
    """Fetch recent AI papers from arxiv API, sorted by submission date"""
    now = datetime.utcnow()
    
    print(f"Fetching papers from arxiv API...")
    print(f"Target: {max_papers} recent AI papers")
    print(f"Categories: {', '.join(AI_CATEGORIES)}")
    
    all_papers = []
    seen_ids = set()
    papers_per_category = max(10, max_papers // len(AI_CATEGORIES))
    
    for category in AI_CATEGORIES:
        # Search by category, sorted by submission date
        search_query = f"cat:{category}"
        encoded_query = urllib.parse.quote(search_query)
        
        # Fetch recent papers sorted by submission date
        api_url = f"{ARXIV_API_URL}?search_query={encoded_query}&start=0&max_results={papers_per_category}&sortBy=submittedDate&sortOrder=descending"
        
        print(f"  Fetching from {category}...")
        feed = feedparser.parse(api_url)
        
        for entry in feed.entries:
            arxiv_id = entry.id.split('/abs/')[-1] if '/abs/' in entry.id else entry.id
            
            if arxiv_id in seen_ids:
                continue
            seen_ids.add(arxiv_id)
            
            # Parse published date
            published_str = entry.published
            try:
                published = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ")
            except:
                try:
                    published = datetime.strptime(published_str, "%Y-%m-%d")
                except:
                    published = now
            
            paper = {
                'title': entry.title,
                'summary': entry.summary,
                'published': entry.published,
                'published_dt': published,
                'updated': entry.updated,
                'link': entry.link,
                'arxiv_id': arxiv_id,
                'categories': [tag.term for tag in entry.tags] if hasattr(entry, 'tags') else [],
                'authors': [author.name for author in entry.authors] if hasattr(entry, 'authors') else []
            }
            all_papers.append(paper)
        
        # Be nice to the API
        time.sleep(0.3)
    
    # Sort all papers by published date (most recent first)
    all_papers.sort(key=lambda x: x['published_dt'], reverse=True)
    
    # Take only the most recent max_papers
    result = all_papers[:max_papers]
    
    print(f"Found {len(result)} unique papers (sorted by date)")
    return result

def analyze_trends(papers):
    """Analyze research trends from the papers"""
    trends = {
        'categories_count': {},
        'keywords': {},
        'total_papers': len(papers)
    }
    
    # Count categories
    for paper in papers:
        for cat in paper['categories']:
            trends['categories_count'][cat] = trends['categories_count'].get(cat, 0) + 1
    
    # Extract common keywords from titles
    common_words = ['learning', 'neural', 'network', 'model', 'transformer', 'diffusion', 
                    'vision', 'language', 'generation', 'optimization', 'attention',
                    'large', 'foundation', 'multimodal', 'reinforcement', 'robot',
                    'agent', 'llm', 'generative', 'deep', 'fine-tuning', 'prompt',
                    'reasoning', 'benchmark', 'evaluation', 'efficient']
    
    for paper in papers:
        title_lower = paper['title'].lower()
        for word in common_words:
            if word in title_lower:
                trends['keywords'][word] = trends['keywords'].get(word, 0) + 1
    
    # Sort by frequency
    trends['top_categories'] = sorted(trends['categories_count'].items(), 
                                       key=lambda x: x[1], reverse=True)[:10]
    trends['top_keywords'] = sorted(trends['keywords'].items(), 
                                     key=lambda x: x[1], reverse=True)[:10]
    
    return trends

def generate_html_report(papers, trends):
    """Generate HTML email content"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Build category stats HTML
    category_html = ""
    for cat, count in trends['top_categories']:
        category_html += f"<tr><td>{cat}</td><td>{count}</td></tr>"
    
    if not category_html:
        category_html = "<tr><td colspan='2'>No data available</td></tr>"
    
    # Build keyword stats HTML
    keyword_html = ""
    for word, count in trends['top_keywords']:
        keyword_html += f"<tr><td>{word}</td><td>{count}</td></tr>"
    
    if not keyword_html:
        keyword_html = "<tr><td colspan='2'>No data available</td></tr>"
    
    # Build papers HTML
    papers_html = ""
    if papers:
        for i, paper in enumerate(papers, 1):
            # Clean summary (remove extra whitespace and limit length)
            summary = re.sub(r'\s+', ' ', paper['summary']).strip()
            summary = summary.replace('\n', ' ')
            if len(summary) > 600:
                summary = summary[:597] + "..."
            
            authors = ", ".join(paper['authors'][:5])
            if len(paper['authors']) > 5:
                authors += f" et al. ({len(paper['authors'])} authors)"
            
            categories = ", ".join(paper['categories'])
            
            papers_html += f"""
            <div class="paper">
                <h3>{i}. <a href="{paper['link']}">{paper['title']}</a></h3>
                <p class="meta">
                    <strong>Authors:</strong> {authors if authors else 'N/A'}<br>
                    <strong>Categories:</strong> {categories if categories else 'N/A'}<br>
                    <strong>Published:</strong> {paper['published']}<br>
                    <strong>arXiv ID:</strong> {paper['arxiv_id']}
                </p>
                <p class="abstract"><strong>Abstract:</strong> {summary}</p>
            </div>
            <hr>
            """
    else:
        papers_html = "<p>No papers found.</p>"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 900px;
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
            h2 {{
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
                margin-top: 30px;
            }}
            h3 {{
                color: #34495e;
                margin-top: 20px;
            }}
            .stats {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 10px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #3498db;
                color: white;
            }}
            tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
            .paper {{
                margin: 20px 0;
                padding: 15px;
                background: #fff;
                border-left: 4px solid #3498db;
            }}
            .paper h3 {{
                margin: 0 0 10px 0;
                color: #2c3e50;
                font-size: 16px;
            }}
            .paper h3 a {{
                color: #667eea;
                text-decoration: none;
            }}
            .paper h3 a:hover {{
                text-decoration: underline;
            }}
            .meta {{
                font-size: 13px;
                color: #666;
                margin: 5px 0;
            }}
            .abstract {{
                font-size: 14px;
                color: #444;
                margin-top: 10px;
                text-align: justify;
                line-height: 1.7;
            }}
            hr {{
                border: none;
                border-top: 1px solid #eee;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 2px solid #3498db;
                color: #666;
                font-size: 12px;
                text-align: center;
            }}
            a {{
                color: #3498db;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .stats-box {{
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
                <h1>🤖 Arxiv Daily AI Paper Report</h1>
                <p>Generated: {now} | Recent AI Papers</p>
            </div>
            
            <div class="stats-box">
                <div class="stat-item">
                    <div class="stat-number">{trends['total_papers']}</div>
                    <div class="stat-label">Papers Found</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(trends['top_categories'])}</div>
                    <div class="stat-label">Categories</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(trends['top_keywords'])}</div>
                    <div class="stat-label">Hot Topics</div>
                </div>
            </div>
            
            <h2>📊 Research Trends</h2>
            <div class="stats">
                <h3>Top Categories</h3>
                <table>
                    <tr><th>Category</th><th>Count</th></tr>
                    {category_html}
                </table>
                
                <h3>Hot Keywords in Titles</h3>
                <table>
                    <tr><th>Keyword</th><th>Frequency</th></tr>
                    {keyword_html}
                </table>
            </div>
            
            <h2>📄 Papers List</h2>
            {papers_html}
            
            <div class="footer">
                <p>This report was automatically generated by Arxiv Daily Bot</p>
                <p>Data source: <a href="https://arxiv.org/">arxiv.org</a></p>
                <p>🤖 AI Paper Report Bot | leotangbot@163.com</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def send_email(html_content):
    """Send HTML email via SMTP"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = Header(f"🤖 Arxiv Daily AI Paper Report - {today}", 'utf-8')
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    
    # Attach HTML content
    html_part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(html_part)
    
    # Send email
    print(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}...")
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("✅ Email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def main():
    print("=" * 60)
    print("Arxiv Daily AI Paper Report Generator")
    print("=" * 60)
    
    # Fetch papers
    papers = fetch_arxiv_papers(max_papers=50)
    
    # Analyze trends
    trends = analyze_trends(papers)
    
    print("\n📊 Trend Analysis:")
    print(f"  Top categories: {trends['top_categories'][:5]}")
    print(f"  Top keywords: {trends['top_keywords'][:5]}")
    
    # Generate HTML report
    html_content = generate_html_report(papers, trends)
    
    # Send email
    success = send_email(html_content)
    
    print("\n" + "=" * 60)
    if success:
        print("Report generation and email delivery completed successfully!")
    else:
        print("Report generated but email delivery failed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
