<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { formatDateOrDash } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { getLot } from '@/features/production'
import { getProductionOrder } from '@/features/production'
import { getMadeItemFileBlob } from '@/features/made-items'
import { useMadeItemFilesStore } from '@/features/made-items'
import { useMadeItemPicturesStore } from '@/features/made-items'
import { useShownPicture } from '@/shared/pictures'
import { MadeItemThumbnailCell } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { useBlobObjectUrl } from '@/shared/composables/useBlobObjectUrl'
import FilesSection from '@/shared/components/files/FilesSection.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import { ProductionOrderCompletionDialog } from '@/features/production'
import { ManufacturingAssessmentDialog } from '@/features/production'
import { useProductionOrderFilesStore } from '@/features/production'
import { getProductionOrderFileBlob } from '@/features/production'
import { productionOrderStatusSeverity } from '@/features/production'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import QaTaskControls from '../components/QaTaskControls.vue'
import QaTaskInspectionPanel from '../components/QaTaskInspectionPanel.vue'
import QaTaskResultsPanel from '../components/QaTaskResultsPanel.vue'
import { EVIDENCE_FILES } from '../utils/evidenceFiles'

import type { LotResponse, LotStepResponse } from '@/features/production'
import type { ProductionOrderResponse } from '@/features/production'
import type { MadeItemFile } from '@/features/made-items'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

// Loads the three.js viewer only for items with a mesh.
const MeshViewer = defineAsyncComponent(() => import('@/core/components/MeshViewer.vue'))

const { t } = useI18n()
const { localize } = useLocalizedText()
const route = useRoute()
const router = useRouter()
const hostStore = useHostStore()
const { format: madeItemLabel } = useMadeItemLabel()
const { hasPermission } = usePermissions()
const madeItemFiles = useMadeItemFilesStore()
const evidenceStore = useProductionOrderFilesStore()
const inspectionMethodsStore = useInspectionMethodsStore()

const orderId = computed(() => Number(route.params.orderId))

const order = ref<ProductionOrderResponse | null>(null)
const lot = ref<LotResponse | null>(null)
const loading = ref(false)
const loadError = ref(false)

const canRecord = computed(() => hasPermission(Permission.WRITE_INSPECTIONS))

// ── Load ──────────────────────────────────────────────────────────────

