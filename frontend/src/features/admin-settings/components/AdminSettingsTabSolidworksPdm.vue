<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useConfirm } from 'openvue/useconfirm'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePdmSyncActivityStore } from '../stores/pdmSyncActivityStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useSettingsSave } from '../composables/useSettingsSave'
import { extractApiError } from '@/core/utils/errors'
import {
  buildRequiredFieldNames,
  mergeRevisionFieldPolicy,
  validateKindVariableMatch,
  validateVariableMap,
  validateWritebackVariables,
} from '../utils/itemFieldOwnership'
import {
  hasFeatureTreeTemplateError,
  validateFeatureTreeTemplate,
} from '../utils/featureTreeTemplate'
import { validatePdmSync } from '../utils/pdmSync'
import { useTemplateFileTransfer } from '@/shared/composables/useTemplateFileTransfer'
import { parseTemplateFile, requireStringMap, unknownKeys } from '@/shared/utils/templateFile'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import ItemFieldOwnershipTable from './ItemFieldOwnershipTable.vue'
import PdmConnectionSection from './pdm/PdmConnectionSection.vue'
import PdmSyncSection from './pdm/PdmSyncSection.vue'
import FeatureTreeTemplateField from './pdm/FeatureTreeTemplateField.vue'
import PdmDatacardHeader from './pdm/PdmDatacardHeader.vue'
import PdmApiConsolePanel from './pdm/PdmApiConsolePanel.vue'
import PdmFilesDialog from './pdm/PdmFilesDialog.vue'
import PdmSyncLogDialog from './pdm/PdmSyncLogDialog.vue'
import PdmReconciliationDialog from './pdm/PdmReconciliationDialog.vue'
import PdmUsersDialog from './pdm/PdmUsersDialog.vue'
import PdmSyncActivityDialog from './pdm/PdmSyncActivityDialog.vue'
import type { ItemFieldOwnership, PdmAddinLanguage, PdmSession, PdmWatchedFolder } from '../types/adminSettingsTypes'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const { t } = useI18n()
const appToast = useAppToast()
const confirm = useConfirm()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

// Local edit state keyed by field name. Only pdm_update_in_place is edited
// here; the Numbering tab owns web_requires_revision.
const madeVariableMap = reactive<Record<string, string>>({})
const boughtVariableMap = reactive<Record<string, string>>({})
const madeUpdateInPlace = reactive<Record<string, boolean>>({})
// Required-field toggles keyed by field or pseudo-rule name, shared by the
// Validation column and the "Further Rules" checklist. Never holds a locked
// name.
const madeRequired = reactive<Record<string, boolean>>({})
const boughtRequired = reactive<Record<string, boolean>>({})

let seededFor: unknown = null

function ensureSeeded(): void {
  const pdm = store.settings?.pdm
  const madeItems = store.settings?.made_items
  if (!pdm || !madeItems || seededFor === pdm) return
  seededFor = pdm

  for (const row of pdm.item_fields.made) {
    madeVariableMap[row.field] = pdm.made_item_variable_map[row.field] ?? ''
    if (row.mappable && !pdm.locked_required_fields.made.includes(row.field)) {
      madeRequired[row.field] = pdm.required_fields.made.includes(row.field)
    }
  }
  for (const row of pdm.item_fields.bought) {
    boughtVariableMap[row.field] = pdm.bought_item_variable_map[row.field] ?? ''
    if (row.mappable && !pdm.locked_required_fields.bought.includes(row.field)) {
      boughtRequired[row.field] = pdm.required_fields.bought.includes(row.field)
    }
  }
  for (const name of pdm.required_field_rules.made) {
    madeRequired[name] = pdm.required_fields.made.includes(name)
  }
  for (const name of pdm.required_field_rules.bought) {
    boughtRequired[name] = pdm.required_fields.bought.includes(name)
  }
  for (const entry of madeItems.revision_field_policy) {
    madeUpdateInPlace[entry.field] = entry.pdm_update_in_place
  }
}

const madeRuleNames = computed<string[]>(() => store.settings?.pdm.required_field_rules.made ?? [])
const boughtRuleNames = computed<string[]>(
  () => store.settings?.pdm.required_field_rules.bought ?? [],
)

