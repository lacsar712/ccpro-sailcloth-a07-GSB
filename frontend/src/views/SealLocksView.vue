<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const seals = ref([])
const lofts = ref([])
const error = ref('')
const busy = ref(false)
const filter = ref('active')

const form = reactive({
  loftId: null,
  sealNumber: '',
})

const isAdmin = computed(() => auth.user?.role === 'admin')

const filtered = computed(() => {
  if (filter.value === 'active') return seals.value.filter((s) => s.active)
  if (filter.value === 'voided') return seals.value.filter((s) => !s.active)
  return seals.value
})

async function load() {
  error.value = ''
  try {
    const [s, l] = await Promise.all([api.get('/seals/'), api.get('/lofts/')])
    seals.value = s.data.results || s.data
    lofts.value = l.data.results || l.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
  } catch {
    error.value = '铅封锁加载失败'
  }
}

async function createLock() {
  error.value = ''
  const sealNumber = form.sealNumber.trim()
  if (!sealNumber) {
    error.value = '铅封号不得为空'
    return
  }
  busy.value = true
  try {
    await api.post('/seals/', { loftId: form.loftId, sealNumber })
    form.sealNumber = ''
    await load()
  } catch (e) {
    const data = e.response?.data
    error.value =
      data?.sealNumber?.[0] ||
      data?.detail ||
      '落锁失败（同帆布间未作废铅封号不得重复）'
  } finally {
    busy.value = false
  }
}

async function voidLock(row) {
  error.value = ''
  busy.value = true
  try {
    await api.post(`/seals/${row.id}/void/`)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || '作废失败（仅管理员可作废）'
  } finally {
    busy.value = false
  }
}

function fmt(t) {
  return t ? new Date(t).toLocaleString() : '—'
}

onMounted(load)
</script>

<template>
  <div>
    <h1>铅封锁</h1>
    <p class="sub">新布卷入晾晒架前，须先在同帆布间落一条未作废铅封。操作工可落锁；作废仅管理员。作废后该号可再发。</p>
    <p v-if="error" class="error">{{ error }}</p>

    <form class="panel row" @submit.prevent="createLock">
      <label>帆布间
        <select v-model.number="form.loftId" required>
          <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
      </label>
      <label>铅封号
        <input v-model="form.sealNumber" required placeholder="不得为空" />
      </label>
      <button class="btn" type="submit" :disabled="busy">落锁</button>
    </form>

    <div class="seal-filter">
      <button
        class="btn secondary"
        type="button"
        :class="{ 'filter-on': filter === 'active' }"
        @click="filter = 'active'"
      >未作废</button>
      <button
        class="btn secondary"
        type="button"
        :class="{ 'filter-on': filter === 'voided' }"
        @click="filter = 'voided'"
      >已作废</button>
      <button
        class="btn secondary"
        type="button"
        :class="{ 'filter-on': filter === 'all' }"
        @click="filter = 'all'"
      >全部</button>
    </div>

    <table>
      <thead>
        <tr>
          <th>帆布间</th>
          <th>铅封号</th>
          <th>状态</th>
          <th>落锁时刻</th>
          <th>落锁人</th>
          <th>绑定布卷</th>
          <th>作废时刻</th>
          <th>作废人</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in filtered" :key="row.id" :class="{ 'row-voided': !row.active }">
          <td>{{ row.loftName }}</td>
          <td>{{ row.sealNumber }}</td>
          <td>
            <span class="badge" :class="row.active ? 'badge-raw' : 'badge-cured'">
              {{ row.active ? '未作废' : '已作废' }}
            </span>
            <span v-if="row.bound" class="hint">（已用）</span>
            <span v-else-if="row.active" class="hint">（待用）</span>
          </td>
          <td>{{ fmt(row.lockedAt) }}</td>
          <td>{{ row.lockedBy }}</td>
          <td>{{ row.rollCode || '—' }}</td>
          <td>{{ fmt(row.voidedAt) }}</td>
          <td>{{ row.voidedBy || '—' }}</td>
          <td>
            <button
              v-if="row.active"
              class="btn secondary"
              type="button"
              :disabled="busy || !isAdmin"
              :title="isAdmin ? '作废后该号可再发' : '仅管理员可作废'"
              @click="voidLock(row)"
            >作废</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!filtered.length" class="hint">没有符合筛选条件的铅封锁。</p>
  </div>
</template>

<style scoped>
.seal-filter {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}
.filter-on {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.row-voided {
  opacity: 0.6;
}
</style>
