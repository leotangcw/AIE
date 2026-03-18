# 前端架构设计

**版本**: v1.0
**更新日期**: 2026-03-08

---

## 1. 前端概述

AIE 前端采用 Vue 3 + TypeScript 技术栈，提供现代化的用户界面。

### 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.x | 核心框架 |
| TypeScript | 5.x | 类型系统 |
| Vite | 5.x | 构建工具 |
| Pinia | 2.x | 状态管理 |
| Vue Router | 4.x | 路由管理 |
| Vue I18n | 9.x | 国际化 |

---

## 2. 目录结构

```
frontend/
├── src/
│   ├── main.ts                 # 应用入口
│   ├── App.vue                 # 根组件
│   ├── env.d.ts                # 环境类型定义
│   │
│   ├── api/                    # API 客户端
│   │ ├── client.ts             # Axios 客户端
│   │ ├── endpoints.ts          # API 端点定义
│   │ ├── websocket.ts          # WebSocket 客户端
│   │ └── index.ts              # 统一导出
│   │
│   ├── components/             # 通用组件
│   │ ├── common/               # 通用 UI 组件
│   │ └── layout/               # 布局组件
│   │
│   ├── modules/                # 业务模块
│   │ ├── chat/                 # 聊天模块
│   │ ├── settings/             # 设置模块
│   │ ├── scheduler/            # 调度模块
│   │ ├── memory/               # 记忆模块
│   │ ├── skills/               # 技能模块
│   │ ├── tools/                # 工具模块
│   │ ├── system/               # 系统模块
│   │ └── experience/           # 经验模块
│   │
│   ├── store/                  # Pinia Stores
│   │ ├── chat.ts               # 聊天 Store
│   │ ├── settings.ts           # 设置 Store
│   │ ├── tools.ts              # 工具 Store
│   │ └── ...
│   │
│   ├── router/                 # 路由配置
│   │ └── index.ts
│   │
│   ├── i18n/                   # 国际化配置
│   │ └── locales/
│   │
│   ├── composables/            # 组合式 API
│   │ └── ...
│   │
│   ├── utils/                  # 工具函数
│   │ └── ...
│   │
│   ├── types/                  # 类型定义
│   │ └── ...
│   │
│   └── assets/                 # 静态资源
│       ├── css/
│       └── images/
│
├── dist/                       # 构建产物
├── public/                     # 公共文件
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## 3. 核心模块设计

### 3.1 Chat 模块

**路径**: `src/modules/chat/`

#### 文件结构

```
chat/
├── ChatWindow.vue          # 聊天窗口主组件
├── MessageList.vue         # 消息列表
├── MessageItem.vue         # 消息项
├── SessionPanel.vue        # 会话面板
└── TimelinePanel.vue       # 时间线面板
```

#### ChatWindow.vue

**职责**: 聊天界面主容器，集成消息输入、显示和发送功能

**核心功能**:
- 消息输入框 (支持多行、快捷命令)
- 消息列表展示
- 流式消息接收
- 工具调用展示
- 会话管理

```typescript
// 核心状态
const state = reactive({
  sessions: [],
  currentSessionId: null,
  messages: [],
  isSending: false,
  isStreaming: false,
})

// 核心方法
async function sendMessage(content: string) {
  // 1. 添加用户消息到列表
  // 2. 通过 WebSocket 发送
  // 3. 监听流式响应
  // 4. 更新 AI 消息
}

async function loadSession(sessionId: string) {
  // 加载会话历史
}

async function createNewSession() {
  // 创建新会话
}
```

#### MessageItem.vue

**职责**: 单条消息展示组件

**支持的消息类型**:
- 文本消息
- 工具调用消息 (带进度展示)
- 系统消息
- 错误消息

```vue
<template>
  <div :class="['message', message.role]">
    <div class="message-header">
      <span class="sender">{{ senderName }}</span>
      <span class="time">{{ formatTime(message.timestamp) }}</span>
    </div>
    <div class="message-content">
      <!-- 文本内容 -->
      <div v-if="message.type === 'text'" v-html="formattedContent"></div>

      <!-- 工具调用 -->
      <div v-if="message.type === 'tool_call'" class="tool-call">
        <ToolCallViewer :tool-call="message.toolCall" />
      </div>
    </div>
  </div>
