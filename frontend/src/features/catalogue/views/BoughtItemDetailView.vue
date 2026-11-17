<script setup lang="ts">
// /catalogue/bought-items/:id, the bought item detail page.
// useBoughtItemDetailPage owns the data.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useClipboard } from '@/core/composables/useClipboard'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePageTitle } from '@/core/composables/usePageTitle'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

import CatalogueItemDetailGrid from '../components/CatalogueItemDetailGrid.vue'
import CatalogueItemDemandsCard from '../components/CatalogueItemDemandsCard.vue'
import CatalogueItemFilesCard from '../components/CatalogueItemFilesCard.vue'
import CatalogueItemMedia from '../components/CatalogueItemMedia.vue'
import CatalogueItemOrdersCard from '../components/CatalogueItemOrdersCard.vue'
import CatalogueItemUsageCard from '../components/CatalogueItemUsageCard.vue'
import CatalogueItemChangelogCard from '@/shared/components/changelog/ChangelogCard.vue'
import { useCatalogueItemFiles } from '../composables/useCatalogueItemFiles'
import { useCatalogueItemPrint } from '../composables/useCatalogueItemPrint'
import { BoughtItemAddToOrderDialog, OrderDetailDialog } from '@/features/orders'
import { BoughtItemDemandDetailDialog } from '@/features/procurement'

import { useShownPicture } from '@/shared/pictures'
import { useBoughtItemDetailPage } from '../composables/useBoughtItemDetailPage'

import type { MenuItem } from 'openvue/menuitem'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import {
  BoughtItemDemandCreateForm,
  BoughtItemDetailDialog,
  BoughtItemDetailFields,
  BoughtItemEdpLookupDialog,
  BoughtItemPicturesSection,
  BoughtItemThumbnailCell,
  getBoughtItemFileBlob,
  useBoughtItemFilesStore,
  useBoughtItemPicturesStore,
} from '@/features/bought-items'
import type { BoughtItemDemandResponse } from '@/features/bought-items'

// The Item card shows thumbnail, image and mesh; the Files card lists PDFs,
// the only remaining category. Uploads stay in the edit dialog.
const FILES_CARD_CATEGORIES = ['pdf']

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { hasPermission } = usePermissions()
const hostStore = useHostStore()
const { copyToClipboard } = useClipboard()
const { printing, print } = useCatalogueItemPrint('bought')

// A computed, since a successor link navigates this route to another id.
const itemId = computed(() => Number(route.params.id))

const {
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
  sectionLimit,
  reload,
  reloadDemands,
  reloadOrders,
} = useBoughtItemDetailPage(itemId)

watchLoadingBar(loading)

// Falls back to the generic route title until the item loads, then shows
// its identity, the same value the InfoBar's own visible strip leads with.
const pageHeading = computed(() =>
  item.value ? (item.value.part_number ?? item.value.order_code_1) : t('pageTitles.boughtItemDetail'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })

const canEdit = computed(() => hasPermission(Permission.WRITE_BOUGHT_ITEMS))
const canCreateDemand = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
const canAddToOrder = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
const { missing } = useMissingPermission()

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
  filesStore: useBoughtItemFilesStore(),
  fetchBlob: getBoughtItemFileBlob,
  filesCardCategories: FILES_CARD_CATEGORIES,
  categoryLabelPrefix: 'boughtItems.catalogue.files.categories',
})

const picturesStore = useBoughtItemPicturesStore()
const shownPicture = useShownPicture(picturesStore, () => item.value?.id ?? null)

// ── Edit dialog ──────────────────────────────────────────────────────

const showEditDialog = ref(false)
const showEdpLookup = ref(false)

watch(showEditDialog, (open, wasOpen) => {
  if (!open && wasOpen) void reload({ quiet: true })
})

// ── Create demand ────────────────────────────────────────────────────

const showCreateDemand = ref(false)

function onDemandCreated(): void {
  void reloadDemands({ quiet: true })
}

// ── Add to order ─────────────────────────────────────────────────────

const showAddToOrder = ref(false)

