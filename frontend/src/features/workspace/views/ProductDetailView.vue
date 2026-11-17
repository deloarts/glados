<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProjects, ProjectBomTab } from '@/features/projects'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { usePermissions } from '@/core/composables/usePermissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { Permission } from '@/core/auth/permissions'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useRouteTab } from '@/shared/composables/useRouteTab'
import type { ProjectResponse } from '@/features/projects'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import { HelpButton } from '@/shared/help'
import {
  CalculationsList,
  countCalculationsByDevice,
  NewCalculationButton,
  ProductDeviceCalculations,
} from '@/features/tools'
import { ChecklistsList, NewChecklistButton } from '@/features/checklists'
import {
  ProductDevicesControls,
  ProductDevicesTab,
  ProductDevicesViews,
  useProductDevicesViewStore,
} from '@/features/product-devices'
import { SequencesControls, SequencesTab } from '@/features/sequences'
import { MeetingNotesControls, MeetingNotesTable, MeetingNotesViews } from '@/features/meetings'
import { getProducts, ProductFilesTab, ProductFormDialog } from '@/features/products'
import type { ProductResponse } from '@/features/products'
import ProductOverviewTab from '../components/ProductOverviewTab.vue'
import ProductProjectsTab from '../components/ProductProjectsTab.vue'
import ProjectCostsTab from '../components/ProjectCostsTab.vue'
import ProjectOrdersTab from '../components/ProjectOrdersTab.vue'
import { useProductProcurement } from '../composables/useProductProcurement'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { hasPermission } = usePermissions()
const currentUserStore = useCurrentUserStore()
const usersStore = useUsersStore()
const hostStore = useHostStore()

const productId = computed(() => Number(route.params.id))

const loading = ref(true)
const notFound = ref(false)
const loadError = ref(false)

watchLoadingBar(loading)

const product = ref<ProductResponse | null>(null)
const projects = ref<ProjectResponse[]>([])

// The tab is part of the URL, such as /workspace/products/4/devices; the
// overview lives on the bare product URL.
const PRODUCT_TABS = new Set([
  'overview',
  'projects',
  'meeting-notes',
  'bom',
  'orders',
  'costs',
  'files',
  'devices',
  'sequences',
  'calculations',
  'checklists',
])
// A tab of a switched-off feature, or Files without storage, is not offered.
function tabAllowed(tab: string): boolean {
  switch (tab) {
    case 'files':
      return hostStore.storageEnabled
    case 'devices':
      return hostStore.devicesEnabled
    case 'sequences':
      return hostStore.sequencesEnabled
    case 'calculations':
      return hostStore.calculationsEnabled
    case 'checklists':
      return hostStore.checklistsEnabled
    default:
      return true
  }
}
const activeTab = useRouteTab({
  param: 'tab',
  validTabs: PRODUCT_TABS,
  defaultTab: 'overview',
  basePath: () => `/workspace/products/${String(route.params.id)}`,
  isAllowed: tabAllowed,
  defaultOnBase: true,
})
// The flags can arrive after the tab was resolved, so a tab switched off
// meanwhile falls back to the overview.
watch(
  () => tabAllowed(activeTab.value),
  (allowed) => {
    if (!allowed) activeTab.value = 'overview'
  },
)

const devicesView = useProductDevicesViewStore()

// The Devices tab has a handbook page per view mode, the Sequences tab one of
// its own, and the Calculations and Checklists tabs share the page on
// document revisions. Every other tab opens the page on products.
const DEVICE_MODE_SLUGS = {
  list: 'workspace/product-devices',
  overview: 'workspace/device-overview',
  completeness: 'workspace/device-completeness',
  tags: 'workspace/plc-tags',
} as const
const handbookSlug = computed(() => {
  switch (activeTab.value) {
    case 'devices':
      return DEVICE_MODE_SLUGS[devicesView.mode]
    case 'sequences':
      return 'workspace/flow-sequences'
    case 'meeting-notes':
      return 'workspace/meeting-notes'
    case 'calculations':
    case 'checklists':
      return 'workspace/document-revisions'
    default:
      return undefined
  }
})

