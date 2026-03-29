<template>
  <div class="team-manager">
    <!-- Header -->
    <div class="manager-header">
      <h3 class="manager-title">团队模板</h3>
      <button class="create-btn" @click="openEditor(null)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        创建团队
      </button>
    </div>

    <!-- Team list -->
    <div v-if="teamsStore.teams.length > 0" class="team-list">
      <div
        v-for="team in teamsStore.teams"
        :key="team.id"
        class="team-card"
      >
        <div class="team-card-header">
          <div class="team-card-info">
            <span class="team-name">{{ team.name }}</span>
            <span class="mode-badge" :class="`mode-${team.mode}`">
              {{ modeLabels[team.mode] || team.mode }}
            </span>
          </div>
          <div class="team-card-actions">
            <button
              class="icon-btn start"
              :class="{ disabled: !team.is_active }"
              :title="team.is_active ? `启动 ${team.name}` : '请先启用团队'"
              @click="handleStartTeam(team)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </button>
            <button
              class="icon-btn"
              :class="{ active: team.is_active }"
              :title="team.is_active ? '停用' : '启用'"
              @click="handleToggleActive(team.id)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
            </button>
            <button
              class="icon-btn"
              title="编辑"
              @click="openEditor(team)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button
              class="icon-btn danger"
              title="删除"
              @click="handleDelete(team.id, team.name)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>

        <!-- Members -->
        <div class="team-members">
          <span class="member-count">{{ team.agents.length }} 个成员</span>
          <div class="member-chips">
            <span
              v-for="agent in team.agents"
              :key="agent.id"
              class="member-chip"
            >
              {{ agent.role }}
              <span v-if="team.mode === 'graph' && agent.depends_on && agent.depends_on.length > 0" class="dep-hint" :title="`依赖: ${agent.depends_on.join(', ')}`">
                ({{ agent.depends_on.length }})
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="manager-empty">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
      <p>暂无团队模板</p>
      <button class="create-btn" @click="openEditor(null)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        创建第一个团队
      </button>
    </div>

    <!-- Team Editor Modal -->
    <TeamEditor
      v-if="editingTeam !== undefined"
      :team="editingTeam"
      @close="closeEditor"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTeamsStore } from '@/store/teams'
import type { AgentTeamResponse } from '@/api/agentTeams'
import TeamEditor from './TeamEditor.vue'

const teamsStore = useTeamsStore()

const editingTeam = ref<AgentTeamResponse | null | undefined>(undefined)

const modeLabels: Record<string, string> = {
  pipeline: 'Pipeline',
  graph: 'Graph',
  council: 'Council',
}

function openEditor(team: AgentTeamResponse | null) {
  editingTeam.value = team
}

function closeEditor() {
  editingTeam.value = undefined
}

function onSaved() {
  closeEditor()
}

async function handleToggleActive(id: string) {
  await teamsStore.toggleTeamActive(id)
}

function handleStartTeam(team: AgentTeamResponse) {
  if (!team.is_active) return
  teamsStore.requestChatInput(`@${team.name} `)
}

async function handleDelete(id: string, name: string) {
  if (confirm(`确定要删除团队 "${name}" 吗？此操作不可撤销。`)) {
    await teamsStore.deleteTeam(id)
  }
}
</script>

<style scoped>
.team-manager {
  padding: 12px;
}

/* Header */
.manager-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.manager-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  margin: 0;
}

.create-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid var(--accent-color, #4f8ff7);
  border-radius: 6px;
  background: transparent;
  color: var(--accent-color, #4f8ff7);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.create-btn:hover {
  background: var(--accent-color, #4f8ff7);
  color: #fff;
}

/* Team list */
.team-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.team-card {
  background: var(--bg-secondary, #16162a);
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 8px;
  padding: 10px 12px;
  transition: border-color 0.15s;
}

.team-card:hover {
  border-color: rgba(79, 143, 247, 0.3);
}

.team-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.team-card-info {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

.team-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mode-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
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

/* Card actions */
.team-card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary, #888);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.icon-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary, #e0e0e0);
}

.icon-btn.active {
  color: var(--accent-color, #4f8ff7);
}

.icon-btn.start {
  color: #5cb85c;
}

.icon-btn.start:hover:not(.disabled) {
  color: #5cb85c;
  background: rgba(92, 184, 92, 0.12);
}

.icon-btn.start.disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.icon-btn.danger:hover {
  color: #d9534f;
  background: rgba(217, 83, 79, 0.1);
}

/* Members section */
.team-members {
  margin-top: 8px;
}

.member-count {
  font-size: 11px;
  color: var(--text-tertiary, #888);
  display: block;
  margin-bottom: 6px;
}

.member-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.member-chip {
  font-size: 11px;
  color: var(--text-secondary, #aaa);
  background: rgba(255, 255, 255, 0.04);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-color, #2a2a3a);
}

.dep-hint {
  color: var(--text-tertiary, #666);
  font-size: 10px;
}

/* Empty state */
.manager-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--text-tertiary, #666);
}

.manager-empty svg {
  opacity: 0.4;
}

.manager-empty p {
  font-size: 13px;
  margin: 0;
}
</style>
