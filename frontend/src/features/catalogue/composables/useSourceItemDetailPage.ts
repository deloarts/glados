import { computed, onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { aggregateItemUsage } from '../utils/itemUsage'
import { createSection, runSection } from '../composables/useCatalogueItemSections'
import type { ItemDemandRow, ItemOrderRow, ItemUsageDemand, ItemUsageRow } from '../types/itemDetail'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useLiveStore } from '@/core/realtime/liveStore'
import { LiveResource } from '@/core/realtime/resources'
import type { LiveSignal } from '@/core/realtime/types'
import { getOrders } from '@/features/orders'
import { getProjects } from '@/features/projects'
import type { ProjectResponse } from '@/features/projects'
import { getSourceItemChangelog, getSourceItemDemands, sourceItemsApi } from '@/features/source-items'
import type {
  SourceItemChangelogEntry,
  SourceItemDemandResponse,
  SourceItemResponse,
} from '@/features/source-items'



const SECTION_LIMIT = 200
/** The server caps project ids at 200 per request, so larger sets are chunked. */
const PROJECT_CHUNK_SIZE = 200

/**
 * Everything the source item detail page shows: the item and its demands,
 * orders, changelog and usage sections. Each section loads and fails on its
 * own, so one bad section never blanks the page. itemId is a ref so a route
 * param change reloads without remounting the view.
 */
