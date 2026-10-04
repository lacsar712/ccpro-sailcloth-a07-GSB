<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import api from '../api'

const rolls = ref([])
const lofts = ref([])
const error = ref('')
const editing = ref(null)
const availableLocks = ref([])
const lockGateMsg = ref('')
const form = reactive({
  loftId: null,
  rollCode: '',
  status: 'raw',
  fabricWeightGsm: 380,
  notes: '',
})

const statusLabel = { raw: '原布', dipping: '浸渍中', cured: '已固化' }

async function load() {
  error.value = ''
  try {
    const [r, l] = await Promise.all([api.get('/rolls/'), api.get('/lofts/')])
    rolls.value = r.data.results || r.data
    lofts.value = l.data.results || l.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
    await loadAvailableLocks()
  } catch {
    error.value = '加载失败'
  }
}

async function loadAvailableLocks() {
  // 新建布卷前读取将要绑定的未作废锁；改已有卷不要求新锁。
  if (editing.value || !form.loftId) {
    availableLocks.value = []
    lockGateMsg.value = ''
    return
  }
  try {
    const { data } = await api.get('/locks/', {
      params: { loftId: form.loftId, state: 'active', available: 1 },
    })
    availableLocks.value = data.results || data
  } catch {
    availableLocks.value = []
  }
  lockGateMsg.value = availableLocks.value.length
    ? ''
    : '该帆布间暂无未作废的可用铅封锁，请先在「铅封锁」页落锁后再新建布卷'
}

function startEdit(row) {
  editing.value = row.id
  form.loftId = row.loftId
  form.rollCode = row.rollCode
  form.status = row.status
  form.fabricWeightGsm = row.fabricWeightGsm
  form.notes = row.notes || ''
}

function resetForm() {
  editing.value = null
  form.rollCode = ''
  form.status = 'raw'
  form.fabricWeightGsm = 380
  form.notes = ''
  if (lofts.value.length) form.loftId = lofts.value[0].id
}

async function save() {
  error.value = ''
  try {
    if (editing.value) {
      await api.patch(`/rolls/${editing.value}/`, { ...form })
    } else {
      await api.post('/rolls/', { ...form })
    }
    resetForm()
    await load()
  } catch (e) {
    const data = e.response?.data
    const detail = Array.isArray(data?.detail) ? data.detail[0] : data?.detail
    error.value =
      data?.status?.[0] ||
      data?.rollCode?.[0] ||
      detail ||
      '保存失败（若标为已固化，请确认最近浸渍固化时长 ≥ 12 小时）'
  }
}

watch(() => form.loftId, loadAvailableLocks)
watch(editing, loadAvailableLocks)

onMounted(load)
</script>

<template>
  <div>
    <h1>布卷台账</h1>
    <p class="sub">次要列表入口。日常请在晾晒架点选布卷操作；此处用于新建/改卷号等台账维护。新建布卷须先有未作废铅封锁；改克重/备注不要求新锁。标「已固化」仍受固化时长 ≥ 12 小时约束。</p>
    <p v-if="error" class="error">{{ error }}</p>

    <form class="panel row" @submit.prevent="save">
      <label>帆布间
        <select v-model.number="form.loftId" required>
          <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
      <label>卷号
        <input v-model="form.rollCode" required />
      </label>
      <label>状态
        <select v-model="form.status">
          <option value="raw">原布</option>
          <option value="dipping">浸渍中</option>
          <option value="cured">已固化</option>
        </select>
      </label>
      <label>克重 gsm
        <input v-model.number="form.fabricWeightGsm" type="number" />
      </label>
      <label>备注
        <input v-model="form.notes" />
      </label>
      <button class="btn" type="submit" :disabled="!editing && !availableLocks.length">
        {{ editing ? '更新' : '新建' }}
      </button>
      <button v-if="editing" class="btn secondary" type="button" @click="resetForm">取消</button>
      <p v-if="!editing && lockGateMsg" class="error" style="flex-basis:100%;margin:0">
        {{ lockGateMsg }}
      </p>
      <p v-else-if="!editing && availableLocks.length" class="hint" style="flex-basis:100%;margin:0">
        将绑定铅封锁：{{ availableLocks[0].sealNumber }}（{{ availableLocks[0].lockedBy }} 落锁于
        {{ new Date(availableLocks[0].lockedAt).toLocaleString() }}）
      </p>
    </form>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>卷号</th>
          <th>状态</th>
          <th>克重</th>
          <th>铅封号</th>
          <th>备注</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rolls" :key="row.id">
          <td>{{ row.loftName }}</td>
          <td>{{ row.rollCode }}</td>
          <td><span class="badge" :class="'badge-' + row.status">{{ statusLabel[row.status] || row.status }}</span></td>
          <td>{{ row.fabricWeightGsm }}</td>
          <td>{{ row.sealNumber || '—' }}</td>
          <td>{{ row.notes }}</td>
          <td><button class="btn secondary" type="button" @click="startEdit(row)">编辑</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
