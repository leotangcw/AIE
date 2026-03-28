<template>
  <div class="advanced-config">
    <div class="section-header">
      <h3 class="section-title">
        {{ $t('settings.advanced.title') }}
      </h3>
      <p class="section-desc">
        {{ $t('settings.advanced.description') }}
      </p>
    </div>

    <!-- Sub-tabs for different advanced settings -->
    <div class="advanced-tabs">
      <div class="tab-buttons">
        <button
          class="tab-btn"
          :class="{ active: activeSubTab === 'subAgent' }"
          @click="activeSubTab = 'subAgent'"
        >
          <BotIcon :size="18" />
          <span>{{ $t('settings.advanced.subAgent') }}</span>
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeSubTab === 'embedder' }"
          @click="activeSubTab = 'embedder'"
        >
          <BinaryIcon :size="18" />
          <span>{{ $t('settings.advanced.embedder') }}</span>
        </button>
      </div>

      <div class="tab-content">
        <SubAgentConfig v-if="activeSubTab === 'subAgent'" />
        <EmbedderConfig v-else-if="activeSubTab === 'embedder'" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Bot as BotIcon, Binary as BinaryIcon } from 'lucide-vue-next'
import SubAgentConfig from './SubAgentConfig.vue'
import EmbedderConfig from './EmbedderConfig.vue'

const activeSubTab = ref<'subAgent' | 'embedder'>('subAgent')
</script>

<style scoped>
.advanced-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.section-header {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.section-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
}

.advanced-tabs {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.tab-buttons {
  display: flex;
  gap: var(--spacing-sm);
  border-bottom: 2px solid var(--border-color);
  padding-bottom: 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
}

.tab-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.tab-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-content {
  width: 100%;
}
</style>