async function load(): Promise<void> {
  loading.value = true
  loadError.value = false
  order.value = null
  lot.value = null
  try {
    const fetched = await getProductionOrder(orderId.value)
    order.value = fetched
    lot.value = await getLot(fetched.lot_id)
    if (hostStore.storageEnabled) {
      void madeItemFiles.fetchFiles(fetched.made_item_id)
    }
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

watch(orderId, load, { immediate: true })

const pageHeading = computed(() =>
  order.value ? order.value.production_order_number : t('productionQa.detail.title'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })

// ── Derived task context ──────────────────────────────────────────────

const position = computed(
  () => lot.value?.positions?.find((p) => p.id === order.value?.lot_position_id) ?? null,
)
const steps = computed<LotStepResponse[]>(() => position.value?.steps ?? [])
const inspectionStep = computed(() => steps.value.find((s) => s.role === 'inspection') ?? null)

// The step carries only the method's name, so its description and label
// colours come from the shared method list, which includes archived methods.
if (inspectionMethodsStore.items.length === 0) void inspectionMethodsStore.refresh()
const inspectionMethod = computed(
  () =>
    inspectionMethodsStore.getById(inspectionStep.value?.inspection_method_id) ??
    null,
)

// A non-inspection order reached through this route is a wrong link rather
// than an error. Say so instead of rendering a QA page for milling.
const isInspectionTask = computed(() => inspectionStep.value !== null)

const requiresEvidence = computed(
  () => inspectionStep.value?.inspection_method_requires_evidence === true,
)
const evidenceFiles = computed(() =>
  order.value ? evidenceStore.getFiles(order.value.id) : [],
)
const hasEvidence = computed(() =>
  evidenceFiles.value.some((f) => f.category === 'measurement_report'),
)
const evidenceBlocking = computed(() => requiresEvidence.value && !hasEvidence.value)

const isTerminal = computed(
  () => order.value?.status === 'completed' || order.value?.status === 'canceled',
)
// can_start is false for an order that already runs, so only a queued or
// paused order is actually waiting on its upstream step.
const isWaitingOnUpstream = computed(
  () =>
    (order.value?.status === 'queued' || order.value?.status === 'paused') &&
    order.value.can_start !== true,
)

// ── Part picture and files (mesh / drawing) ────────────────────────────

const partFiles = computed(() =>
  order.value ? madeItemFiles.getFiles(order.value.made_item_id) : [],
)
const shownPicture = useShownPicture(
  useMadeItemPicturesStore(),
  () => order.value?.made_item_id ?? null,
)
const meshFile = computed(() => partFiles.value.find((f) => f.category === 'mesh') ?? null)
const drawingFile = computed(() => partFiles.value.find((f) => f.category === 'drawing') ?? null)

const meshBlob = ref<Blob | null>(null)
const meshLoading = ref(false)

watch(
  () => meshFile.value?.id ?? null,
  async (fileId) => {
    meshBlob.value = null
    if (fileId === null || !meshFile.value || !order.value) return
    meshLoading.value = true
    try {
      meshBlob.value = await getMadeItemFileBlob(order.value.made_item_id, fileId)
    } finally {
      meshLoading.value = false
    }
  },
  { immediate: true },
)

// The PDF drawing is previewed through an object URL in the browser viewer.
const { url: drawingUrl, loading: drawingLoading } = useBlobObjectUrl(
  () => drawingFile.value?.id ?? null,
  (fileId) => (order.value ? getMadeItemFileBlob(order.value.made_item_id, fileId) : null),
)

interface PreviewTarget {
  name: string
  mimeType: string
  fetch: () => Promise<Blob>
}

const previewFile = ref<PreviewTarget | null>(null)
const showFilePreview = ref(false)

function openFile(file: MadeItemFile | null): void {
  const itemId = order.value?.made_item_id
  if (!file || itemId === undefined) return
  previewFile.value = {
    name: file.file_name,
    mimeType: file.mime_type,
    fetch: () => getMadeItemFileBlob(itemId, file.id),
  }
  showFilePreview.value = true
}

function openPicture(): void {
  const picture = shownPicture.value
  if (!picture) return
  previewFile.value = { name: picture.name, mimeType: 'image/*', fetch: picture.fetchImage }
  showFilePreview.value = true
}

async function fetchPreviewBlob(): Promise<Blob> {
  const target = previewFile.value
  if (!target) throw new Error('No file selected')
  return target.fetch()
}

// Refetches only the order after a start, so the viewers and files keep
// their state. A failed refetch falls back to the full load, which shows
// the load error.
async function refreshOrder(): Promise<void> {
  try {
    order.value = await getProductionOrder(orderId.value)
  } catch {
    await load()
  }
}

// ── Recording ─────────────────────────────────────────────────────────

const showCompletion = ref(false)
// The completion that completes the order asks for the assessment, as on
// the queue board, so inspection steps feed the same data.
const assessmentTarget = ref<ProductionOrderResponse | null>(null)
const showAssessment = ref(false)

async function onRecorded(updated: ProductionOrderResponse): Promise<void> {
  showCompletion.value = false
  if (updated.status === 'completed') {
    assessmentTarget.value = updated
    showAssessment.value = true
  }
  await load()
}

function goBack(): void {
  void router.push('/production/qa')
}
</script>

<template>
  <PageLayout>
    <template #info>
      <InfoBar>
        <template v-if="order">
          <span class="order-number">{{ order.production_order_number }}</span>
          <span class="info-sep" />
          <Tag
            :value="t(`productionQueue.status.${order.status}`)"
            :severity="productionOrderStatusSeverity[order.status]"
          />
          <template v-if="lot">
            <span class="info-sep" />
            <span class="info-muted">{{
              madeItemLabel(lot.made_item_part_number, lot.made_item_revision)
            }}</span>
            <span class="info-sep" />
            <span class="info-muted">{{ lot.made_item_article_name }}</span>
          </template>
          <template v-if="inspectionStep">
            <span class="info-sep" />
            <Tag
              :value="localize(inspectionStep.inspection_method_name)"
              icon="mdi mdi-clipboard-check-outline"
              :severity="inspectionMethod ? undefined : 'secondary'"
              :style="
                inspectionMethod
                  ? {
                      color: inspectionMethod.label_font_color,
                      backgroundColor: inspectionMethod.label_color,
                    }
                  : undefined
              "
            />
          </template>
        </template>
        <template v-else-if="loading">
          <Skeleton width="9rem" height="1.5rem" border-radius="1rem" />
          <Skeleton width="5.5rem" height="1.5rem" border-radius="1rem" />
        </template>
      </InfoBar>
    </template>

    <template #controls>
      <QaTaskControls
        :order="order"
        :steps="steps"
        :lot="lot"
        @back="goBack"
        @record="showCompletion = true"
        @started="refreshOrder"
      />
    </template>

    <div v-if="loading" class="state-center" />
    <div v-else-if="loadError" class="state-center state-message">
      <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('productionQa.detail.loadError') }}</span>
    </div>
    <div v-else-if="order && !isInspectionTask" class="state-center state-message">
      <i class="mdi mdi-clipboard-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('productionQa.detail.notAnInspection') }}</span>
    </div>

    <div v-else-if="order && lot" class="qa-grid">
      <!-- Left: the part and what it is measured against. -->
      <div class="qa-column">
        <Panel :header="t('productionQa.detail.part')">
          <div class="part-layout">
            <button
              v-if="hostStore.storageEnabled"
              type="button"
              class="part-thumb"
              @click="openPicture"
            >
              <MadeItemThumbnailCell
                :item-id="order.made_item_id"
                :item-name="lot.made_item_article_name"
                size="6rem"
                no-image-icon="mdi mdi-image-off-outline"
              />
            </button>
            <div class="detail-grid">
              <div class="field">
                <span class="field-label">{{ t('productionQa.detail.material') }}</span>
                <span class="field-value">{{
                  lot.made_item_material || getEmptyPlaceholder()
                }}</span>
              </div>
              <div class="field">
                <span class="field-label">{{ t('productionQa.detail.lot') }}</span>
                <RouterLink :to="`/production/lots/${lot.id}`" class="field-value">
                  {{ lot.lot_number }}
                </RouterLink>
              </div>
              <div class="field">
                <span class="field-label">{{ t('productionQa.detail.position') }}</span>
                <span class="field-value">{{
                  position
                    ? `${position.sequence} / ${lot.positions?.length ?? 0}`
                    : getEmptyPlaceholder()
                }}</span>
              </div>
              <div class="field">
                <span class="field-label">{{ t('productionQa.detail.project') }}</span>
                <span class="field-value">{{ lot.project_number || getEmptyPlaceholder() }}</span>
              </div>
              <div class="field">
                <span class="field-label">{{ t('productionQa.detail.quantity') }}</span>
                <span class="field-value">{{ order.quantity_completed }} / {{ order.quantity }}</span>
              </div>
              <div class="field">
                <span class="field-label">{{ t('productionQa.detail.planned') }}</span>
                <span class="field-value">{{ formatDateOrDash(order.planned_start) }}</span>
              </div>
            </div>
          </div>
        </Panel>

        <!-- 3D and the drawing are what a QA engineer actually measures
             against, so they get real estate rather than a file row. -->
        <Panel v-if="hostStore.storageEnabled" :header="t('productionQa.detail.model')">
          <div v-if="meshLoading" class="viewer-box viewer-state">
            <ProgressSpinner style="width: 2rem" />
          </div>
          <!-- Wrapped, since MeshViewer fills its parent's height. -->
          <div v-else-if="meshBlob" class="viewer-box">
            <MeshViewer :blob="meshBlob" />
          </div>
          <div v-else class="viewer-box viewer-state viewer-empty">
            <i class="mdi mdi-cube-outline" aria-hidden="true" />
            <span>{{ t('productionQa.detail.noModel') }}</span>
          </div>
        </Panel>

        <Panel v-if="hostStore.storageEnabled" :header="t('productionQa.detail.drawing')">
          <template #icons>
            <Button
              v-if="drawingFile"
              icon="mdi mdi-arrow-expand"
              size="small"
              text
              rounded
              severity="secondary"
              v-tooltip.top.focus="t('productionQa.detail.openDrawing')"
              :aria-label="t('productionQa.detail.openDrawing')"
              @click="openFile(drawingFile)"
            />
          </template>
          <div v-if="drawingLoading" class="viewer-box viewer-state">
            <ProgressSpinner style="width: 2rem" />
          </div>
          <div
            v-else-if="drawingUrl"
            class="viewer-box drawing-box"
            role="button"
            tabindex="0"
            :aria-label="t('productionQa.detail.openDrawing')"
            @click="openFile(drawingFile)"
            @keydown.enter="openFile(drawingFile)"
            @keydown.space.prevent="openFile(drawingFile)"
          >
            <iframe
              :src="`${drawingUrl}#toolbar=0&navpanes=0&scrollbar=0&view=FitV`"
              :title="t('productionQa.detail.drawing')"
              class="drawing-frame"
              tabindex="-1"
            />
          </div>
          <div v-else class="viewer-box viewer-state viewer-empty">
            <i class="mdi mdi-file-pdf-box" aria-hidden="true" />
            <span>{{ t('productionQa.detail.noDrawing') }}</span>
          </div>
        </Panel>
      </div>

      <!-- Right: the inspection, its results and its evidence. -->
      <div class="qa-column">
        <QaTaskInspectionPanel
          :order="order"
          :inspection-step="inspectionStep"
          :method="inspectionMethod"
          :can-record="canRecord"
          :evidence-blocking="evidenceBlocking"
          :waiting-on-upstream="isWaitingOnUpstream"
        />

        <QaTaskResultsPanel :completions="order.completions ?? []" />

        <Panel v-if="hostStore.storageEnabled" :header="t('productionQa.detail.evidence')">
          <FilesSection
            :item-id="order.id"
            :files-store="evidenceStore"
            :multi="EVIDENCE_FILES"
            :can-edit="canRecord && !isTerminal"
            allow-capture
            :fetch-blob="getProductionOrderFileBlob"
          />
        </Panel>
      </div>
    </div>
  </PageLayout>

  <ProductionOrderCompletionDialog
    v-model:visible="showCompletion"
    :order="order"
    :steps="steps"
    @recorded="onRecorded"
  />

  <ManufacturingAssessmentDialog v-model:visible="showAssessment" :order="assessmentTarget" />

  <FilePreviewDialog
    v-if="previewFile"
    v-model:visible="showFilePreview"
    :filename="previewFile.name"
    :mime-type="previewFile.mimeType"
    :fetch-blob="fetchPreviewBlob"
  />
</template>

<style scoped lang="scss">
// ── Info bar ──────────────────────────────────────────────────────────

.order-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

// ── State screens ─────────────────────────────────────────────────────

.state-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: var(--space-3);
}

.state-message {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-md);

  .state-icon {
    font-size: var(--font-size-3xl);
  }
}

// ── Panel grid ────────────────────────────────────────────────────────

// Fills the page's content card and scrolls inside it. The gap equals the
// card's own padding, so the gutters between panels match the outer ones.
.qa-grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: var(--space-2);

  @media (max-width: $bp-lg) {
    grid-template-columns: minmax(0, 1fr);
  }
}

.qa-column {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

// ── Fields ────────────────────────────────────────────────────────────

.part-layout {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
}

.part-thumb {
  display: inline-flex;
  flex-shrink: 0;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
}

.detail-grid {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-value {
  font-size: var(--font-size-sm);
}

// ── Viewers ───────────────────────────────────────────────────────────

.viewer-box {
  display: flex;
  height: 20rem;
}

.viewer-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

.viewer-empty {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);

  i {
    font-size: var(--font-size-3xl);
  }
}

.drawing-box {
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.drawing-frame {
  width: 100%;
  height: 100%;
  border: 0;
  pointer-events: none;
}
</style>
