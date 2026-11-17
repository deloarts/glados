<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import EmptyState from '@/shared/components/EmptyState.vue'
import { placeInList, useRowDragReorder } from '@/shared/composables/useRowDragReorder'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import {
  placeProductDeviceKind,
  placeProductDeviceOption,
  setProductDeviceKindArchived,
  setProductDeviceOptionArchived,
} from '../api/productDeviceResourcesApi'
import { getPlcEnvironmentTemplate, setPlcEnvironmentArchived } from '../api/plcEnvironmentsApi'
import PlcEnvironmentDialog from '../components/PlcEnvironmentDialog.vue'
import ProductDeviceKindDialog from '../components/ProductDeviceKindDialog.vue'
import ProductDeviceOptionDialog from '../components/ProductDeviceOptionDialog.vue'
import { usePlcEnvironmentsStore } from '../stores/plcEnvironmentsStore'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import type { ListPlaceTarget } from '@/shared/types/listOrder'
import type {
  PlcEnvironment,
  PlcEnvironmentSettings,
  ProductDeviceKind,
  ProductDeviceOption,
  ProductDeviceOptionCategory,
} from '../types/productDevice'

/**
 * The resources tab for the lists product devices pick from: driving media,
 * device kinds, component roles, energy behaviours and sequence names, and
 * the PLC environments their tags are named for. The lists are maintained
 * here; entries are archived, never deleted. Every list but the PLC
 * environments is ordered by hand with the arrows of each row, and the
 * pickers offer the entries in that order, so the ones used most go first.
 */

type ListKey = ProductDeviceOptionCategory | 'kind' | 'plc_environment'

const LISTS: { key: ListKey; icon: string }[] = [
  { key: 'driving_medium', icon: 'mdi-air-filter' },
  { key: 'kind', icon: 'mdi-engine-outline' },
  { key: 'component_role', icon: 'mdi-puzzle-outline' },
  { key: 'energy_behaviour', icon: 'mdi-flash-outline' },
  { key: 'sequence_name', icon: 'mdi-sitemap-outline' },
  { key: 'plc_environment', icon: 'mdi-chip' },
]

const { t } = useI18n()
const toast = useAppToast()
const { toastOnError } = useErrorToast()
const { localize } = useLocalizedText()
const { hasPermission } = usePermissions()
const store = useProductDeviceResourcesStore()
const { loading, kinds } = storeToRefs(store)
watchLoadingBar(loading)

const { missing } = useMissingPermission()
const canWrite = computed(() => hasPermission(Permission.WRITE_PRODUCT_DEVICE_RESOURCES))
/** Names the missing write permission on the disabled New buttons and edit entries. */
const writeBlocked = computed(() => missing(Permission.WRITE_PRODUCT_DEVICE_RESOURCES))

// The switch needs a string label per option, otherwise SelectButton hands
// the whole option object to its toggle buttons as the label.
const listOptions = computed(() =>
  LISTS.map((list) => ({ ...list, label: t(`productDevices.resources.lists.${list.key}`) })),
)

const activeList = ref<ListKey>('driving_medium')
const showArchived = ref(false)

/** The option category the table shows, or null for kinds and PLC environments. */
const activeCategory = computed<ProductDeviceOptionCategory | null>(() =>
  activeList.value === 'kind' || activeList.value === 'plc_environment' ? null : activeList.value,
)
const optionRows = computed(() =>
  activeCategory.value === null ? [] : store.optionsOf(activeCategory.value, showArchived.value),
)
const kindRows = computed(() => kinds.value.filter((kind) => showArchived.value || !kind.archived))

const optionDialogVisible = ref(false)
const editingOption = ref<ProductDeviceOption | undefined>(undefined)
const kindDialogVisible = ref(false)
const editingKind = ref<ProductDeviceKind | undefined>(undefined)

const environmentsStore = usePlcEnvironmentsStore()
const environmentRows = computed(() =>
  environmentsStore.environments.filter((e) => showArchived.value || !e.archived),
)
const environmentDialogVisible = ref(false)
const editingEnvironment = ref<PlcEnvironment | undefined>(undefined)
const environmentTemplate = ref<PlcEnvironmentSettings | undefined>(undefined)

function reload(): void {
  void store.load(true)
  environmentsStore.load(true).catch(toastOnError())
}

onMounted(reload)

