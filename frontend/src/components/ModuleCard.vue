<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { DashboardModule } from '@/modules/portal/types'

const props = defineProps<{
  module: DashboardModule
}>()

const router = useRouter()
const { t } = useI18n()

function handleAction(e: Event) {
  e.stopPropagation()
  if (props.module.status === 'planned') {
    ElMessage.info(t('common.coming_soon'))
    return
  }
  if (props.module.route && props.module.route !== '#') {
    router.push(props.module.route)
  }
}

function handleCardClick() {
  if (props.module.status === 'planned') {
    ElMessage.info(t('common.coming_soon'))
    return
  }
  if (props.module.route && props.module.route !== '#') {
    router.push(props.module.route)
  }
}
</script>

<template>
  <el-card
    class="module-card"
    :class="[`color-${module.color}`, module.status]"
    shadow="hover"
    @click="handleCardClick"
  >
    <div v-if="module.status === 'planned'" class="planned-badge">
      {{ t('common.coming_soon') }}
    </div>

    <div class="card-icon" :class="`icon-${module.color}`">
      <el-icon :size="40">
        <component :is="module.icon" />
      </el-icon>
    </div>

    <h3 class="card-title">{{ t(module.titleKey) }}</h3>
    <p class="card-desc">{{ t(module.descKey) }}</p>

    <el-button
      type="primary"
      size="default"
      :disabled="module.status === 'planned'"
      class="card-action"
      @click="handleAction"
    >
      {{ t(module.actionKey) }}
    </el-button>
  </el-card>
</template>

<style scoped>
.module-card {
  width: 280px;
  height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  text-align: center;
  padding: 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
}

.module-card:not(.planned):hover {
  transform: translateY(-4px);
}

/* ── Planned / disabled state ── */
.module-card.planned {
  opacity: 0.55;
  cursor: default;
  filter: grayscale(0.35);
}
.module-card.planned:hover {
  transform: none;
}

.planned-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 0.7rem;
  background: var(--el-color-info-light-3);
  color: var(--el-color-info);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  line-height: 1.4;
}

/* ── Icon ── */
.card-icon {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  flex-shrink: 0;
}
.card-icon :deep(.el-icon) {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── Title & Desc ── */
.card-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0 0 4px;
  color: var(--el-text-color-primary);
  flex-shrink: 0;
}

.card-desc {
  font-size: 0.82rem;
  color: var(--el-text-color-secondary);
  margin: 0 0 14px;
  line-height: 1.45;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Button ── */
.card-action {
  flex-shrink: 0;
  margin-top: auto;
}

/* ── Color themes ── */
.icon-employee { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.icon-user { background: var(--el-color-success-light-9); color: var(--el-color-success); }
.icon-payroll { background: #fdf6ec; color: var(--el-color-warning); }
.icon-invoice { background: var(--el-color-danger-light-9); color: var(--el-color-danger); }
.icon-masterdata { background: #ecf5ff; color: #409eff; }
.icon-timesheet { background: #f0f9eb; color: #67c23a; }
.icon-customer { background: #fef0f0; color: #f56c6c; }
.icon-vendor { background: #f4f4f5; color: #909399; }
.icon-reimbursement { background: #fdf6ec; color: #e6a23c; }
.icon-interview { background: #f0f9eb; color: #67c23a; }
</style>
