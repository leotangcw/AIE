# AIE 项目记忆

## 敏感信息安全规范

### 1. 禁止提交到 GitHub 的内容

以下内容**绝对禁止**提交到代码仓库：

| 类型 | 示例 | 说明 |
|------|------|------|
| API Keys | `sk-sp-xxx`, `OPENAI_API_KEY=xxx` | 所有 Provider 的 API 密钥 |
| SMTP 密码/授权码 | `SENDER_PASSWORD = "xxx"` | 邮件发送密码 |
| 数据库文件 | `*.db`, `*.sqlite` | 可能包含敏感数据 |
| 日志文件 | `*.log`, `audit_*.log` | 可能包含对话历史 |
| 环境配置文件 | `.env` | 包含实际配置 |
| 备份文件 | `*.bak`, `*.backup` | 可能包含旧版敏感数据 |
| 模型文件 | `*.bin`, `*.safetensors` | 版权和大小问题 |

### 2. 正确的配置管理方式

**使用环境变量模板文件 `.env.example`**：

```bash
# 复制模板
cp .env.example .env

# 编辑填入真实值
vim .env
```

`.env.example` 模板内容：
```bash
# API Keys
OPENAI_API_KEY=your_api_key_here
DASHSCOPE_API_KEY=

# 邮件配置
SMTP_SERVER=smtp.example.com
SENDER_EMAIL=your_email@example.com
SENDER_PASSWORD=your_smtp_auth_code
```

**在代码中使用环境变量**：
```python
import os

API_KEY = os.environ.get("OPENAI_API_KEY", "")
SMTP_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
```

### 3. .gitignore 规则

项目根目录的 `.gitignore` 已配置：

```gitignore
# Data - 敏感数据，禁止提交
data/

# Environment
.env
.env.local
.env.*.local

# Logs
*.log
logs/

# Python
__pycache__/
*.py[cod]
*.egg-info/
```

### 4. 提交前检查清单

每次 `git commit` 前执行：

```bash
# 1. 检查暂存的文件
git status

# 2. 确认没有敏感文件
git diff --cached --name-only | grep -E "\.env$|\.db$|\.log$|\.bak$"

# 3. 检查代码中是否有硬编码密钥
grep -rE "password\s*=\s*['\"][^'\"]{8,}['\"]" --include="*.py" .
grep -rE "api_key\s*=\s*['\"][a-zA-Z0-9]{20,}['\"]" --include="*.py" .
```

### 5. 已泄露敏感数据的处理

如果发现敏感信息被误提交：

**步骤 1：立即修改泄露的密钥**
- 在 Provider 控制台删除/禁用泄露的 API Key
- 创建新的 API Key

**步骤 2：清理 GitHub 历史**
```bash
# 使用 BFG Repo-Cleaner（推荐）
java -jar bfg.jar --delete-files "*.bak" --replace-text passwords.txt your-repo.git

# 或使用 git filter-branch
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch sensitive-file.txt' \
  --tag-name-filter cat -- --all
```

**步骤 3：Force push**
```bash
git push origin main --force
```

**步骤 4：通知协作者**
- 协作者需要重新 clone
- 告知泄露的风险

### 6. 本地敏感数据隔离

建议将敏感数据存放在项目外的目录：

```bash
# 创建敏感数据目录（不在项目内）
mkdir -p ~/aie-secrets

# 软链接到项目（可选）
ln -s ~/aie-secrets/.env .env
```

### 7. 数据库中的敏感信息

`data/aie.db` 等数据库文件包含：
- 用户对话历史
- API Keys（用户配置）
- 工具调用记录

**禁止提交数据库文件**，已添加到 `.gitignore`。

### 8. 审计日志

`data/audit_logs/*.log` 包含：
- 工具调用参数
- 对话内容片段
- 用户请求记录

**禁止提交日志文件**，已添加到 `.gitignore`。

---

*本文档由 AIE 自动生成，最后更新：2026-03-23*
