<script setup lang="ts">
import { ref } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import MachinePoolsControls from '../components/MachinePoolsControls.vue'
import MachinePoolsViews from '../components/MachinePoolsViews.vue'
import MachinePoolsTable from '../components/MachinePoolsTable.vue'
import MachinePoolFormDialog from '../components/MachinePoolFormDialog.vue'

import type { MachinePoolResponse } from '../types/machinePoolsResponse'

const tableRef = ref<InstanceType<typeof MachinePoolsTable> | null>(null)
const showFormDialog = ref(false)
const editingPool = ref<MachinePoolResponse | null>(null)

function openCreate(): void {
  editingPool.value = null
  showFormDialog.value = true
}

function openEdit(pool: MachinePoolResponse): void {
  editingPool.value = pool
  showFormDialog.value = true
}

function onSaved(): void {
  tableRef.value?.refresh()
}
</script>

<template>

  <PageLayout>
    <template #controls>
      <MachinePoolsControls @create="openCreate" />
    </template>
    <template #views>
      <MachinePoolsViews />
    </template>

    <MachinePoolsTable ref="tableRef" @edit="openEdit" />
  </PageLayout>

  <MachinePoolFormDialog v-model:visible="showFormDialog" :pool="editingPool" @saved="onSaved" />
</template>
