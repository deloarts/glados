<script setup lang="ts">
// /catalogue/made-items/:id, the made item detail page.
// useMadeItemDetailPage owns the data.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useClipboard } from '@/core/composables/useClipboard'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useHostStore } from '@/core/host/stores/hostStore'
import { usePageTitle } from '@/core/composables/usePageTitle'

import CatalogueItemChangelogCard from '@/shared/components/changelog/ChangelogCard.vue'
import CatalogueItemDemandsCard from '../components/CatalogueItemDemandsCard.vue'
import CatalogueItemDetailGrid from '../components/CatalogueItemDetailGrid.vue'
import CatalogueItemFilesCard from '../components/CatalogueItemFilesCard.vue'
import CatalogueItemLotsCard from '../components/CatalogueItemLotsCard.vue'
import CatalogueItemMedia from '../components/CatalogueItemMedia.vue'
import CatalogueItemOrdersCard from '../components/CatalogueItemOrdersCard.vue'
import CatalogueItemUsageCard from '../components/CatalogueItemUsageCard.vue'
import { useCatalogueItemFiles } from '../composables/useCatalogueItemFiles'
import { useCatalogueItemPrint } from '../composables/useCatalogueItemPrint'
import { OrderDetailDialog } from '@/features/orders'
import { MadeItemDemandDetailDialog } from '@/features/production'
import { useLotDetail } from '@/shared/composables/useLotDetail'

import { useShownPicture } from '@/shared/pictures'
import { useMadeItemDetailPage } from '../composables/useMadeItemDetailPage'

import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import {
  getMadeItemFileBlob,
  MadeItemDemandCreateForm,
  MadeItemDetailDialog,
  MadeItemDetailFields,
  MadeItemLinkedSourceCard,
  MadeItemPicturesSection,
  MadeItemProcessGrouping,
  MadeItemThumbnailCell,
  useMadeItemFilesStore,
  useMadeItemLabel,
  useMadeItemPicturesStore,
} from '@/features/made-items'
import type { MadeItemDemandResponse } from '@/features/made-items'

// The Item card shows thumbnail, image, mesh and drawing; the Files card
// lists the rest. Uploads stay in the edit dialog.
const FILES_CARD_CATEGORIES = ['dxf', 'step', 'pdf']

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { hasPermission } = usePermissions()
const { copyToClipboard } = useClipboard()
const hostStore = useHostStore()
const { format: madeItemLabel } = useMadeItemLabel()
const lotDialog = useLotDetail()

// A computed, since a successor link navigates this route to another id.
const itemId = computed(() => Number(route.params.id))

const {
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
  sectionLimit,
  reload,
  reloadDemands,
  reloadOrders,
  reloadLots,
} = useMadeItemDetailPage(itemId)

watchLoadingBar(loading)

const pageHeading = computed(() =>
  item.value ? madeItemLabel(item.value.part_number, item.value.revision) : t('pageTitles.madeItemDetail'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })

const canEdit = computed(() => hasPermission(Permission.WRITE_MADE_ITEMS))
const canCreateDemand = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
const { missing } = useMissingPermission()

// A plain push is enough; the page's id watcher reloads everything.
function onRevisionSelect(id: number): void {
  if (id === itemId.value) return
  void router.push(`/catalogue/made-items/${id}`)
}

// Says plainly when an older revision is shown, instead of leaving it to a
// 409 on save.
const currentRevisionSummary = computed(() => {
  const current = item.value
  if (!current || !revisions.value) return null
  return revisions.value.items.find((r) => r.id === current.id) ?? null
})

const isNotNewest = computed(() => {
  if (!hostStore.madeItemPartNumbers.revision.only_newest_editable) return false
  return currentRevisionSummary.value !== null && currentRevisionSummary.value.is_newest === false
})

const newestRevisionLabel = computed(
  () => revisions.value?.items.find((r) => r.is_newest)?.revision ?? '',
)

// ── Item card media ──────────────────────────────────────────────────

