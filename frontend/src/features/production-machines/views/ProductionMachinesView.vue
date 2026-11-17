<script setup lang="ts">
import { ref } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ProductionMachinesControls from '../components/ProductionMachinesControls.vue'
import ProductionMachinesViews from '../components/ProductionMachinesViews.vue'
import ProductionMachinesTable from '../components/ProductionMachinesTable.vue'
import ProductionMachineFormDialog from '../components/ProductionMachineFormDialog.vue'
import MachineCalendarDialog from '../components/MachineCalendarDialog.vue'
import DefaultCalendarDialog from '../components/DefaultCalendarDialog.vue'
import MachineDowntimeFormDialog from '../components/MachineDowntimeFormDialog.vue'
import MachineDowntimesDialog from '../components/MachineDowntimesDialog.vue'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'

const tableRef = ref<InstanceType<typeof ProductionMachinesTable> | null>(null)
const showFormDialog = ref(false)
const editingMachine = ref<ProductionMachineResponse | null>(null)
const showCalendarDialog = ref(false)
const calendarMachine = ref<ProductionMachineResponse | null>(null)
const showDefaultCalendarDialog = ref(false)
const showDowntimeFormDialog = ref(false)
const downtimeMachine = ref<ProductionMachineResponse | null>(null)
const showDowntimesDialog = ref(false)

function openCreate(): void {
  editingMachine.value = null
  showFormDialog.value = true
}

function openEdit(machine: ProductionMachineResponse): void {
  editingMachine.value = machine
  showFormDialog.value = true
}

function openCalendar(machine: ProductionMachineResponse): void {
  calendarMachine.value = machine
  showCalendarDialog.value = true
}

function openAddDowntime(machine: ProductionMachineResponse): void {
  downtimeMachine.value = machine
  showDowntimeFormDialog.value = true
}

function onSaved(): void {
  tableRef.value?.refresh()
}
</script>

<template>

  <PageLayout>
    <template #controls>
      <ProductionMachinesControls
        @create="openCreate"
        @default-calendar="showDefaultCalendarDialog = true"
        @downtimes="showDowntimesDialog = true"
      />
    </template>
    <template #views>
      <ProductionMachinesViews />
    </template>

    <ProductionMachinesTable
      ref="tableRef"
      @edit="openEdit"
      @manage-calendar="openCalendar"
      @add-downtime="openAddDowntime"
    />
  </PageLayout>

  <ProductionMachineFormDialog
    v-model:visible="showFormDialog"
    :machine="editingMachine"
    @saved="onSaved"
  />
  <MachineCalendarDialog v-model:visible="showCalendarDialog" :machine="calendarMachine" />
  <DefaultCalendarDialog v-model:visible="showDefaultCalendarDialog" />
  <MachineDowntimeFormDialog
    v-model:visible="showDowntimeFormDialog"
    :machine="downtimeMachine"
    @saved="onSaved"
  />
  <MachineDowntimesDialog v-model:visible="showDowntimesDialog" />
</template>
