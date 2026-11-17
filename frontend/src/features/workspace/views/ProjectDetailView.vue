<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import {
  getProjects,
  getProjectSummary,
  ProjectBomTab,
  ProjectFormDialog,
} from '@/features/projects'
import ProjectCostsTab from '../components/ProjectCostsTab.vue'
import ProjectOrdersTab from '../components/ProjectOrdersTab.vue'
import { getDemands } from '@/features/bought-items'
import { getMadeItemDemands } from '@/features/made-items'
import { getSourceItemDemands } from '@/features/source-items'
import { getOrders } from '@/features/orders'
import { fetchAllPages } from '@/core/api/fetchAllPages'
import { usePermissions } from '@/core/composables/usePermissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { Permission } from '@/core/auth/permissions'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import type { ProjectResponse, ProjectSummaryResponse } from '@/features/projects'
import type { BoughtItemDemandResponse } from '@/features/bought-items'
import type { MadeItemDemandResponse } from '@/features/made-items'
import type { SourceItemDemandResponse } from '@/features/source-items'
import type { OrderResponse } from '@/features/orders'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import { HelpButton } from '@/shared/help'
import { CalculationsList, NewCalculationButton } from '@/features/tools'
import { canStartChecklistFor, ChecklistsList, NewChecklistButton } from '@/features/checklists'
import { MeetingNotesControls, MeetingNotesTable, MeetingNotesViews } from '@/features/meetings'
import ProjectOverviewTab from '../components/ProjectOverviewTab.vue'
import { useRouteTab } from '@/shared/composables/useRouteTab'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { hasPermission } = usePermissions()
const currentUserStore = useCurrentUserStore()
const usersStore = useUsersStore()
const hostStore = useHostStore()
const { tabOffered } = usePhoneLayout()

const projectId = Number(route.params.id)

const loading = ref(true)
const notFound = ref(false)
const loadError = ref(false)

watchLoadingBar(loading)

const project = ref<ProjectResponse | null>(null)
const summary = ref<ProjectSummaryResponse | null>(null)
const demands = ref<BoughtItemDemandResponse[]>([])
const madeDemands = ref<MadeItemDemandResponse[]>([])
const sourceDemands = ref<SourceItemDemandResponse[]>([])
const orders = ref<OrderResponse[]>([])