const {
  itemFiles,
  meshFile,
  fetchItemFileBlob,
  filesCardRows,
  filesCategoryLabel,
  filesCardLoading,
  deletingFileId,
  onDeleteFile,
} = useCatalogueItemFiles({
  itemId,
  item,
  filesStore: useMadeItemFilesStore(),
  fetchBlob: getMadeItemFileBlob,
  filesCardCategories: FILES_CARD_CATEGORIES,
  categoryLabelPrefix: 'madeItems.catalogue.files.categories',
})

const picturesStore = useMadeItemPicturesStore()
const shownPicture = useShownPicture(picturesStore, () => item.value?.id ?? null)

// Only made items have a drawing category.
const drawingFile = computed(() => itemFiles.value.find((f) => f.category === 'drawing') ?? null)

// Only demands with an alteration row add the alteration column.
const hasAlterationDemand = computed(() => demandRows.value.some((row) => row.extra !== undefined))

// ── Edit dialog ──────────────────────────────────────────────────────

const showEditDialog = ref(false)

watch(showEditDialog, (open, wasOpen) => {
  if (!open && wasOpen) void reload({ quiet: true })
})

// ── Create demand ────────────────────────────────────────────────────

const showCreateDemand = ref(false)

function onDemandCreated(): void {
  void reloadDemands({ quiet: true })
}

// ── Demand detail dialog ─────────────────────────────────────────────

const selectedDemand = ref<MadeItemDemandResponse | null>(null)
const showDemandDetail = ref(false)

function onOpenDemand(id: number): void {
  selectedDemand.value = demands.data.find((demand) => demand.id === id) ?? null
  showDemandDetail.value = true
}

function onDemandUpdated(): void {
  void reloadDemands({ quiet: true })
}

// ── Order detail dialog ──────────────────────────────────────────────

const orderDetailOrderId = ref<number | null>(null)
const showOrderDetail = ref(false)

function openOrderDetail(orderId: number): void {
  orderDetailOrderId.value = orderId
  showOrderDetail.value = true
}

watch(showOrderDetail, (open, wasOpen) => {
  if (!open && wasOpen) void reloadOrders({ quiet: true })
})

// ── Lots card (made only) ───────────────────────────────────────────

function onOpenLot(id: number): void {
  lotDialog.openLotDetail(id)
}

// The app-wide lot dialog can be opened from anywhere, so the lots section
// reloads when it closes.
watch(lotDialog.visible, (isVisible) => {
  if (!isVisible) void reloadLots({ quiet: true })
})

// ── Print menu ───────────────────────────────────────────────────────

const { printing, print } = useCatalogueItemPrint('made')
const printMenu = ref()

function togglePrintMenu(event: Event): void {
  printMenu.value?.toggle(event)
}

const printMenuItems = computed<MenuItem[]>(() => {
  const current = item.value
  if (!current) return []
  return [
    {
      label: t('catalogue.itemDetail.actions.printLabel'),
      icon: 'mdi mdi-tag-outline',
      disabled: printing.value === 'label',
      command: () => void print({ id: current.id, summary: current.article_name }, 'label'),
    },
    {
      label: t('catalogue.itemDetail.actions.printDocket'),
      icon: 'mdi mdi-file-document-outline',
      disabled: printing.value === 'docket',
      command: () => void print({ id: current.id, summary: current.article_name }, 'docket'),
    },
  ]
})
</script>