// The dialog emits nothing on success, so closing signals it is done.
watch(showAddToOrder, (open, wasOpen) => {
  if (!open && wasOpen) void reloadOrders({ quiet: true })
})

// ── Demand detail dialog ─────────────────────────────────────────────

const selectedDemand = ref<BoughtItemDemandResponse | null>(null)
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

// ── Print menu ───────────────────────────────────────────────────────

const printMenu = ref()

function toggleMenu(menu: { toggle(event: Event): void } | undefined, event: Event): void {
  menu?.toggle(event)
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
          <span class="item-number">{{ item.part_number ?? item.order_code_1 }}</span>
          <span class="info-sep" />
          <Tag
            :value="t(`boughtItems.catalogue.status.${item.status}`)"
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
            :label="t('boughtItems.catalogue.page.back')"
            severity="contrast"
            text
            @click="router.push('/catalogue/bought-items')"
          />

          <template v-if="item">
            <Divider layout="vertical" />

            <span v-tooltip.bottom="missing(Permission.WRITE_BOUGHT_ITEMS) || undefined">
              <Button
                icon="mdi mdi-pencil"
                :label="t('catalogue.itemDetail.actions.edit')"
                severity="contrast"
                text
                :disabled="!canEdit"
                @click="showEditDialog = true"
              />
            </span>
            <span
              v-if="hostStore.edpEnabled"
              v-tooltip.bottom="missing(Permission.WRITE_BOUGHT_ITEMS) || undefined"
            >
              <Button
                icon="mdi mdi-database-search-outline"
                :label="t('boughtItems.edpLookup.action')"
                severity="contrast"
                text
                :disabled="!canEdit"
                data-testid="bought-item-edp-lookup"
                @click="showEdpLookup = true"
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
            <span v-tooltip.bottom="missing(Permission.WRITE_ORDERS) || undefined">
              <Button
                icon="mdi mdi-cart-arrow-right"
                :label="t('catalogue.itemDetail.actions.addToOrder')"
                severity="contrast"
                text
                :disabled="!canAddToOrder"
                @click="showAddToOrder = true"
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
                @click="toggleMenu(printMenu, $event)"
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
        id-prefix="bought-item-detail"
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
                :fetch-blob="fetchItemFileBlob"
              >
                <BoughtItemThumbnailCell
                  :item-id="item.id"
                  :item-name="item.article_name"
                  size="6rem"
                  no-image-icon="mdi mdi-image-off-outline"
                />
              </CatalogueItemMedia>
              <div class="item-fields-wrap">
                <BoughtItemDetailFields :item="item" :show-status="false" />
              </div>
            </div>
            <BoughtItemPicturesSection
              v-if="hostStore.storageEnabled"
              :item-id="item.id"
              readonly
            />
          </div>
        </Panel>
      </template>

      <template #demands>
        <CatalogueItemDemandsCard
          kind="bought"
          :rows="demandRows"
          :loading="demands.loading"
          :error="demands.error"
          :truncated="demands.truncated"
          :limit="sectionLimit"
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
    </CatalogueItemDetailGrid>
  </PageLayout>

  <Menu ref="printMenu" :model="printMenuItems" popup />

  <BoughtItemDetailDialog v-model:visible="showEditDialog" :item="item" edit-on-open />

  <BoughtItemEdpLookupDialog v-model:visible="showEdpLookup" :item="item" @applied="reload()" />

  <BoughtItemDemandCreateForm
    v-model:visible="showCreateDemand"
    :preset-item="item"
    @created="onDemandCreated"
  />

  <BoughtItemAddToOrderDialog v-model:visible="showAddToOrder" :item="item" />

  <BoughtItemDemandDetailDialog
    v-model:visible="showDemandDetail"
    :demand="selectedDemand"
    @updated="onDemandUpdated"
  />

  <OrderDetailDialog
    v-if="orderDetailOrderId !== null"
    v-model:visible="showOrderDetail"
    :order-id="orderDetailOrderId"
  />
</template>

<style scoped lang="scss">
.item-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

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

// Keeps BoughtItemDetailFields, which renders several roots, one flex item.
.item-fields-wrap {
  flex: 1;
  min-width: 0;
}
</style>
