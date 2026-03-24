<template>
  <div class="audio-player">
    <button class="play-button" @click="togglePlay">
      <PauseIcon v-if="isPlaying" :size="20" />
      <PlayIcon v-else :size="20" />
    </button>

    <div class="audio-info">
      <div class="audio-name">{{ name }}</div>
      <div class="audio-duration">{{ formatDuration(duration) }}</div>
    </div>

    <div class="audio-waveform">
      <div
        class="waveform-progress"
        :style="{ width: `${progress}%` }"
      />
    </div>

    <audio
      ref="audioRef"
      :src="src"
      @timeupdate="onTimeUpdate"
      @loadedmetadata="onLoaded"
      @ended="onEnded"
      @error="onError"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Play as PlayIcon, Pause as PauseIcon } from 'lucide-vue-next'

const props = defineProps<{
  src: string
  name?: string
}>()

const audioRef = ref<HTMLAudioElement>()
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)

const progress = computed(() => {
  if (duration.value === 0) return 0
  return (currentTime.value / duration.value) * 100
})

function togglePlay() {
  if (!audioRef.value) return

  if (isPlaying.value) {
    audioRef.value.pause()
    isPlaying.value = false
  } else {
    audioRef.value.play()
    isPlaying.value = true
  }
}

function onTimeUpdate() {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
  }
}

function onLoaded() {
  if (audioRef.value) {
    duration.value = audioRef.value.duration
  }
}

function onEnded() {
  isPlaying.value = false
  currentTime.value = 0
}

function onError(e: Event) {
  console.error('Audio error:', e)
  isPlaying.value = false
}

function formatDuration(seconds: number): string {
  if (isNaN(seconds)) return '0:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
</script>

<style scoped>
.audio-player {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--color-bg-secondary, #f5f5f5);
  border-radius: 8px;
  width: 100%;
  max-width: 300px;
}

.play-button {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-primary, #3b82f6);
  color: white;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
}

.play-button:hover {
  background: var(--color-primary-hover, #2563eb);
}

.audio-info {
  flex: 1;
  min-width: 0;
}

.audio-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.audio-duration {
  font-size: 11px;
  color: var(--color-text-secondary, #666);
}

.audio-waveform {
  width: 60px;
  height: 4px;
  background: #ddd;
  border-radius: 2px;
  overflow: hidden;
}

.waveform-progress {
  height: 100%;
  background: var(--color-primary, #3b82f6);
  transition: width 0.1s;
}
</style>
