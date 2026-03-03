# CountBot 文档中心

欢迎来到 CountBot 文档中心，这里提供完整的技术文档、开发指南和最佳实践。

## 文档导航

### 快速开始

- [快速开始指南](quick-start-guide.md) - 5分钟上手 CountBot
- [部署与运维](deployment.md) - 安装、启动、生产部署指南

### 核心概念

- [Agent Loop](agent-loop.md) - ReAct 循环的工作原理
- [记忆系统](memory.md) - 智能记忆的实现机制
- [Cron 调度器](cron.md) - 精确按需唤醒的定时任务系统

### 功能模块

- [渠道系统](channels.md) - 多渠道消息接入配置与内置命令
- [渠道故障排查](channel-troubleshooting.md) - 常见渠道连接问题排查
- [工具系统](tools.md) - 内置工具使用和自定义开发
- [技能系统](skills.md) - 技能插件开发指南
- [远程认证](auth.md) - 零配置安全模型详解

### 配置参考

- [配置手册](configuration-manual.md) - 完整的配置项说明
- [API 参考](api-reference.md) - REST API 和 WebSocket 接口文档

### 开发指南

- [CI 测试](ci-testing.md) - 本地 CI 测试指南

## 按场景查找

### 我想快速体验
1. 查看 [快速开始指南](quick-start-guide.md)
2. 按照步骤安装和启动
3. 配置一个 LLM 提供商即可使用

### 我想了解原理
1. 深入 [Agent Loop](agent-loop.md) 理解核心循环
2. 学习 [记忆系统](memory.md) 的实现机制

### 我想接入消息渠道
1. 查看 [渠道系统](channels.md) 了解支持的渠道
2. 按照文档配置对应渠道的参数
3. 在设置页面启用渠道

### 我想开发自定义功能
1. 阅读 [工具系统](tools.md) 学习如何开发工具
2. 参考 [技能系统](skills.md) 创建技能插件
3. 查看 [API 参考](api-reference.md) 了解接口

### 我想管理定时任务
1. 阅读 [Cron 调度器](cron.md) 了解定时任务系统
2. 通过聊天使用 `cron-manager` 技能创建和管理定时任务（含会话管理）
3. 通过 API 或前端面板进行高级管理

### 我想部署到生产环境
1. 阅读 [部署与运维](deployment.md)
2. 配置 [远程认证](auth.md) 保护安全
3. 参考 [配置手册](configuration-manual.md) 优化配置

## 技术栈

### 后端
- FastAPI - 现代化 Web 框架
- SQLAlchemy 2.0 - 异步 ORM
- LiteLLM - 统一 LLM 接口
- Pydantic v2 - 数据验证

### 前端
- Vue 3 - 渐进式框架
- TypeScript - 类型安全
- Pinia - 状态管理
- Vue I18n - 国际化

> **注意：** 前端源代码正在最后的全力优化中，优化完成后将全量上传。当前仓库中 `frontend/dist/` 为构建后的 HTML 文件，不影响使用。