</template>
```

### 3.2 Settings 模块

**路径**: `src/modules/settings/`

#### 文件结构

```
settings/
├── SettingsPanel.vue       # 设置面板主组件
├── ModelConfig.vue         # 模型配置
├── ProviderConfig.vue      # 提供商配置
├── PersonaConfig.vue       # 角色配置
├── PersonalityEditor.vue   # 性格编辑器
├── ChannelsConfig.vue      # 渠道配置
├── SecurityConfig.vue      # 安全配置
├── RulesConfig.vue         # 规则配置
├── KnowledgeConfig.vue     # 知识库配置
├── WorkspaceConfig.vue     # 工作区配置
└── SettingsPanel_styles.css
```

#### SettingsPanel.vue

**职责**: 设置模块主容器，提供 Tab 式配置界面

```vue
<template>
  <div class="settings-panel">
    <Tabs v-model="activeTab">
      <Tab name="model" label="模型配置">
        <ModelConfig />
      </Tab>
      <Tab name="provider" label="提供商配置">
        <ProviderConfig />
      </Tab>
      <Tab name="persona" label="角色配置">
        <PersonaConfig />
      </Tab>
      <Tab name="channels" label="渠道配置">
        <ChannelsConfig />
      </Tab>
      <Tab name="security" label="安全配置">
        <SecurityConfig />
      </Tab>
      <!-- 更多 Tab... -->
    </Tabs>
  </div>
</template>
```

#### 配置组件通用模式

```typescript
// 每个配置组件都遵循类似模式
const settingsStore = useSettingsStore()

const localConfig = ref({})

async function loadConfig() {
  localConfig.value = await settingsStore.getConfig()
}

async function saveConfig() {
  await settingsStore.updateConfig(localConfig.value)
}

async function resetConfig() {
  localConfig.value = await settingsStore.resetConfig()
}
```

### 3.3 Scheduler 模块

**路径**: `src/modules/scheduler/`

#### 功能
- 定时任务列表
- 创建/编辑/删除任务
- 任务执行历史
- Cron 表达式生成器

### 3.4 Memory 模块

**路径**: `src/modules/memory/`

#### 功能
- 记忆列表展示
- 记忆搜索
- 记忆添加/删除
- 记忆重要性管理

### 3.5 Skills 模块

**路径**: `src/modules/skills/`

#### 功能
- 技能列表
- 技能编辑器
- 技能导入/导出
- 技能应用历史

---

## 4. API 客户端设计

**路径**: `src/api/`

### 4.1 Axios 客户端

**文件**: `client.ts`

```typescript
import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器
apiClient.interceptors.request.use(config => {
  // 添加认证 token
  const token = localStorage.getItem('AIE_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器
apiClient.interceptors.response.use(
  response => response,
  error => {
    // 错误处理
    if (error.response?.status === 401) {
      // 未授权，跳转登录
    }
    return Promise.reject(error)
  }
)
```

### 4.2 API 端点

**文件**: `endpoints.ts`

```typescript
// Chat API
export const chatAPI = {
  getSessions: () => apiClient.get<Session[]>('/chat/sessions'),
  createSession: (data: CreateSessionRequest) =>
    apiClient.post<Session>('/chat/sessions', data),
  deleteSession: (id: string) =>
    apiClient.delete(`/chat/sessions/${id}`),
  getMessages: (sessionId: string) =>
    apiClient.get<Message[]>(`/chat/sessions/${sessionId}/messages`),
  sendMessage: (data: SendMessageRequest) =>
    apiClient.post('/chat/send', data),
}

// Settings API
export const settingsAPI = {
  getConfig: () => apiClient.get<Settings>('/settings'),
  updateConfig: (config: Settings) =>
    apiClient.put('/settings', config),
  resetConfig: () => apiClient.post('/settings/reset'),
}

// Tools API
export const toolsAPI = {
  executeTool: (data: ExecuteToolRequest) =>
    apiClient.post('/tools/execute', data),
  listTools: () => apiClient.get('/tools/list'),
}

// Cron API
export const cronAPI = {
  getJobs: () => apiClient.get<CronJob[]>('/cron/jobs'),
  createJob: (data: CreateCronJobRequest) =>
    apiClient.post('/cron/jobs', data),
  updateJob: (id: string, data: UpdateCronJobRequest) =>
    apiClient.put(`/cron/jobs/${id}`, data),
  deleteJob: (id: string) =>
    apiClient.delete(`/cron/jobs/${id}`),
  triggerJob: (id: string) =>
    apiClient.post(`/cron/jobs/${id}/trigger`),
}
```

### 4.3 WebSocket 客户端

**文件**: `websocket.ts`

```typescript
class WebSocketClient {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5

  connect() {
    const token = localStorage.getItem('AIE_token')
    this.ws = new WebSocket(`ws://localhost:8000/ws/chat?token=${token}`)

    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
    }

    this.ws.onclose = () => {
      console.log('WebSocket closed')
      this.reconnect()
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      this.handleMessage(data)
    }
  }

  private reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      setTimeout(() => this.connect(), 1000 * this.reconnectAttempts)
    }
  }

  sendMessage(type: string, data: any) {
    this.ws?.send(JSON.stringify({ type, data }))
  }

  on(event: string, callback: (data: any) => void) {
    // 事件订阅
  }
}