const editDialogVisible = ref(false)

// The Bill of Material, Orders and Costs tabs sum up all projects of the
// product; their data loads the first time one of them opens.
const {
  summary: productSummary,
  boughtDemands,
  madeDemands,
  sourceDemands,
  orders,
  loading: procurementLoading,
  failed: procurementFailed,
  ensureLoaded: ensureProcurementLoaded,
} = useProductProcurement(productId)
watchLoadingBar(procurementLoading)
const PROCUREMENT_TABS = ['bom', 'orders', 'costs']
watch([activeTab, productId], ([tab]) => {
  if (PROCUREMENT_TABS.includes(tab)) void ensureProcurementLoaded()
})
const projectIds = computed(() => projects.value.map((project) => project.id))

const canManage = computed(() => hasPermission(Permission.MANAGE_PROJECTS))
const canWrite = computed(() => hasPermission(Permission.WRITE_PROJECTS))
const canEdit = computed(
  () =>
    canManage.value ||
    (canWrite.value && product.value?.designated_user_id === currentUserStore.user?.id),
)
const canCreateCalculation = computed(() => hasPermission(Permission.WRITE_CALCULATIONS))
const canCreateChecklist = computed(() => hasPermission(Permission.WRITE_CHECKLISTS))
// Without the rights the buttons stay visible, disabled, and say why.
const { missing } = useMissingPermission()
const editBlocked = computed(() => {
  if (canEdit.value) return ''
  if (!canWrite.value && !canManage.value) return missing(Permission.WRITE_PROJECTS)
  return t('resources.products.detail.editDesignatedOnly')
})
const createCalculationBlocked = computed(() => missing(Permission.WRITE_CALCULATIONS))
const createChecklistBlocked = computed(() => missing(Permission.WRITE_CHECKLISTS))

// A tab without actions gets no controls bar, so the page shows no empty bar.
const hasControls = computed(() => {
  if (activeTab.value === 'overview') return true
  if (!product.value) return false
  switch (activeTab.value) {
    case 'devices':
      return !product.value.archived || devicesView.mode === 'tags'
    case 'calculations':
    case 'checklists':
    case 'sequences':
    case 'meeting-notes':
      return true
    default:
      return false
  }
})

// Preselects the product as owner when the new calculation is saved.
const calculationOwner = computed(() =>
  product.value ? `product:${product.value.id}:${product.value.product_number}` : null,
)

// The list endpoint never 404s for an unknown id, so a thrown request is a
// genuine load failure. A response for an id the route has already left is
// dropped. The projects list renders without a paginator, so it requests the
// API maximum instead of the default page size.
async function load(): Promise<void> {
  const id = productId.value
  loading.value = true
  notFound.value = false
  loadError.value = false
  try {
    const [productsPage, projectsPage] = await Promise.all([
      getProducts({ id, limit: 1 }),
      getProjects({
        product_id: id,
        limit: API_MAX_PAGE_SIZE,
        order_by: 'created',
        order_dir: 'desc',
      }),
    ])
    if (productId.value !== id) return
    const [found] = productsPage.items
    if (!found) {
      notFound.value = true
      return
    }
    product.value = found
    projects.value = projectsPage.items
    void usersStore.ensureLoaded()
  } catch {
    if (productId.value !== id) return
    loadError.value = true
  } finally {
    if (productId.value === id) loading.value = false
  }
}

watch(
  productId,
  (newId, oldId) => {
    // Leaving the route fires this sync watcher before unmount, when the id
    // param is gone and the id is NaN. Nothing should load then.
    if (!Number.isInteger(newId)) return
    if (oldId !== undefined && newId !== oldId) {
      product.value = null
      projects.value = []
    }
    void load()
  },
  { immediate: true, flush: 'sync' },
)

function onSaved(updated: ProductResponse): void {
  product.value = updated
}

const pageHeading = computed(() =>
  product.value ? product.value.product_number : t('pageTitles.productDetail'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })
</script>

