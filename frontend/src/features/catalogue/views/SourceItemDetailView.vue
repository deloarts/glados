<script setup lang="ts">
// /catalogue/source-items/:id, the source item detail page.
// useSourceItemDetailPage owns the data.
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
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useHostStore } from '@/core/host/stores/hostStore'
import { usePageTitle } from '@/core/composables/usePageTitle'

import CatalogueItemChangelogCard from '@/shared/components/changelog/ChangelogCard.vue'
import CatalogueItemDemandsCard from '../components/CatalogueItemDemandsCard.vue'
import CatalogueItemDetailGrid from '../components/CatalogueItemDetailGrid.vue'
import CatalogueItemFilesCard from '../components/CatalogueItemFilesCard.vue'
import CatalogueItemMedia from '../components/CatalogueItemMedia.vue'
import CatalogueItemOrdersCard from '../components/CatalogueItemOrdersCard.vue'
import CatalogueItemUsageCard from '../components/CatalogueItemUsageCard.vue'
import { useCatalogueItemFiles } from '../composables/useCatalogueItemFiles'
import { useCatalogueItemPrint } from '../composables/useCatalogueItemPrint'
import { OrderDetailDialog } from '@/features/orders'
import { SourceItemDemandDetailDialog } from '@/features/production'

import { useShownPicture } from '@/shared/pictures'
import { useSourceItemDetailPage } from '../composables/useSourceItemDetailPage'

import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import {
  getSourceItemFileBlob,
  SourceItemDetailDialog,
  SourceItemDetailFields,
  SourceItemPicturesSection,
  sourceItemPlaceholder,
  SourceItemThumbnailCell,
  useSourceItemFilesStore,
  useSourceItemPicturesStore,
} from '@/features/source-items'
import type { SourceItemDemandResponse } from '@/features/source-items'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// The Item card shows thumbnail, image and mesh; the Files card lists PDFs,
// the only remaining category. Uploads stay in the edit dialog.
const FILES_CARD_CATEGORIES = ['pdf']

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { hasPermission } = usePermissions()
const hostStore = useHostStore()

// A computed, so a same-route navigation to another id reloads.
const itemId = computed(() => Number(route.params.id))

const {
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
  sectionLimit,
  reload,
  reloadDemands,
  reloadOrders,
} = useSourceItemDetailPage(itemId)

watchLoadingBar(loading)

const pageHeading = computed(() =>
  item.value ? item.value.dimension || `#${item.value.id}` : t('pageTitles.sourceItemDetail'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })

