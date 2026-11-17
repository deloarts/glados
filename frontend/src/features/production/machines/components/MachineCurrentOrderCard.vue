<script setup lang="ts">
// The machine detail page's hero card, readable from across the shop floor.
// Display-only, since the page's ControlsBar owns the actions; it fetches its
// own supplementary data (files, mesh, source item, demand).
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateTimeOrDash, formatISODate } from '@/core/utils/dates'
import { formatDecimal } from '@/core/utils/numbers'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useHostStore } from '@/core/host/stores/hostStore'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import {
  MadeItemDetailDialog,
  MadeItemDetailFields,
  MadeItemThumbnailCell,
  getMadeItemFileBlob,
  useMadeItemFilesStore,
  useMadeItemLabel,
  useMadeItemPicturesStore,
} from '@/features/made-items'
import {
  SourceItemDetailFields,
  getSourceItemDemand,
  getSourceItemFileBlob,
  useSourceItemFilesStore,
} from '@/features/source-items'
import { useSourceItemsAllocationsStore } from '../../source-item-demands/stores/sourceItemsAllocationsStore'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useShownPicture } from '@/shared/pictures'
import { formatMinutesDuration } from '../../utils/lotStepDisplay'
import { useSourceMaterialCache } from '../../queue/composables/useSourceMaterialCache'
import {
  productionOrderPrioritySeverity,
  productionOrderStatusSeverity,
} from '../../utils/productionOrderStatus'
import MachineFileStrip from './MachineFileStrip.vue'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { LotResponse } from '../../types/productionLotsResponse'
import type { MachineStripFile } from '../types/machineFileStrip'
import type { MadeItemFile, MadeItemResponse } from '@/features/made-items'
import type {
  SourceItemDemandResponse,
  SourceItemDemandSummaryResponse,
  SourceItemFile,
} from '@/features/source-items'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'

// Loads the three.js viewer only for items that have a mesh file.
const MeshViewer = defineAsyncComponent(() => import('@/core/components/MeshViewer.vue'))

const props = defineProps<{
  // Normally one order, a list for merge, split or reassignment edge cases.
  // Empty means idle.
  orders: ProductionOrderResponse[]
  madeItem: MadeItemResponse | null
  itemLoading: boolean
  processMethod: string | null
  // Null while loading or after a failed fetch; dependent sections degrade.
  lot: LotResponse | null
}>()

const { t } = useI18n()
const { openLotDetail } = useLotDetail()
const { format: madeItemLabel } = useMadeItemLabel()
const hostStore = useHostStore()
const { resolve: resolveSourceItem } = useSourceMaterialCache()

// Further concurrent orders get a compact row instead of the hero.
const primary = computed(() => props.orders[0] ?? null)
const extraOrders = computed(() => props.orders.slice(1))

// Setup is not scoped to one order, so every order sharing a position quotes
// the position's full setup estimate, like buildTimeComparison().
const primaryEstimatedSetupMinutes = computed<number | null>(() => {
  const steps =
    props.lot?.positions?.find((p) => p.id === primary.value?.lot_position_id)?.steps ?? []
  if (steps.length === 0) return null
  const total = steps.reduce((sum, s) => sum + (s.estimated_setup_minutes ?? 0), 0)
  return total > 0 ? total : null
})

// The order's total plus the setup share in brackets, omitted when zero.
const primaryEstimatedDisplay = computed(() => {
  if (!primary.value) return ''
  const base = formatMinutesDuration(primary.value.estimated_duration_minutes)
  const setupMinutes = primaryEstimatedSetupMinutes.value
  if (setupMinutes === null) return base
  return `${base} ${t('production.machineDetail.current.estimatedSetup', {
    minutes: formatMinutesDuration(setupMinutes),
  })}`
})

const showMadeItemDetail = ref(false)

// ── Item media + files ──────────────────────────────────────────────────
// The card lives across order transitions, so fetches are watchers keyed on
// the primary order's made_item_id.
const madeItemFilesStore = useMadeItemFilesStore()
const madeItemId = computed(() => primary.value?.made_item_id ?? null)

watch(
  madeItemId,
  (id) => {
    if (id !== null && hostStore.storageEnabled) void madeItemFilesStore.fetchFiles(id)
  },
  { immediate: true },
)

const madeItemFiles = computed<MadeItemFile[]>(() =>
  madeItemId.value !== null ? madeItemFilesStore.getFiles(madeItemId.value) : [],
)

