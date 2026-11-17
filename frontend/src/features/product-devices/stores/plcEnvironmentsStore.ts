import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getPlcEnvironments } from '../api/plcEnvironmentsApi'
import type { PlcEnvironment } from '../types/productDevice'

/**
 * The PLC environments, loaded whole and archived ones included, so a
 * product still shows an environment archived after it was chosen. The
 * product's picker offers live ones only.
 */
export const usePlcEnvironmentsStore = defineStore('plcEnvironments', () => {
  const environments = ref<PlcEnvironment[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  let pending: Promise<void> | null = null

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) return
    if (pending) return pending
    loading.value = true
    pending = getPlcEnvironments()
      .then((result) => {
        environments.value = result
        loaded.value = true
      })
      .finally(() => {
        pending = null
        loading.value = false
      })
    return pending
  }

  const liveEnvironments = computed(() => environments.value.filter((e) => !e.archived))
  const defaultEnvironment = computed(() => environments.value.find((e) => e.is_default && !e.archived) ?? null)
  const byId = computed(() => new Map(environments.value.map((e) => [e.id, e])))

  // Marking one as the default takes the mark from the others, as the server does.
  function upsert(environment: PlcEnvironment): void {
    const others = environment.is_default
      ? environments.value.map((e) => (e.id === environment.id ? e : { ...e, is_default: false }))
      : environments.value
    const index = others.findIndex((e) => e.id === environment.id)
    environments.value = index === -1 ? [...others, environment] : others.map((e, i) => (i === index ? environment : e))
  }

  return { environments, loaded, loading, load, liveEnvironments, defaultEnvironment, byId, upsert }
})
