<template>
  <div class="image-gallery">
    <div
      v-for="(image, index) in images"
      :key="index"
      class="image-item"
    >
      <img
        :src="getImageSrc(image)"
        :alt="image.alt || `Image ${index + 1}`"
        class="gallery-image"
        @click="handleImageClick(image)"
      />
      <div v-if="image.caption" class="image-caption">
        {{ image.caption }}
      </div>
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
import { X as XIcon } from 'lucide-vue-next'

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

function getImageSrc(image: GalleryImage): string {
  // 如果已经是完整 URL 或 data URL，直接返回
  if (image.src.startsWith('http') || image.src.startsWith('data:')) {
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

.image-caption {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 12px;
  text-align: center;
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

.preview-image {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
}
</style>
