<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import type { Component } from 'vue'

import { useAppToast } from '@/core/composables/useAppToast'
import { useHostStore } from '@/core/host/stores/hostStore'
import { HelpButton } from '@/shared/help'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { DocumentDraftDialog } from '@/shared/documents'
import { ReportExportDialog, useReportExport } from '@/shared/reports'
import ToolCalculationControls from '../components/ToolCalculationControls.vue'
import ToolCalculationInfo from '../components/ToolCalculationInfo.vue'
import { toolPath, useSavedCalculation } from '../composables/useSavedCalculation'
import { provideInitialToolInputs, provideToolStateHost } from '../composables/useToolState'
import { toolReportSpec } from '../utils/toolReport'
import { TOOLS, toolByTab } from '../registry'
import type { CalculationOwner } from '../types/calculation'

interface TabConfig {
  value: string
  key: string
  labelKey: string
  icon: string
  component: Component
  saveable: boolean
}

const TABS: TabConfig[] = TOOLS.map((tool) => ({
  value: tool.tab,
  key: tool.key,
  labelKey: tool.labelKey,
  icon: tool.icon,
  component: tool.component,
  saveable: tool.saveable,
}))

const VALID_TABS = new Set(TABS.map((tab) => tab.value))
const DEFAULT_TAB = TABS[0]?.value ?? ''

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useAppToast()

function resolveTab(param: unknown): string {
  return typeof param === 'string' && VALID_TABS.has(param) ? param : DEFAULT_TAB
}

// Switching tabs leaves the open calculation: it belongs to the tool that
// was open and means nothing to the next one.
const activeTab = computed(() => resolveTab(route.params.tab))

// The tab strip shows the clicked tab at once. When the switch is cancelled,
// because unsaved changes asked first, it goes back to the tab still open;
// the tab strip only follows a value that changes.
const shownTab = ref(activeTab.value)
watch(activeTab, (tab) => (shownTab.value = tab))

async function selectTab(tab: string | number): Promise<void> {
  const next = String(tab)
  shownTab.value = next
  if (next === activeTab.value) return
  const failure = await router.replace(toolPath(next, null))
  if (failure) shownTab.value = activeTab.value
}

// With calculations switched off a tool is a plain calculator: nothing is
// saved, loaded or offered as a draft, like the fit calculator.
const hostStore = useHostStore()
const offersCalculations = (tab: { saveable?: boolean }) =>
  Boolean(tab.saveable) && hostStore.calculationsEnabled

const toolState = provideToolStateHost()
const saved = useSavedCalculation(activeTab, toolState)
provideInitialToolInputs(() => saved.initialInputs.value)

function onRestoreDraft(): void {
  saved.restoreDraft()
  toast.success(t('tools.calculations.title'), t('documents.draft.restored'))
}

/** A tool opened from a project or product page offers that owner when saving. */
const defaultOwner = computed<CalculationOwner>(() => {
  const raw = typeof route.query.for === 'string' ? route.query.for : ''
  const [kind, id, ...label] = raw.split(':')
  const ownerId = Number(id)
  if ((kind === 'project' || kind === 'product') && Number.isInteger(ownerId) && ownerId > 0) {
    return { kind, id: ownerId, label: label.join(':') }
  }
  return { kind: 'personal' }
})

/** A tool opened from a device offers that device when saving. */
const defaultDeviceId = computed<number | null>(() => {
  const id = Number(route.query.device)
  return defaultOwner.value.kind !== 'personal' && Number.isInteger(id) && id > 0 ? id : null
})

const { visible: reportVisible, report, open: openReport } = useReportExport()

// Print exports the open calculation as a PDF report; unsaved inputs can be
// downloaded but not sent to a printer.
function print(): void {
  const tool = toolByTab(activeTab.value)
  const spec =
    tool &&
    toolReportSpec(tool, saved.calculation.value, {
      inputs: toolState.value?.inputs ?? {},
      title: toolState.value?.title ?? '',
    })
  if (spec) openReport(spec)
}
</script>

<template>
  <div class="section-view">
    <Tabs :value="shownTab" class="section-tabs fill-tabs fill-tabs--contained" @update:value="selectTab">
      <TabList>
        <Tab v-for="tab in TABS" :key="tab.value" :value="tab.value">
          <i :class="`mdi ${tab.icon} tab-icon`" aria-hidden="true" />
          {{ t(tab.labelKey) }}
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="tab in TABS" :key="tab.value" :value="tab.value">
          <!-- A saveable tool is a detail page: which calculation is open, what
               can be done with it, then the tool itself. The fit calculator is
               looked up, not saved, and shows no bars. -->
          <PageLayout v-if="activeTab === tab.value" :card="false">
            <template v-if="offersCalculations(tab)" #info>
              <ToolCalculationInfo :saved="saved" :description="toolState?.description" />
            </template>
            <template v-if="offersCalculations(tab)" #controls>
              <ToolCalculationControls
                :saved="saved"
                :tool-key="tab.key"
                :tab="tab.value"
                :default-title="toolState?.title ?? ''"
                :default-owner="defaultOwner"
                :default-device-id="defaultDeviceId"
                @print="print"
              />
            </template>
            <component
              :is="tab.component"
              v-if="!saved.resolving.value"
              :key="saved.mountKey.value"
            />
          </PageLayout>
        </TabPanel>
      </TabPanels>
    </Tabs>
    <ReportExportDialog v-model:visible="reportVisible" :report="report">
      <template #handbook>
        <HelpButton slug="resources/report-export" icon="mdi mdi-help" rounded />
      </template>
    </ReportExportDialog>
    <DocumentDraftDialog
      v-if="hostStore.calculationsEnabled"
      :offer="saved.draft.offer.value"
      :saved-since="saved.calculation.value?.changed ?? null"
      @restore="onRestoreDraft"
      @discard="saved.draft.discard()"
      @dismiss="saved.draft.dismiss()"
    />
  </div>
</template>

<style scoped lang="scss">
.section-view {
  height: calc(100% + 1rem);
  margin: -0.5rem;
}

.section-tabs {
  height: 100%;
}

.tab-icon {
  margin-right: var(--space-1);
}
</style>
