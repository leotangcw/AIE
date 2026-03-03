# CI 测试指南

本文档说明如何在本地运行 CI 测试，以及如何解决常见的 CI 错误。

## 本地测试

在推送代码到 GitHub 之前，建议先在本地运行 CI 测试，确保代码质量。

### Linux / macOS

```bash
# 运行测试脚本
./scripts/test_ci.sh
```

### Windows

```cmd
# 运行测试脚本
scripts\test_ci.bat
```

### 手动测试

如果测试脚本无法运行，可以手动执行各项检查：

```bash
# 1. 安装 flake8
pip install flake8

# 2. 运行代码风格检查
flake8 backend --count --select=E9,F63,F7,F82 --show-source --statistics

# 3. 初始化数据库（可选）
python scripts/init_database.py

# 4. 构建前端（如果修改了前端）
cd frontend
npm install
npm run build
```

## 常见 CI 错误及解决方案

### 1. F821: undefined name

**错误示例**：
```
backend/models/message.py:27:21: F821 undefined name 'Session'
```

**原因**：SQLAlchemy 使用字符串形式的类型注解，flake8 认为是未定义的名称。

**解决方案**：
```python
# 在文件开头添加
from __future__ import annotations
from typing import TYPE_CHECKING

# 使用条件导入
if TYPE_CHECKING:
    from backend.models.session import Session
```

### 2. E501: line too long

**错误示例**：
```
backend/app.py:45:80: E501 line too long (95 > 79 characters)
```

**解决方案**：
- 将长行拆分为多行
- 或在 `.flake8` 中调整 `max-line-length`

### 3. F401: imported but unused

**错误示例**：
```
backend/models/__init__.py:1:1: F401 'backend.models.message' imported but unused
```

**解决方案**：
- 删除未使用的导入
- 或使用 `# noqa: F401` 注释（如果是有意为之）

### 4. E302: expected 2 blank lines

**错误示例**：
```
backend/app.py:10:1: E302 expected 2 blank lines, found 1
```

**解决方案**：
- 在类定义和函数定义前添加两个空行

### 5. W503: line break before binary operator

**说明**：这个警告已在 `.flake8` 中忽略，因为它与 PEP 8 的最新建议冲突。

## flake8 配置

项目根目录的 `.flake8` 文件包含了 flake8 的配置：

```ini
[flake8]
max-line-length = 100
ignore = E203, W503, E501
exclude = .git, __pycache__, .venv, frontend, website, data
max-complexity = 10
```

### 配置说明

- `max-line-length`: 最大行长度设为 100（默认 79）
- `ignore`: 忽略的错误代码
  - `E203`: 冒号前的空格（与 black 冲突）
  - `W503`: 二元运算符前的换行（与 PEP 8 更新冲突）
  - `E501`: 行太长（已通过 max-line-length 控制）
- `exclude`: 排除的目录
- `max-complexity`: 最大圈复杂度

## GitHub Actions 工作流

项目包含两个 CI 工作流：

### 1. ci.yml - 代码质量检查

触发条件：
- 推送到 `main` 或 `dev` 分支
- 创建 Pull Request 到 `main` 分支

检查内容：
- Python 代码风格（flake8）
- 数据库初始化
- 前端构建

### 2. build-desktop.yml - 桌面应用构建

触发条件：
- 推送标签（`v*`）
- 手动触发

构建内容：
- Linux 桌面应用
- Windows 桌面应用
- macOS 桌面应用

## 最佳实践

### 推送前检查清单

- [ ] 运行本地 CI 测试
- [ ] 确保所有测试通过
- [ ] 检查 commit 信息是否符合规范
- [ ] 确认没有敏感信息（API Key、密码等）

### 代码风格建议

1. **使用类型注解**
   ```python
   def process_message(message: str) -> dict:
       ...
   ```

2. **保持函数简洁**
   - 单个函数不超过 50 行
   - 圈复杂度不超过 10

3. **添加文档字符串**
   ```python
   def calculate_score(data: dict) -> float:
       """计算评分
       
       Args:
           data: 输入数据
           
       Returns:
           评分结果
       """
       ...
   ```

4. **使用有意义的变量名**
   ```python
   # 好
   user_count = len(users)
   
   # 不好
   n = len(users)
   ```

## 故障排除

### 本地测试失败但 CI 通过

可能原因：
- 本地环境与 CI 环境不一致
- 依赖版本不同

解决方案：
```bash
# 重新安装依赖
pip install -r requirements.txt --force-reinstall
```

### CI 通过但本地测试失败

可能原因：
- 本地有未提交的文件
- 本地配置文件不同

解决方案：
```bash
# 检查未提交的文件
git status

# 查看差异
git diff
```

### 网络问题导致推送失败

解决方案：
```bash
# 配置代理（如果需要）
git config --global http.proxy socks5://127.0.0.1:1080

# 推送
git push origin main

# 取消代理
git config --global --unset http.proxy
```

## 参考资源

- [flake8 文档](https://flake8.pycqa.org/)
- [PEP 8 风格指南](https://pep8.org/)
- [GitHub Actions 文档](https://docs.github.com/actions)

---

如有问题，欢迎在 [Issues](https://github.com/countbot-ai/CountBot/issues) 中提问。
