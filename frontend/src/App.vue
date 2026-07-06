<script setup lang="ts">
import { RouterView } from 'vue-router'
import { onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import ja from 'element-plus/dist/locale/ja.mjs'
import en from 'element-plus/dist/locale/en.mjs'

const auth = useAuthStore()
const i18nStore = useI18nStore()

const epLocales: Record<string, any> = { en, ja, zh: zhCn }
const epLocale = computed(() => epLocales[i18nStore.locale] || en)

onMounted(() => {
  auth.init()
})
</script>

<template>
  <el-config-provider :locale="epLocale">
    <RouterView />
  </el-config-provider>
</template>