<template>
  <PageLayout wrap-menu>
    <template #info>
      <InfoBar>
        <template v-if="item">
          <span class="item-number">{{ madeItemLabel(item.part_number, item.revision) }}</span>
          <Select
            v-if="(revisions?.items.length ?? 0) > 1"
            :aria-label="t('madeItems.catalogue.columns.revision')"
            class="revision-select"
            :model-value="item.id"
            :options="revisions?.items ?? []"
            option-label="revision"
            option-value="id"
            @update:model-value="onRevisionSelect"
          >
            <template #option="{ option }">
              <div class="revision-option">
                <span>{{ option.revision }}</span>
                <Tag
                  :value="t(`madeItems.catalogue.status.${option.status}`)"
                  :severity="catalogueStatusTagSeverity(option.status)"
                />
              </div>
            </template>
          </Select>
          <span class="info-sep" />
          <Tag
            :value="t(`madeItems.catalogue.status.${item.status}`)"
            :severity="catalogueStatusTagSeverity(item.status)"
          />
          <span class="info-sep" />
          <span class="info-muted">{{ item.article_name }}</span>
        </template>
        <template v-else-if="loading">
          <Skeleton width="7rem" height="1.5rem" border-radius="1rem" />
          <Skeleton width="5.5rem" height="1.5rem" border-radius="1rem" />
        </template>
      </InfoBar>
    </template>

    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            icon="mdi mdi-arrow-left"
            :label="t('madeItems.catalogue.page.back')"
            severity="contrast"
            text
            @click="router.push('/catalogue/made-items')"
          />

          <template v-if="item">
            <Divider layout="vertical" />

            <span v-tooltip.bottom="missing(Permission.WRITE_MADE_ITEMS) || undefined">
              <Button
                icon="mdi mdi-pencil"
                :label="t('catalogue.itemDetail.actions.edit')"
                severity="contrast"
                text
                :disabled="!canEdit"
                @click="showEditDialog = true"
              />
            </span>
            <span v-tooltip.bottom="missing(Permission.WRITE_DEMAND_ITEMS) || undefined">
              <Button
                icon="mdi mdi-clipboard-plus-outline"
                :label="t('catalogue.itemDetail.actions.createDemand')"
                severity="contrast"
                text
                :disabled="!canCreateDemand"
                @click="showCreateDemand = true"
              />
            </span>
            <span v-tooltip.bottom="t('madeItems.catalogue.page.addToOrderUnavailable')">
              <Button
                icon="mdi mdi-cart-arrow-right"
                :label="t('catalogue.itemDetail.actions.addToOrder')"
                severity="contrast"
                text
                disabled
              />
            </span>

            <Divider layout="vertical" />

            <span v-tooltip.bottom="missing(Permission.PRINT_DOCUMENTS) || undefined">
              <Button
                icon="mdi mdi-printer-outline"
                :label="t('catalogue.itemDetail.actions.print')"
                severity="contrast"
                text
                :disabled="!canPrint"
                @click="togglePrintMenu($event)"
              />
            </span>
            <Button
              icon="mdi mdi-content-copy"
              :label="t('common.copyUuid')"
              severity="contrast"
              text
              @click="copyToClipboard(item.public_id)"
            />
          </template>
        </template>
        <template #handbook>
          <ShareButton :public-id="item?.public_id" />
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <template #views>
      <ViewsBar
        id-prefix="made-item-detail"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="false"
        @sync="reload()"
      />
    </template>

    <div v-if="loading" class="state-center" />
    <div v-else-if="notFound" class="state-center state-message">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('catalogue.itemDetail.notFound') }}</span>
    </div>
    <div v-else-if="loadError" class="state-center state-message">
      <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('catalogue.itemDetail.loadError') }}</span>
    </div>

    <CatalogueItemDetailGrid v-else-if="item">
      <template #item>
        <Panel :header="t('catalogue.itemDetail.cards.item')">
          <div class="card-scroll-body">
            <Message v-if="isNotNewest" severity="info" :closable="false" class="not-newest-notice">
              {{ t('madeItems.edit.notNewestNotice', { revision: newestRevisionLabel }) }}
            </Message>

            <div class="item-layout">
              <CatalogueItemMedia
                v-if="hostStore.storageEnabled"
                :picture="shownPicture"
                :mesh-file="meshFile"
                :drawing-file="drawingFile"
                :fetch-blob="fetchItemFileBlob"
              >
                <MadeItemThumbnailCell
                  :item-id="item.id"
                  :item-name="item.article_name"
                  size="6rem"
                  no-image-icon="mdi mdi-image-off-outline"
                />
              </CatalogueItemMedia>
              <div class="item-fields-wrap">
                <MadeItemDetailFields :item="item" :show-status="false" />
              </div>
            </div>
            <MadeItemPicturesSection
              v-if="hostStore.storageEnabled"
              :item-id="item.id"
              readonly
            />
          </div>
        </Panel>
      </template>

      <template #demands>
        <CatalogueItemDemandsCard
          kind="made"
          :rows="demandRows"
          :loading="demands.loading"
          :error="demands.error"
          :truncated="demands.truncated"
          :limit="sectionLimit"
          :extra-label="
            hasAlterationDemand ? t('catalogue.itemDetail.demands.columns.alteration') : undefined
          "
          @open="onOpenDemand"
        />
      </template>

      <template #orders>
        <CatalogueItemOrdersCard
          :rows="orders.data"
          :loading="orders.loading"
          :error="orders.error"
          :truncated="orders.truncated"
          :limit="sectionLimit"
          @open-order="openOrderDetail"
        />
      </template>

      <template v-if="hostStore.storageEnabled" #files>
        <CatalogueItemFilesCard
          :files="filesCardRows"
          :category-label="filesCategoryLabel"
          :can-edit="canEdit"
          :fetch-blob="fetchItemFileBlob"
          :deleting="deletingFileId"
          :loading="filesCardLoading"
          @delete="onDeleteFile"
        />
      </template>

      <template #usedIn>
        <CatalogueItemUsageCard
          :rows="usageRows"
          :loading="usageLoading"
          :error="usageError"
          @open-order="openOrderDetail"
        />
      </template>

      <template #changelog>
        <CatalogueItemChangelogCard
          :entries="changelog.data"
          :loading="changelog.loading"
          :error="changelog.error"
        />
      </template>

      <template #processes>
        <Panel :header="t('catalogue.itemDetail.cards.processes')">
          <div class="card-scroll-body">
            <MadeItemProcessGrouping
              :item-id="item.id"
              :processes="item.processes ?? []"
              readonly
              show-times
              hide-hint
            />
          </div>
        </Panel>
      </template>

      <template #source>
        <MadeItemLinkedSourceCard :item="item" />
      </template>

      <template v-if="hostStore.productionPlanningEnabled" #lots>
        <CatalogueItemLotsCard
          :lots="lots.data"
          :loading="lots.loading"
          :error="lots.error"
          :truncated="lots.truncated"
          :limit="sectionLimit"
          @open-lot="onOpenLot"
        />
      </template>
    </CatalogueItemDetailGrid>
  </PageLayout>

  <MadeItemDetailDialog v-model:visible="showEditDialog" :item="item" edit-on-open />

  <MadeItemDemandCreateForm
    v-model:visible="showCreateDemand"
    :preset-item="item"
    @created="onDemandCreated"
  />

  <MadeItemDemandDetailDialog
    v-model:visible="showDemandDetail"
    :demand="selectedDemand"
    @updated="onDemandUpdated"
  />

  <OrderDetailDialog
    v-if="orderDetailOrderId !== null"
    v-model:visible="showOrderDetail"
    :order-id="orderDetailOrderId"
  />

  <Menu ref="printMenu" :model="printMenuItems" popup />
</template>

<style scoped lang="scss">
.item-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.revision-select {
  width: auto;
  min-width: 6rem;
  margin-left: var(--space-2);
}

.revision-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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

.card-scroll-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

// The scroll body is a plain block, so the notice needs its own margin.
.not-newest-notice {
  margin-bottom: var(--space-4);
}

// Media tiles at a fixed width beside the field grid.
.item-layout {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
}

// Keeps MadeItemDetailFields one flex item, however many roots it renders.
.item-fields-wrap {
  flex: 1;
  min-width: 0;
}
</style>
