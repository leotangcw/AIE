# 知识检索系统 - 界面合并实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 合并"知识库"和"知识中枢"为统一的"知识检索系统"入口，在主侧边栏显示，移除设置中的重复tab

**Architecture:** 创建新的统一组件 KnowledgeSearchSystem.vue，包含知识源管理 + 检索配置，更新导航和翻译

**Tech Stack:** Vue 3 + TypeScript + vue-i18n

---

### Task 1: 创建统一组件 KnowledgeSearchSystem.vue

**Files:**
- Create: `frontend/src/modules/knowledge/KnowledgeSearchSystem.vue`

**Step 1: 创建组件文件**

```vue
<template>
  <div class="knowledge-search-system">
    <!-- 头部 -->
    <div class="section-header">
      <h2>{{ $t('knowledgeSearch.title') }}</h2>
      <p>{{ $t('knowledgeSearch.description') }}</p>
    </div>

    <!-- 知识源管理 -->
    <div class="config-section">
      <h3>{{ $t('knowledgeSearch.sourceManagement') }}</h3>
      <!-- 源列表和创建对话框 -->
    </div>

    <!-- 检索配置 -->
    <div class="config-section">
      <h3>{{ $t('knowledgeSearch.retrieveConfig') }}</h3>
      <!-- 处理模式、LLM配置、缓存配置 -->
    </div>

    <!-- 测试检索 -->
    <div class="config-section">
      <h3>{{ $t('knowledgeSearch.testRetrieve') }}</h3>
      <!-- 检索测试表单和结果 -->
    </div>
  </div>
</template>
```

**Step 2: 实现知识源管理功能**

从现有 KnowledgeConfig.vue 复制源列表和创建对话框逻辑

**Step 3: 实现检索配置功能**

从现有 KnowledgeHubConfig.vue 复制处理模式、LLM、缓存配置

**Step 4: 实现测试检索功能**

合并两边的检索测试逻辑

---

### Task 2: 创建知识检索图标

**Files:**
- Modify: `frontend/src/modules/chat/ChatWindow.vue`

**Step 1: 创建组合图标组件**

在 ChatWindow.vue 中使用 BookOpen 图标 + Search 图标叠加

```vue
<div class="knowledge-icon">
  <BookOpen :size="20" />
  <Search :size="12" class="search-badge" />
</div>
```

---

### Task 3: 更新侧边栏导航

**Files:**
- Modify: `frontend/src/modules/chat/ChatWindow.vue:导航配置`
- Modify: `frontend/src/i18n/locales/zh-CN.json`
- Modify: `frontend/src/i18n/locales/en-US.json`

**Step 1: 更新导航配置**

将原 knowledge 和 knowledge_hub 替换为单一的 knowledge_search

**Step 2: 添加翻译**

```json
"knowledgeSearch": {
  "title": "知识检索系统",
  "description": "统一的企业知识检索和管理平台"
}
```

---

### Task 4: 移除设置中的重复tab

**Files:**
- Modify: `frontend/src/modules/settings/SettingsPanel.vue`

**Step 1: 移除知识库和知识中枢tab**

删除 knowledge 和 knowledge_hub 两个 tab

---

### Task 5: 添加翻译文本

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.json`
- Modify: `frontend/src/i18n/locales/en-US.json`

**Step 1: 添加统一组件翻译**

复制 knowledgeHubConfig 和 knowledge 的翻译到一个新的 knowledgeSearch key

---

### Task 6: 构建和测试

**Step 1: 构建前端**

```bash
cd frontend && npm run build
```

**Step 2: 验证**

- 主侧边栏显示新的"知识检索系统"图标
- 点击进入后能看到知识源管理、检索配置、测试检索三个部分
- 设置页面不再有"知识库"和"知识中枢"tab
