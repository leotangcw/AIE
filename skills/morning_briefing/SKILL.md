# 🌅 Morning Briefing Skill

## 功能描述
自动生成并发送每日晨报，包含：
- 🌤️ 天气信息（wttr.in API）
- 📰 最新新闻（TechCrunch RSS）
- 📊 arXiv AI 论文速递
- 🗣️ TTS 语音摘要（可选，需配置 sherpa-onnx）

## ✅ 测试状态
- [x] 天气获取
- [x] 论文获取
- [x] 新闻获取
- [x] HTML 生成
- [x] 邮件发送
- [ ] TTS 语音（需下载模型）

## 使用方法
```bash
# 预览 HTML
python3 skills/morning_briefing/generate.py --preview

# 发送邮件
python3 skills/morning_briefing/generate.py --send

# 完整模式（邮件+TTS）
python3 skills/morning_briefing/generate.py --send --tts
```

## 配置项
| 项目 | 值 |
|------|-----|
| 收件邮箱 | tangchengwen@163.com |
| 发件邮箱 | leotangbot@163.com |
| SMTP | smtp.163.com:465 (SSL) |
| 天气城市 | Beijing |
| 新闻源 | TechCrunch RSS |
| 论文源 | arXiv cs.AI |

## 定时任务
```bash
# 每天早上 7:00 发送
crontab -e
0 7 * * * cd /mnt/d/code/AIE_0302/AIE && python3 skills/morning_briefing/generate.py --send
```

## 文件结构
```
skills/morning_briefing/
├── SKILL.md          # 技能说明
├── generate.py       # 主脚本
└── (运行时生成)
    ├── morning_briefing_preview.html  # HTML 预览
    └── morning_briefing.mp3           # TTS 音频（可选）
```

## 依赖
```bash
pip install feedparser requests
```

## TTS 配置（可选）
```bash
# 下载 sherpa-onnx 中文模型
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-zh_CN-huayan-medium.tar.bz2
tar -xjf vits-piper-zh_CN-huayan-medium.tar.bz2

# 修改 generate.py 中的模型路径
```
