import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { watch } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { useI18nStore } from './stores/i18n'
import type { SupportedLang } from './types'

// Import i18n locale messages
import enMessages from './i18n/en.json'
import jaMessages from './i18n/ja.json'
import zhMessages from './i18n/zh.json'

// Import global styles
import './styles/variables.css'
import './styles/base.css'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: {
    en: enMessages,
    ja: jaMessages,
    zh: zhMessages,
  },
})

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(i18n)
app.use(ElementPlus)

// Sync i18n store locale with vue-i18n locale
const i18nStore = useI18nStore()
i18n.global.locale.value = i18nStore.locale as SupportedLang

// Watch for locale changes from i18n store and sync to vue-i18n
watch(
  () => i18nStore.locale,
  (newLocale) => {
    i18n.global.locale.value = newLocale as SupportedLang
  }
)

app.mount('#app')
