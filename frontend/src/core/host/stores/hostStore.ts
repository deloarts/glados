import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getValues } from '../api/getValues'
import { getCapabilities } from '../api/getCapabilities'
import { getNumberingPolicy } from '../api/getNumberingPolicy'
import { setDisplayCurrency } from '@/core/utils/currency'
import { setDisplayTimezone } from '@/core/utils/dates'
import type { MadeItemPartNumberPolicy, PartNumberPolicy } from '../api/getNumberingPolicy'

// Mirrors the backend defaults, used until /host/numbering has answered so
// forms render in their most permissive state rather than briefly locking a
// field the user is allowed to fill in.
function defaultPartNumberPolicy(): PartNumberPolicy {
  return {
    auto: false,
    editable: true,
    source: 'internal',
    example: '',
    web_creation_allowed: true,
    external_pattern: '',
  }
}

// Same reasoning, plus the revision defaults (numeric start, colon separator
// display-only, no letter skipping, only the newest revision editable, ask
// for what happens to the predecessor).
function defaultMadeItemPartNumberPolicy(): MadeItemPartNumberPolicy {
  return {
    ...defaultPartNumberPolicy(),
    revision: {
      start: '0',
      separator: ':',
      skip_ambiguous_letters: false,
      only_newest_editable: true,
      predecessor_status_web: 'ask',
      field_policy: [],
    },
  }
}

