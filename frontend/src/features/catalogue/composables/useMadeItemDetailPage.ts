import { computed, onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useLiveStore } from '@/core/realtime/liveStore'
import { LiveResource } from '@/core/realtime/resources'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { createSection, runSection } from '../composables/useCatalogueItemSections'
import { aggregateItemUsage } from '../utils/itemUsage'
import { getOrders } from '@/features/orders'
import { getLots } from '@/features/production'
import { getProjects } from '@/features/projects'

import type { LiveSignal } from '@/core/realtime/types'
import type { ItemDemandRow, ItemOrderRow, ItemUsageDemand } from '../types/itemDetail'
import type { LotSummaryResponse } from '@/features/production'
import type { ProjectResponse } from '@/features/projects'
import {
  getMadeItemChangelog,
  getMadeItemDemands,
  getMadeItemRevisions,
  getMadeItems,
  useMadeItemLabel,
} from '@/features/made-items'
import type {
  MadeItemChangelogEntry,
  MadeItemDemandResponse,
  MadeItemResponse,
  MadeItemRevisionsResponse,
} from '@/features/made-items'

/**
 * Row limit per section, which shows a truncation notice when reached.
 * Also the chunk size of the project batch lookup.
 */
const SECTION_LIMIT = 200

/**
 * Everything the made item detail page needs: the item and its demands,
 * orders, lots, changelog and projects. Each section loads and fails on its
 * own, so one bad section never blanks the page. A standalone page owns its
 * record instead of going through a list store.
 */