export const wsClient = new WebSocketClient()
```

---

## 5. Store 设计

### 5.1 Chat Store

```typescript
import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: [] as Session[],
    currentSessionId: null as string | null,
    messages: [] as Message[],
    isStreaming: false,
  }),

  getters: {
    currentSession: (state) =>
      state.sessions.find(s => s.id === state.currentSessionId),
  },

  actions: {
    async loadSessions() {
      const response = await chatAPI.getSessions()
      this.sessions = response.data
    },

    async createSession(name: string) {
      const response = await chatAPI.createSession({ name })
      this.sessions.push(response.data)
      return response.data
    },

    async loadMessages(sessionId: string) {
      const response = await chatAPI.getMessages(sessionId)
      this.messages = response.data
    },

    async sendMessage(content: string) {
      // 添加用户消息
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content,
        timestamp: new Date(),
      }
      this.messages.push(userMessage)

      // 创建占位 AI 消息
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      }
      this.messages.push(aiMessage)

      // 通过 WebSocket 发送
      wsClient.sendMessage('send_message', {
        session_id: this.currentSessionId,
        content,
      })
    },

    handleStreamChunk(chunk: string) {
      const lastMessage = this.messages[this.messages.length - 1]
      if (lastMessage && lastMessage.isStreaming) {
        lastMessage.content += chunk
      }
    },

    handleStreamDone() {
      const lastMessage = this.messages[this.messages.length - 1]
      if (lastMessage) {
        lastMessage.isStreaming = false
      }
    },
  },
})
```

### 5.2 Settings Store

```typescript
export const useSettingsStore = defineStore('settings', {
  state: () => ({
    config: null as Settings | null,
    isLoading: false,
  }),

  actions: {
    async loadConfig() {
      this.isLoading = true
      try {
        const response = await settingsAPI.getConfig()
        this.config = response.data
      } finally {
        this.isLoading = false
      }
    },

    async updateConfig(config: Settings) {
      await settingsAPI.updateConfig(config)
      this.config = config
    },
  },
})
```

---

## 6. 类型定义

### 6.1 核心类型

**路径**: `src/types/`

```typescript
// 会话
export interface Session {
  id: string
  name: string
  created_at: string
  updated_at: string
}

// 消息
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  isStreaming?: boolean
  toolCalls?: ToolCall[]
}

// 工具调用
export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, any>
  result?: string
  status?: 'pending' | 'success' | 'error'
}

// 设置
export interface Settings {
  model: ModelConfig
  providers: Record<string, ProviderConfig>
  channels: ChannelsConfig
  security: SecurityConfig
  persona: PersonaConfig
}

// 定时任务
export interface CronJob {
  id: string
  name: string
  cron_expression: string
  message: string
  channel: string
  chat_id: string
  enabled: boolean
  next_run?: string
}
```

---

## 7. 路由配置

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/chat',
  },
  {
    path: '/chat',
    component: () => import('@/modules/chat/ChatWindow.vue'),
  },
  {
    path: '/settings',
    component: () => import('@/modules/settings/SettingsPanel.vue'),
  },
  {
    path: '/scheduler',
    component: () => import('@/modules/scheduler/SchedulerPanel.vue'),
  },
  {
    path: '/memory',
    component: () => import('@/modules/memory/MemoryPanel.vue'),
  },
  {
    path: '/skills',
    component: () => import('@/modules/skills/SkillsPanel.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
```

---

## 8. 样式系统

### 8.1 CSS 变量

```css
:root {
  /* 颜色 */
  --primary-color: #1890ff;
  --success-color: #52c41a;
  --warning-color: #faad14;
  --error-color: #f5222d;

  /* 背景色 */
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;

  /* 文字颜色 */
  --text-primary: #333333;
  --text-secondary: #666666;
  --text-disabled: #999999;

  /* 边框 */
  --border-color: #d9d9d9;

  /* 圆角 */
  --border-radius: 4px;

  /* 阴影 */
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 暗色主题 */
.dark-theme {
  --bg-primary: #141414;
  --bg-secondary: #1f1f1f;
  --text-primary: #ffffff;
  --text-secondary: #cccccc;
  --border-color: #434343;
}
```

---

## 9. 待办事项 (TODO)

### 高优先级
- [ ] 完善错误边界处理
- [ ] 添加加载骨架屏
- [ ] 实现响应式布局

### 中优先级
- [ ] 添加动画效果
- [ ] 优化长列表性能
- [ ] 实现离线支持

### 低优先级
- [ ] PWA 支持
- [ ] 桌面端优化
- [ ] 更多主题
