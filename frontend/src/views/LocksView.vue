<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const locks = ref([])
const lofts = ref([])
const error = ref('')
const notice = ref('')
const busy = ref(false)
const stateFilter = ref('all')
const loftFilter = ref('')
const form = reactive({ loftId: null, sealNumber: '' })

const isAdmin = computed(() => auth.user?.role === 'admin')

function fmt(dt) {
  return dt ? new Date(dt).toLocaleString() : '—'
}

function firstError(data, fallback) {
  if (!data) return fallback
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) return String(detail[0])
  for (const key of Object.keys(data)) {
    const v = data[key]
    if (Array.isArray(v) && v.length) return String(v[0])
    if (typeof v === 'string') return v
  }
  return fallback
}

async function loadLocks() {
  const params = {}
  if (stateFilter.value !== 'all') params.state = stateFilter.value
  if (loftFilter.value) params.loftId = loftFilter.value
  const { data } = await api.get('/locks/', { params })
  locks.value = data.results || data
}

async function load() {
  error.value = ''
  try {
    const l = await api.get('/lofts/')
    lofts.value = l.data.results || l.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
    await loadLocks()
  } catch {
    error.value = '铅封锁加载失败'
  }
}

async function placeLock() {
  error.value = ''
  notice.value = ''
  busy.value = true
  const seal = form.sealNumber.trim()
  try {
    await api.post('/locks/', { loftId: form.loftId, sealNumber: seal })
    notice.value = `铅封号 ${seal} 已落锁，可入架新建布卷`
    form.sealNumber = ''
    await loadLocks()
  } catch (e) {
    error.value = firstError(e.response?.data, '落锁失败')
  } finally {
    busy.value = false
  }
}

async function voidLock(row) {
  if (!window.confirm(`确认作废铅封号 ${row.sealNumber}？作废后该号可再发。`)) return
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    await api.post(`/locks/${row.id}/void/`)
    notice.value = `铅封号 ${row.sealNumber} 已作废`
    await loadLocks()
  } catch (e) {
    error.value = firstError(e.response?.data, '作废失败')
  } finally {
    busy.value = false
  }
}

watch([stateFilter, loftFilter], () => {
  loadLocks().catch(() => {
    error.value = '铅封锁加载失败'
  })
})

onMounted(load)
</script>

<template>
  <div>
    <h1>铅封锁</h1>
    <p class="sub">新布卷入晾晒架前，须先在对应帆布间落一条未作废铅封号；同间未作废铅封号唯一。落锁操作工即可，作废仅管理员，作废后该号可再发。</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="ok">{{ notice }}</p>

    <form class="panel row" @submit.prevent="placeLock">
      <label>帆布间
        <select v-model.number="form.loftId" required>
          <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
      <label>铅封号
        <input v-model="form.sealNumber" required maxlength="60" placeholder="如 SN-2026-001" />
      </label>
      <button class="btn" type="submit" :disabled="busy || !form.sealNumber.trim()">落锁</button>
    </form>

    <div class="panel row">
      <label>状态
        <select v-model="stateFilter">
          <option value="all">全部</option>
          <option value="active">未作废</option>
          <option value="voided">已作废</option>
        </select>
      </label>
      <label>帆布间
        <select v-model="loftFilter">
          <option value="">全部</option>
          <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
    </div>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>铅封号</th>
          <th>状态</th>
          <th>落锁时刻</th>
          <th>落锁人</th>
          <th>作废时刻</th>
          <th>绑定布卷</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in locks" :key="row.id">
          <td>{{ row.loftName }}</td>
          <td>{{ row.sealNumber }}</td>
          <td>
            <span class="badge" :class="row.voidedAt ? 'badge-voided' : 'badge-active'">
              {{ row.voidedAt ? '已作废' : '未作废' }}
            </span>
          </td>
          <td>{{ fmt(row.lockedAt) }}</td>
          <td>{{ row.lockedBy }}</td>
          <td>{{ fmt(row.voidedAt) }}</td>
          <td>{{ row.rollCode || '—' }}</td>
          <td>
            <button
              v-if="!row.voidedAt && isAdmin"
              class="btn secondary"
              type="button"
              :disabled="busy"
              @click="voidLock(row)"
            >作废</button>
            <span v-else class="hint">—</span>
          </td>
        </tr>
        <tr v-if="!locks.length">
          <td colspan="8" class="hint">暂无铅封锁记录</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