async function createEnvironment(): Promise<void> {
  try {
    environmentTemplate.value = await getPlcEnvironmentTemplate()
  } catch {
    environmentTemplate.value = undefined
  }
  editingEnvironment.value = undefined
  environmentDialogVisible.value = true
}

function editEnvironment(environment: PlcEnvironment): void {
  editingEnvironment.value = environment
  environmentDialogVisible.value = true
}

/** Opens the create dialog for one list and switches the table to it, so the new entry shows up. */
function onCreate(list: ListKey): void {
  activeList.value = list
  if (list === 'kind') {
    editingKind.value = undefined
    kindDialogVisible.value = true
  } else if (list === 'plc_environment') {
    void createEnvironment()
  } else {
    editingOption.value = undefined
    optionDialogVisible.value = true
  }
}

function editOption(option: ProductDeviceOption): void {
  editingOption.value = option
  optionDialogVisible.value = true
}

function editKind(kind: ProductDeviceKind): void {
  editingKind.value = kind
  kindDialogVisible.value = true
}

// Row actions live in a context menu per table: edit, archive or restore, and
// copying the UUID. The archive calls go straight to the API and the result
// replaces the row in the store.
const {
  cm: optionCm,
  contextMenuTarget: optionMenuTarget,
  contextMenuItems: optionMenuItems,
  onRowContextMenu: onOptionContextMenu,
} = useManagementResourceActions<ProductDeviceOption>(
  {
    archive: async (id) => store.upsertOption(await setProductDeviceOptionArchived(id, true)),
    restore: async (id) => store.upsertOption(await setProductDeviceOptionArchived(id, false)),
  },
  {
    i18nPrefix: 'productDevices.resources',
    entityLabel: (option) => localize(option.label),
    deletePermission: Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
    archivable: { isArchived: (option) => option.archived },
    showDetailItem: false,
    editItem: (option) => ({
      label: t('productDevices.resources.editEntry'),
      icon: 'mdi mdi-pencil',
      disabled: !canWrite.value,
      title: writeBlocked.value || undefined,
      command: () => editOption(option),
    }),
  },
)

const {
  cm: kindCm,
  contextMenuTarget: kindMenuTarget,
  contextMenuItems: kindMenuItems,
  onRowContextMenu: onKindContextMenu,
} = useManagementResourceActions<ProductDeviceKind>(
  {
    archive: async (id) => store.upsertKind(await setProductDeviceKindArchived(id, true)),
    restore: async (id) => store.upsertKind(await setProductDeviceKindArchived(id, false)),
  },
  {
    i18nPrefix: 'productDevices.resources',
    entityLabel: (kind) => localize(kind.label),
    deletePermission: Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
    archivable: { isArchived: (kind) => kind.archived },
    showDetailItem: false,
    editItem: (kind) => ({
      label: t('productDevices.resources.editKind'),
      icon: 'mdi mdi-pencil',
      disabled: !canWrite.value,
      title: writeBlocked.value || undefined,
      command: () => editKind(kind),
    }),
  },
)

const {
  cm: environmentCm,
  contextMenuTarget: environmentMenuTarget,
  contextMenuItems: environmentMenuItems,
  onRowContextMenu: onEnvironmentContextMenu,
} = useManagementResourceActions<PlcEnvironment>(
  {
    archive: async (id) => environmentsStore.upsert(await setPlcEnvironmentArchived(id, true)),
    restore: async (id) => environmentsStore.upsert(await setPlcEnvironmentArchived(id, false)),
  },
  {
    i18nPrefix: 'productDevices.resources',
    entityLabel: (environment) => environment.name,
    deletePermission: Permission.WRITE_PRODUCT_DEVICE_RESOURCES,
    archivable: { isArchived: (environment) => environment.archived },
    showDetailItem: false,
    editItem: (environment) => ({
      label: t('productDevices.plc.editEnvironment'),
      icon: 'mdi mdi-pencil',
      disabled: !canWrite.value,
      title: writeBlocked.value || undefined,
      command: () => editEnvironment(environment),
    }),
  },
)

// ── Order ─────────────────────────────────────────────────────────────

// The grip in the first column drags a row to a new place, for users who may
// edit the lists. The store takes the new order at once, archived entries
// hidden from the table included, so the row stays where it was dropped; the
// server's answer then replaces it, and a failure reloads the lists.
async function placeOptimistically<T>(
  show: () => void,
  request: () => Promise<T>,
  apply: (result: T) => void,
): Promise<void> {
  show()
  try {
    apply(await request())
  } catch (error) {
    void store.load(true)
    throw error
  }
}

