# AIE Docker 快速开始指南

> 使用 Docker Compose 一键部署 AIE

---

## 📋 快速开始

### 1. 环境要求

- Docker 20.10+
- Docker Compose 2.0+

### 2. 配置环境变量

```bash
# 复制环境变量配置
cp docker/.env.docker.example .env.docker

# 编辑配置（特别是 API 密钥）
# .env.docker
API_KEY=your-api-key-here
SECRET_KEY=your-secret-key
```

### 3. 一键启动

```bash
# Linux/macOS
cd docker
./docker-start.sh -p dev -a up

# Windows
cd docker
docker-start.bat -p dev -a up
```

---

## 🏗️ 环境配置

### 开发环境 (dev)

启动开发环境，包含热重载：

```bash
./docker-start.sh -p dev
```

访问地址：
- 前端：http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档：http://localhost:8000/docs

### CI 环境 (ci)

运行 CI 测试：

```bash
# 运行完整 CI 流程
./docker-start.sh -p ci -a test

# 或手动运行
docker-compose --profile ci up ci-test
```

### 生产环境 (prod)

构建并启动生产环境：

```bash
./docker-start.sh -p prod
```

访问地址：
- 应用：http://localhost

---

## 🔧 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend

# 重启服务
docker-compose restart

# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v

# 构建镜像
docker-compose build

# 重新构建并启动
docker-compose up -d --build
```

---

## 📁 数据持久化

以下数据通过 Docker 卷持久化：

- `postgres_data`: PostgreSQL 数据库
- `redis_data`: Redis 缓存
- `ci_coverage`: CI 测试覆盖报告

查看数据卷：

```bash
docker volume ls | grep aie
```

---

## 🐛 故障排除

### 容器无法启动

```bash
# 查看详细日志
docker-compose logs backend

# 检查端口占用
docker ps
```

### 数据库连接失败

```bash
# 检查数据库是否就绪
docker-compose exec postgres pg_isready
```

---

## 🔗 相关文档

- [环境变量配置](./.env.docker.example)
- [生产部署指南](../deployment.md)