export function useMadeItemDetailPage(itemId: Ref<number>) {
  const hostStore = useHostStore()
  const { format: madeItemLabel } = useMadeItemLabel()
  const live = useLiveStore()

  const item = ref<MadeItemResponse | null>(null)
  const loading = ref(true)
  const notFound = ref(false)
  const loadError = ref(false)

  // Backs the revision Select, which shows plain text while this is null.
  const revisions = ref<MadeItemRevisionsResponse | null>(null)

  const demands = createSection<MadeItemDemandResponse[]>([])
  const orders = createSection<ItemOrderRow[]>([])
  const lots = createSection<LotSummaryResponse[]>([])
  const changelog = createSection<MadeItemChangelogEntry[]>([])

  // Rebuilt on every load and read only through usageRows, so it needs no
  // section state.
  const projectsById = ref<Map<number, ProjectResponse>>(new Map())

  // ── Item ────────────────────────────────────────────────────────────
  // Fetched through the list endpoint with an id filter; an empty page means
  // not found.

  async function loadItem(quiet: boolean): Promise<void> {
    // Captured so a stale response never overwrites a newer id's state.
    const id = itemId.value
    if (!quiet) loading.value = true
    try {
      const page = await getMadeItems({ id, limit: 1 })
      if (itemId.value !== id) return
      const found = page.items[0] ?? null
      item.value = found
      notFound.value = found === null
      loadError.value = false
    } catch {
      if (itemId.value !== id) return
      loadError.value = true
    } finally {
      // A stale response must not end a newer request's loading state.
      if (!quiet && itemId.value === id) loading.value = false
    }
  }

  async function loadRevisions(): Promise<void> {
    const id = itemId.value
    try {
      const result = await getMadeItemRevisions(id)
      if (itemId.value !== id) return
      revisions.value = result
    } catch {
      if (itemId.value !== id) return
      revisions.value = null
    }
  }

  // ── Sections ────────────────────────────────────────────────────────

  async function loadDemands(opts?: { quiet?: boolean }): Promise<void> {
    const id = itemId.value
    await runSection(
      demands,
      async () => {
        const page = await getMadeItemDemands({
          made_item_id: id,
          limit: SECTION_LIMIT,
          order_by: 'created',
          order_dir: 'desc',
        })
        return page.items
      },
      { limit: SECTION_LIMIT, quiet: opts?.quiet, isCurrent: () => itemId.value === id },
    )
  }

  async function loadOrders(opts?: { quiet?: boolean }): Promise<void> {
    // The orders endpoint pages by order, not by this item's lines, so
    // truncation comes from the raw page and is applied after a successful run.
    const id = itemId.value
    let truncated: boolean | null = null
    await runSection(
      orders,
      async () => {
        const page = await getOrders({
          made_item_id: id,
          limit: SECTION_LIMIT,
          order_by: 'created',
          order_dir: 'desc',
        })
        truncated = page.items.length >= SECTION_LIMIT
        const rows: ItemOrderRow[] = []
        for (const order of page.items) {
          for (const orderItem of order.items ?? []) {
            if (orderItem.made_item_id === id) rows.push({ order, orderItem })
          }
        }
        return rows
      },
      { quiet: opts?.quiet, isCurrent: () => itemId.value === id },
    )
    if (truncated !== null && itemId.value === id) orders.truncated = truncated
  }

  async function loadLots(opts?: { quiet?: boolean }): Promise<void> {
    // Without production planning there is no Lots card.
    if (!hostStore.productionPlanningEnabled) return
    const id = itemId.value
    await runSection(
      lots,
      async () => {
        const page = await getLots({
          made_item_id: id,
          limit: SECTION_LIMIT,
          order_by: 'created',
          order_dir: 'desc',
        })
        return page.items
      },
      { limit: SECTION_LIMIT, quiet: opts?.quiet, isCurrent: () => itemId.value === id },
    )
  }

  async function loadChangelog(opts?: { quiet?: boolean }): Promise<void> {
    const id = itemId.value
    await runSection(changelog, () => getMadeItemChangelog(id), {
      quiet: opts?.quiet,
      isCurrent: () => itemId.value === id,
    })
  }

  // Rebuilt from the project ids the loaded demands and orders reference.
  async function loadProjects(): Promise<void> {
    const id = itemId.value
    const ids = new Set<number>()
    for (const demand of demands.data) ids.add(demand.project_id)
    for (const row of orders.data) {
      const projectId = row.orderItem.project_id
      if (projectId !== null && projectId !== undefined) ids.add(projectId)
    }
    if (ids.size === 0) {
      if (itemId.value === id) projectsById.value = new Map()
      return
    }

    const idList = [...ids]
    const chunks: number[][] = []
    for (let i = 0; i < idList.length; i += SECTION_LIMIT) {
      chunks.push(idList.slice(i, i + SECTION_LIMIT))
    }

    const pages = await Promise.all(
      chunks.map((chunk) => getProjects({ ids: chunk, limit: chunk.length })),
    )
    if (itemId.value !== id) return
    const next = new Map<number, ProjectResponse>()
    for (const page of pages) {
      for (const project of page.items) next.set(project.id, project)
    }
    projectsById.value = next
  }

  // ── Derived rows ────────────────────────────────────────────────────

  const demandRows = computed<ItemDemandRow[]>(() =>
    demands.data.map((demand) => ({
      id: demand.id,
      status: demand.status,
      quantity: demand.quantity,
      unit: demand.unit,
      highPriority: demand.high_priority,
      projectNumber: demand.project_number,
      projectCustomer: demand.project_customer,
      desiredDeliveryDate: demand.desired_delivery_date,
      created: demand.created,
      creatorName: demand.creator?.full_name ?? getEmptyPlaceholder(),
      creator: demand.creator,
      extra: demand.is_alteration
        ? madeItemLabel(demand.alteration_of_made_item_part_number, demand.alteration_of_made_item_revision)
        : undefined,
    })),
  )

  const usageRows = computed(() =>
    aggregateItemUsage(
      demands.data.map(
        (demand): ItemUsageDemand => ({
          projectId: demand.project_id,
          projectNumber: demand.project_number,
          projectCustomer: demand.project_customer,
          projectDescription: demand.project_description,
          projectStatus: demand.project_status,
          quantity: demand.quantity,
          status: demand.status,
        }),
      ),
      orders.data,
      projectsById.value,
    ),
  )

  // The usage card draws on demands and orders, so it inherits their state.
  const usageLoading = computed(() => demands.loading || orders.loading)
  const usageError = computed(() => demands.error || orders.error)

  // ── Reload orchestration ────────────────────────────────────────────

  async function reloadDemands(opts?: { quiet?: boolean }): Promise<void> {
    await loadDemands(opts)
  }

  // A new order can reference an unseen project that usageRows needs.
  async function reloadOrders(opts?: { quiet?: boolean }): Promise<void> {
    await loadOrders(opts)
    await loadProjects()
  }

  async function reloadLots(opts?: { quiet?: boolean }): Promise<void> {
    await loadLots(opts)
  }

  async function reload(opts?: { quiet?: boolean }): Promise<void> {
    const quiet = opts?.quiet ?? false
    await Promise.all([
      loadItem(quiet),
      loadDemands({ quiet }),
      loadOrders({ quiet }),
      loadLots({ quiet }),
      loadChangelog({ quiet }),
      loadRevisions(),
    ])
    await loadProjects()
  }

  // flush: 'sync' clears the old item's state in the same tick as the id
  // change, so the new page never shows the previous item's sections.
  watch(
    itemId,
    (newId, oldId) => {
      // Leaving the route fires this sync watcher before unmount, when the id
      // param is gone and the id is NaN. Nothing should load then.
      if (!Number.isInteger(newId)) return
      if (oldId !== undefined && newId !== oldId) {
        item.value = null
        notFound.value = false
        loadError.value = false
        revisions.value = null
        demands.data = []
        demands.error = false
        demands.truncated = false
        demands.loading = false
        orders.data = []
        orders.error = false
        orders.truncated = false
        orders.loading = false
        lots.data = []
        lots.error = false
        lots.truncated = false
        lots.loading = false
        changelog.data = []
        changelog.error = false
        changelog.truncated = false
        changelog.loading = false
        projectsById.value = new Map()
      }
      void reload()
    },
    { immediate: true, flush: 'sync' },
  )

  // ── Live sync ────────────────────────────────────────────────────────
  // The item itself has no live resource. 'bulk' reloads like 'created',
  // since it carries no id to check.

  function isRelevant(signal: LiveSignal, contains: (id: number) => boolean): boolean {
    return signal.action === 'created' || signal.action === 'bulk' || contains(signal.id)
  }

  const unsubscribeDemands = live.on(LiveResource.MADE_ITEM_DEMANDS, (signal) => {
    if (isRelevant(signal, (id) => demands.data.some((d) => d.id === id))) {
      void reloadDemands({ quiet: true })
    }
  })

  const unsubscribeOrders = live.on(LiveResource.ORDERS, (signal) => {
    if (isRelevant(signal, (id) => orders.data.some((row) => row.order.id === id))) {
      void reloadOrders({ quiet: true })
    }
  })

  const unsubscribeLots = live.on(LiveResource.PRODUCTION_LOTS, (signal) => {
    if (!hostStore.productionPlanningEnabled) return
    if (isRelevant(signal, (id) => lots.data.some((lot) => lot.id === id))) {
      void reloadLots({ quiet: true })
    }
  })

  // Recovers whatever was missed while disconnected.
  watch(
    () => live.reconnectCount,
    () => void reload({ quiet: true }),
  )

  onScopeDispose(() => {
    unsubscribeDemands()
    unsubscribeOrders()
    unsubscribeLots()
  })

  return {
    item,
    loading,
    notFound,
    loadError,
    revisions,
    demands,
    orders,
    lots,
    changelog,
    demandRows,
    usageRows,
    usageLoading,
    usageError,
    sectionLimit: SECTION_LIMIT,
    reload,
    reloadDemands,
    reloadOrders,
    reloadLots,
  }
}