const meshFile = computed(
  () => madeItemFiles.value.find((f) => f.category === 'mesh') ?? null,
)
const meshBlob = ref<Blob | null>(null)
const meshLoading = ref(false)

watch(
  () => meshFile.value?.id ?? null,
  async (fileId) => {
    meshBlob.value = null
    if (fileId === null || madeItemId.value === null) return
    meshLoading.value = true
    try {
      meshBlob.value = await getMadeItemFileBlob(madeItemId.value, fileId)
    } finally {
      meshLoading.value = false
    }
  },
  { immediate: true },
)

function fetchMadeItemFileBlob(file: MachineStripFile): Promise<Blob> {
  if (madeItemId.value === null) return Promise.reject(new Error('No made item.'))
  return getMadeItemFileBlob(madeItemId.value, file.id)
}

// Once the hero shows the mesh, the strip must not repeat it.
const heroShowsMesh = computed(() => meshLoading.value || meshBlob.value !== null)

const shownPicture = useShownPicture(useMadeItemPicturesStore(), () => madeItemId.value)

// Every file, but never the mesh while the hero shows it.
const madeItemStripFiles = computed<MadeItemFile[]>(() =>
  madeItemFiles.value.filter(
    (f) => !(heroShowsMesh.value && meshFile.value && f.id === meshFile.value.id),
  ),
)

// ── Hero media tile preview ──────────────────────────────────────────────
// Opens the mesh while the hero shows it, else the picture shown for the
// item; without either the tile is not interactive.
interface HeroPreview {
  name: string
  mimeType: string
  fetch: () => Promise<Blob>
}

const heroPreviewFile = computed<HeroPreview | null>(() => {
  const mesh = meshFile.value
  if (heroShowsMesh.value && mesh) {
    return { name: mesh.file_name, mimeType: mesh.mime_type, fetch: () => fetchMadeItemFileBlob(mesh) }
  }
  const picture = shownPicture.value
  return picture ? { name: picture.name, mimeType: 'image/*', fetch: picture.fetchImage } : null
})
const showHeroPreview = ref(false)

function openHeroPreview(): void {
  if (heroPreviewFile.value) showHeroPreview.value = true
}

function fetchHeroPreviewBlob(): Promise<Blob> {
  const preview = heroPreviewFile.value
  if (!preview) return Promise.reject(new Error('No file selected.'))
  return preview.fetch()
}

// ── Source item (raw material, stock case) ──────────────────────────────
// Stock sources only; bought or made sources fall back to the lot's
// denormalized source label in the template.
const sourceItem = computed(() => resolveSourceItem(props.lot?.source_item_id ?? null))

const sourceItemFilesStore = useSourceItemFilesStore()
const sourceItemId = computed(() => sourceItem.value?.id ?? null)

watch(
  sourceItemId,
  (id) => {
    if (id !== null && hostStore.storageEnabled) void sourceItemFilesStore.fetchFiles(id)
  },
  { immediate: true },
)

const sourceItemFiles = computed<SourceItemFile[]>(() =>
  sourceItemId.value !== null ? sourceItemFilesStore.getFiles(sourceItemId.value) : [],
)

// The source item has no hero tile, so every file goes in the strip.
const sourceItemStripFiles = sourceItemFiles

function fetchSourceItemFileBlob(file: MachineStripFile): Promise<Blob> {
  if (sourceItemId.value === null) return Promise.reject(new Error('No source item.'))
  return getSourceItemFileBlob(sourceItemId.value, file.id)
}

// Delivered, then expected, then ordered.
const sourceOrderStateLabel = computed(() => {
  const lot = props.lot
  if (!lot?.source_order_id) return null
  if (lot.source_delivery_date) {
    return t('productionQueue.card.sourceDelivered', { date: formatISODate(lot.source_delivery_date) })
  }
  if (lot.source_expected_delivery_date) {
    return t('productionQueue.card.sourceExpected', {
      date: formatISODate(lot.source_expected_delivery_date),
    })
  }
  return t('productionQueue.card.sourceOrdered', { number: lot.source_order_number })
})

// The demand behind the lot's raw-material source with its allocation
// summary, fetched here because nothing else on the page needs it.
const sourceItemsAllocationsStore = useSourceItemsAllocationsStore()
const sourceItemDemand = ref<SourceItemDemandResponse | null>(null)

