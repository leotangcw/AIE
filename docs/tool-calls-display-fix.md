# 工具调用显示修复总结

## 问题描述

工具调用（tool calls）在页面刷新后消失，即使数据已存储在数据库中。

## 根本原因

前端 `ChatWindow.vue` 在加载消息时存在数据覆盖问题：

1. API 正确返回了包含 `tool_calls` 的消息数据
2. 前端加载消息后，又查询 `/api/tools/conversations` 作为备用数据源
3. **关键问题**：备用数据无条件覆盖了 API 返回的 `tool_calls`

```typescript
// 问题代码
if (byMsgId.has(mid)) {
  msg.toolCalls = byMsgId.get(mid)  // ❌ 直接覆盖
}
```

## 修复方案

### 后端修改

1. **API 返回工具调用** (`backend/api/chat.py`)
   - `get_session_messages` 查询 `tool_conversations` 表
   - 返回 `MessageResponse` 包含 `tool_calls` 字段

2. **统一记录机制** (`backend/modules/tools/registry.py`)
   - `ToolRegistry.execute()` 自动记录工具调用
   - 主 agent 循环禁用自动记录（使用自定义逻辑）
   - 子 agent 和 API 调用自动记录

### 前端修改

**`frontend/src/modules/chat/ChatWindow.vue`**

修改 `loadSessionMessages` 函数，只在消息没有 `toolCalls` 时才使用备用数据：

```typescript
// 修复后的代码
if (byMsgId.has(mid) && (!msg.toolCalls || msg.toolCalls.length === 0)) {
  msg.toolCalls = byMsgId.get(mid)  // ✅ 仅在需要时填充
}
```

同样的逻辑应用于时间戳关联的旧数据兼容：

```typescript
const assistantMsgs = messages.value
  .map((msg, idx) => ({ msg, idx }))
  .filter(item => item.msg.role === 'assistant' && (!item.msg.toolCalls || item.msg.toolCalls.length === 0))
```

## 数据流程

```
数据库 → API (返回 tool_calls) → Store → ChatWindow → MessageItem → UI 显示
         ↓
    备用查询（仅用于旧数据兼容）
```

## 修改文件

### 后端
- `backend/api/chat.py` - API 返回工具调用
- `backend/modules/tools/registry.py` - 统一记录机制
- `backend/modules/agent/loop.py` - 禁用主循环自动记录

### 前端
- `frontend/src/modules/chat/ChatWindow.vue` - 修复数据覆盖问题
- `frontend/src/api/endpoints.ts` - 类型定义
- `frontend/src/store/chat.ts` - 数据传递

## 测试验证

1. 发送包含工具调用的消息
2. 刷新页面
3. 确认工具调用正确显示

## 兼容性

- 新数据：优先使用 API 返回的 `tool_calls`
- 旧数据：通过 `message_id` 或时间戳关联备用数据
- 向后兼容：不影响现有功能

## 相关 Issue

修复了工具调用在页面刷新后消失的问题。
