<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18nStore } from '@/stores/i18n'
import { useI18n } from 'vue-i18n'
import { publicApi } from '@/api/client'
import type { SupportedLang } from '@/types'

const BYPASS_AUTH = import.meta.env.VITE_DEV_BYPASS_AUTH === 'true'

interface EntityOption {
  entity_id: string
  entity_code: string
  entity_name_en: string
  entity_name_ja: string
  entity_name_zh: string
  country: string
  status: string
}

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const i18nStore = useI18nStore()
const { t, locale } = useI18n()

const languages: { code: SupportedLang; label: string }[] = [
  { code: 'ja', label: '日本語' },
  { code: 'zh', label: '中文' },
  { code: 'en', label: 'English' },
]

const STORAGE_KEY = 'tacai_user_admin_last_entity_by_email'
const FALLBACK_ENTITY = 'TAKK'

const entities = ref<EntityOption[]>([])
const entityCodes = ref<string[]>([])
const loadingEntities = ref(true)
const loadError = ref('')

const entityCode = ref('TAKK')
const email = ref('admin@tacai.local')
const password = ref('')
const error = ref('')
const loading = ref(false)

// ---- Entity helpers ----

function entityName(entity: EntityOption): string {
  const lang = locale.value as string
  return String(
    entity[`entity_name_${lang}` as keyof EntityOption] ||
    entity.entity_name_en ||
    entity.entity_name_ja ||
    ''
  )
}

function entityLabel(entity: EntityOption): string {
  const code = entity.entity_code
  const name = entityName(entity)
  return name ? `${code} - ${name}` : code
}

function canonicalEntityCode(value: string): string {
  const requested = (value || '').trim().toLowerCase()
  if (!requested) return ''
  for (const code of entityCodes.value) {
    if (code.toLowerCase() === requested) return code
  }
  return ''
}

function setEntity(value: string) {
  const canonical = canonicalEntityCode(value) || (value || '').trim()
  entityCode.value = canonical || FALLBACK_ENTITY
}

// ---- localStorage helpers ----

function loadMap(): Record<string, string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function saveMap(value: Record<string, string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {
    // Ignore storage failures
  }
}

function normalizedEmail(): string {
  return (email.value || '').trim().toLowerCase()
}

function fillEntityFromEmail() {
  const em = normalizedEmail()
  if (!em) {
    if (!entityCode.value.trim()) setEntity(FALLBACK_ENTITY)
    return
  }
  const stored = canonicalEntityCode(loadMap()[em])
  if (stored) {
    setEntity(stored)
  } else if (!entityCode.value.trim()) {
    setEntity(FALLBACK_ENTITY)
  } else {
    setEntity(entityCode.value)
  }
}

// ---- Load entities from public API ----

async function loadEntities() {
  loadingEntities.value = true
  loadError.value = ''
  try {
    const response = await publicApi.entities()
    const list = (response.data?.entities || []) as EntityOption[]
    entities.value = list
    entityCodes.value = list.map(e => e.entity_code).filter(Boolean)
    if (list.length === 0) {
      loadError.value = 'No active entities found.'
    }
  } catch {
    loadError.value = 'Failed to load entities. Please try again.'
  } finally {
    loadingEntities.value = false
  }
}

// ---- Login handler ----

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    // Persist entity ↔ email mapping
    const em = normalizedEmail()
    const code = canonicalEntityCode(entityCode.value) || entityCode.value.trim() || FALLBACK_ENTITY
    if (em && code) {
      const map = loadMap()
      map[em] = code
      saveMap(map)
    }

    const success = await auth.login(email.value, password.value, code)
    if (success) {
      // After successful login, navigate to Vue SPA Dashboard
      // The session cookie (tacai_session_id) is now set — all API calls are authenticated
      const redirect = (route.query.redirect as string) || '/dashboard'
      router.push(redirect)
    } else {
      error.value = auth.error || t('validation.invalid_login')
    }
  } catch {
    error.value = t('validation.invalid_login')
  } finally {
    loading.value = false
  }
}

// ---- Init ----

function initEntityField() {
  if (!entityCode.value.trim()) setEntity(FALLBACK_ENTITY)
  setEntity(entityCode.value)
  if (email.value.trim() && entityCode.value === FALLBACK_ENTITY) {
    fillEntityFromEmail()
  }
}

onMounted(async () => {
  // ── Dev bypass: skip login form, auto-authenticate and go to dashboard ──
  if (BYPASS_AUTH) {
    await auth.login(email.value, '', entityCode.value)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
    return
  }
  await loadEntities()
  initEntityField()
})
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <div class="brand-mark">TACAI</div>
      <div v-if="BYPASS_AUTH" class="dev-bypass-badge">🔧 DEV MODE — Auth Bypassed</div>
      <h1>{{ t('login.title') }}</h1>
      <p class="muted login-subtitle">{{ t('login.subtitle') }}</p>

      <!-- Language switcher -->
      <div class="language-switcher login-lang-switcher">
        <span>{{ t('language.label') }}</span>
        <a
          v-for="lang in languages"
          :key="lang.code"
          :class="{ active: i18nStore.locale === lang.code }"
          href="#"
          @click.prevent="i18nStore.setLocale(lang.code)"
        >{{ lang.label }}</a>
      </div>

      <!-- Loading state -->
      <div v-if="loadingEntities" class="login-loading">
        <span class="spinner"></span>
      </div>

      <!-- Load error -->
      <div v-else-if="loadError" class="alert">{{ loadError }}</div>

      <!-- Login form -->
      <template v-else>
        <div v-if="error" class="alert">{{ error }}</div>

        <form @submit.prevent="handleLogin" class="login-form">
          <!-- Entity code: select dropdown -->
          <label for="entity_code_select">
            {{ t('field.entity_code') }}
            <select
              id="entity_code_select"
              :value="canonicalEntityCode(entityCode) || ''"
              @change="setEntity(($event.target as HTMLSelectElement).value)"
            >
              <option value="">--</option>
              <option
                v-for="entity in entities"
                :key="entity.entity_id"
                :value="entity.entity_code"
              >
                {{ entityLabel(entity) }}
              </option>
            </select>
          </label>

          <!-- Entity code: manual input with datalist -->
          <label for="entity_code">
            {{ t('field.entity_code_manual') }}
            <input
              id="entity_code"
              v-model="entityCode"
              :list="'entity_code_options'"
              required
              placeholder="TAKK"
              autocomplete="organization"
              @change="setEntity(entityCode)"
              @blur="setEntity(entityCode)"
            >
            <datalist id="entity_code_options">
              <option
                v-for="entity in entities"
                :key="entity.entity_id"
                :value="entity.entity_code"
                :label="entityLabel(entity)"
              />
            </datalist>
          </label>
          <p class="muted helper-text">{{ t('login.entity_help') }}</p>

          <!-- Email -->
          <label for="email">
            {{ t('field.email') }}
            <input
              id="email"
              v-model="email"
              type="email"
              required
              autocomplete="username"
              @change="fillEntityFromEmail"
              @blur="fillEntityFromEmail"
            >
          </label>

          <!-- Password -->
          <label for="password">
            {{ t('field.password') }}
            <input
              id="password"
              v-model="password"
              type="password"
              required
              autocomplete="current-password"
            >
          </label>

          <button type="submit" :disabled="loading" class="login-submit-btn">
            <span v-if="loading" class="spinner spinner--small"></span>
            <span v-else>{{ t('login.submit') }}</span>
          </button>
        </form>

        <p class="muted login-hint">{{ t('login.hint') }}</p>
      </template>
    </section>
  </main>
</template>