// Revision is data, not identity, for bought items (docs/FIELD_OWNERSHIP.md
// principle 2), so it is a normal checkbox here and this hint explains
// unchecking it.
const boughtRevisionOptional = computed<boolean>(() => {
  ensureSeeded()
  return boughtRequired.revision === false
})

const madeRows = computed<ItemFieldOwnership[]>(() => {
  ensureSeeded()
  return store.settings?.pdm.item_fields.made ?? []
})

const boughtRows = computed<ItemFieldOwnership[]>(() => {
  ensureSeeded()
  return store.settings?.pdm.item_fields.bought ?? []
})

function mappableCount(rows: ItemFieldOwnership[]): number {
  return rows.filter((row) => row.mappable).length
}

function mappedCount(rows: ItemFieldOwnership[], map: Record<string, string>): number {
  return rows.filter((row) => row.mappable && (map[row.field] ?? '').trim() !== '').length
}

const madeMappableCount = computed(() => mappableCount(madeRows.value))
const madeMappedCount = computed(() => mappedCount(madeRows.value, madeVariableMap))
const boughtMappableCount = computed(() => mappableCount(boughtRows.value))
const boughtMappedCount = computed(() => mappedCount(boughtRows.value, boughtVariableMap))

function mappedCountLabel(mapped: number, total: number): string {
  return t('adminSettings.solidworksPdm.fieldsMappedCount', { mapped, total })
}

// ── Variable maps as a template file ──
// An import fills the variable maps of the mappable fields it names; the
// admin saves as usual. The export writes the maps the form holds now.

const VARIABLE_MAP_KEYS = ['made_item_variable_map', 'bought_item_variable_map'] as const

const { importFiles, exportFile } = useTemplateFileTransfer()

const importVariableMapsBlocked = computed(() =>
  canWrite ? '' : t('common.permissionMissing', { permission: permissionLabel(t, Permission.WRITE_SETTINGS) }),
)

function mappableVariables(rows: ItemFieldOwnership[], map: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    rows.filter((row) => row.mappable).map((row) => [row.field, (map[row.field] ?? '').trim()]),
  )
}

function onImportVariableMaps(): void {
  void importFiles('.json', ([file]) => {
    const content = parseTemplateFile(file!.text, 'pdm_variable_maps')
    const ignored = unknownKeys(content, VARIABLE_MAP_KEYS)
    const targets = [
      { key: VARIABLE_MAP_KEYS[0], rows: madeRows.value, map: madeVariableMap },
      { key: VARIABLE_MAP_KEYS[1], rows: boughtRows.value, map: boughtVariableMap },
    ]
    // Every map is read before any is applied, so a bad file changes nothing.
    const values = targets.map(({ key }) => (key in content ? requireStringMap(content, key) : {}))
    targets.forEach(({ key, rows, map }, index) => {
      for (const [field, variable] of Object.entries(values[index]!)) {
        if (rows.some((row) => row.field === field && row.mappable)) map[field] = variable
        else ignored.push(`${key}.${field}`)
      }
    })
    return ignored
  })
}

function onExportVariableMaps(): void {
  exportFile(
    'pdm_variable_maps',
    {
      made_item_variable_map: mappableVariables(madeRows.value, madeVariableMap),
      bought_item_variable_map: mappableVariables(boughtRows.value, boughtVariableMap),
    },
    'variable_maps.json',
  )
}

const madeValidation = computed(() => validateVariableMap(madeVariableMap))
const boughtValidation = computed(() => validateVariableMap(boughtVariableMap))
const kindMismatch = computed(() => validateKindVariableMatch(madeVariableMap, boughtVariableMap))
const writebackMismatch = computed(() =>
  validateWritebackVariables(madeVariableMap, boughtVariableMap, syncForm.writeback_enabled),
)

// ── SolidWorks PDM Web API connection ───────────────────────────────────
interface ConnectionForm {
  base_url: string
  vault_name: string
  username: string
  password: string
  verify_certificate: boolean
  timeout_seconds: number
}

const connectionForm = reactive<ConnectionForm>({
  base_url: '',
  vault_name: '',
  username: '',
  password: '',
  verify_certificate: true,
  timeout_seconds: 15,
})

