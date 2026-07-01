<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { employeeApi, masterdataApi } from '@/api/client'
import { ArrowLeft } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)

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
})

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch { return }
  submitting.value = true; errors.value = []
  try {
    const payload: Record<string, any> = {}
    // Flatten nested form to flat keys
    for (const [section, fields] of Object.entries(form.value)) {
      for (const [key, val] of Object.entries(fields as Record<string, any>)) {
        if (val) payload[`${section}.${key}`] = val
      }
    }
    const { data } = await (employeeApi as any).create(payload)
    if (data?.success) {
      router.push(`/employees/${data.employee_id}`)
    } else {
      errors.value = data?.errors || ['Failed to create employee']
    }
  } catch (e: any) {
    errors.value = e?.response?.data?.errors || [e?.message || 'Failed to create employee']
  } finally { submitting.value = false }
}
</script>

<template>
  <div class="page">
    <div class="topbar">
      <div>
        <p class="eyebrow">Employee Management</p>
        <h1>New Employee</h1>
      </div>
      <div class="topbar-actions">
        <el-button @click="router.push('/employees')"><el-icon><ArrowLeft /></el-icon>Back to List</el-button>
      </div>
    </div>

    <el-card shadow="never" style="max-width:800px">
      <el-alert v-if="errors.length" type="error" show-icon style="margin-bottom:16px">
        <li v-for="(e, i) in errors" :key="i">{{ e }}</li>
      </el-alert>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleSubmit">
        <el-divider content-position="left">Profile</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Display Name" prop="profile.name.display_name">
              <el-input v-model="form.profile.name.display_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Email" prop="profile.email">
              <el-input v-model="form.profile.email" type="email" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Phone">
              <el-input v-model="form.profile.phone" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">Employment</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Legal Entity" prop="employment.entity_id">
              <el-select v-model="form.employment.entity_id" placeholder="Select entity" style="width:100%">
                <el-option v-for="e in entityOptions" :key="e.entity_id" :label="`${e.entity_code} - ${e.entity_name_en}`" :value="e.entity_id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Department">
              <el-select v-model="form.employment.department_id" placeholder="Select department" clearable style="width:100%">
                <el-option v-for="d in deptOptions" :key="d.department_id" :label="`${d.department_code} - ${d.department_name_en}`" :value="d.department_id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Position">
              <el-input v-model="form.employment.position" placeholder="e.g. Software Engineer" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Employment Type" prop="employment.employment_type">
              <el-select v-model="form.employment.employment_type" style="width:100%">
                <el-option label="Seishain" value="seishain" /><el-option label="Keiyaku" value="keiyaku" />
                <el-option label="Haken" value="haken" /><el-option label="Part-Time" value="part_time" />
                <el-option label="Intern" value="intern" /><el-option label="Outsourcing" value="outsourcing" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Status" prop="employment.status">
              <el-select v-model="form.employment.status" style="width:100%">
                <el-option label="Active" value="active" /><el-option label="Probation" value="probation" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Join Date">
              <el-date-picker v-model="form.employment.join_date" type="date" placeholder="Select date" style="width:100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item style="margin-top:16px">
          <el-button type="primary" @click="handleSubmit" :loading="submitting">Create Employee</el-button>
          <el-button @click="router.push('/employees')">Cancel</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
