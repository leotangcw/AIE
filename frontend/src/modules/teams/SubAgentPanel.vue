<template>
  <div class="sub-agent-panel">
    <!-- Tab bar -->
    <div class="panel-tabs">
      <button
        class="tab-btn"
        :class="{ active: teamsStore.activeTab === 'running' }"
        @click="teamsStore.activeTab = 'running'"
      >
        运行中
        <span
          v-if="teamsStore.runningAgentCount > 0"
          class="tab-badge"
        >
          {{ teamsStore.runningAgentCount }}
        </span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: teamsStore.activeTab === 'manage' }"
        @click="teamsStore.activeTab = 'manage'"
      >
        管理
      </button>
    </div>

    <!-- Running tab -->
    <div v-show="teamsStore.activeTab === 'running'" class="tab-content running-tab">
      <!-- Workflow header -->
      <div v-if="teamsStore.currentWorkflow" class="workflow-header">
        <span class="mode-badge" :class="`mode-${teamsStore.currentWorkflow.mode}`">
          {{ modeLabel }}
        </span>
        <span class="workflow-name">{{ teamsStore.currentWorkflow.team_name }}</span>
      </div>

      <!-- Agent slots -->
      <div v-if="teamsStore.currentWorkflow && teamsStore.currentWorkflow.agents.length > 0" class="agent-slots">
        <SubAgentSlot
          v-for="agent in teamsStore.currentWorkflow.agents"
          :key="agent.agent_id"
          :agent="agent"
          class="agent-slot-item"
        />
      </div>

      <!-- Empty state -->
      <div v-else class="panel-empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        <p>暂无运行中的工作流</p>
      </div>
    </div>

    <!-- Manage tab -->
    <div v-show="teamsStore.activeTab === 'manage'" class="tab-content manage-tab">
      <TeamManager />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTeamsStore } from '@/store/teams'
import SubAgentSlot from './SubAgentSlot.vue'
import TeamManager from './TeamManager.vue'

const teamsStore = useTeamsStore()

const modeLabels: Record<string, string> = {
  pipeline: 'Pipeline',
  graph: 'Graph',
  council: 'Council',
}

const modeLabel = computed(() => {
  if (!teamsStore.currentWorkflow) return ''
  return modeLabels[teamsStore.currentWorkflow.mode] || teamsStore.currentWorkflow.mode
})
</script>

<style scoped>
.sub-agent-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary, #1a1a2e);
  color: var(--text-primary, #e0e0e0);
  overflow: hidden;
}

/* Tab bar */
.panel-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border-color, #2a2a3a);
  background: var(--bg-secondary, #16162a);
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary, #aaa);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: color 0.15s, background 0.15s;
  position: relative;
}

.tab-btn:hover {
  color: var(--text-primary, #e0e0e0);
  background: rgba(255, 255, 255, 0.03);
}

.tab-btn.active {
  color: var(--accent-color, #4f8ff7);
}

.tab-btn.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 20%;
  right: 20%;
  height: 2px;
  background: var(--accent-color, #4f8ff7);
  border-radius: 1px 1px 0 0;
}

.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  font-size: 10px;
  font-weight: 600;
  background: var(--accent-color, #4f8ff7);
  color: #fff;
  border-radius: 9px;
}

/* Tab content */
.tab-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Running tab */
.running-tab {
  overflow-y: auto;
}

.workflow-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color, #2a2a3a);
  flex-shrink: 0;
}

.mode-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mode-badge.mode-pipeline {
  color: #5cb85c;
  background: rgba(92, 184, 92, 0.15);
}

.mode-badge.mode-graph {
  color: #f0ad4e;
  background: rgba(240, 173, 78, 0.15);
}

.mode-badge.mode-council {
  color: #9b59b6;
  background: rgba(155, 89, 182, 0.15);
}

.workflow-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
}

/* Agent slots container */
.agent-slots {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px;
  overflow-y: auto;
}

.agent-slot-item {
  min-height: 160px;
  max-height: 300px;
  flex: 1;
}

/* Empty state */
.panel-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-tertiary, #666);
}

.panel-empty-state .empty-icon {
  opacity: 0.4;
}

.panel-empty-state p {
  font-size: 13px;
}

/* Manage tab */
.manage-tab {
  overflow-y: auto;
}

/* Scrollbar styling */
.running-tab::-webkit-scrollbar,
.manage-tab::-webkit-scrollbar,
.agent-slots::-webkit-scrollbar {
  width: 4px;
}

.running-tab::-webkit-scrollbar-track,
.manage-tab::-webkit-scrollbar-track,
.agent-slots::-webkit-scrollbar-track {
  background: transparent;
}

.running-tab::-webkit-scrollbar-thumb,
.manage-tab::-webkit-scrollbar-thumb,
.agent-slots::-webkit-scrollbar-thumb {
  background: var(--border-color, #2a2a3a);
  border-radius: 2px;
}
</style>