// ── SolidWorks PDM synchronisation ──────────────────────────────────────
interface SyncForm {
  enabled: boolean
  watched_folders: PdmWatchedFolder[]
  made_released_state_ids: number[]
  made_obsolete_state_ids: number[]
  made_replaced_state_ids: number[]
  bought_released_state_ids: number[]
  bought_obsolete_state_ids: number[]
  bought_replaced_state_ids: number[]
  document_released_state_ids: number[]
  poll_interval_minutes: number
  cold_folder_max_multiplier: number
  ingest_concurrency: number
  cad_items_read_only: boolean
  addin_language: PdmAddinLanguage
  writeback_enabled: boolean
  made_item_extensions: string[]
  bought_item_extensions: string[]
  document_categories: Record<string, string>
  document_excluded_kinds: Record<string, string[]>
  thumbnails_enabled: boolean
  stuck_after_days: number
  set_approver_from_pdm: boolean
}

const syncForm = reactive<SyncForm>({
  enabled: false,
  watched_folders: [],
  made_released_state_ids: [],
  made_obsolete_state_ids: [],
  made_replaced_state_ids: [],
  bought_released_state_ids: [],
  bought_obsolete_state_ids: [],
  bought_replaced_state_ids: [],
  document_released_state_ids: [],
  poll_interval_minutes: 15,
  cold_folder_max_multiplier: 8,
  ingest_concurrency: 4,
  cad_items_read_only: true,
  addin_language: '',
  writeback_enabled: false,
  made_item_extensions: [],
  bought_item_extensions: [],
  document_categories: {},
  document_excluded_kinds: {},
  thumbnails_enabled: false,
  stuck_after_days: 7,
  set_approver_from_pdm: false,
})

// One feature-tree template per kind, see docs/FIELD_OWNERSHIP.md, "Label
// properties and the feature-tree template".
const madeFeatureTreeTemplate = ref('')
const boughtFeatureTreeTemplate = ref('')

watch(
  () => store.settings?.pdm,
  (pdm) => {
    if (!pdm) return
    connectionForm.base_url = pdm.base_url
    connectionForm.vault_name = pdm.vault_name
    connectionForm.username = pdm.username
    connectionForm.password = ''
    connectionForm.verify_certificate = pdm.verify_certificate
    connectionForm.timeout_seconds = pdm.timeout_seconds

    syncForm.enabled = pdm.enabled
    syncForm.watched_folders = pdm.watched_folders.map((folder) => ({ ...folder }))
    syncForm.made_released_state_ids = [...pdm.made_released_state_ids]
    syncForm.made_obsolete_state_ids = [...pdm.made_obsolete_state_ids]
    syncForm.made_replaced_state_ids = [...pdm.made_replaced_state_ids]
    syncForm.bought_released_state_ids = [...pdm.bought_released_state_ids]
    syncForm.bought_obsolete_state_ids = [...pdm.bought_obsolete_state_ids]
    syncForm.bought_replaced_state_ids = [...pdm.bought_replaced_state_ids]
    syncForm.document_released_state_ids = [...pdm.document_released_state_ids]
    syncForm.poll_interval_minutes = pdm.poll_interval_minutes
    syncForm.cold_folder_max_multiplier = pdm.cold_folder_max_multiplier
    syncForm.ingest_concurrency = pdm.ingest_concurrency
    syncForm.cad_items_read_only = pdm.cad_items_read_only
    syncForm.addin_language = pdm.addin_language as PdmAddinLanguage
    syncForm.writeback_enabled = pdm.writeback_enabled
    syncForm.made_item_extensions = [...pdm.made_item_extensions]
    syncForm.bought_item_extensions = [...pdm.bought_item_extensions]
    syncForm.document_categories = { ...pdm.document_categories }
    syncForm.document_excluded_kinds = { ...pdm.document_excluded_kinds }
    syncForm.thumbnails_enabled = pdm.thumbnails_enabled
    syncForm.stuck_after_days = pdm.stuck_after_days
    syncForm.set_approver_from_pdm = pdm.set_approver_from_pdm

    madeFeatureTreeTemplate.value = pdm.made_feature_tree_template
    boughtFeatureTreeTemplate.value = pdm.bought_feature_tree_template
  },
  { immediate: true },
)

const passwordConfigured = computed(() => store.settings?.pdm.password_configured ?? false)
const configured = computed(() => store.settings?.pdm.configured ?? false)
const session = computed<PdmSession>(
  () => store.settings?.pdm.session ?? { active: false, obtained_at: null, user_id: null },
)