export const useHostStore = defineStore('host', () => {
  const loaded = ref(false)
  const languages = ref<string[]>([])
  const timezones = ref<string[]>([])
  const dateFormats = ref<string[]>([])
  const themePresets = ref<string[]>([])
  const themeSurfaces = ref<string[]>([])
  const themePrimaries = ref<string[]>([])
  const supplierLevels = ref<string[]>([])
  const storageEnabled = ref(false)
  const mailEnabled = ref(false)
  // The total size of a composed mail's attachments, the backend default
  // until the capabilities arrive.
  const mailAttachmentLimitMb = ref(10)

  // Off by default, so it never flashes on at first paint.
  const officeLauncherEnabled = ref(false)
  const officeSharepointUrl = ref('')

  // Off by default, so the banner never flashes on.
  const maintenanceEnabled = ref(false)
  const maintenanceMessage = ref<string | null>(null)

  // The backend defaults, so the first paint does not jump.
  const defaultLanguage = ref('enGB')
  const defaultTimezone = ref('Europe/Vienna')
  const defaultDateFormat = ref('iso')

  const currency = ref('EUR')
  const startPages = ref<string[]>([])
  const tokenMaxLifetimeDays = ref(365)
  // Served by the backend so the frontend never hardcodes them.
  const addinScopes = ref<string[]>([])
  const pdmAddinScopes = ref<string[]>([])
  // Off by default: AI agents reach Glados only once the admin switched
  // agent access on with the company's approval recorded. The agent token
  // presets and their lifetime cap come from the backend as well.
  const agentAccessEnabled = ref(false)
  const agentTokenMaxLifetimeDays = ref(30)
  const agentReadScopes = ref<string[]>([])
  const agentDraftScopes = ref<string[]>([])

  const boughtItemPartNumbers = ref<PartNumberPolicy>(defaultPartNumberPolicy())
  const madeItemPartNumbers = ref<MadeItemPartNumberPolicy>(defaultMadeItemPartNumberPolicy())

  // On by default: a section that disappears is less jarring than one that
  // pops in, and nothing the user may see is hidden.
  const productionPlanningEnabled = ref(true)
  // The optional modules an admin can switch off, on by default for the
  // same reason. Sequences arrive already off while devices are off.
  const calculationsEnabled = ref(true)
  const checklistsEnabled = ref(true)
  const devicesEnabled = ref(true)
  const sequencesEnabled = ref(true)
  const todosEnabled = ref(true)
  // Off by default: time tracking is opt-in per instance, so its surfaces
  // only appear once the capabilities confirm it.
  const timeTrackingEnabled = ref(false)
  // The name of the time tracking system as the time tracking service
  // reports it, so labels can name the system without the frontend
  // assuming which one it is.
  const timeTrackingProviderLabel = ref<string | null>(null)
  // Off by default: the EPLAN Data Portal lookups appear once the
  // capabilities confirm the portal is switched on with a token.
  const edpEnabled = ref(false)

  const emptyPlaceholder = ref('-')

  const productNumberPattern = ref('')
  const projectNumberPattern = ref('')
  const allowHeadlessProjects = ref(true)

  // Off by default, so forms never flash read-only inputs.
  const pdmEnabled = ref(false)
  // The backend default; it only locks fields together with pdmEnabled.
  const cadItemsReadOnly = ref(true)

  // Shared by concurrent callers so the /host requests fire only once.
  let pending: Promise<void> | null = null

  async function fetch(): Promise<void> {
    if (loaded.value) return
    if (pending) return pending

    pending = (async () => {
      const [values, caps, numbering] = await Promise.all([
        getValues(),
        getCapabilities(),
        getNumberingPolicy(),
      ])
      languages.value = values.languages
      timezones.value = values.timezones ?? []
      dateFormats.value = values.date_formats ?? []
      themePresets.value = values.theme_presets
      themeSurfaces.value = values.theme_surfaces
      themePrimaries.value = values.theme_primaries
      supplierLevels.value = values.supplier_levels
      startPages.value = values.start_pages ?? []
      storageEnabled.value = caps.storage_enabled
      mailEnabled.value = caps.mail_enabled
      mailAttachmentLimitMb.value = caps.mail_attachment_limit_mb
      officeLauncherEnabled.value = caps.office_launcher_enabled
      officeSharepointUrl.value = caps.office_sharepoint_url
      maintenanceEnabled.value = caps.maintenance_enabled
      maintenanceMessage.value = caps.maintenance_message
      defaultLanguage.value = caps.default_language
      defaultTimezone.value = caps.default_timezone
      // Every timestamp from the API is UTC; this is the one wall clock the
      // whole app renders them against (see core/utils/dates.ts).
      setDisplayTimezone(caps.default_timezone)
      defaultDateFormat.value = caps.default_date_format
      currency.value = caps.currency
      setDisplayCurrency(caps.currency)
      tokenMaxLifetimeDays.value = caps.token_max_lifetime_days
      addinScopes.value = caps.addin_scopes
      pdmAddinScopes.value = caps.pdm_addin_scopes
      agentAccessEnabled.value = caps.agent_access_enabled
      agentTokenMaxLifetimeDays.value = caps.agent_token_max_lifetime_days
      agentReadScopes.value = caps.agent_read_scopes
      agentDraftScopes.value = caps.agent_draft_scopes
      productionPlanningEnabled.value = caps.features.production_planning
      calculationsEnabled.value = caps.features.calculations ?? true
      checklistsEnabled.value = caps.features.checklists ?? true
      devicesEnabled.value = caps.features.devices ?? true
      sequencesEnabled.value = caps.features.sequences ?? true
      todosEnabled.value = caps.features.todos ?? true
      timeTrackingEnabled.value = caps.features.time_tracking
      timeTrackingProviderLabel.value = caps.features.time_tracking_provider_label ?? null
      edpEnabled.value = caps.features.eplan_data_portal ?? false
      emptyPlaceholder.value = caps.empty_value_placeholder
      boughtItemPartNumbers.value = numbering.bought_items
      madeItemPartNumbers.value = numbering.made_items
      productNumberPattern.value = numbering.product_number_pattern
      projectNumberPattern.value = numbering.project_number_pattern
      allowHeadlessProjects.value = numbering.allow_headless_projects
      pdmEnabled.value = numbering.pdm_enabled
      cadItemsReadOnly.value = numbering.cad_items_read_only
      loaded.value = true
    })().finally(() => {
      pending = null
    })

    return pending
  }

  return {
    loaded,
    languages,
    timezones,
    dateFormats,
    themePresets,
    themeSurfaces,
    themePrimaries,
    supplierLevels,
    storageEnabled,
    mailEnabled,
    mailAttachmentLimitMb,
    officeLauncherEnabled,
    officeSharepointUrl,
    maintenanceEnabled,
    maintenanceMessage,
    defaultLanguage,
    defaultTimezone,
    defaultDateFormat,
    currency,
    startPages,
    tokenMaxLifetimeDays,
    addinScopes,
    pdmAddinScopes,
    agentAccessEnabled,
    agentTokenMaxLifetimeDays,
    agentReadScopes,
    agentDraftScopes,
    boughtItemPartNumbers,
    madeItemPartNumbers,
    productionPlanningEnabled,
    calculationsEnabled,
    checklistsEnabled,
    devicesEnabled,
    sequencesEnabled,
    todosEnabled,
    timeTrackingEnabled,
    timeTrackingProviderLabel,
    edpEnabled,
    emptyPlaceholder,
    productNumberPattern,
    projectNumberPattern,
    allowHeadlessProjects,
    pdmEnabled,
    cadItemsReadOnly,
    fetch,
  }
})
