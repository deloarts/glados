<!--
  The SolidWorks PDM tab's "API Console" side panel: lists the 113-entry
  SOLIDWORKS PDM Web API operation catalogue, grouped by resource group,
  filterable by group and free-text search. Modelled on ApiKeyDocsPanel.vue
  (same Panel + header row + close button shape, same method-severity Tag),
  but rows open PdmOperationDialog.vue instead of expanding inline: the
  console executes real calls against the live vault, it does not just
  document them.

  Mutating rows (28 of the 113) stay locked, shown with a lock icon and
  not clickable, until the parent's "Allow Critical Endpoints" switch
  (criticalMode) is on. While the deployment leaves mutating operations off
  (mutatingOperationsEnabled false) the lock's tooltip names that instead.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAdminSettingsStore } from '../../stores/adminSettingsStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import PdmOperationDialog from './PdmOperationDialog.vue'
import type { PdmOperation } from '../../types/adminSettingsTypes'

const METHOD_SEVERITY: Record<string, string> = {
  GET: 'info',
  POST: 'success',
  PUT: 'warn',
  PATCH: 'warn',
  DELETE: 'danger',
}

const { t } = useI18n()
const store = useAdminSettingsStore()

const props = defineProps<{
  criticalMode: boolean
  mutatingOperationsEnabled: boolean
}>()

const lockedTooltip = computed(() =>
  props.mutatingOperationsEnabled
    ? t('adminSettings.solidworksPdm.pdm.console.mutatingLockedTooltip')
    : t('adminSettings.solidworksPdm.pdm.console.mutatingDisabledTooltip'),
)

const emit = defineEmits<{ close: [] }>()

const loading = ref(false)
const loadFailed = ref(false)
const search = ref('')
const groupFilter = ref<string | null>(null)

watchLoadingBar(loading)

async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    await store.loadPdmOperations()
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)

const groupOptions = computed<string[]>(() =>
  [...new Set(store.pdmOperations.map((op) => op.group))].sort((a, b) => a.localeCompare(b)),
)

const filteredOperations = computed<PdmOperation[]>(() => {
  const query = search.value.trim().toLowerCase()
  return store.pdmOperations.filter((op) => {
    if (groupFilter.value && op.group !== groupFilter.value) return false
    if (!query) return true
    return (
      op.path.toLowerCase().includes(query) ||
      op.description.toLowerCase().includes(query) ||
      op.id.toLowerCase().includes(query)
    )
  })
})

interface OperationGroup {
  group: string
  operations: PdmOperation[]
}

const groupedOperations = computed<OperationGroup[]>(() => {
  const byGroup = new Map<string, PdmOperation[]>()
  for (const op of filteredOperations.value) {
    const bucket = byGroup.get(op.group)
    if (bucket) bucket.push(op)
    else byGroup.set(op.group, [op])
  }
  return [...byGroup.entries()]
    .map(([group, operations]) => ({
      group,
      operations: operations.sort((a, b) => a.path.localeCompare(b.path)),
    }))
    .sort((a, b) => a.group.localeCompare(b.group))
})

const isEmpty = computed(
  () => !loading.value && !loadFailed.value && groupedOperations.value.length === 0,
)

function isLocked(op: PdmOperation, criticalMode: boolean): boolean {
  return op.mutating && !criticalMode
}

const selectedOperation = ref<PdmOperation | null>(null)
const dialogVisible = ref(false)

function onRowClick(op: PdmOperation, criticalMode: boolean): void {
  if (isLocked(op, criticalMode)) return
  selectedOperation.value = op
  dialogVisible.value = true
}
</script>

<template>
  <Panel class="console-panel fill-panel">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('adminSettings.solidworksPdm.pdm.console.title') }}</span>
        <div class="panel-header-actions">
          <Select
            v-model="groupFilter"
            :aria-label="t('adminSettings.solidworksPdm.pdm.console.groupFilter')"
            :options="groupOptions"
            :placeholder="t('adminSettings.solidworksPdm.pdm.console.groupFilterAll')"
            show-clear
            class="group-select"
          />
          <IconField>
            <InputIcon class="mdi mdi-magnify" />
            <InputText
              v-model="search"
              :placeholder="t('adminSettings.solidworksPdm.pdm.console.searchPlaceholder')"
              class="search-input"
            />
          </IconField>
          <Button
            icon="mdi mdi-close"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="t('common.close')"
            :aria-label="t('common.close')"
            @click="emit('close')"
          />
        </div>
      </div>
    </template>

    <div class="console-body">
      <div v-if="loading" class="console-status" />

      <Message v-else-if="loadFailed" severity="error" :closable="false">
        <div class="console-error">
          <span>{{ t('adminSettings.solidworksPdm.pdm.console.loadFailed') }}</span>
          <Button :label="t('common.reload')" size="small" text @click="load" />
        </div>
      </Message>

      <Message v-else-if="isEmpty" severity="info" :closable="false">
        {{ t('adminSettings.solidworksPdm.pdm.console.empty') }}
      </Message>

      <template v-else>
        <div v-for="group in groupedOperations" :key="group.group" class="console-group">
          <div class="group-title">{{ group.group }}</div>

          <div
            v-for="op in group.operations"
            :key="op.id"
            class="op-row"
            :class="{ 'op-row--locked': isLocked(op, criticalMode) }"
            role="button"
            tabindex="0"
            :aria-disabled="isLocked(op, criticalMode) || undefined"
            @click="onRowClick(op, criticalMode)"
            @keydown.enter="onRowClick(op, criticalMode)"
          >
            <Tag class="op-method" :severity="METHOD_SEVERITY[op.method] ?? 'secondary'" :value="op.method" />
            <code class="op-path">{{ op.path }}</code>
            <span class="op-description">{{ op.description }}</span>
            <i
              v-if="isLocked(op, criticalMode)"
              class="mdi mdi-lock-outline op-lock"
              data-testid="op-lock"
              v-tooltip.top="lockedTooltip"
            />
          </div>
        </div>
      </template>
    </div>
  </Panel>

  <PdmOperationDialog
    v-model:visible="dialogVisible"
    :operation="selectedOperation"
    :critical-mode="criticalMode"
  />
</template>

<style scoped lang="scss">
.console-panel {
  flex: 0 0 auto;
  width: 34rem;
  max-width: 100%;
  --fill-panel-overflow-y: hidden;
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-2);
}

.panel-title {
  flex-shrink: 0;
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.group-select {
  width: 9rem;
}

.search-input {
  width: 10rem;
}

.console-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.console-status {
  display: flex;
  justify-content: center;
  padding: var(--space-6) 0;
}

.console-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.console-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.group-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.op-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--p-content-border-radius);
  cursor: pointer;

  &:hover {
    background: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: 2px solid var(--p-focus-ring-color);
    outline-offset: -2px;
  }

  &--locked {
    cursor: default;
    opacity: 0.6;

    &:hover {
      background: transparent;
    }
  }
}

.op-method {
  flex: 0 0 auto;
  font-size: var(--font-size-xs);
}

.op-path {
  flex: 0 0 auto;
  font-family: monospace;
  font-size: var(--font-size-sm);
}

.op-description {
  flex: 1;
  min-width: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.op-lock {
  flex: 0 0 auto;
  color: var(--p-text-muted-color);
}
</style>
