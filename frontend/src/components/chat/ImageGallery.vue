<template>
  <div class="image-gallery">
    <div
      v-for="(image, index) in images"
      :key="index"
      class="image-item"
    >
      <template v-if="errorImages.has(index)">
        <div class="image-error">
          <span class="error-text">图片加载失败</span>
          <button class="retry-btn" @click="retryImage(index)">重试</button>
          <a
            v-if="getImageSrc(image)"
            class="download-btn"
            :href="getImageSrc(image)"
            download
            @click.stop
          >
            <DownloadIcon :size="14" />
          </a>
        </div>
      </template>
      <template v-else>
        <img
          :src="getImageSrc(image)"
          :alt="image.alt || `Image ${index + 1}`"
          class="gallery-image"
          @click="handleImageClick(image)"
          @error="errorImages.add(index)"
        />
        <div v-if="image.caption" class="image-caption">
          {{ image.caption }}
        </div>
        <button
          class="image-download-btn"
          :href="getImageSrc(image)"
          title="下载图片"
          @click.stop="downloadImage(image)"
        >
          <DownloadIcon :size="14" />
        </button>
      </template>
    </div>

    <!-- 图片预览弹窗 -->
    <Teleport to="body">
      <div
        v-if="previewVisible"
        class="image-preview-modal"
        @click.self="closePreview"
      >
        <button class="preview-close" @click="closePreview">
          <XIcon :size="24" />
        </button>
        <a
          v-if="previewSrc"
          class="preview-download"
          :href="previewSrc"
          download
          title="下载图片"
          @click.stop
        >
          <DownloadIcon :size="20" />
        </a>
        <img
          :src="previewSrc"
          alt="Preview"
          class="preview-image"
        />
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { X as XIcon, Download as DownloadIcon } from 'lucide-vue-next'

interface GalleryImage {
  src: string
  alt?: string
  caption?: string
}

const props = defineProps<{
  images: GalleryImage[]
}>()

const previewVisible = ref(false)
const previewSrc = ref('')
const errorImages = ref(new Set<number>())

function getImageSrc(image: GalleryImage): string {
  // 如果已经是完整 URL 或 data URL，直接返回
  if (image.src.startsWith('http') || image.src.startsWith('data:')) {
    return image.src
  }
  // 如果已经是 /api/files/ 开头，直接返回（后端已构建完整路径）
  if (image.src.startsWith('/api/files/')) {
    return image.src
  }
  // 如果是相对路径，添加前缀
  return `/api/files/${image.src}`
}

function handleImageClick(image: GalleryImage) {
  previewSrc.value = getImageSrc(image)
  previewVisible.value = true
}

function closePreview() {
  previewVisible.value = false
  previewSrc.value = ''
}

function retryImage(index: number) {
  errorImages.value.delete(index)
  // 触发 Vue 响应式更新
  errorImages.value = new Set(errorImages.value)
}

function downloadImage(image: GalleryImage) {
  const src = getImageSrc(image)
  const a = document.createElement('a')
  a.href = src
  a.download = image.alt || 'image'
  a.click()
}
</script>

<style scoped>
.image-gallery {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
}

.image-item {
  position: relative;
  max-width: 200px;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}

.image-item:hover {
  transform: scale(1.02);
}

.gallery-image {
  width: 100%;
  height: auto;
  display: block;
  object-fit: cover;
}

.image-error {
  width: 200px;
  height: 100px;
  display: flex;
  align-items: center;
  gap: 6px;
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

.image-download-btn,
.image-caption {
  position: absolute;
}

.image-caption {
  bottom: 0;
  left: 0;
  right: 0;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 12px;
  text-align: center;
}

.image-download-btn {
  top: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.5);
  border: none;
  color: white;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.image-item:hover .image-download-btn {
  opacity: 1;
}

.image-download-btn:hover {
  background: rgba(0, 0, 0, 0.7);
}

.download-btn {
  color: var(--color-text-secondary, #999);
  padding: 2px;
}

.image-preview-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.preview-close {
  position: absolute;
  top: 20px;
  right: 20px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: white;
  padding: 8px;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.2s;
}

.preview-close:hover {
  background: rgba(255, 255, 255, 0.2);
}

.preview-download {
  position: absolute;
  top: 20px;
  right: 60px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: white;
  padding: 8px;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.2s;
}

.preview-download:hover {
  background: rgba(255, 255, 255, 0.2);
}

.preview-image {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
}
</style>