export function useSourceItemDetailPage(itemId: Ref<number>) {
  const live = useLiveStore()

  const item = ref<SourceItemResponse | null>(null)
  const loading = ref(true)
  const notFound = ref(false)
  const loadError = ref(false)

  const demands = createSection<SourceItemDemandResponse[]>([])
  const orders = createSection<ItemOrderRow[]>([])
  const changelog = createSection<SourceItemChangelogEntry[]>([])

  const projectsById = ref<Map<number, ProjectResponse>>(new Map())

  async function loadItem(opts: { quiet?: boolean } = {}): Promise<void> {
    const quiet = opts.quiet ?? false
    // Captured so a stale response never overwrites a newer id's state.
    const id = itemId.value
    if (!quiet) loading.value = true
    try {
      const page = await sourceItemsApi.list({ id, limit: 1 })
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

  async function loadDemandsSection(opts: { quiet?: boolean } = {}): Promise<void> {
    const id = itemId.value
    await runSection(
      demands,
      () =>
        getSourceItemDemands({
          source_item_id: id,
          limit: SECTION_LIMIT,
          order_by: 'created',
          order_dir: 'desc',
        }),
      { limit: SECTION_LIMIT, quiet: opts.quiet, isCurrent: () => itemId.value === id },
    )
  }

  async function loadOrdersSection(opts: { quiet?: boolean } = {}): Promise<void> {
    const id = itemId.value
    // The orders endpoint pages by order, not by this item's lines, so
    // truncation comes from the raw order page after runSection settles.
    let truncated: boolean | null = null
    await runSection(
      orders,
      async () => {
        const page = await getOrders({
          source_item_id: id,
          limit: SECTION_LIMIT,
          order_by: 'created',
          order_dir: 'desc',
        })
        truncated = page.items.length >= SECTION_LIMIT
        const rows: ItemOrderRow[] = []
        for (const order of page.items) {
          for (const orderItem of order.items ?? []) {
            if (orderItem.source_item_id === id) rows.push({ order, orderItem })
          }
        }
        return rows
      },
      { quiet: opts.quiet, isCurrent: () => itemId.value === id },
    )
    if (truncated !== null && itemId.value === id) orders.truncated = truncated
  }

  async function loadChangelogSection(opts: { quiet?: boolean } = {}): Promise<void> {
    const id = itemId.value
    await runSection(changelog, () => getSourceItemChangelog(id), {
      quiet: opts.quiet,
      isCurrent: () => itemId.value === id,
    })
  }

  /** Distinct project ids from demands and orders, chunked per request. */
  async function loadProjects(): Promise<void> {
    const id = itemId.value
    const ids = new Set<number>()
    for (const demand of demands.data) ids.add(demand.project_id)
    for (const row of orders.data) {
      const projectId = row.orderItem.project_id
      if (projectId !== null && projectId !== undefined) ids.add(projectId)
    }

    const idList = [...ids]
    if (idList.length === 0) {
      if (itemId.value === id) projectsById.value = new Map()
      return
    }

    const map = new Map<number, ProjectResponse>()
    for (let i = 0; i < idList.length; i += PROJECT_CHUNK_SIZE) {
      const chunk = idList.slice(i, i + PROJECT_CHUNK_SIZE)
      try {
        const page = await getProjects({ ids: chunk, limit: chunk.length })
        for (const project of page.items) map.set(project.id, project)
      } catch {
        // Best-effort: unresolved projects show the "no product" placeholder.
      }
    }
    if (itemId.value === id) projectsById.value = map
  }

  /**
   * Reloads only the demands section. A demand edit never changes its
   * project, so projects stay valid.
   */
  async function reloadDemands(opts: { quiet?: boolean } = {}): Promise<void> {
    await loadDemandsSection(opts)
  }

  /**
   * Reloads the orders section and then projects, since a new order can
   * reference an unseen project.
   */
  async function reloadOrders(opts: { quiet?: boolean } = {}): Promise<void> {
    await loadOrdersSection(opts)
    await loadProjects()
  }

  /**
   * Full reload: the item and every section in parallel, then the projects
   * lookup once demands and orders have settled.
   */
  async function reload(opts: { quiet?: boolean } = {}): Promise<void> {
    await Promise.all([
      loadItem(opts),
      loadDemandsSection(opts),
      loadOrdersSection(opts),
      loadChangelogSection(opts),
    ])
    await loadProjects()
  }

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
      extra: demand.lot_number,
    })),
  )

  const usageRows = computed<ItemUsageRow[]>(() => {
    const usageDemands: ItemUsageDemand[] = demands.data.map((demand) => ({
      projectId: demand.project_id,
      projectNumber: demand.project_number,
      projectCustomer: demand.project_customer,
      projectDescription: demand.project_description,
      projectStatus: demand.project_status,
      quantity: demand.quantity,
      status: demand.status,
    }))
    return aggregateItemUsage(usageDemands, orders.data, projectsById.value)
  })

  // The usage card is derived from demands and orders, so it inherits their
  // state.
  const usageLoading = computed(() => demands.loading || orders.loading)
  const usageError = computed(() => demands.error || orders.error)

  // ── Live sync ────────────────────────────────────────────────────────
  // 'bulk' reloads like 'created', since it carries no id to check.

  function isRelevant(signal: LiveSignal, contains: (id: number) => boolean): boolean {
    return signal.action === 'created' || signal.action === 'bulk' || contains(signal.id)
  }

  const unsubscribeDemands = live.on(LiveResource.SOURCE_ITEM_DEMANDS, (signal) => {
    if (isRelevant(signal, (id) => demands.data.some((demand) => demand.id === id))) {
      void reloadDemands({ quiet: true })
    }
  })

  const unsubscribeOrders = live.on(LiveResource.ORDERS, (signal) => {
    if (isRelevant(signal, (id) => orders.data.some((row) => row.order.id === id))) {
      void reloadOrders({ quiet: true })
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
  })

  // Loads immediately and on every id change. flush: 'sync' clears the old
  // item's state in the same tick, so the new page never shows the previous
  // item's sections.
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
        demands.data = []
        demands.error = false
        demands.truncated = false
        demands.loading = false
        orders.data = []
        orders.error = false
        orders.truncated = false
        orders.loading = false
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

  return {
    item,
    loading,
    notFound,
    loadError,
    demands,
    demandRows,
    orders,
    changelog,
    usageRows,
    usageLoading,
    usageError,
    sectionLimit: SECTION_LIMIT,
    reload,
    reloadDemands,
    reloadOrders,
  }
}