// The tab is part of the URL, such as /workspace/projects/4/costs; the
// overview lives on the bare project URL.
const PROJECT_TABS = new Set([
  'overview',
  'meeting-notes',
  'bom',
  'orders',
  'costs',
  'calculations',
  'checklists',
])
// A tab of a switched-off feature is not offered.
function tabAllowed(tab: string): boolean {
  if (tab === 'calculations') return hostStore.calculationsEnabled
  if (tab === 'checklists') return hostStore.checklistsEnabled
  return true
}
const activeTab = useRouteTab({
  param: 'tab',
  validTabs: PROJECT_TABS,
  defaultTab: 'overview',
  basePath: () => `/workspace/projects/${String(route.params.id)}`,
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
const editDialogVisible = ref(false)

const canManage = computed(() => hasPermission(Permission.MANAGE_PROJECTS))
const canWrite = computed(() => hasPermission(Permission.WRITE_PROJECTS))
const canEdit = computed(
  () =>
    canManage.value ||
    (canWrite.value && project.value?.designated_user_id === currentUserStore.user?.id),
)
// Without the right the Edit button stays visible, disabled, and says why.
const { missing } = useMissingPermission()
const editBlocked = computed(() => {
  if (canEdit.value) return ''
  if (!canWrite.value) return missing(Permission.WRITE_PROJECTS)
  return t('resources.projects.detail.editDesignatedOnly')
})
const canCreateCalculation = computed(() => hasPermission(Permission.WRITE_CALCULATIONS))
const canCreateChecklist = computed(() => hasPermission(Permission.WRITE_CHECKLISTS))
// New Checklist is only offered while some checklist type can belong to a
// project; without the permission it shows disabled and names it.
const offersChecklist = computed(() => canStartChecklistFor('project'))
const createCalculationBlocked = computed(() => missing(Permission.WRITE_CALCULATIONS))
const createChecklistBlocked = computed(() => missing(Permission.WRITE_CHECKLISTS))

// The Calculations and Checklists tabs open the handbook page on document
// revisions and the Meeting Notes tab its own; every other tab opens the
// page on projects, from the route.
const handbookSlug = computed(() => {
  if (activeTab.value === 'calculations' || activeTab.value === 'checklists') {
    return 'workspace/document-revisions'
  }
  return activeTab.value === 'meeting-notes' ? 'workspace/meeting-notes' : undefined
})

// A tab without actions gets no controls bar, so the page shows no empty bar.
const hasControls = computed(() => {
  if (activeTab.value === 'overview') return true
  if (activeTab.value === 'calculations' || activeTab.value === 'meeting-notes') return true
  if (activeTab.value === 'checklists') return offersChecklist.value
  return false
})

// Preselects the project as owner when the new calculation is saved.
const calculationOwner = computed(() =>
  project.value ? `project:${project.value.id}:${project.value.project_number}` : null,
)

async function load(): Promise<void> {
  loading.value = true
  notFound.value = false
  loadError.value = false
  try {
    const [projectsPage, summaryData, demandRows, madeRows, sourceRows, orderRows] =
      await Promise.all([
        getProjects({ id: projectId, limit: 1 }),
        getProjectSummary(projectId),
        // The lists render without a paginator, so each is read page by
        // page until the project's last row.
        fetchAllPages((page) =>
          getDemands({
            ...page,
            project_id: projectId,
            order_by: 'manufacturer_name',
            order_dir: 'asc',
          }),
        ),
        fetchAllPages((page) => getMadeItemDemands({ ...page, project_id: projectId })),
        fetchAllPages((page) => getSourceItemDemands({ ...page, project_id: projectId })),
        fetchAllPages((page) => getOrders({ ...page, project_id: projectId })),
      ])
    const [firstProject] = projectsPage.items
    if (!firstProject) {
      notFound.value = true
      return
    }
    project.value = firstProject
    summary.value = summaryData
    demands.value = demandRows
    madeDemands.value = madeRows
    sourceDemands.value = sourceRows
    orders.value = orderRows
    void usersStore.ensureLoaded()
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)

function onSaved(updated: ProjectResponse): void {
  project.value = updated
}

const pageHeading = computed(() =>
  project.value ? project.value.project_number : t('pageTitles.projectDetail'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })
</script>

<template>
  <div class="detail-view">
    <Tabs v-model:value="activeTab" class="detail-tabs fill-tabs">
      <TabList>
        <Tab value="overview">{{ t('resources.projects.detail.tabs.overview') }}</Tab>
        <Tab v-if="tabOffered('meeting-notes')" value="meeting-notes">{{
          t('resources.projects.detail.tabs.meetingNotes')
        }}</Tab>
        <Tab v-if="tabOffered('bom')" value="bom">{{
          t('resources.projects.detail.tabs.bom')
        }}</Tab>
        <Tab v-if="tabOffered('orders')" value="orders">{{
          t('resources.projects.detail.tabs.orders')
        }}</Tab>
        <Tab v-if="tabOffered('costs')" value="costs">{{
          t('resources.projects.detail.tabs.costs')
        }}</Tab>
        <Tab
          v-if="hostStore.calculationsEnabled && tabOffered('calculations')"
          value="calculations"
          >{{ t('resources.projects.detail.tabs.calculations') }}</Tab
        >
        <Tab v-if="hostStore.checklistsEnabled && tabOffered('checklists')" value="checklists">{{
          t('resources.projects.detail.tabs.checklists')
        }}</Tab>
      </TabList>
      <TabPanels>
        <!-- One panel for the active tab, holding the whole page below the strip. -->
        <TabPanel :value="activeTab">
          <PageLayout>
            <template #info>
              <InfoBar>
                <template v-if="project">
                  <span class="project-number">{{ project.project_number }}</span>
                  <span v-if="project.customer" class="info-sep" />
                  <span v-if="project.customer" class="info-customer">{{ project.customer.name }}</span>
                  <span v-if="project.description" class="info-sep" />
                  <span v-if="project.description" class="info-description">{{
                    project.description
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
                      :label="t('resources.projects.detail.back')"
                      severity="contrast"
                      text
                      @click="router.push('/workspace/projects')"
                    />
                    <span v-if="project" v-tooltip.bottom="editBlocked">
                      <Button
                        icon="mdi mdi-pencil"
                        :label="t('resources.projects.editProject')"
                        severity="contrast"
                        text
                        :disabled="!canEdit"
                        data-testid="project-edit"
                        @click="editDialogVisible = true"
                      />
                    </span>
                  </template>
                  <span
                    v-if="project && activeTab === 'calculations'"
                    v-tooltip.bottom="createCalculationBlocked || undefined"
                  >
                    <NewCalculationButton
                      :owner="calculationOwner"
                      :disabled="!canCreateCalculation"
                    />
                  </span>
                  <span
                    v-if="project && activeTab === 'checklists' && offersChecklist"
                    v-tooltip.bottom="createChecklistBlocked || undefined"
                  >
                    <NewChecklistButton
                      :project-id="projectId"
                      :owner-label="project.project_number"
                      :disabled="!canCreateChecklist"
                    />
                  </span>
                  <MeetingNotesControls
                    v-if="project && activeTab === 'meeting-notes'"
                    owner-kind="project"
                    :owner-id="projectId"
                  />
                </template>
                <template #handbook>
                  <ShareButton v-if="activeTab === 'overview'" :public-id="project?.public_id" />
                  <HelpButton rounded :slug="handbookSlug" />
                </template>
              </ControlsBar>
            </template>

            <template v-if="project && activeTab === 'meeting-notes'" #views>
              <MeetingNotesViews owner-kind="project" />
            </template>

            <div v-if="loading" class="state-center" />
            <div v-else-if="notFound" class="state-center state-message">
              <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
              <span>{{ t('resources.projects.detail.notFound') }}</span>
            </div>
            <div v-else-if="loadError" class="state-center state-message">
              <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
              <span>{{ t('resources.projects.detail.loadError') }}</span>
            </div>

            <template v-else-if="project">
              <ProjectOverviewTab
                v-if="activeTab === 'overview'"
                :project="project"
                :summary="summary"
                :bom-count="demands.length + madeDemands.length + sourceDemands.length"
                @open-tab="activeTab = $event"
              />
              <ProjectBomTab
                v-else-if="activeTab === 'bom'"
                :bought-demands="demands"
                :made-demands="madeDemands"
                :source-demands="sourceDemands"
              />
              <ProjectOrdersTab
                v-else-if="activeTab === 'orders'"
                :orders="orders"
                :project-ids="[projectId]"
                :cost-label="t('resources.projects.detail.orders.projectCost')"
              />
              <ProjectCostsTab v-else-if="activeTab === 'costs'" :summary="summary" />
              <CalculationsList v-else-if="activeTab === 'calculations'" :project-id="projectId" />
              <ChecklistsList v-else-if="activeTab === 'checklists'" :project-id="projectId" />
              <MeetingNotesTable
                v-else-if="activeTab === 'meeting-notes'"
                owner-kind="project"
                :owner-id="projectId"
              />
            </template>
          </PageLayout>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>

  <ProjectFormDialog
    v-if="project"
    v-model:visible="editDialogVisible"
    :project="project"
    @saved="onSaved"
  />
</template>

<style scoped lang="scss">
.project-number {
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
