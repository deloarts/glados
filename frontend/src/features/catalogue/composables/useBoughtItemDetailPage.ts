import { computed, onScopeDispose, ref, watch } from 'vue'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useLiveStore } from '@/core/realtime/liveStore'
import { LiveResource } from '@/core/realtime/resources'
import { createSection, runSection } from '../composables/useCatalogueItemSections'
import { aggregateItemUsage } from '../utils/itemUsage'
import { getOrders } from '@/features/orders'
import { getProjects } from '@/features/projects'

import type { Ref } from 'vue'
import type { LiveSignal } from '@/core/realtime/types'
import type { ItemDemandRow, ItemOrderRow, ItemUsageDemand, ItemUsageRow } from '../types/itemDetail'
import type { ProjectResponse } from '@/features/projects'
import { getBoughtItemChangelog, getBoughtItems, getDemands } from '@/features/bought-items'
import type {
  BoughtItemChangelogEntry,
  BoughtItemDemandResponse,
  BoughtItemResponse,
} from '@/features/bought-items'

/** Demands and orders page at 200; the changelog is not paginated. */
const SECTION_LIMIT = 200
/** `/projects?ids=` accepts at most 200 ids, so lookups are chunked. */
const PROJECT_CHUNK_SIZE = 200

/**
 * Everything the bought item detail page renders: the item and its demands,
 * orders, changelog and usage sections, each loading and failing on its own.
 * A standalone page owns its record instead of going through a list store.
 * itemId is a ref so a same-route navigation to another id reloads.
 */
export function useBoughtItemDetailPage(itemId: Ref<number>) {
  const live = useLiveStore()

  const item = ref<BoughtItemResponse | null>(null)
  /**
   * The item's own loading flag; each section tracks its own state, so a
   * slow section never blocks it.
   */
  const loading = ref(true)
  const notFound = ref(false)
  const loadError = ref(false)

  const demands = createSection<BoughtItemDemandResponse[]>([])
  const orders = createSection<ItemOrderRow[]>([])
  const changelog = createSection<BoughtItemChangelogEntry[]>([])
  const projectsById = ref(new Map<number, ProjectResponse>())

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

  // The "used in" card inherits the state of both fetches it draws on.
  const usageLoading = computed(() => demands.loading || orders.loading)
  const usageError = computed(() => demands.error || orders.error)

  async function loadItem(quiet: boolean): Promise<void> {
    // Captured before the await, so a stale response never overwrites a
    // newer id's state.
    const id = itemId.value
    if (!quiet) loading.value = true
    try {
      const page = await getBoughtItems({ id, limit: 1 })
      if (itemId.value !== id) return
      const found = page.items[0] ?? null
      item.value = found
      notFound.value = !found
      loadError.value = false
    } catch {
      if (itemId.value !== id) return
      // The list endpoint never 404s for an unknown id, so a thrown request is a
      // genuine load failure.
      loadError.value = true
    } finally {
      // Only the current id may clear the flag, or a stale response would end
      // a newer request's loading early.
      if (!quiet && itemId.value === id) loading.value = false
    }
  }

  async function loadDemands(opts?: { quiet?: boolean }): Promise<void> {
    const id = itemId.value
    await runSection(
      demands,
      () =>
        getDemands({
          item_id: id,
          limit: SECTION_LIMIT,
          order_by: 'created',
          order_dir: 'desc',
        }),
      { limit: SECTION_LIMIT, quiet: opts?.quiet, isCurrent: () => itemId.value === id },
    )
  }

  async function loadOrdersOnly(opts?: { quiet?: boolean }): Promise<void> {
    const id = itemId.value
    // The orders endpoint pages by order, not by this item's lines, so
    // truncation comes from the raw page and is applied after a successful run.
    let truncated: boolean | null = null
    await runSection(
      orders,
      async () => {
        const page = await getOrders({
          bought_item_id: id,
          limit: SECTION_LIMIT,
          order_by: 'created',
          order_dir: 'desc',
        })
        truncated = page.items.length >= SECTION_LIMIT
        const rows: ItemOrderRow[] = []
        for (const order of page.items) {
          for (const orderItem of order.items ?? []) {
            if (orderItem.bought_item_id === id) rows.push({ order, orderItem })
          }
        }
        return rows
      },
      { quiet: opts?.quiet, isCurrent: () => itemId.value === id },
    )
    if (truncated !== null && itemId.value === id) orders.truncated = truncated
  }

  async function loadChangelog(opts?: { quiet?: boolean }): Promise<void> {
    const id = itemId.value
    await runSection(changelog, () => getBoughtItemChangelog(id), {
      quiet: opts?.quiet,
      isCurrent: () => itemId.value === id,
    })
  }

  /**
   * Projects of the fetched demands and orders, for the "used in" card's
   * product column. A failed chunk only blanks those products.
   */
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
    try {
      const map = new Map<number, ProjectResponse>()
      for (let i = 0; i < idList.length; i += PROJECT_CHUNK_SIZE) {
        const chunk = idList.slice(i, i + PROJECT_CHUNK_SIZE)
        const page = await getProjects({ ids: chunk, limit: chunk.length })
        for (const project of page.items) map.set(project.id, project)
      }
      // The same staleness guard as every other section.
      if (itemId.value === id) projectsById.value = map
    } catch {
      // Keep the previous map rather than losing the whole card.
    }
  }

  /**
   * Targeted refresh for the demands card/dialogs (edit, status change,
   * a live demand signal).
   */
  async function reloadDemands(opts?: { quiet?: boolean }): Promise<void> {
    await loadDemands(opts)
  }

  /**
   * Refreshes the orders and the projects lookup, since a changed order
   * line can bring a new project.
   */
  async function reloadOrders(opts?: { quiet?: boolean }): Promise<void> {
    await loadOrdersOnly(opts)
    await loadProjects()
  }

  /**
   * Reloads the item and every section in parallel, then the projects
   * lookup once demands and orders settled.
   */
  async function reload(opts?: { quiet?: boolean }): Promise<void> {
    const quiet = opts?.quiet ?? false
    await Promise.all([
      loadItem(quiet),
      loadDemands({ quiet }),
      loadOrdersOnly({ quiet }),
      loadChangelog({ quiet }),
    ])
    await loadProjects()
  }

  // ── Live sync for demands and orders signals ──────────────────────────
  //
  // A signal matters when it creates a record (which may belong here), is a
  // bulk signal without usable ids, or names a record already shown.

  function isRelevant(signal: LiveSignal, contains: (id: number) => boolean): boolean {
    return signal.action === 'created' || signal.action === 'bulk' || contains(signal.id)
  }

  const unsubscribeDemands = live.on(LiveResource.BOUGHT_ITEM_DEMANDS, (signal) => {
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

  // `immediate` starts the first load during setup and reloads on an id
  // change. `flush: 'sync'` resets in the same tick, so the new item never
  // briefly shows the previous item's sections.
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
    orders,
    changelog,
    demandRows,
    usageRows,
    usageLoading,
    usageError,
    sectionLimit: SECTION_LIMIT,
    reload,
    reloadDemands,
    reloadOrders,
  }
}