<template>
  <div class="detail-view">
    <Tabs v-model:value="activeTab" class="detail-tabs fill-tabs">
      <TabList>
        <Tab value="overview">{{ t('resources.products.detail.tabs.overview') }}</Tab>
        <Tab value="projects">{{ t('resources.products.detail.tabs.projects') }}</Tab>
        <Tab value="meeting-notes">{{ t('resources.products.detail.tabs.meetingNotes') }}</Tab>
        <Tab value="bom">{{ t('resources.products.detail.tabs.bom') }}</Tab>
        <Tab value="orders">{{ t('resources.products.detail.tabs.orders') }}</Tab>
        <Tab value="costs">{{ t('resources.products.detail.tabs.costs') }}</Tab>
        <Tab v-if="hostStore.storageEnabled" value="files">{{
          t('resources.products.detail.tabs.files')
        }}</Tab>
        <Tab v-if="hostStore.devicesEnabled" value="devices">{{
          t('resources.products.detail.tabs.devices')
        }}</Tab>
        <Tab v-if="hostStore.sequencesEnabled" value="sequences">{{
          t('resources.products.detail.tabs.sequences')
        }}</Tab>
        <Tab v-if="hostStore.calculationsEnabled" value="calculations">{{
          t('resources.products.detail.tabs.calculations')
        }}</Tab>
        <Tab v-if="hostStore.checklistsEnabled" value="checklists">{{
          t('resources.products.detail.tabs.checklists')
        }}</Tab>
      </TabList>
      <TabPanels>
        <!-- One panel for the active tab, holding the whole page below the strip. -->
        <TabPanel :value="activeTab">
          <PageLayout>
            <template #info>
              <InfoBar>
                <template v-if="product">
                  <span class="product-number">{{ product.product_number }}</span>
                  <span class="info-sep" />
                  <Tag
                    :value="
                      product.is_active
                        ? t('resources.products.detail.active')
                        : t('resources.products.detail.inactive')
                    "
                    :severity="product.is_active ? 'success' : 'secondary'"
                  />
                  <span v-if="product.customer" class="info-sep" />
                  <span v-if="product.customer" class="info-customer">{{ product.customer.name }}</span>
                  <span v-if="product.description" class="info-sep" />
                  <span v-if="product.description" class="info-description">{{
                    product.description
                  }}</span>
                </template>
              </InfoBar>
            </template>

            <template v-if="hasControls" #controls>
              <ControlsBar>
                <template #start>
                  <!-- The record's own actions belong to its overview; the other tabs bring theirs. -->
                  <template v-if="activeTab === 'overview'">
                    <Button
                      icon="mdi mdi-arrow-left"
                      :label="t('resources.products.detail.back')"
                      severity="contrast"
                      text
                      @click="router.push('/workspace/products')"
                    />
                    <span v-if="product" v-tooltip.bottom="editBlocked || undefined">
                      <Button
                        icon="mdi mdi-pencil"
                        :label="t('resources.products.editProduct')"
                        severity="contrast"
                        text
                        :disabled="!canEdit"
                        data-testid="product-edit"
                        @click="editDialogVisible = true"
                      />
                    </span>
                  </template>
                  <span
                    v-if="product && activeTab === 'calculations'"
                    v-tooltip.bottom="createCalculationBlocked || undefined"
                  >
                    <NewCalculationButton
                      :owner="calculationOwner"
                      :disabled="!canCreateCalculation"
                    />
                  </span>
                  <ProductDevicesControls
                    v-if="product && activeTab === 'devices'"
                    :can-edit="canEdit && !product.archived"
                    :archived="product.archived"
                  />
                  <SequencesControls
                    v-if="product && activeTab === 'sequences'"
                    :product-archived="product.archived"
                  />
                  <span
                    v-if="product && activeTab === 'checklists'"
                    v-tooltip.bottom="createChecklistBlocked || undefined"
                  >
                    <NewChecklistButton
                      :product-id="product.id"
                      :owner-label="product.product_number"
                      :disabled="!canCreateChecklist"
                    />
                  </span>
                  <MeetingNotesControls
                    v-if="product && activeTab === 'meeting-notes'"
                    owner-kind="product"
                    :owner-id="product.id"
                  />
                </template>
                <template #handbook>
                  <ShareButton v-if="activeTab === 'overview'" :public-id="product?.public_id" />
                  <HelpButton rounded :slug="handbookSlug" />
                </template>
              </ControlsBar>
            </template>

            <template v-if="product && activeTab === 'devices'" #views>
              <ProductDevicesViews />
            </template>
            <template v-else-if="product && activeTab === 'meeting-notes'" #views>
              <MeetingNotesViews owner-kind="product" />
            </template>

            <div v-if="loading" class="state-center" />
            <div v-else-if="notFound" class="state-center state-message">
              <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
              <span>{{ t('resources.products.detail.notFound') }}</span>
            </div>
            <div v-else-if="loadError" class="state-center state-message">
              <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
              <span>{{ t('resources.products.detail.loadError') }}</span>
            </div>

            <template v-else-if="product">
              <ProductOverviewTab
                v-if="activeTab === 'overview'"
                :product="product"
                :projects="projects"
                @open-tab="activeTab = $event"
              />
              <ProductProjectsTab v-else-if="activeTab === 'projects'" :projects="projects" />
              <Message
                v-else-if="procurementFailed && ['bom', 'orders', 'costs'].includes(activeTab)"
                severity="error"
                >{{ t('resources.products.detail.procurementLoadError') }}</Message
              >
              <ProjectBomTab
                v-else-if="activeTab === 'bom'"
                :bought-demands="boughtDemands"
                :made-demands="madeDemands"
                :source-demands="sourceDemands"
                by-project
              />
              <ProjectOrdersTab
                v-else-if="activeTab === 'orders'"
                :orders="orders"
                :project-ids="projectIds"
                :cost-label="t('resources.projects.detail.orders.productCost')"
              />
              <ProjectCostsTab v-else-if="activeTab === 'costs'" :summary="productSummary" />
              <ProductFilesTab
                v-else-if="activeTab === 'files' && hostStore.storageEnabled"
                :product="product"
              />
              <ProductDevicesTab
                v-else-if="activeTab === 'devices'"
                :product-id="product.id"
                :product-number="product.product_number"
                :disciplines="{
                  pneumatics: product.contains_pneumatics,
                  hydraulics: product.contains_hydraulics,
                  electrics: product.contains_electrics,
                  robotics: product.contains_robotics,
                }"
                :can-edit="canEdit && !product.archived"
                :count-calculations="
                  hostStore.calculationsEnabled ? countCalculationsByDevice : undefined
                "
              >
                <template v-if="hostStore.calculationsEnabled" #calculations="{ device, onLoaded }">
                  <ProductDeviceCalculations :device="device" @loaded="onLoaded" />
                </template>
              </ProductDevicesTab>
              <SequencesTab
                v-else-if="activeTab === 'sequences'"
                :product-id="product.id"
                :can-edit-variants="canEdit && !product.archived"
              />
              <CalculationsList
                v-else-if="activeTab === 'calculations'"
                :product-id="product.id"
                include-product-projects
              />
              <ChecklistsList
                v-else-if="activeTab === 'checklists'"
                :product-id="product.id"
                include-product-projects
              />
              <MeetingNotesTable
                v-else-if="activeTab === 'meeting-notes'"
                owner-kind="product"
                :owner-id="product.id"
              />
            </template>
          </PageLayout>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>

  <ProductFormDialog
    v-if="product"
    v-model:visible="editDialogVisible"
    :product="product"
    @saved="onSaved"
  />
</template>

<style scoped lang="scss">
.product-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-customer {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.info-description {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 30rem;
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

// ── Tab strip above the page ──────────────────────────────────────────

// The strip runs flush to the edges of the content area, as on the
// catalogue and procurement pages; below it the active tab is a page of its
// own with the info, controls and views bars and the content card.
.detail-view {
  height: calc(100% + 1rem);
  margin: -0.5rem;
}

.detail-tabs {
  height: 100%;
}
</style>
