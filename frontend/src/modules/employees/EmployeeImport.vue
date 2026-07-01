<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadInstance } from 'element-plus'

const router = useRouter()
const uploadRef = ref<UploadInstance>()
const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const result = ref<{ success: boolean; created: number; total_rows: number; errors: any[]; errors_count: number } | null>(null)
const error = ref('')

function downloadTemplate() {
  window.open('http://127.0.0.1:8004/exports/employees-import-template.csv', '_blank')
}

async function handleUpload() {
  if (fileList.value.length === 0) { error.value = 'Please select a CSV file'; return }
  uploading.value = true; error.value = ''; result.value = null
  try {
    const file = fileList.value[0].raw
    if (!file) { error.value = 'No file selected'; uploading.value = false; return }
    const formData = new FormData()
    formData.append('file', file)
    // Use raw XMLHttpRequest for multipart upload
    const xhr = new XMLHttpRequest()
    xhr.withCredentials = true
    xhr.open('POST', '/api/employees/import')
    xhr.onload = () => {
      try { result.value = JSON.parse(xhr.responseText) }
      catch { error.value = 'Failed to parse response' }
      uploading.value = false
    }
    xhr.onerror = () => { error.value = 'Upload failed'; uploading.value = false }
    xhr.send(formData)
  } catch (e: any) {
    error.value = e?.message || 'Upload failed'; uploading.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="topbar">
      <div>
        <p class="eyebrow">Employee Management</p>
        <h1>Import Employees (CSV)</h1>
      </div>
      <div class="topbar-actions">
        <el-button @click="router.push('/employees')"><el-icon><ArrowLeft /></el-icon>Back to List</el-button>
      </div>
    </div>

    <el-card shadow="never" style="max-width:700px">
      <el-alert v-if="error" :title="error" type="error" show-icon closable style="margin-bottom:16px" />

      <!-- Upload Area -->
      <el-upload
        ref="uploadRef" v-model:file-list="fileList"
        drag accept=".csv" :limit="1" :auto-upload="false"
        :on-exceed="() => error='Only 1 file allowed'"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">Drop CSV file here or <em>click to select</em></div>
        <template #tip>
          <div class="el-upload__tip">CSV files only. Required columns: employee_name, legal_entity_code, department_code, employment_type, status</div>
        </template>
      </el-upload>

      <div style="margin-top:16px">
        <el-button type="primary" @click="handleUpload" :loading="uploading" :disabled="fileList.length === 0">
          <el-icon><UploadFilled /></el-icon>Import
        </el-button>
        <el-button @click="router.push('/employees')">Cancel</el-button>
        <el-button link type="primary" @click="downloadTemplate">
          Download Template CSV
        </el-button>
      </div>

      <!-- Result -->
      <el-alert v-if="result" :type="result.success ? 'success' : 'warning'" show-icon style="margin-top:20px" :closable="false">
        <template #title>
          <span v-if="result.success">Imported {{ result.created }} of {{ result.total_rows }} rows successfully!</span>
          <span v-else>Import completed with errors: {{ result.errors_count }} issue(s) in {{ result.total_rows }} rows.</span>
        </template>
        <ul v-if="result.errors?.length" style="margin-top:8px;max-height:200px;overflow:auto">
          <li v-for="(e, i) in result.errors.slice(0, 20)" :key="i">Row {{ e.row }}: {{ e.message }} ({{ e.field }})</li>
          <li v-if="result.errors.length > 20">... and {{ result.errors.length - 20 }} more errors</li>
        </ul>
      </el-alert>
    </el-card>
  </div>
</template>
