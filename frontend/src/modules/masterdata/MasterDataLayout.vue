<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import EntityList from './EntityList.vue'
import DepartmentList from './DepartmentList.vue'
import TeamList from './TeamList.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const activeTab = ref<string>((route.query.tab as string) || 'entities')

watch(activeTab, (val) => {
  router.replace({ query: { ...route.query, tab: val } })
})
</script>

<template>
  <div class="masterdata-layout">
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane name="entities" :label="t('entity.list_title')">
        <EntityList />
      </el-tab-pane>
      <el-tab-pane name="departments" :label="t('department.list_title')">
        <DepartmentList />
      </el-tab-pane>
      <el-tab-pane name="teams" :label="t('team.list_title')">
        <TeamList />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.masterdata-layout {
  padding: 0;
}
</style>
