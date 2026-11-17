<script setup lang="ts" generic="T extends DemandsTableRow">
// The table frame shared by the bought, made and source item demand tables:
// the lazy paginated DataTable with its row filter bar, row grouping header
// and empty state, the bulk selection, actions and row number columns, the
// desired delivery and created columns that close every table, the
// context menu and the bulk cancel confirm. Each kind plugs its own columns
// in through the `columns` slot, its row buttons through `row-actions`, and
// keeps its stores, dialogs and menu entries to itself. Nothing in here
// knows which kind it renders.
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useLayoutStore } from '@/core/stores/layoutStore'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import ConfirmActionDialog from '@/shared/components/dialogs/ConfirmActionDialog.vue'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import DemandDateCell from './DemandDateCell.vue'
import DemandDateRangeFilter from './DemandDateRangeFilter.vue'
import {
  demandRowNumberColumnDef,
  demandDesiredDeliveryColumnDef,
  demandCreatedColumnDef,
} from './demandColumnDefs'

import type {
  DataTableFilterMeta,
  DataTablePageEvent,
  DataTableRowClickEvent,
  DataTableRowContextMenuEvent,
  DataTableRowSelectEvent,
} from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'
import type { DemandsTableRow, DemandsTableShellLabels } from './demandsTableShell'

type DateRangeValue = Date | Array<Date | null> | null | undefined

const props = withDefaults(
  defineProps<{
    items: T[]
    total: number
    first: number
    rows: number
    /**
     * OpenVue's row filter bar needs an entry per filterable column even
     * though filtering runs server side, see the kind's decoy object.
     */
    filters: DataTableFilterMeta
    groupBy: string | null
    /** Row field holding the group label, from useDemandGrouping. */
    groupRowsBy: string | undefined
    /** Header icon per grouping of the kind's own, such as project. */
    groupIcons: Record<string, string>
    /**
     * Shows the checkbox column to a user who cannot change demands, for
     * example while a manage panel works on the selection. A user who can
     * change demands always sees it.
     */
    showSelectionColumn: boolean
    showActions: boolean
    actionsWidth: string
    tableMinWidth?: string
    contextMenuItems: MenuItem[]
    labels: DemandsTableShellLabels
  }>(),
  { tableMinWidth: '60rem' },
)

// One shared selection drives the bulk checkbox column and the open gesture
// through selectionMode="multiple" with metaKeySelection: click opens,
// ctrl-click toggles, shift-click ranges. The context menu has its own
// selection. While rows are selected OpenVue drops keyboard row access,
// an accepted trade-off.
const selection = defineModel<T[]>('selection', { required: true })
const contextMenuSelection = defineModel<T | null>('contextMenuSelection', { required: true })
const bulkCancelVisible = defineModel<boolean>('bulkCancelVisible', { required: true })
const desiredRange = defineModel<DateRangeValue>('desiredRange', { required: true })
const creatorId = defineModel<number | null>('creatorId', { required: true })
/** Leave unbound for a created column that filters by its creator only. */
const createdRange = defineModel<DateRangeValue>('createdRange')

const emit = defineEmits<{
  page: [event: DataTablePageEvent]
  'row-click': [event: DataTableRowClickEvent<T>]
  'row-select': [event: DataTableRowSelectEvent<T>]
  'table-click-capture': [event: MouseEvent]
  'confirm-bulk-cancel': []
}>()

defineSlots<{
  columns?(): unknown
  'row-actions'?(props: { data: T }): unknown
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { hasPermission } = usePermissions()

// Bulk actions such as bucket assignment and status changes work on the
// selection, so a user who may run them keeps the checkboxes and the select
// all box in view instead of building a selection with ctrl-click first.
const isSelectionColumnVisible = computed(
  () => props.showSelectionColumn || hasPermission(Permission.WRITE_DEMAND_ITEMS),
)

const contextMenu = ref<{ show: (event: Event) => void } | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  contextMenu.value?.show(event.originalEvent)
}
</script>

<template>
  <DataTable
    :value="items"
    data-key="id"
    lazy
    paginator
    :total-records="total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="emit('page', $event)"
    scrollable
    scroll-height="flex"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    resizable-columns
    column-resize-mode="expand"
    filter-display="row"
    :filters="filters"
    size="small"
    :table-style="`min-width: ${tableMinWidth}`"
    :row-group-mode="groupBy ? 'subheader' : undefined"
    :group-rows-by="groupRowsBy"
    selection-mode="multiple"
    :meta-key-selection="true"
    context-menu
    :selection="selection"
    @update:selection="(v) => (selection = v as T[])"
    @row-click="emit('row-click', $event)"
    @row-select="emit('row-select', $event)"
    @click.capture="emit('table-click-capture', $event)"
    v-model:context-menu-selection="contextMenuSelection"
    @row-contextmenu="onRowContextMenu"
    class="phone-columns clickable-rows"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="groupBy === 'status'" class="mdi mdi-flag-outline" aria-hidden="true" />
        <i v-else-if="groupBy === 'bucket'" class="mdi mdi-bucket-outline" aria-hidden="true" />
        <i v-else :class="groupIcons[groupBy]" aria-hidden="true" />
        <span class="group-header-label">{{ groupRowsBy ? data[groupRowsBy] : '' }}</span>
      </div>
    </template>
    <template #empty>
      <EmptyState />
    </template>

    <Column v-if="isSelectionColumnVisible" selection-mode="multiple" style="width: 3rem" frozen />

    <Column v-if="showActions" :style="`width: ${actionsWidth}`" frozen align-frozen="right">
      <template #body="{ data }: { data: T }">
        <div class="row-actions">
          <slot name="row-actions" :data="data" />
        </div>
      </template>
    </Column>

    <Column v-bind="demandRowNumberColumnDef()" class="phone-row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>

    <slot name="columns" />

    <Column v-bind="demandDesiredDeliveryColumnDef(labels.desiredDelivery)">
      <template #body="{ data }: { data: T }">
        <DemandDateCell :value="data.desired_delivery_date" />
      </template>
      <template #filter>
        <DemandDateRangeFilter
          v-model="desiredRange"
          :placeholder="labels.dateFilterPlaceholder"
          @clear-click="desiredRange = null"
        />
      </template>
    </Column>

    <!-- When the demand was created and by whom. Without a bound range the
         filter picks the creator only. -->
    <Column v-bind="demandCreatedColumnDef(labels.created)">
      <template #body="{ data }: { data: T }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          :range="createdRange ?? null"
          :column="labels.created"
          :placeholder="labels.creatorPlaceholder"
          :user-only="createdRange === undefined"
          @update:range="createdRange = $event"
        />
      </template>
    </Column>

    <Column />
  </DataTable>

  <ConfirmActionDialog
    v-model:visible="bulkCancelVisible"
    :header="labels.bulkCancelHeader"
    :message="labels.bulkCancelMessage"
    :confirm-label="labels.bulkCancelAction"
    :dismiss-label="t('common.no')"
    @confirm="emit('confirm-bulk-cancel')"
  />

  <ContextMenu
    ref="contextMenu"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuSelection = null"
  />
</template>

<style scoped lang="scss">
.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}
</style>
