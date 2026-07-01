<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usersApi } from '@/api/client'
import type { FormInstance, FormRules } from 'element-plus'

const { t } = useI18n()
const router = useRouter()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const formErrors = ref<string[]>([])

const form = reactive({
  username: '',
  display_name: '',
  email: '',
  user_type: 'employee',
  status: 'active',
  initial_password: '',
  phone: '',
  department: '',
  position: '',
})

const rules: FormRules = {
  username: [{ required: true, message: 'Username is required', trigger: 'blur' }],
  display_name: [{ required: true, message: 'Display name is required', trigger: 'blur' }],
  email: [
    { required: true, message: 'Email is required', trigger: 'blur' },
    { type: 'email', message: 'Invalid email format', trigger: 'blur' },
  ],
  initial_password: [
    { required: true, message: 'Password is required', trigger: 'blur' },
    { min: 6, message: 'Password must be at least 6 characters', trigger: 'blur' },
  ],
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  formErrors.value = []
  try {
    const response = await usersApi.create({ ...form })
    if (response.data?.success) {
      router.push('/users')
    } else {
      formErrors.value = [response.data?.error || 'Failed to create user']
    }
  } catch (e: any) {
    const data = e?.response?.data
    formErrors.value = data?.errors || [data?.error || 'Failed to create user']
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>{{ t('users.form.title_create') }}</h1>
      </div>
      <el-button @click="router.push('/users')">{{ t('action.cancel') }}</el-button>
    </div>

    <el-card shadow="never" style="max-width: 640px">
      <el-alert v-if="formErrors.length" type="error" show-icon closable @close="formErrors = []" style="margin-bottom: 20px">
        <ul style="margin: 0; padding-left: 16px">
          <li v-for="(err, i) in formErrors" :key="i">{{ err }}</li>
        </ul>
      </el-alert>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleSubmit">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('field.username')" prop="username">
              <el-input v-model="form.username" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.display_name')" prop="display_name">
              <el-input v-model="form.display_name" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('field.email')" prop="email">
              <el-input v-model="form.email" type="email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.phone')">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('field.user_type')">
              <el-select v-model="form.user_type" style="width: 100%">
                <el-option :label="t('user_type.employee')" value="employee" />
                <el-option :label="t('user_type.admin')" value="admin" />
                <el-option :label="t('user_type.external')" value="external" />
                <el-option :label="t('user_type.system')" value="system" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.status')">
              <el-select v-model="form.status" style="width: 100%">
                <el-option :label="t('status.active')" value="active" />
                <el-option :label="t('status.inactive')" value="inactive" />
                <el-option :label="t('status.locked')" value="locked" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('field.initial_password')" prop="initial_password">
              <el-input v-model="form.initial_password" type="password" show-password />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider />

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="t('field.department')">
              <el-input v-model="form.department" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.position')">
              <el-input v-model="form.position" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            {{ submitting ? '...' : t('action.save') }}
          </el-button>
          <el-button @click="router.push('/users')">{{ t('action.cancel') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}
</style>
