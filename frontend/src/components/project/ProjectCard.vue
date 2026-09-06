<template>
  <div class="project-card book-card" @click="$emit('click')">
    <!-- 书页边缘 -->
    <div class="book-pages"></div>
    <!-- 书脊 -->
    <div class="book-spine"></div>
    <!-- 封面内容 -->
    <div class="book-content">
      <!-- 封面顶部装饰 -->
      <div class="book-cover-top"></div>
      <div class="project-card-header">
        <h3 class="project-card-title text-ellipsis">{{ project.title }}</h3>
        <el-dropdown trigger="click">
          <el-button size="small" text class="menu-btn" @click.stop>
            <el-icon><MoreFilled /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click.stop="$emit('edit', project)">
                <el-icon><Edit /></el-icon>编辑
              </el-dropdown-item>
              <el-dropdown-item @click.stop="$emit('delete', project)" divided>
                <el-icon><Delete /></el-icon>删除
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <p v-if="project.description" class="project-card-desc">
        {{ project.description }}
      </p>
      <div class="project-card-footer">
        <span class="project-card-date">
          {{ formatDate(project.updated_at || project.created_at, 'date') }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { MoreFilled, Edit, Delete } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'

defineProps({
  project: { type: Object, required: true },
})

defineEmits(['click', 'edit', 'delete'])
</script>

<style lang="scss" scoped>
.book-card {
  position: relative;
  background: linear-gradient(135deg, 
    rgba(45, 55, 72, 0.95) 0%, 
    rgba(30, 41, 59, 0.98) 40%,
    rgba(26, 35, 50, 0.99) 100%
  );
  border-radius: 4px 12px 12px 4px;
  border: 1px solid rgba(70, 80, 100, 0.6);
  box-shadow: 
    4px 4px 12px rgba(0, 0, 0, 0.5),
    -1px 0 3px rgba(0, 0, 0, 0.2),
    inset 0 0 20px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  cursor: pointer;
  height: 280px;
  width: 180px;
  display: flex;
  flex-direction: column;
  transform-origin: left center;
  
  &:hover {
    transform: perspective(800px) rotateY(-8deg) translateX(-5px);
    box-shadow: 
      12px 8px 24px rgba(0, 0, 0, 0.6),
      4px 4px 8px rgba(0, 0, 0, 0.3),
      inset 0 0 30px rgba(129, 140, 248, 0.1);
    border-color: rgba(129, 140, 248, 0.4);
    
    .book-spine {
      width: 12px;
      background: linear-gradient(180deg, 
        rgba(129, 140, 248, 0.9) 0%, 
        rgba(99, 102, 241, 0.95) 50%, 
        rgba(55, 48, 163, 0.9) 100%
      );
    }
    
    .book-pages {
      width: 6px;
      opacity: 0.9;
    }
  }
}

.book-pages {
  position: absolute;
  right: 0;
  top: 8px;
  bottom: 8px;
  width: 4px;
  background: linear-gradient(180deg, 
    rgba(200, 190, 170, 0.4) 0%,
    rgba(180, 170, 150, 0.5) 50%,
    rgba(160, 150, 130, 0.4) 100%
  );
  border-radius: 0 2px 2px 0;
  transition: all 0.4s ease;
  opacity: 0.7;
}

.book-spine {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8px;
  background: linear-gradient(180deg, 
    rgba(99, 102, 241, 0.7) 0%, 
    rgba(79, 70, 229, 0.8) 30%, 
    rgba(67, 56, 202, 0.85) 60%,
    rgba(55, 48, 163, 0.8) 100%
  );
  border-radius: 6px 0 0 6px;
  transition: all 0.4s ease;
  box-shadow: 
    inset -1px 0 2px rgba(0, 0, 0, 0.2),
    1px 0 3px rgba(0, 0, 0, 0.15);
}

.book-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: 8px;
  position: relative;
  overflow: hidden;
}

.book-cover-top {
  height: 4px;
  background: linear-gradient(90deg, 
    rgba(129, 140, 248, 0.3) 0%,
    rgba(99, 102, 241, 0.4) 20%,
    rgba(129, 140, 248, 0.5) 50%,
    rgba(99, 102, 241, 0.4) 80%,
    rgba(129, 140, 248, 0.3) 100%
  );
}

.project-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 1rem 1rem 0.75rem 1.25rem;
  background: linear-gradient(180deg, rgba(99, 102, 241, 0.08) 0%, transparent 100%);
  border-bottom: 1px solid rgba(70, 80, 100, 0.4);
}

.menu-btn {
  color: rgba(156, 163, 175, 0.6) !important;
  padding: 4px !important;
  &:hover {
    color: var(--text-primary) !important;
    background: rgba(255, 255, 255, 0.1) !important;
  }
}

.project-card-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0;
  flex: 1;
  min-width: 0;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.project-card-desc {
  font-size: 0.85rem;
  color: rgba(156, 163, 175, 0.85);
  margin: 0;
  line-height: 1.5;
  padding: 0.75rem 1rem 0.5rem 1.25rem;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1rem 0.6rem 1.25rem;
  border-top: 1px solid rgba(70, 80, 100, 0.4);
  margin-top: auto;
  background: linear-gradient(0deg, rgba(0, 0, 0, 0.1) 0%, transparent 100%);
}

.project-card-date {
  font-size: 0.75rem;
  color: rgba(107, 114, 128, 0.8);
  font-weight: 500;
}
</style>