const { handlePt, onRowReorder: onOptionReorder } = useRowDragReorder(
  () => optionRows.value,
  (id: number, target: ListPlaceTarget) => {
    const category = activeCategory.value
    if (category === null) return Promise.resolve()
    return placeOptimistically(
      () => store.replaceOptionsOf(category, placeInList(store.optionsOf(category, true), id, target)),
      () => placeProductDeviceOption(id, target),
      (ordered) => store.replaceOptionsOf(category, ordered),
    )
  },
)

const { onRowReorder: onKindReorder } = useRowDragReorder(
  () => kindRows.value,
  (id: number, target: ListPlaceTarget) =>
    placeOptimistically(
      () => store.replaceKinds(placeInList(kinds.value, id, target)),
      () => placeProductDeviceKind(id, target),
      (ordered) => store.replaceKinds(ordered),
    ),
)

/** The prefixes of the four plain signal types, as the table shows them. */
function prefixSummary(environment: PlcEnvironment): string {
  return (['di', 'do', 'ai', 'ao'] as const)
    .map((key) => environment.prefixes[key])
    .filter(Boolean)
    .join(' ')
}

function liveLabels(items: { label: Record<string, string>; archived: boolean }[]): string {
  return items
    .filter((item) => !item.archived)
    .map((item) => localize(item.label))
    .join(', ')
}

function onSaved(label: Record<string, string>): void {
  toast.success(localize(label), t('productDevices.resources.saved'))
}
</script>

