<template>
  <div class="video-player">
    <template v-if="hasError">
      <div class="video-error">
        <span class="error-text">视频加载失败</span>
        <button class="retry-btn" @click="retryVideo">重试</button>
        <a
          v-if="resolvedSrc"
          class="download-btn-link"
          :href="resolvedSrc"
          download
          @click.stop
        >
          <DownloadIcon :size="16" />
        </a>
      </div>
    </template>
    <template v-else>
      <div class="video-container">
        <video
          :key="errorKey"
          :src="resolvedSrc"
          controls
          preload="metadata"
          :poster="poster"
          @error="handleError"
          class="video-element"
        />
        <button class="video-download-btn" title="下载视频" @click="downloadVideo">
          <DownloadIcon :size="16" />
        </button>
      </div>
    </template>
    <div class="video-name" v-if="name">{{ name }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download as DownloadIcon } from 'lucide-vue-next'

const props = defineProps<{
  src: string
  name?: string
  poster?: string
}>()

const hasError = ref(false)
const errorKey = ref(0)

const resolvedSrc = computed(() => {
  if (!props.src) return ''
  // 如果已经是 /api/files/ 开头或完整 URL，直接返回
  if (props.src.startsWith('/api/files/')) return props.src
  if (props.src.startsWith('http://') || props.src.startsWith('https://')) return props.src
  // 其他相对路径添加前缀
  return `/api/files/${props.src}`
})

function handleError(e: Event) {
  console.error('Video error:', e)
  hasError.value = true
}

function retryVideo() {
  hasError.value = false
  errorKey.value++
}

function downloadVideo() {
  const src = resolvedSrc.value
  if (!src) return
  const a = document.createElement('a')
  a.href = src
  a.download = props.name || 'video'
  a.click()
}
</script>

<style scoped>
.video-player {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  max-width: 480px;
}

.video-container {
  position: relative;
}

.video-element {
  width: 100%;
  border-radius: 8px;
  background: #000;
}

.video-download-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.5);
  border: none;
  color: white;
  padding: 6px;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.video-container:hover .video-download-btn {
  opacity: 1;
}

.video-download-btn:hover {
  background: rgba(0, 0, 0, 0.7);
}

.video-error {
  width: 100%;
  height: 120px;
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  background: var(--color-bg-secondary, #f5f5f5);
  border-radius: 8px;
  border: 1px dashed #ccc;
}

.error-text {
  font-size: 12px;
  color: var(--color-text-secondary, #999);
}

.retry-btn {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #ddd;
  background: white;
  cursor: pointer;
  color: var(--color-text, #333);
}

.retry-btn:hover {
  background: #f0f0f0;
}

.download-btn-link {
  color: var(--color-text-secondary, #999);
  padding: 4px;
}

.video-name {
  font-size: 12px;
  color: var(--color-text-secondary, #666);
  padding: 0 2px;
}
</style>