const pdmSyncValidation = computed(() =>
  validatePdmSync({
    enabled: syncForm.enabled,
    watchedFolders: syncForm.watched_folders,
    madeReleasedStateIds: syncForm.made_released_state_ids,
    boughtReleasedStateIds: syncForm.bought_released_state_ids,
  }),
)

const madeFeatureTreeValidation = computed(() =>
  validateFeatureTreeTemplate(madeFeatureTreeTemplate.value, madeVariableMap),
)
const boughtFeatureTreeValidation = computed(() =>
  validateFeatureTreeTemplate(boughtFeatureTreeTemplate.value, boughtVariableMap),
)

const hasValidationError = computed(
  () =>
    madeValidation.value.duplicate ||
    madeValidation.value.missingIdentity ||
    boughtValidation.value.duplicate ||
    boughtValidation.value.missingIdentity ||
    kindMismatch.value ||
    writebackMismatch.value ||
    pdmSyncValidation.value.hasError ||
    hasFeatureTreeTemplateError(madeFeatureTreeValidation.value) ||
    hasFeatureTreeTemplateError(boughtFeatureTreeValidation.value),
)

const { saving, onSave } = useSettingsSave(() => {
  const pdm = store.settings?.pdm
  const madeItems = store.settings?.made_items
  if (!pdm || !madeItems) return Promise.resolve()

  const madeMap: Record<string, string> = {}
  for (const row of pdm.item_fields.made) {
    if (row.mappable) madeMap[row.field] = (madeVariableMap[row.field] ?? '').trim()
  }
  const boughtMap: Record<string, string> = {}
  for (const row of pdm.item_fields.bought) {
    if (row.mappable) boughtMap[row.field] = (boughtVariableMap[row.field] ?? '').trim()
  }
  const requiredFields = {
    made: buildRequiredFieldNames(madeRequired),
    bought: buildRequiredFieldNames(boughtRequired),
  }

  // web_requires_revision survives untouched from the store.
  const policy = mergeRevisionFieldPolicy(
    pdm.item_fields.made.filter((row) => row.policy_applicable),
    madeItems.revision_field_policy,
    madeUpdateInPlace,
    'pdm_update_in_place',
  )

  return Promise.all([
    store.savePdm({
      made_item_variable_map: madeMap,
      bought_item_variable_map: boughtMap,
      base_url: connectionForm.base_url.trim(),
      vault_name: connectionForm.vault_name.trim(),
      username: connectionForm.username.trim(),
      password: connectionForm.password.trim() || null,
      verify_certificate: connectionForm.verify_certificate,
      timeout_seconds: connectionForm.timeout_seconds,
      // Every sync field is sent as the form holds it, only the folder paths trimmed.
      ...syncForm,
      watched_folders: syncForm.watched_folders.map((folder) => ({
        ...folder,
        path: folder.path.trim(),
      })),
      required_fields: requiredFields,
      made_feature_tree_template: madeFeatureTreeTemplate.value,
      bought_feature_tree_template: boughtFeatureTreeTemplate.value,
    }),
    store.saveMadeItems({ revision_field_policy: policy }),
  ])
})

// ── Test connection (unsaved form values) ──────────────────────────────
const canTest = computed(
  () =>
    canWrite &&
    !!connectionForm.base_url.trim() &&
    !!connectionForm.vault_name.trim() &&
    !!connectionForm.username.trim(),
)

const testing = ref(false)

async function onTest(): Promise<void> {
  testing.value = true
  try {
    const result = await store.verifyPdm({
      base_url: connectionForm.base_url.trim(),
      vault_name: connectionForm.vault_name.trim(),
      username: connectionForm.username.trim(),
      password: connectionForm.password.trim() || null,
      verify_certificate: connectionForm.verify_certificate,
      timeout_seconds: connectionForm.timeout_seconds,
    })
    appToast.success(
      t('adminSettings.solidworksPdm.pdm.testSuccess'),
      t('adminSettings.solidworksPdm.pdm.testSuccessDetail', {
        product: result.product_name,
        version: result.app_version,
        userId: result.user_id,
      }),
    )
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.solidworksPdm.pdm.testFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
  } finally {
    testing.value = false
  }
}

