<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { employeeApi, masterdataApi } from '@/api/client'
import { ArrowLeft } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const isEdit = computed(() => !!route.params.id)
const employeeId = computed(() => route.params.id as string)
const pageTitle = computed(() => isEdit.value ? t('employee.edit.title') : t('employee.create.title'))

const formRef = ref<FormInstance>()
const submitting = ref(false)
const loading = ref(false)

const form = ref({
  profile: { name: { display_name: '', last_name: '', first_name: '' }, email: '', phone: '' },
  employment: { entity_id: '', department_id: '', position: '', employment_type: 'seishain', status: 'active', join_date: '' },
})

const rules: FormRules = {
  'profile.name.display_name': [{ required: true, message: 'Name is required', trigger: 'blur' }],
  'profile.email': [{ required: true, message: 'Email is required', trigger: 'blur' }, { type: 'email', message: 'Invalid email', trigger: 'blur' }],
  'employment.entity_id': [{ required: true, message: 'Entity is required', trigger: 'change' }],
  'employment.employment_type': [{ required: true, message: 'Type is required', trigger: 'change' }],
  'employment.status': [{ required: true, message: 'Status is required', trigger: 'change' }],
}

const entityOptions = ref<{ entity_id: string; entity_code: string; entity_name_en: string }[]>([])
const deptOptions = ref<{ department_id: string; department_code: string; department_name_en: string }[]>([])
const errors = ref<string[]>([])

onMounted(async () => {
  try {
    const [er, dr] = await Promise.all([masterdataApi.entities(), masterdataApi.departments()])
    entityOptions.value = er.data?.entities || []
    deptOptions.value = dr.data?.departments || []
  } catch { /* ignore */ }

  // Edit mode: load existing employee data
  if (isEdit.value) {
    loading.value = true
    try {
      const { data } = await employeeApi.get(employeeId.value)
      const emp = data?.employee
      if (emp) {
        // Map API response back to form structure
        const p = emp.profile || {}
        const e = emp.employment || {}
        const name = p.name || {}
        form.value = {
          profile: {
            name: {
              display_name: name.display_name || '',
              last_name: name.family_name || name.last_name || '',
              first_name: name.given_name || name.first_name || '',
            },
            email: p.email || '',
            phone: p.phone || '',
          },
          employment: {
            entity_id: e.entity_id || '',
            department_id: e.department_id || '',
            position: e.position || '',
            employment_type: e.employment_type || (e.contract || {}).employment_type || 'seishain',
            status: e.status || 'active',
            join_date: e.join_date || '',
          },
        }
      }
    } catch (e: any) {
      errors.value = [e?.message || 'Failed to load employee']
    } finally { loading.value = false }
  }
})

function flatten(obj: Record<string, any>, prefix = ''): Record<string, any> {
  const result: Record<string, any> = {}
  for (const [key, val] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      Object.assign(result, flatten(val, fullKey))
    } else if (val) {
      result[fullKey] = val
    }
  }
  return result
}
async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch { return }
  submitting.value = true; errors.value = []
  try {
    // Flatten nested form to flat dot-notation keys (unified API format)
    const payload: Record<string, any> = flatten(form.value)
    if (isEdit.value) {
      const { data } = await (employeeApi as any).update(employeeId.value, payload)
      if (data?.employee) {
        router.push(`/employees/${employeeId.value}`)
      } else {
        errors.value = data?.errors || ['Failed to update employee']
      }
    } else {
      const { data } = await (employeeApi as any).create(payload)
      if (data?.success || data?.employee) {
        router.push('/employees')
      } else {
        errors.value = data?.errors || ['Failed to create employee']
      }
    }
  } catch (e: any) {
    errors.value = e?.response?.data?.errors || [e?.message || 'Failed to save employee']
  } finally { submitting.value = false }
}
</script>

<template>
  <div class="page">
    <el-alert v-if="loading" type="info" show-icon :title="t('common.loading') || 'Loading...'" style="margin-bottom:16px" />

    <div class="topbar">
      <div>
        <p class="eyebrow">{{ t('employee.module_title') }}</p>
        <h1>{{ pageTitle }}</h1>
      </div>
      <div class="topbar-actions">
        <el-button @click="router.push('/employees')"><el-icon><ArrowLeft /></el-icon>{{ t('action.back') }}</el-button>
      </div>
    </div>

    <el-card shadow="never" style="max-width:800px">
      <el-alert v-if="errors.length" type="error" show-icon style="margin-bottom:16px">
        <li v-for="(e, i) in errors" :key="i">{{ e }}</li>
      </el-alert>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleSubmit">
        <el-divider content-position="left">{{ t('employee.section_profile') }}</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.profile__name__display_name')" prop="profile.name.display_name">
              <el-input v-model="form.profile.name.display_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.profile__email')" prop="profile.email">
              <el-input v-model="form.profile.email" type="email" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.profile__phone')">
              <el-input v-model="form.profile.phone" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">{{ t('employee.section_employment') }}</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.employment__entity_id')" prop="employment.entity_id">
              <el-select v-model="form.employment.entity_id" :placeholder="t('action.select')" style="width:100%">
                <el-option v-for="e in entityOptions" :key="e.entity_id" :label="`${e.entity_code} - ${e.entity_name_en}`" :value="e.entity_id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('field.employment__department_id')">
              <el-select v-model="form.employment.department_id" :placeholder="t('action.select')" clearable style="width:100%">
                <el-option v-for="d in deptOptions" :key="d.department_id" :label="`${d.department_code} - ${d.department_name_en}`" :value="d.department_id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.employment__position')">
              <el-input v-model="form.employment.position" :placeholder="t('employee.position_placeholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item :label="t('field.employment__employment_type')" prop="employment.employment_type">
              <el-select v-model="form.employment.employment_type" style="width:100%">
                <el-option :label="t('enum.employment_type.seishain')" value="seishain" />
                <el-option :label="t('enum.employment_type.keiyaku')" value="keiyaku" />
                <el-option :label="t('enum.employment_type.haken')" value="haken" />
                <el-option :label="t('enum.employment_type.part_time')" value="part_time" />
                <el-option :label="t('enum.employment_type.intern')" value="intern" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item :label="t('field.employment__status')" prop="employment.status">
              <el-select v-model="form.employment.status" style="width:100%">
                <el-option :label="t('enum.status.active')" value="active" />
                <el-option :label="t('enum.status.probation')" value="probation" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('field.employment__join_date')">
              <el-date-picker v-model="form.employment.join_date" type="date" :placeholder="t('action.select')" style="width:100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item style="margin-top:16px">
          <el-button type="primary" @click="handleSubmit" :loading="submitting">{{ isEdit ? t('common.save') : t('action.create') }}</el-button>
          <el-button @click="router.push('/employees')">{{ t('action.cancel') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
