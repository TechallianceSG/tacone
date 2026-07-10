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
  let detected: SupportedLang
  if (nav.startsWith('ja')) detected = 'ja'
  else if (nav.startsWith('zh')) detected = 'zh'
  else detected = 'en'
  // Persist so that API client (client.ts) sees the same language
  saveLang(detected)
  return detected
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