// ── API console and critical-endpoints switch, page-local only ──────────
const showConsole = ref(false)
const criticalMode = ref(false)
// PDM__ALLOW_MUTATING_OPERATIONS on the server. While it is off the backend
// refuses every mutating call, so the switch stays disabled with a tooltip.
const mutatingOperationsEnabled = computed(
  () => store.settings?.pdm.mutating_operations_enabled ?? false,
)

// Resizable from its left edge, docked to #panels-end, width persisted per
// user.
const {
  width: consoleWidth,
  isResizing: isResizingConsole,
  onResizeStart: onConsoleResizeStart,
  onResizeKey: onConsoleResizeKey,
  min: consoleMin,
  max: consoleMax,
} = useResizablePanelWidth({
  defaultWidth: 476,
  min: 360,
  max: () => window.innerWidth * 0.7,
  dockedTo: 'end',
  storageKey: 'glados.adminSettings.pdmConsolePanelWidth',
})

// ── PDM files dialog ─────────────────────────────────────────────────────
const showPdmFilesDialog = ref(false)
const pdmFilesBadgeCount = computed(() => {
  const counts = store.settings?.pdm.snapshot_counts ?? {}
  return (counts.pending ?? 0) + (counts.conflict ?? 0) + (counts.error ?? 0)
})

// ── PDM sync log dialog ──────────────────────────────────────────────────
const showPdmSyncLogDialog = ref(false)

// ── PDM reconciliation dialog ────────────────────────────────────────────
const showPdmReconciliationDialog = ref(false)

// ── PDM user matching dialog ─────────────────────────────────────────────
const showPdmUsersDialog = ref(false)

function onToggleCriticalMode(): void {
  if (criticalMode.value) {
    criticalMode.value = false
    return
  }
  confirm.require({
    message: t('adminSettings.solidworksPdm.pdm.console.criticalConfirmMessage'),
    header: t('adminSettings.solidworksPdm.pdm.console.criticalConfirmHeader'),
    icon: 'mdi mdi-alert',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: {
      label: t('adminSettings.solidworksPdm.pdm.console.criticalConfirmAccept'),
      severity: 'danger',
    },
    accept: () => {
      criticalMode.value = true
    },
  })
}

// ── "Synchronize with PDM" (ControlsBar) ────────────────────────────────
// Gated on the saved enabled state, since the backend rejects the poll with
// 409 until PDM is enabled and configured. While a synchronisation is
// requested or running the button spins and only opens the activity dialog;
// otherwise a click requests one first. The spin is the icon, not
// the button's own loading state, which would make it unclickable.
const syncActivity = usePdmSyncActivityStore()
const pollEnabled = computed(() => canWrite && (store.settings?.pdm.enabled ?? false))
const polling = ref(false)
const showSyncActivityDialog = ref(false)
const syncButtonIcon = computed(() =>
  polling.value || syncActivity.busy ? 'mdi mdi-loading mdi-spin' : 'mdi mdi-sync',
)

onMounted(() => syncActivity.startPolling())
onUnmounted(() => syncActivity.stopPolling())

async function onSyncButton(): Promise<void> {
  if (!syncActivity.busy && !polling.value) {
    const requested = await onPoll()
    if (!requested) return
  }
  showSyncActivityDialog.value = true
}

async function onPoll(): Promise<boolean> {
  polling.value = true
  try {
    await store.requestPdmPoll()
    syncActivity.markRequested()
    appToast.success(t('adminSettings.solidworksPdm.pdm.sync.pollRequested'))
    return true
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.solidworksPdm.pdm.sync.pollFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
    return false
  } finally {
    polling.value = false
  }
}

// ── "Watch folder" (ControlsBar) ─────────────────────────────────────────
// Drives PdmSyncSection's folder picker, the same dialog each row opens.
const pdmSyncSectionRef = ref<InstanceType<typeof PdmSyncSection> | null>(null)

// The flex-row layout applies only while the API console is open.
const dataAreaClass = computed(() => (showConsole.value ? 'pdm-tab-data pdm-view-data' : 'pdm-tab-data'))
</script>

