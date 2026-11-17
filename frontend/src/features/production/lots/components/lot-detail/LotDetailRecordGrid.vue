<script setup lang="ts">
// The read-only record view: Lot and Item pinned on the left, everything
// else in one tabbed pane on the right, so each card gets the room it needs.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

import type { LotResponse, LotEventResponse } from '../../../types/productionLotsResponse'
import type { LotChangelogEntry } from '../../types/lotChangelogResponse'
import type { useLotRecordData } from '../../composables/useLotRecordData'
import type {
  SourceItemDemandResponse,
  SourceItemDemandSummaryResponse,
  SourceItemAllocationResponse,
} from '@/features/source-items'

import LotRecordLot from './LotRecordLot.vue'
import LotRecordProject from './LotRecordProject.vue'
import LotRecordItem from './LotRecordItem.vue'
import LotRecordSource from './LotRecordSource.vue'
import LotRecordDemands from './LotRecordDemands.vue'
import LotRecordMaterialReceipts from './LotRecordMaterialReceipts.vue'
import LotRecordPositionBalances from './LotRecordPositionBalances.vue'
import LotRecordExecution from './LotRecordExecution.vue'
import LotRecordAudit from './LotRecordAudit.vue'

const props = withDefaults(
  defineProps<{
    lot: LotResponse
    variant?: 'dialog' | 'page'
    changelog: LotChangelogEntry[]
    recordData: ReturnType<typeof useLotRecordData>
    events: LotEventResponse[]
    eventsLoading: boolean
    sourceItemDemand: SourceItemDemandResponse | null
    sourceItemDemandArrived: number
    sourceItemDemandSummary: SourceItemDemandSummaryResponse | null
    demandAllocations: SourceItemAllocationResponse[]
    manageMode: boolean
    canWrite: boolean
    canApprove: boolean
  }>(),
  { variant: 'dialog' },
)

defineEmits<{
  'view-item': []
  'view-source-item': []
  'change-source': []
  'view-demand': []
  'create-demand': []
  'approve-source': []
  'reject-source': []
}>()

// Five tabs do not fit a phone's width, so the strip scrolls there.
const { isPhone } = usePhoneLayout()
const { t } = useI18n()

// Execution is the working area and the reason most people open a lot, so
// it is the tab that shows first. The others are reference material.
const activeTab = ref('execution')

// Each tab label carries a short hint of what it hides.
const positionCount = computed(() => props.lot.positions?.length ?? 0)
const positionsInProgress = computed(
  () => (props.lot.positions ?? []).filter((p) => p.status === 'in_progress').length,
)
</script>

<template>
  <div class="record-grid">
    <div class="record-column">
      <LotRecordLot
        class="record-card record-card--scroll area-lot"
        :lot="lot"
        :changelog="changelog"
        :variant="variant"
      />

      <LotRecordItem
        class="record-card record-card--scroll area-item"
        :lot="lot"
        :made-item="recordData.madeItem.value"
        @view-item="$emit('view-item')"
      />
    </div>

    <Tabs v-model:value="activeTab" class="record-tabs" lazy :scrollable="isPhone">
      <TabList class="record-tablist">
        <Tab class="record-tab" value="execution">
          <span class="tab-title">{{ t('production.lots.detail.record.execution.title') }}</span>
          <span class="tab-hint">
            {{ t('production.lots.detail.record.tabs.positions', positionCount) }}
            <template v-if="positionsInProgress > 0">
              · {{ t('production.lots.detail.record.tabs.inProgress', positionsInProgress) }}
            </template>
          </span>
        </Tab>
        <Tab class="record-tab" value="source">
          <span class="tab-title">{{ t('production.lots.detail.record.tabs.sourceAndDemand') }}</span>
          <span class="tab-hint">{{
            lot.source_label || t('production.lots.detail.record.tabs.noSource')
          }}</span>
        </Tab>
        <Tab class="record-tab" value="balance">
          <span class="tab-title">{{ t('production.lots.detail.record.tabs.balance') }}</span>
          <span class="tab-hint">{{ t('production.lots.detail.record.tabs.balanceHint') }}</span>
        </Tab>
        <Tab class="record-tab" value="project">
          <span class="tab-title">{{ t('production.lots.detail.record.project.title') }}</span>
          <span class="tab-hint">{{ lot.project_number }}</span>
        </Tab>
        <Tab class="record-tab" value="audit">
          <span class="tab-title">{{ t('production.lots.detail.audit.title') }}</span>
          <span class="tab-hint">{{
            t('production.lots.detail.record.tabs.events', events.length)
          }}</span>
        </Tab>
      </TabList>

      <TabPanels class="record-panels">
        <TabPanel class="record-panel" value="execution">
          <LotRecordExecution
            class="area-execution"
            :lot="lot"
            :events="events"
            :orders-for-position="recordData.ordersForPosition"
            :provisions-for-position="recordData.provisionsForPosition"
            :assessment-for-order="recordData.assessmentForOrder"
            :order-item-for-position="recordData.orderItemForPosition"
            :order-by-id="recordData.orderById"
            :files-for-order="recordData.filesForOrder"
          />
        </TabPanel>

        <TabPanel class="record-panel" value="source">
          <div class="source-pane">
            <LotRecordSource
              class="record-card record-card--scroll area-source"
              :lot="lot"
              :source-item="recordData.sourceItem.value"
              :source-item-demand="sourceItemDemand"
              :source-item-demand-arrived="sourceItemDemandArrived"
              :summary="sourceItemDemandSummary"
              :allocations="demandAllocations"
              :source-order="recordData.orderById(lot.source_order_id ?? null)"
              :manage-mode="manageMode"
              :can-write="canWrite"
              :can-approve="canApprove"
              @view-source-item="$emit('view-source-item')"
              @change-source="$emit('change-source')"
              @view-demand="$emit('view-demand')"
              @create-demand="$emit('create-demand')"
              @approve-source="$emit('approve-source')"
              @reject-source="$emit('reject-source')"
            />

            <LotRecordDemands
              class="record-card record-card--scroll area-demand"
              :demands="recordData.demands.value"
              :loading="recordData.loading.value"
            />

            <LotRecordMaterialReceipts
              class="record-card record-card--scroll area-receipts"
              :lot-id="lot.id"
            />
          </div>
        </TabPanel>

        <TabPanel class="record-panel" value="balance">
          <LotRecordPositionBalances class="record-card record-card--scroll" :lot-id="lot.id" />
        </TabPanel>

        <TabPanel class="record-panel" value="project">
          <LotRecordProject
            class="record-card record-card--scroll area-project"
            :lot="lot"
            :project="recordData.project.value"
          />
        </TabPanel>

        <TabPanel class="record-panel" value="audit">
          <LotRecordAudit
            class="record-card record-card--scroll area-audit"
            :events="events"
            :changelog="changelog"
            :loading="eventsLoading"
            :required-delivery-date="lot.required_delivery_date ?? null"
          />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped lang="scss">
