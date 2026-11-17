import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  getProductDeviceKinds,
  getProductDeviceOptions,
} from '../api/productDeviceResourcesApi'
import type {
  ProductDeviceKind,
  ProductDeviceOption,
  ProductDeviceOptionCategory,
} from '../types/productDevice'

/**
 * The lists product devices pick from, loaded whole and archived entries
 * included, so existing devices still resolve an entry that was archived
 * after they chose it. Pickers offer live entries only, in the order kept
 * by hand in the resources section.
 */
export const useProductDeviceResourcesStore = defineStore('productDeviceResources', () => {
  const options = ref<ProductDeviceOption[]>([])
  const kinds = ref<ProductDeviceKind[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  let pending: Promise<void> | null = null

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) return
    if (pending) return pending
    loading.value = true
    pending = (async () => {
      const [loadedOptions, loadedKinds] = await Promise.all([
        getProductDeviceOptions(),
        getProductDeviceKinds(),
      ])
      options.value = loadedOptions
      kinds.value = loadedKinds
      loaded.value = true
    })().finally(() => {
      pending = null
      loading.value = false
    })
    return pending
  }

  function optionsOf(
    category: ProductDeviceOptionCategory,
    includeArchived = false,
  ): ProductDeviceOption[] {
    return options.value.filter(
      (option) => option.category === category && (includeArchived || !option.archived),
    )
  }

  const optionById = computed(() => new Map(options.value.map((option) => [option.id, option])))
  const kindById = computed(() => new Map(kinds.value.map((kind) => [kind.id, kind])))
  const liveKinds = computed(() => kinds.value.filter((kind) => !kind.archived))

  function upsertOption(option: ProductDeviceOption): void {
    const index = options.value.findIndex((o) => o.id === option.id)
    if (index === -1) options.value.push(option)
    else options.value.splice(index, 1, option)
  }

  function upsertKind(kind: ProductDeviceKind): void {
    const index = kinds.value.findIndex((k) => k.id === kind.id)
    if (index === -1) kinds.value.push(kind)
    else kinds.value.splice(index, 1, kind)
  }

  /** Replaces one category with its entries as the server ordered them after a move. */
  function replaceOptionsOf(
    category: ProductDeviceOptionCategory,
    ordered: ProductDeviceOption[],
  ): void {
    options.value = [...options.value.filter((option) => option.category !== category), ...ordered]
  }

  function replaceKinds(ordered: ProductDeviceKind[]): void {
    kinds.value = ordered
  }

  return {
    options,
    kinds,
    loaded,
    loading,
    load,
    optionsOf,
    optionById,
    kindById,
    liveKinds,
    upsertOption,
    upsertKind,
    replaceOptionsOf,
    replaceKinds,
  }
})
