<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import api from '../api'

const rolls = ref([])
const lofts = ref([])
const availableLocks = ref([])
const error = ref('')
const editing = ref(null)
const form = reactive({
  loftId: null,
  rollCode: '',
  status: 'raw',
  fabricWeightGsm: 380,
  notes: '',
})

const statusLabel = { raw: '原布', dipping: '浸渍中', cured: '已固化' }

const isNew = computed(() => !editing.value)

// 新建时将要绑定的锁：该帆布间最早落锁的未作废、未使用铅封
const pendingLock = computed(() => {
  if (!isNew.value || !form.loftId) return null
  return availableLocks.value[0] || null
})

async function loadLocks() {
  if (!form.loftId) {
    availableLocks.value = []
    return
  }
  try {
    const { data } = await api.get('/seals/', {
      params: { loftId: form.loftId, state: 'active', bound: 'false' },
    })
    availableLocks.value = data.results || data
  } catch {
    availableLocks.value = []
  }
}

async function load() {
  error.value = ''
  try {
    const [r, l] = await Promise.all([api.get('/rolls/'), api.get('/lofts/')])
    rolls.value = r.data.results || r.data
    lofts.value = l.data.results || l.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
    await loadLocks()
  } catch {
    error.value = '加载失败'
  }
}

watch(() => form.loftId, () => {
  if (isNew.value) loadLocks()
})

function startEdit(row) {
  editing.value = row.id
  form.loftId = row.loftId
  form.rollCode = row.rollCode
  form.status = row.status
  form.fabricWeightGsm = row.fabricWeightGsm
  form.notes = row.notes || ''
  availableLocks.value = []
}

function resetForm() {
  editing.value = null
  form.rollCode = ''
  form.status = 'raw'
  form.fabricWeightGsm = 380
  form.notes = ''
  if (lofts.value.length) form.loftId = lofts.value[0].id
  loadLocks()
}

async function save() {
  error.value = ''
  if (isNew.value) {
    // 点新建布卷时先读将要绑定的未作废锁；没有则中文挡住
    await loadLocks()
    if (!pendingLock.value) {
      error.value = '该帆布间没有未作废且未使用的铅封锁，不能新建布卷；请先到「铅封锁」落锁。'
      return
    }
  }
  try {
    if (editing.value) {
      // 改已有卷的克重/备注等不需要新锁
      await api.patch(`/rolls/${editing.value}/`, { ...form })
    } else {
      await api.post('/rolls/', { ...form, sealLockId: pendingLock.value.id })
    }
    resetForm()
    await load()
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.sealLock?.[0] ||
      data?.status?.[0] ||
      data?.rollCode?.[0] ||
      data?.detail ||
      '保存失败（若标为已固化，请确认最近浸渍固化时长 ≥ 12 小时）'
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h1>布卷台账</h1>
    <p class="sub">次要列表入口。新建布卷前须在同帆布间落一条未作废铅封，建卷成功即在同一事务内绑锁；改已有卷的克重、备注不要求新锁。标「已固化」仍受固化时长 ≥ 12 小时约束。</p>
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
      <button class="btn" type="submit">{{ editing ? '更新' : '新建' }}</button>
      <button v-if="editing" class="btn secondary" type="button" @click="resetForm">取消</button>
    </form>

    <p v-if="isNew && pendingLock" class="ok">
      将绑定铅封锁：<strong>{{ pendingLock.sealNumber }}</strong>
      （{{ pendingLock.lockedBy }} 于 {{ new Date(pendingLock.lockedAt).toLocaleString() }} 落锁）
    </p>
    <p v-else-if="isNew && form.loftId" class="error">
      该帆布间没有未作废且未使用的铅封锁，不能新建布卷；请先到<router-link to="/seals">铅封锁</router-link>落锁。
    </p>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>卷号</th>
          <th>铅封号</th>
          <th>状态</th>
          <th>克重</th>
          <th>备注</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rolls" :key="row.id">
          <td>{{ row.loftName }}</td>
          <td>{{ row.rollCode }}</td>
          <td>{{ row.sealNumber || '—' }}</td>
          <td><span class="badge" :class="'badge-' + row.status">{{ statusLabel[row.status] || row.status }}</span></td>
          <td>{{ row.fabricWeightGsm }}</td>
          <td>{{ row.notes }}</td>
          <td><button class="btn secondary" type="button" @click="startEdit(row)">编辑</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