const canWrite = computed(() => hasPermission(Permission.WRITE_SOURCE_ITEMS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
const { missing } = useMissingPermission()

const subLabel = computed(() =>
  item.value
    ? [item.value.material, localizeLabel(item.value.type_name)].filter(Boolean).join(' | ')
    : '',
)

// ── Item card media ──────────────────────────────────────────────────

const {
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
  filesStore: useSourceItemFilesStore(),
  fetchBlob: getSourceItemFileBlob,
  filesCardCategories: FILES_CARD_CATEGORIES,
  categoryLabelPrefix: 'sourceItems.catalogue.files.categories',
})

const picturesStore = useSourceItemPicturesStore()
const shownPicture = useShownPicture(picturesStore, () => item.value?.id ?? null)

// Without a mesh file the tile shows the shape placeholder resolved from
// the dimension. A real mesh always wins.
const meshPlaceholderUrl = computed(() =>
  meshFile.value ? null : (sourceItemPlaceholder(item.value?.dimension ?? null)?.mesh ?? null),
)

// ── Edit dialog ─────────────────────────────────────────────────────────

const showEditDialog = ref(false)

// The dialog writes into the list store, which this page does not read, so
// the page reloads on close.
watch(showEditDialog, (open, wasOpen) => {
  if (!open && wasOpen) void reload({ quiet: true })
})

// ── Demand detail dialog ───────────────────────────────────────────────

const demandDialogTarget = ref<SourceItemDemandResponse | null>(null)
const showDemandDialog = ref(false)

function openDemandDetail(id: number): void {
  demandDialogTarget.value = demands.data.find((demand) => demand.id === id) ?? null
  showDemandDialog.value = true
}

function onDemandUpdated(): void {
  void reloadDemands({ quiet: true })
}

// ── Order detail dialog ────────────────────────────────────────────────
// Mounted lazily, since it brings its own ConfirmDialog.

const orderDetailOrderId = ref<number | null>(null)
const showOrderDetail = ref(false)

function openOrderDetail(orderId: number): void {
  orderDetailOrderId.value = orderId
  showOrderDetail.value = true
}

watch(showOrderDetail, (open, wasOpen) => {
  if (!open && wasOpen) void reloadOrders({ quiet: true })
})

// ── Print menu ──────────────────────────────────────────────────────────

const { printing, print } = useCatalogueItemPrint('source')
const printMenu = ref()

function togglePrintMenu(event: Event): void {
  printMenu.value?.toggle(event)
}

const printMenuItems = computed<MenuItem[]>(() => {
  const current = item.value
  if (!current) return []
  const target = { id: current.id, summary: localizeLabel(current.type_name) }
  return [
    {
      label: t('catalogue.itemDetail.actions.printLabel'),
      icon: 'mdi mdi-tag-outline',
      disabled: printing.value === 'label',
      command: () => void print(target, 'label'),
    },
    {
      label: t('catalogue.itemDetail.actions.printDocket'),
      icon: 'mdi mdi-file-document-outline',
      disabled: printing.value === 'docket',
      command: () => void print(target, 'docket'),
    },
  ]
})
</script>

<template>
  <PageLayout>
    <template #info>
      <InfoBar>
        <template v-if="item">
          <span class="item-number">{{ item.dimension || `#${item.id}` }}</span>
          <span class="info-sep" />
          <Tag
            :value="t(`sourceItems.catalogue.status.${item.status}`)"
            :severity="catalogueStatusTagSeverity(item.status)"
          />
          <span class="info-sep" />
          <span class="info-muted">{{ subLabel }}</span>
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
            :label="t('sourceItems.catalogue.page.back')"
            severity="contrast"
            text
            @click="router.push('/catalogue/source-items')"
          />

          <template v-if="item">
            <Divider layout="vertical" />

            <span v-tooltip.bottom="missing(Permission.WRITE_SOURCE_ITEMS) || undefined">
              <Button
                icon="mdi mdi-pencil"
                :label="t('catalogue.itemDetail.actions.edit')"
                severity="contrast"
                text
                :disabled="!canWrite"
                @click="showEditDialog = true"
              />
            </span>
            <span v-tooltip.bottom="t('sourceItems.catalogue.page.createDemandUnavailable')">
              <Button
                icon="mdi mdi-clipboard-plus-outline"
                :label="t('catalogue.itemDetail.actions.createDemand')"
                severity="contrast"
                text
                disabled
              />
            </span>
            <span v-tooltip.bottom="t('sourceItems.catalogue.page.addToOrderUnavailable')">
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
        id-prefix="source-item-detail"
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
            <div class="item-layout">
              <CatalogueItemMedia
                v-if="hostStore.storageEnabled"
                :picture="shownPicture"
                :mesh-file="meshFile"
                :mesh-placeholder-url="meshPlaceholderUrl"
                :fetch-blob="fetchItemFileBlob"
              >
                <SourceItemThumbnailCell
                  :item-id="item.id"
                  :item-name="subLabel"
                  :dimension="item.dimension"
                  size="6rem"
                  no-image-icon="mdi mdi-image-off-outline"
                />
              </CatalogueItemMedia>
              <div class="item-fields-wrap">
                <SourceItemDetailFields :item="item" :show-status="false" />
              </div>
            </div>
            <SourceItemPicturesSection
              v-if="hostStore.storageEnabled"
              :item-id="item.id"
              readonly
            />
          </div>
        </Panel>
      </template>

      <template v-if="hostStore.storageEnabled" #files>
        <CatalogueItemFilesCard
          :files="filesCardRows"
          :category-label="filesCategoryLabel"
          :can-edit="canWrite"
          :fetch-blob="fetchItemFileBlob"
          :deleting="deletingFileId"
          :loading="filesCardLoading"
          @delete="onDeleteFile"
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

      <template #demands>
        <CatalogueItemDemandsCard
          kind="source"
          :rows="demandRows"
          :loading="demands.loading"
          :error="demands.error"
          :truncated="demands.truncated"
          :limit="sectionLimit"
          :extra-label="t('catalogue.itemDetail.demands.columns.lot')"
          @open="openDemandDetail"
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
    </CatalogueItemDetailGrid>
  </PageLayout>

  <SourceItemDetailDialog v-model:visible="showEditDialog" :item="item" edit-on-open />

  <SourceItemDemandDetailDialog
    v-model:visible="showDemandDialog"
    :demand="demandDialogTarget"
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
// Buttons wrap as a whole instead of breaking their labels, and the start
// group wraps instead of overflowing. Scoped to the ControlsBar and ViewsBar
// toolbars, not the InfoBar.
:deep(.view-menu .p-button-label) {
  white-space: nowrap;
}

:deep(.view-menu > .p-toolbar .p-toolbar-start) {
  flex-wrap: wrap;
  row-gap: var(--space-2);
}

.item-number {
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

// Media tiles at a fixed width beside the field grid.
.item-layout {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
}

// Keeps SourceItemDetailFields, which renders several roots, one flex item.
.item-fields-wrap {
  flex: 1;
  min-width: 0;
}
</style>
