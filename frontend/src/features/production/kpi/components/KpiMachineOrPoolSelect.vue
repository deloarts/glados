<script setup lang="ts">
// One filter Select for machines and pools, keyed "machine:<id>" or
// "pool:<id>", or null for all.
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'

import { getMachinePools, getProductionMachines } from '@/features/production-machines'

import type { MachinePoolResponse, ProductionMachineResponse } from '@/features/production-machines'

interface Props {
  inputId?: string
  disabled?: boolean
}

defineProps<Props>()

const model = defineModel<string | null>({ default: null })

const { t } = useI18n()

const machines = ref<ProductionMachineResponse[]>([])
const pools = ref<MachinePoolResponse[]>([])
const loading = ref(false)

interface TargetOption {
  key: string
  label: string
}

interface TargetGroup {
  key: 'pools' | 'machines'
  label: string
  items: TargetOption[]
}

const groups = ref<TargetGroup[]>([])

function buildGroups(): TargetGroup[] {
  const allGroups: TargetGroup[] = [
    {
      key: 'pools',
      label: t('productionKpi.filters.poolsGroup'),
      items: [...pools.value]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((pool) => ({ key: `pool:${pool.id}`, label: pool.name })),
    },
    {
      key: 'machines',
      label: t('productionKpi.filters.machinesGroup'),
      items: [...machines.value]
        .sort((a, b) => a.internal_name.localeCompare(b.internal_name))
        .map((machine) => ({ key: `machine:${machine.id}`, label: machine.internal_name })),
    },
  ]
  return allGroups.filter((group) => group.items.length > 0)
}

onMounted(async () => {
  loading.value = true
  try {
    const [machinesResult, poolsResult] = await Promise.all([
      getProductionMachines({ limit: API_MAX_PAGE_SIZE }),
      getMachinePools({ limit: API_MAX_PAGE_SIZE }),
    ])
    machines.value = machinesResult.items
    pools.value = poolsResult.items
    groups.value = buildGroups()
  } finally {
    loading.value = false
  }
})

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    :input-id="inputId"
    v-model="model"
    :options="groups"
    option-label="label"
    option-value="key"
    option-group-label="label"
    option-group-children="items"
    :loading="loading"
    :disabled="disabled"
    :placeholder="t('productionKpi.filters.machineOrPoolPlaceholder')"
    show-clear
    filter
    fluid
  />
</template>