watch(
  () => props.lot?.input_demand_id ?? null,
  async (demandId) => {
    sourceItemDemand.value = null
    if (demandId === null) return
    try {
      sourceItemDemand.value = await getSourceItemDemand(demandId)
      await sourceItemsAllocationsStore.fetchSummaries([demandId])
    } catch {
      // Fails soft so a blip does not sink the rest of the card.
      sourceItemDemand.value = null
    }
  },
  { immediate: true },
)

const sourceItemDemandSummary = computed<SourceItemDemandSummaryResponse | null>(() =>
  sourceItemDemand.value
    ? (sourceItemsAllocationsStore.getSummary(sourceItemDemand.value.id) ?? null)
    : null,
)
</script>

<template>
  <Panel :header="t('production.machineDetail.current.title')">
    <div class="card-scroll-body">
      <div v-if="!primary" class="empty-note">
        {{ t('production.machineDetail.current.empty') }}
      </div>

      <template v-else>
        <div class="order-hero">
          <div class="hero-header">
            <div class="hero-media">
              <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- a button only while there is something to open, the role and tabindex are bound to that -->
              <div
                class="hero-media-tile"
                :class="{ 'hero-media-tile--clickable': !!heroPreviewFile }"
                :role="heroPreviewFile ? 'button' : undefined"
                :tabindex="heroPreviewFile ? 0 : undefined"
                v-tooltip.top="
                  heroPreviewFile
                    ? t('production.lots.detail.record.item.openFile', {
                        name: heroPreviewFile.name,
                      })
                    : undefined
                "
                :aria-label="
                  heroPreviewFile
                    ? t('production.lots.detail.record.item.openFile', {
                        name: heroPreviewFile.name,
                      })
                    : undefined
                "
                @click="openHeroPreview"
                @keydown.enter="openHeroPreview"
                @keydown.space.prevent="openHeroPreview"
              >
                <template v-if="meshLoading || meshBlob">
                  <i v-if="meshLoading" class="mdi mdi-loading mdi-spin" aria-hidden="true" />
                  <MeshViewer v-else-if="meshBlob" :blob="meshBlob" />
                </template>
                <MadeItemThumbnailCell
                  v-else
                  :item-id="primary.made_item_id"
                  :item-name="primary.made_item_part_number"
                  size="9rem"
                  no-image-icon="mdi mdi-image-outline"
                />
              </div>
            </div>

            <div class="hero-header-main">
              <div class="hero-headline-row">
                <span class="hero-headline">{{
                  madeItemLabel(primary.made_item_part_number, primary.made_item_revision)
                }}</span>
                <Button
                  icon="mdi mdi-eye-outline"
                  text
                  rounded
                  size="small"
                  severity="secondary"
                  :disabled="!madeItem"
                  v-tooltip.top="t('production.machineDetail.current.openItem')"
                  :aria-label="t('production.machineDetail.current.openItem')"
                  @click="showMadeItemDetail = true"
                />
                <i
                  v-if="primary.pinned"
                  class="mdi mdi-pin hero-pin"
                  v-tooltip.top="t('production.machineDetail.current.pinned')"
                />
              </div>

              <div class="hero-identity">
                <div class="identity-field">
                  <span class="identity-label">{{
                    t('production.lots.detail.record.project.number')
                  }}</span>
                  <RouterLink
                    v-if="lot"
                    class="identity-value identity-link"
                    :to="`/workspace/projects/${lot.project_id}`"
                  >
                    {{ lot.project_number }}
                  </RouterLink>
                  <span v-else class="identity-value">{{ getEmptyPlaceholder() }}</span>
                </div>
                <div class="identity-field">
                  <span class="identity-label">{{ t('production.machineDetail.current.lot') }}</span>
                  <a
                    class="identity-value identity-link lot-link"
                    role="button"
                    tabindex="0"
                    @click="openLotDetail(primary.lot_id)"
                    @keydown.enter="openLotDetail(primary.lot_id)"
                  >
                    {{ primary.lot_number }}
                  </a>
                </div>
                <div class="identity-field">
                  <span class="identity-label">{{
                    t('production.lots.detail.record.execution.orderDialog.position')
                  }}</span>
                  <span class="identity-value">{{
                    t('production.lots.detail.record.execution.orderDialog.positionValue', {
                      sequence: primary.lot_position_sequence,
                      count: primary.lot_position_count,
                    })
                  }}</span>
                </div>
              </div>

              <div class="hero-tags">
                <Tag
                  :value="t(`productionQueue.status.${primary.status}`)"
                  :severity="productionOrderStatusSeverity[primary.status]"
                />
                <Tag
                  :value="t(`productionQueue.priority.${primary.priority}`)"
                  :severity="productionOrderPrioritySeverity[primary.priority]"
                />
              </div>
            </div>
          </div>

          <div class="hero-meta">
            <div class="meta-row">
              <span class="meta-label">{{ t('productionQueue.card.quantity') }}</span>
              <span class="meta-value">{{ primary.quantity_completed }} / {{ primary.quantity }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">{{
                t('production.lots.detail.record.execution.estimated')
              }}</span>
              <span class="meta-value">{{ primaryEstimatedDisplay }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">{{ t('productionQueue.card.processMethod') }}</span>
              <span class="meta-value">{{ processMethod ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">{{ t('production.machineDetail.current.orderNumber') }}</span>
              <span class="meta-value">{{ primary.production_order_number }}</span>
            </div>
            <div v-if="primary.actual_start" class="meta-row">
              <span class="meta-label">{{ t('production.machineDetail.current.started') }}</span>
              <span class="meta-value">{{ formatDateTimeOrDash(primary.actual_start) }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">{{
                t('production.lots.detail.record.execution.startedBy')
              }}</span>
              <span class="meta-value">{{
                primary.started_operator?.full_name ?? getEmptyPlaceholder()
              }}</span>
            </div>
          </div>

          <div v-if="primary.note" class="hero-note">{{ primary.note }}</div>
        </div>

        <div v-if="extraOrders.length" class="extra-orders">
          <span class="section-label">{{ t('production.machineDetail.current.additional') }}</span>
          <div v-for="order in extraOrders" :key="order.id" class="extra-order-row">
            <span class="extra-order-number">{{ order.production_order_number }}</span>
            <Tag
              :value="t(`productionQueue.status.${order.status}`)"
              :severity="productionOrderStatusSeverity[order.status]"
            />
            <span class="extra-order-qty">{{ order.quantity_completed }} / {{ order.quantity }}</span>
          </div>
        </div>

        <Divider />

        <MachineFileStrip
          v-if="madeItemStripFiles.length"
          class="item-file-strip"
          :files="madeItemStripFiles"
          :fetch-blob="fetchMadeItemFileBlob"
        />

        <div class="item-section">
          <span class="section-label">{{ t('production.machineDetail.item.title') }}</span>
          <Skeleton v-if="itemLoading" height="12rem" />
          <MadeItemDetailFields v-else-if="madeItem" :item="madeItem" />
        </div>

        <template v-if="lot">
          <Divider />

          <div class="source-section">
            <span class="section-label">{{ t('production.lots.detail.record.source.title') }}</span>

            <template v-if="lot.source_item_id != null">
              <Skeleton v-if="!sourceItem" height="8rem" />

              <template v-else>
                <MachineFileStrip
                  v-if="sourceItemStripFiles.length"
                  :files="sourceItemStripFiles"
                  :fetch-blob="fetchSourceItemFileBlob"
                />

                <SourceItemDetailFields :item="sourceItem" />

                <template v-if="sourceOrderStateLabel || lot.input_demand_id">
                  <Divider />

                  <div class="source-procurement">
                    <span class="section-label">{{
                      t('production.machineDetail.source.orderDetails')
                    }}</span>

                    <div v-if="sourceOrderStateLabel" class="field">
                      <span class="field-label">{{
                        t('production.lots.detail.record.orderDetail.orderStatus')
                      }}</span>
                      <span class="field-value">{{ sourceOrderStateLabel }}</span>
                    </div>

                    <template v-if="lot.input_demand_id">
                      <div class="field">
                        <span class="field-label">{{
                          t('production.lots.detail.record.sourceDemand.status')
                        }}</span>
                        <Tag
                          v-if="sourceItemDemand"
                          class="demand-status-tag"
                          :value="t(`sourceItems.demands.status.${sourceItemDemand.status}`)"
                          :severity="DEMAND_STATUS_SEVERITY[sourceItemDemand.status]"
                        />
                        <span v-else class="field-value">{{ getEmptyPlaceholder() }}</span>
                      </div>

                      <div v-if="sourceItemDemandSummary" class="demand-summary-grid">
                        <div class="field">
                          <span class="field-label">{{
                            t('production.lots.detail.record.sourceDemand.ordered')
                          }}</span>
                          <span class="field-value">{{
                            formatDecimal(sourceItemDemandSummary.ordered)
                          }}</span>
                        </div>
                        <div class="field">
                          <span class="field-label">{{
                            t('production.lots.detail.record.sourceDemand.inTransit')
                          }}</span>
                          <span class="field-value">{{
                            formatDecimal(sourceItemDemandSummary.in_transit)
                          }}</span>
                        </div>
                        <div class="field">
                          <span class="field-label">{{
                            t('production.lots.detail.record.sourceDemand.delivered')
                          }}</span>
                          <span class="field-value">{{
                            formatDecimal(sourceItemDemandSummary.delivered)
                          }}</span>
                        </div>
                        <div class="field">
                          <span class="field-label">{{
                            t('production.machineDetail.source.remaining')
                          }}</span>
                          <span class="field-value">{{
                            formatDecimal(sourceItemDemandSummary.remaining)
                          }}</span>
                        </div>
                      </div>
                    </template>
                  </div>
                </template>
              </template>
            </template>

            <div v-else class="source-fallback">
              <span class="field-value">{{ lot.source_label || getEmptyPlaceholder() }}</span>
              <span v-if="lot.source_sublabel" class="field-sublabel">{{ lot.source_sublabel }}</span>
            </div>
          </div>
        </template>
      </template>
    </div>

    <FilePreviewDialog
      v-if="heroPreviewFile"
      v-model:visible="showHeroPreview"
      :filename="heroPreviewFile.name"
      :mime-type="heroPreviewFile.mimeType"
      :fetch-blob="fetchHeroPreviewBlob"
    />
    <MadeItemDetailDialog v-model:visible="showMadeItemDetail" :item="madeItem" />
  </Panel>
</template>

<style scoped lang="scss">
.empty-note {
  padding: var(--space-2) 0;
}

.order-hero {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.hero-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
}

.hero-media {
  flex-shrink: 0;
}

.hero-media-tile {
  width: 9rem;
  height: 9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--p-border-radius-sm);
  border: 1px solid var(--p-content-border-color);
  overflow: hidden;

  &--clickable {
    cursor: pointer;

    &:hover {
      border-color: var(--p-primary-color);
    }

    &:focus-visible {
      outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
      outline-offset: 2px;
    }
  }
}

.hero-header-main {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.hero-headline-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.hero-headline {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  line-height: 1.15;
}

.hero-pin {
  color: var(--p-orange-500, var(--p-primary-color));
  font-size: var(--font-size-lg);
}

.hero-identity {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.identity-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.identity-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.identity-value {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.identity-link {
  color: var(--p-primary-color);
  text-decoration: none;
  cursor: pointer;
  width: fit-content;

  &:hover {
    text-decoration: underline;
  }
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.hero-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.meta-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--font-size-md);
}

.meta-label {
  color: var(--p-text-muted-color);
  min-width: 8rem;
  flex-shrink: 0;
}

.meta-value {
  font-weight: 600;
  min-width: 0;
}

.hero-note {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  white-space: pre-wrap;
}

.extra-orders {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-top: var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
}

.extra-order-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.extra-order-number {
  font-weight: 600;
}

.extra-order-qty {
  color: var(--p-text-muted-color);
  margin-left: auto;
}

.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

// A sibling of .item-section rather than inside a spaced flex column, so it
// needs its own top spacing.
.item-file-strip {
  padding-top: var(--space-3);
}

.item-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
}

.source-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
}

.source-fallback {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
}

.source-procurement {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

// Stops the flex column's cross-axis stretch so the tag hugs its text.
.demand-status-tag {
  align-self: flex-start;
}

.demand-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(6rem, 1fr));
  gap: var(--space-2) var(--space-4);
}

.field {
  min-width: 0;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

// Wide screens only: the shared detail grids get a third column here via
// :deep(), since the shared components also render at narrow widths. The
// min-width: 0 lets long values wrap instead of overflowing their track.
@media (min-width: $bp-2xl) {
  .item-section :deep(.detail-grid),
  .source-section :deep(.detail-grid) {
    grid-template-columns: repeat(3, 1fr);
  }

  .item-section :deep(.field),
  .source-section :deep(.field),
  .item-section :deep(.field-value-row),
  .source-section :deep(.field-value-row) {
    min-width: 0;
  }

  .item-section :deep(.field-value),
  .source-section :deep(.field-value) {
    overflow-wrap: break-word;
  }
}
</style>