<template>

  <PageLayout>
    <template #controls>
      <ControlsBar>
        <template #start>
          <span v-for="list in LISTS" :key="list.key" v-tooltip.bottom="writeBlocked || undefined">
            <Button
              :label="t(`productDevices.resources.create.${list.key}`)"
              icon="mdi mdi-plus"
              severity="contrast"
              text
              :disabled="!canWrite"
              :data-testid="`device-resource-create-${list.key}`"
              @click="onCreate(list.key)"
            />
          </span>
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <template #views>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.sync')"
            icon="mdi mdi-sync"
            severity="contrast"
            text
            :loading="loading"
            @click="reload"
          />
          <Button
            :label="t('common.showArchived')"
            icon="mdi mdi-archive-outline"
            severity="contrast"
            :text="!showArchived"
            @click="showArchived = !showArchived"
          />
          <Divider layout="vertical" />
          <SelectButton
            v-model="activeList"
            :options="listOptions"
            option-label="label"
            option-value="key"
            :allow-empty="false"
            class="list-switch"
            data-testid="device-resource-list"
          >
            <template #option="{ option }">
              <i :class="`mdi ${option.icon}`" aria-hidden="true" />
              <span>{{ option.label }}</span>
            </template>
          </SelectButton>
        </template>
      </Toolbar>
    </template>

    <p class="list-hint">{{ t(`productDevices.resources.hints.${activeList}`) }}</p>

    <DataTable
      v-if="activeList === 'plc_environment'"
      v-model:context-menu-selection="environmentMenuTarget"
      :value="environmentRows"
      data-key="id"
      size="small"
      scrollable
      scroll-height="flex"
      context-menu
      class="resources-table"
      data-testid="plc-environments-table"
      @row-contextmenu="onEnvironmentContextMenu"
    >
      <template #empty><EmptyState /></template>
      <Column header="#" body-class="row-number" class="column-fit">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('productDevices.plc.fields.name')" class="column-fit">
        <template #body="{ data }: { data: PlcEnvironment }">
          {{ data.name }}
          <Tag v-if="data.is_default" :value="t('productDevices.plc.defaultTag')" severity="info" class="ml-tag" />
          <Tag v-if="data.archived" :value="t('common.archivedTag')" severity="warn" class="ml-tag" />
        </template>
      </Column>
      <Column :header="t('productDevices.plc.sections.prefixes')" class="column-fit">
        <template #body="{ data }: { data: PlcEnvironment }">
          <code>{{ prefixSummary(data) }}</code>
        </template>
      </Column>
      <Column :header="t('productDevices.plc.fields.maxTagLength')" class="column-fit">
        <template #body="{ data }: { data: PlcEnvironment }">{{ data.max_tag_length }}</template>
      </Column>
      <Column :header="t('productDevices.plc.fields.tagTable')">
        <template #body="{ data }: { data: PlcEnvironment }">{{ data.tag_table }}</template>
      </Column>
    </DataTable>

    <DataTable
      v-else-if="activeCategory !== null"
      v-model:context-menu-selection="optionMenuTarget"
      :value="optionRows"
      data-key="id"
      size="small"
      scrollable
      scroll-height="flex"
      context-menu
      class="resources-table"
      @row-reorder="onOptionReorder"
      @row-contextmenu="onOptionContextMenu"
    >
      <template #empty><EmptyState /></template>
      <Column
        v-if="canWrite"
        row-reorder
        row-reorder-icon="mdi mdi-drag-vertical"
        :pt="handlePt"
        class="column-fit"
      />
      <Column header="#" body-class="row-number" class="column-fit">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column
        :header="t('productDevices.resources.fields.label')"
        :class="{ 'column-fit': activeList === 'driving_medium' }"
      >
        <template #body="{ data }: { data: ProductDeviceOption }">
          {{ localize(data.label) }}
          <Tag v-if="data.archived" :value="t('common.archivedTag')" severity="warn" class="ml-tag" />
        </template>
      </Column>
      <Column
        v-if="activeList === 'driving_medium'"
        :header="t('productDevices.resources.fields.letter')"
      >
        <template #body="{ data }: { data: ProductDeviceOption }">
          <code>{{ data.letter }}</code>
        </template>
      </Column>
    </DataTable>

    <DataTable
      v-else
      v-model:context-menu-selection="kindMenuTarget"
      :value="kindRows"
      data-key="id"
      size="small"
      scrollable
      scroll-height="flex"
      context-menu
      class="resources-table"
      @row-reorder="onKindReorder"
      @row-contextmenu="onKindContextMenu"
    >
      <template #empty><EmptyState /></template>
      <Column
        v-if="canWrite"
        row-reorder
        row-reorder-icon="mdi mdi-drag-vertical"
        :pt="handlePt"
        class="column-fit"
      />
      <Column header="#" body-class="row-number" class="column-fit">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('productDevices.resources.fields.label')" class="column-fit">
        <template #body="{ data }: { data: ProductDeviceKind }">
          {{ localize(data.label) }}
          <Tag v-if="data.archived" :value="t('common.archivedTag')" severity="warn" class="ml-tag" />
        </template>
      </Column>
      <Column :header="t('productDevices.resources.positions')">
        <template #body="{ data }: { data: ProductDeviceKind }">
          {{ liveLabels(data.positions) }}
        </template>
      </Column>
      <Column :header="t('productDevices.resources.parameters')">
        <template #body="{ data }: { data: ProductDeviceKind }">
          {{ liveLabels(data.parameters) }}
        </template>
      </Column>
    </DataTable>
  </PageLayout>

  <ProductDeviceOptionDialog
    v-if="activeCategory !== null"
    v-model:visible="optionDialogVisible"
    :category="activeCategory"
    :option="editingOption"
    @saved="onSaved($event.label)"
  />
  <ProductDeviceKindDialog
    v-model:visible="kindDialogVisible"
    :kind="editingKind"
    @saved="onSaved($event.label)"
  />

  <ContextMenu ref="optionCm" :model="optionMenuItems" :pt="disabledItemTooltipPt" @hide="optionMenuTarget = null" />
  <ContextMenu ref="kindCm" :model="kindMenuItems" :pt="disabledItemTooltipPt" @hide="kindMenuTarget = null" />
  <ContextMenu ref="environmentCm" :model="environmentMenuItems" :pt="disabledItemTooltipPt" @hide="environmentMenuTarget = null" />
  <PlcEnvironmentDialog
    v-model:visible="environmentDialogVisible"
    :environment="editingEnvironment"
    :template="environmentTemplate"
    @saved="(saved) => toast.success(saved.name, t('productDevices.resources.saved'))"
  />
</template>

<style scoped lang="scss">
.list-switch {
  --p-togglebutton-gap: var(--space-1);
}

.list-hint {
  margin: 0 0 var(--space-2);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.resources-table {
  flex: 1;
  min-height: 0;
}

.ml-tag {
  margin-left: var(--space-2);
}
</style>