<template>
  <PageLayout :class="{ 'is-resizing-ew': isResizingConsole }" :data-class="dataAreaClass">
    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            :loading="saving"
            :disabled="!canWrite || hasValidationError"
            @click="onSave"
          />
          <Button
            :label="t('adminSettings.solidworksPdm.pdm.testConnection')"
            icon="mdi mdi-lan-connect"
            text
            severity="contrast"
            :loading="testing"
            :disabled="!canTest"
            @click="onTest"
          />
          <span v-tooltip.bottom="importVariableMapsBlocked">
            <Button
              :label="t('templateFiles.pdm.importVariableMaps')"
              icon="mdi mdi-file-import-outline"
              text
              severity="contrast"
              :disabled="!canWrite"
              data-testid="pdm-import-variable-maps"
              @click="onImportVariableMaps"
            />
          </span>
          <Button
            :label="t('templateFiles.pdm.exportVariableMaps')"
            icon="mdi mdi-file-export-outline"
            text
            severity="contrast"
            data-testid="pdm-export-variable-maps"
            @click="onExportVariableMaps"
          />
          <Divider layout="vertical" />
          <Button
            :label="t('adminSettings.solidworksPdm.pdm.sync.pollButton')"
            :icon="syncButtonIcon"
            text
            severity="contrast"
            :disabled="!pollEnabled"
            :aria-busy="syncActivity.busy"
            @click="onSyncButton"
          />
          <Button
            :label="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.addButton')"
            icon="mdi mdi-plus"
            text
            severity="contrast"
            :disabled="!canWrite || !configured"
            @click="pdmSyncSectionRef?.openAddPicker()"
          />
          <Divider layout="vertical" />
          <Button
            :label="t('adminSettings.pdmFiles.dialogTitle')"
            icon="mdi mdi-file-sync-outline"
            text
            severity="contrast"
            :badge="pdmFilesBadgeCount > 0 ? String(pdmFilesBadgeCount) : undefined"
            badge-severity="danger"
            @click="showPdmFilesDialog = true"
          />
          <Button
            :label="t('adminSettings.pdmSyncLog.dialogTitle')"
            icon="mdi mdi-history"
            text
            severity="contrast"
            @click="showPdmSyncLogDialog = true"
          />
          <Button
            :label="t('adminSettings.pdmReconciliation.dialogTitle')"
            icon="mdi mdi-scale-balance"
            text
            severity="contrast"
            @click="showPdmReconciliationDialog = true"
          />
          <Button
            :label="t('adminSettings.solidworksPdm.pdm.userMatching.matchButton')"
            icon="mdi mdi-account-sync-outline"
            text
            severity="contrast"
            :disabled="!configured"
            @click="showPdmUsersDialog = true"
          />
        </template>
        <template #end>
          <Button
            v-if="showConsole"
            :label="
              criticalMode
                ? t('adminSettings.solidworksPdm.pdm.console.criticalToggleEnabled')
                : t('adminSettings.solidworksPdm.pdm.console.criticalToggle')
            "
            icon="mdi mdi-alert"
            :severity="criticalMode ? 'danger' : 'contrast'"
            :text="!criticalMode"
            :disabled="!mutatingOperationsEnabled"
            v-tooltip.top="
              !mutatingOperationsEnabled
                ? t('adminSettings.solidworksPdm.pdm.console.mutatingDisabledTooltip')
                : undefined
            "
            @click="onToggleCriticalMode"
          />
        </template>
      </ControlsBar>
    </template>

    <template #views>
      <ViewsBar id-prefix="pdm" hide-views-toggle :has-active-filters="false" @sync="store.fetch()">
        <template #start-extra>
          <Button
            :label="t('adminSettings.solidworksPdm.pdm.console.toggle')"
            icon="mdi mdi-api"
            severity="contrast"
            :text="!showConsole"
            :disabled="!configured"
            v-tooltip.top="
              !configured ? t('adminSettings.solidworksPdm.pdm.console.toggleDisabledTooltip') : undefined
            "
            @click="showConsole = !showConsole"
          />
        </template>
      </ViewsBar>
    </template>

    <template v-if="showConsole" #panels-end>
      <PanelResizeHandle :width="consoleWidth" :min="consoleMin" :max="consoleMax" @start="onConsoleResizeStart" @key="onConsoleResizeKey" />
      <PdmApiConsolePanel
        :style="{ width: consoleWidth + 'px' }"
        :critical-mode="criticalMode"
        :mutating-operations-enabled="mutatingOperationsEnabled"
        @close="showConsole = false"
      />
    </template>

    <div class="settings-fields">
      <PdmConnectionSection
        v-model:enabled="syncForm.enabled"
        v-model:base-url="connectionForm.base_url"
        v-model:vault-name="connectionForm.vault_name"
        v-model:username="connectionForm.username"
        v-model:password="connectionForm.password"
        v-model:verify-certificate="connectionForm.verify_certificate"
        v-model:timeout-seconds="connectionForm.timeout_seconds"
        :can-write="canWrite"
        :password-configured="passwordConfigured"
        :session="session"
      />

      <Divider />

      <PdmSyncSection
        ref="pdmSyncSectionRef"
        :enabled="syncForm.enabled"
        v-model:watched-folders="syncForm.watched_folders"
        v-model:made-released-state-ids="syncForm.made_released_state_ids"
        v-model:made-obsolete-state-ids="syncForm.made_obsolete_state_ids"
        v-model:made-replaced-state-ids="syncForm.made_replaced_state_ids"
        v-model:bought-released-state-ids="syncForm.bought_released_state_ids"
        v-model:bought-obsolete-state-ids="syncForm.bought_obsolete_state_ids"
        v-model:bought-replaced-state-ids="syncForm.bought_replaced_state_ids"
        v-model:document-released-state-ids="syncForm.document_released_state_ids"
        v-model:poll-interval-minutes="syncForm.poll_interval_minutes"
        v-model:cold-folder-max-multiplier="syncForm.cold_folder_max_multiplier"
        v-model:ingest-concurrency="syncForm.ingest_concurrency"
        v-model:cad-items-read-only="syncForm.cad_items_read_only"
        v-model:writeback-enabled="syncForm.writeback_enabled"
        v-model:made-item-extensions="syncForm.made_item_extensions"
        v-model:bought-item-extensions="syncForm.bought_item_extensions"
        v-model:document-categories="syncForm.document_categories"
        v-model:document-excluded-kinds="syncForm.document_excluded_kinds"
        v-model:thumbnails-enabled="syncForm.thumbnails_enabled"
        v-model:stuck-after-days="syncForm.stuck_after_days"
        :can-write="canWrite"
        :configured="configured"
        :last-poll-at="store.settings?.pdm.last_poll_at ?? null"
        :last-poll-error="store.settings?.pdm.last_poll_error ?? null"
        :last-poll-summary="store.settings?.pdm.last_poll_summary ?? null"
        :snapshot-counts="store.settings?.pdm.snapshot_counts ?? {}"
      />

      <Divider />

      <p class="section-label">{{ t('adminSettings.solidworksPdm.pdm.userMatching.sectionTitle') }}</p>
      <div class="toggle-row">
        <Checkbox
          v-model="syncForm.set_approver_from_pdm"
          binary
          input-id="pdm-set-approver-from-pdm"
          :disabled="!canWrite"
        />
        <label for="pdm-set-approver-from-pdm">{{
          t('adminSettings.solidworksPdm.pdm.userMatching.setApproverFromPdm')
        }}</label>
      </div>
      <p class="hint">{{ t('adminSettings.solidworksPdm.pdm.userMatching.setApproverFromPdmHint') }}</p>

      <Divider />

      <PdmDatacardHeader v-model="syncForm.addin_language" :can-write="canWrite" :kind-mismatch="kindMismatch" :writeback-mismatch="writebackMismatch" />

      <Accordion multiple>
        <AccordionPanel value="made">
          <AccordionHeader>
            <div>
              <span class="panel-kind">{{ t('adminSettings.itemFields.madeSection') }}</span>
              <span class="panel-count">{{
                mappedCountLabel(madeMappedCount, madeMappableCount)
              }}</span>
            </div>
          </AccordionHeader>
          <AccordionContent>
            <ItemFieldOwnershipTable
              :variable-map="madeVariableMap"
              :update-in-place="madeUpdateInPlace"
              :required="madeRequired"
              kind="made"
              :fields="madeRows"
              :locked-required="store.settings?.pdm.locked_required_fields.made ?? []"
              :can-write="canWrite"
              :show-pdm-column="true"
            />
            <FeatureTreeTemplateField
              v-model="madeFeatureTreeTemplate"
              :fields="madeRows"
              :variable-map="madeVariableMap"
              :can-write="canWrite"
            />
            <div v-if="madeRuleNames.length > 0" class="required-rules">
              <p class="section-label">{{ t('adminSettings.itemFields.requiredRulesTitle') }}</p>
              <p class="hint">{{ t('adminSettings.itemFields.requiredRulesHint') }}</p>
              <div v-for="name in madeRuleNames" :key="name" class="required-rule-row">
                <Checkbox
                  v-model="madeRequired[name]"
                  binary
                  :input-id="`pdm-required-rule-made-${name}`"
                  :disabled="!canWrite"
                />
                <label :for="`pdm-required-rule-made-${name}`">{{
                  t(`adminSettings.itemFields.requiredRules.${name}`)
                }}</label>
              </div>
            </div>
          </AccordionContent>
        </AccordionPanel>
        <AccordionPanel value="bought">
          <AccordionHeader>
            <div>
              <span class="panel-kind">{{ t('adminSettings.itemFields.boughtSection') }}</span>
              <span class="panel-count">{{
                mappedCountLabel(boughtMappedCount, boughtMappableCount)
              }}</span>
            </div>
          </AccordionHeader>
          <AccordionContent>
            <ItemFieldOwnershipTable
              :variable-map="boughtVariableMap"
              :required="boughtRequired"
              kind="bought"
              :fields="boughtRows"
              :locked-required="store.settings?.pdm.locked_required_fields.bought ?? []"
              :can-write="canWrite"
              :show-pdm-column="false"
            />
            <FeatureTreeTemplateField
              v-model="boughtFeatureTreeTemplate"
              :fields="boughtRows"
              :variable-map="boughtVariableMap"
              :can-write="canWrite"
            />
            <p v-if="boughtRevisionOptional" class="hint bought-revision-hint">
              {{ t('adminSettings.solidworksPdm.pdm.boughtRevisionOptionalHint') }}
            </p>
            <div v-if="boughtRuleNames.length > 0" class="required-rules">
              <p class="section-label">{{ t('adminSettings.itemFields.requiredRulesTitle') }}</p>
              <p class="hint">{{ t('adminSettings.itemFields.requiredRulesHint') }}</p>
              <div v-for="name in boughtRuleNames" :key="name" class="required-rule-row">
                <Checkbox
                  v-model="boughtRequired[name]"
                  binary
                  :input-id="`pdm-required-rule-bought-${name}`"
                  :disabled="!canWrite"
                />
                <label :for="`pdm-required-rule-bought-${name}`">{{
                  t(`adminSettings.itemFields.requiredRules.${name}`)
                }}</label>
              </div>
            </div>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
    </div>
  </PageLayout>

  <PdmFilesDialog v-if="showPdmFilesDialog" v-model:visible="showPdmFilesDialog" />
  <PdmSyncLogDialog v-if="showPdmSyncLogDialog" v-model:visible="showPdmSyncLogDialog" />
  <PdmReconciliationDialog
    v-if="showPdmReconciliationDialog"
    v-model:visible="showPdmReconciliationDialog"
    @open-files="showPdmFilesDialog = true"
  />
  <PdmUsersDialog v-if="showPdmUsersDialog" v-model:visible="showPdmUsersDialog" />
  <PdmSyncActivityDialog
    v-if="showSyncActivityDialog"
    v-model:visible="showSyncActivityDialog"
    @open-log="showPdmSyncLogDialog = true"
  />
</template>

<style scoped lang="scss">
.panel-kind {
  font-weight: 600;
}

.panel-count {
  margin-left: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: normal;
  color: var(--p-text-muted-color);
}

.required-rules {
  margin-top: var(--space-4);
}

.required-rule-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

// Puts the accordion chevron left of the title: the header renders the icon
// after the title, so the row is reversed and packed with flex-end.
:deep(.p-accordionheader) {
  flex-direction: row-reverse;
  justify-content: flex-end;
  gap: var(--space-2);
}

// The overflow keeps a tall mapping accordion scrolling inside the card
// instead of spilling past its border.
:deep(.pdm-tab-data) > .card {
  padding: var(--space-4);
  overflow-y: auto;
}

:deep(.pdm-view-data) {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: var(--space-1);

  > .card {
    flex: 1;
    min-width: 0;
  }
}

.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}
</style>
