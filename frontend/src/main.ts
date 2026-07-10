import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
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

// Sync i18n store locale ⇄ vue-i18n (reactive, both directions)
const i18nStore = useI18nStore()
i18n.global.locale.value = i18nStore.locale as SupportedLang
watch(() => i18nStore.locale, (newLocale) => {
  i18n.global.locale.value = newLocale as SupportedLang
})

app.mount('#app')