// Left third pinned, right two thirds tabbed; cards scroll themselves.
//
// Every height in this chain must be definite: a .record-card--scroll card
// takes its content out of flow and collapses to its header under a
// content-sized ancestor. Hence the explicit 1fr row and flex: 1 1 0.
.record-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  grid-template-rows: minmax(0, 1fr);
  gap: var(--space-4);

  // Too narrow for two columns: the pinned cards stack above the tabs and
  // the whole body scrolls instead. Fixed row heights keep the chain
  // definite here too.
  @media (max-width: $bp-lg) {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: 30rem 40rem;
    overflow-y: auto;
  }
}

.record-column {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);

  > * {
    flex: 1 1 0;
    min-height: 12rem;
  }

  // The Lot card's fields are few and short, the Item card carries
  // thumbnails and files, so Item gets the larger share of the column.
  > .area-lot {
    flex-grow: 2;
  }

  > .area-item {
    flex-grow: 3;
  }
}

// Threads the pane height through the Tabs so the active panel fills it.
// The classes sit on TabList, Tab, TabPanels and TabPanel in this template,
// so they reach OpenVue's elements without naming its internal classes.
.record-tabs {
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
  // The strip sits on the card's own background.
  --p-tabs-tablist-background: transparent;
}

.record-tablist {
  flex-shrink: 0;
}

.record-tab {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-top: var(--space-3);
  padding-bottom: var(--space-3);
}

// Only this component's own panels: the Audit card nests its own Tabs.
.record-panels {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: var(--space-3);
}

// TabPanel renders a fragment, so its element carries no scope attribute
// and a plain scoped `.record-panel` rule never matches it. Reached through
// TabPanels instead; without the flex column the cards of the Source,
// Balance, Project and Audit tabs collapse to their headers.
.record-panels :deep(.record-panel) {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;

  > * {
    flex: 1 1 0;
    min-height: 0;
  }
}

.tab-title {
  font-weight: 600;
}

.tab-hint {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--p-text-muted-color);
  background: var(--p-content-hover-background);
  border-radius: 999px;
  padding: var(--space-1) var(--space-2);
  white-space: nowrap;

  // The tab titles alone already fill a phone's strip.
  @media (max-width: $bp-sm) {
    display: none;
  }
}

// Source Material and Originating Demand side by side; both scroll on
// their own, so the pane stays the height the tab hands it.
.source-pane {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: minmax(0, 1fr) minmax(0, 0.7fr);
  gap: var(--space-4);
  min-height: 0;

  @media (max-width: $bp-lg) {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: repeat(3, minmax(0, 1fr));
  }
}

// The receipts span the pane below the source and the demand.
.area-receipts {
  grid-column: 1 / -1;
}

// min-width: 0 lets the strip scroll instead of widening the column.
.area-execution {
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

// The layout of .record-card and .record-card--scroll lives in _openvue.scss.
// Lot and Item keep their footer inside the scroll body; margin-top: auto
// pins it to the bottom while the fields are short.
.record-card--scroll {
  :deep(.card-scroll-body--with-meta) {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  :deep(.record-meta) {
    flex-shrink: 0;
  }
}
</style>
