# AIE 模型部署指南

> 部署本地 LLM 模型，支持 Ollama、LocalAI 等

---

## 📋 快速开始

### 1. 部署 Ollama 模型

```bash
# 部署默认模型 (qwen2.5:7b)
cd docker
./deploy-model.sh -p ollama

# 部署指定模型
./deploy-model.sh -p ollama -m llama3.2:3b

# 部署多个模型
./deploy-model.sh -p ollama -m "qwen2.5:7b llama3.2:3b"
```

### 2. 查看模型状态

```bash
./deploy-model.sh -a status
```

### 3. 配置 AIE 使用本地模型

编辑 `.env.docker`：

```bash
# 使用 Ollama
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://ollama:11434

# 或使用 LocalAI
LLM_PROVIDER=localai
LLM_MODEL=gpt-3.5-turbo
LOCALAI_BASE_URL=http://localai:8080
```

---

## 🤖 支持的模型提供商

### Ollama (推荐)

| 模型 | 大小 | 说明 |
|------|------|------|
| qwen2.5:7b | 7B | 通义千问，中文支持好 |
| llama3.2:3b | 3B | Llama 轻量版 |
| llama3.2:7b | 7B | Llama 标准版 |
| codellama:7b | 7B | 代码专用 |
| mistral:7b | 7B | Mistral AI |

### LocalAI

兼容 OpenAI API 格式，支持多种开源模型。

### FastChat

支持多模型同时服务，适合企业级部署。

---

## 🔧 高级配置

### GPU 加速

如果有 NVIDIA GPU，自动启用 GPU 加速：

```bash
# 检查 GPU
nvidia-smi

# 查看 Docker 容器 GPU 使用
docker exec aie-ollama nvidia-smi
```

### 模型管理

```bash
# 查看已下载模型
docker exec aie-ollama ollama list

# 拉取新模型
docker exec aie-ollama ollama pull llama3.2:3b

# 删除模型
docker exec aie-ollama ollama rm qwen2.5:7b

# 测试模型
docker exec aie-ollama ollama run qwen2.5:7b '你好'
```

### API 使用

```bash
# Ollama API
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "你好"
}'

# LocalAI API (OpenAI 兼容)
curl http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "gpt-3.5-turbo",
  "messages": [{"role": "user", "content": "你好"}]
}'
```

---

## 📁 数据持久化

模型数据存储在 Docker 卷中：

- `ollama_data`: Ollama 模型
- `localai_models`: LocalAI 模型
- `fastchat_models`: FastChat 模型

查看数据卷大小：

```bash
docker system df -v | grep aie
```

---

## 🐛 故障排除

### 模型下载慢

使用国内镜像：

```bash
# Ollama 镜像
export OLLAMA_DOWNLOAD_URL=https://ollama.com/download
```

### GPU 不可用

确保安装 NVIDIA Container Toolkit：

```bash
# 安装
sudo apt-get install -y nvidia-container-toolkit

# 重启 Docker
sudo systemctl restart docker
```

### 内存不足

使用更小的模型：

```bash
./deploy-model.sh -p ollama -m qwen2.5:1.5b
```

---

## 🔗 相关文档

- [Docker 快速开始](./README.md)
- [环境变量配置](./.env.docker.example)
