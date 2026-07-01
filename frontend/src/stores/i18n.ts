import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { SupportedLang } from '@/types'

const STORAGE_KEY = 'tacai_lang'

function loadLang(): SupportedLang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'ja' || stored === 'zh' || stored === 'en') return stored
  } catch {
    // ignore
  }
  // Detect browser language
  const nav = navigator.language || ''
  if (nav.startsWith('ja')) return 'ja'
  if (nav.startsWith('zh')) return 'zh'
  return 'en'
}

function saveLang(lang: SupportedLang) {
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // ignore
  }
}

export const useI18nStore = defineStore('i18n', () => {
  const locale = ref<SupportedLang>(loadLang())

  function setLocale(lang: SupportedLang) {
    locale.value = lang
    saveLang(lang)
  }

  return { locale, setLocale }
})
