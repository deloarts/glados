/**
 * Admin settings types, aliased from the generated OpenAPI schema. Fields
 * the backend sends as a bare string are narrowed to closed unions so
 * switches on them can be exhaustive.
 */
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type AdminHostSettings = Schemas['AdminHostSettingsResponse']

/** Live machine reading for the Host tab. Never stored. */
export type HostStats = Schemas['HostStatsResponse']

export type ServiceStatus = Schemas['ServiceHealthResponse']['status']

/** Live connectivity reading for one connected service. Never stored. */
export type ServiceHealth = Schemas['ServiceHealthResponse']

export type ServicesHealth = Schemas['ServicesHealthResponse']
export type IntegrationStatus = Schemas['IntegrationStatusResponse']
export type IntegrationsOverview = Schemas['IntegrationsOverviewResponse']

export type AdminAuthSettings = Schemas['AdminAuthSettingsResponse']

export type UpdateAuthSettingsCommand = Schemas['UpdateAuthSettingsRequest']

/**
 * The settings to probe plus a directory account to bind with; nothing is
 * stored.
 */
export type VerifyLdapConnectionCommand = Schemas['VerifyLdapConnectionRequest']

export type AdminMailSettings = Schemas['AdminMailSettingsResponse']

// ── Mail templates ──────────────────────────────────────────────────────

export type MailTemplateKind = Schemas['MailTemplateKind']

/**
 * What the preview branches on: `system` templates are Jinja documents
 * rendered server-side, `supplier` templates are fragments resolved in the
 * frontend.
 */
export type MailTemplateFamily = Schemas['MailTemplateFamily']

/**
 * One kind and language row; read `configured` rather than re-deriving
 * it from `body`.
 */
export type AdminMailTemplate = Schemas['AdminMailTemplateResponse']

/** One kind's metadata plus its stored language rows. */
export type MailTemplateKindGroup = Schemas['MailTemplateKindResponse']

export type AdminMailTemplatesResponse = Schemas['AdminMailTemplatesResponse']

export type MailTemplateEntryCommand = Schemas['MailTemplateEntryRequest']

/** PUT body for one kind; the kind is a path parameter. */
export type UpdateMailTemplatesCommand = Schemas['UpdateMailTemplatesRequest']

/** Renders the draft against the kind's sample context, without a language. */
export type PreviewMailTemplateCommand = Schemas['PreviewMailTemplateRequest']

export type MailTemplatePreviewResult = Schemas['PreviewMailTemplateResponse']

export type AdminStorageSettings = Schemas['AdminStorageSettingsResponse']

export type StorageProvider = AdminStorageSettings['provider']

// The backend takes any string and rejects an unknown provider itself.
export type UpdateStorageSettingsCommand = Omit<
  Schemas['UpdateStorageSettingsRequest'],
  'provider'
> & {
  provider: StorageProvider
}

export type StorageMigrationResult = Schemas['StorageMigrationResponse']

export type StorageMigrationStatus = Schemas['StorageMigrationStatusResponse']

/**
 * One `progress` frame of the migration stream, sent before each object is
 * copied: `current` is its 1-based position among `total`.
 */
export interface StorageMigrationProgressEvent {
  current: number
  total: number
  key: string
}

export type AdminSecuritySettings = Schemas['AdminSecuritySettingsResponse']

export type UpdateSecuritySettingsCommand = Schemas['UpdateSecuritySettingsRequest']

export type AdminFeatureSettings = Schemas['AdminFeatureSettingsResponse']

export type UpdateFeatureSettingsCommand = Schemas['UpdateFeatureSettingsRequest']

export type AdminGeneralSettings = Schemas['AdminGeneralSettingsResponse']

export type UpdateGeneralSettingsCommand = Schemas['UpdateGeneralSettingsRequest']

export type AdminBrandingSettings = Schemas['AdminBrandingSettingsResponse']

export type UpdateBrandingSettingsCommand = Schemas['UpdateBrandingSettingsRequest']

export type AdminNotificationSettings = Schemas['AdminNotificationSettingsResponse']

export type UpdateNotificationSettingsCommand = Schemas['UpdateNotificationSettingsRequest']

export type AdminMaintenanceSettings = Schemas['AdminMaintenanceSettingsResponse']

export type UpdateMaintenanceSettingsCommand = Schemas['UpdateMaintenanceSettingsRequest']

/** Mapped to OpenVue's severity names only at render time. */
export type AnnouncementSeverity = Schemas['AnnouncementSeverity']

/** Dismissal is keyed on `updated_at`, so an edited banner reappears. */
export type AdminBannerSettings = Schemas['AdminBannerSettingsResponse']

/** `shows_from` and `shows_until` are instants, sent with `toISOString()`. */
export type UpdateBannerSettingsCommand = Schemas['UpdateBannerSettingsRequest']

export type AdminRetentionSettings = Schemas['AdminRetentionSettingsResponse']

export type UpdateRetentionSettingsCommand = Schemas['UpdateRetentionSettingsRequest']

export type AdminOrderSettings = Schemas['AdminOrderSettingsResponse']

export type UpdateOrderSettingsCommand = Schemas['UpdateOrderSettingsRequest']

/** `ask` lets the form decide the predecessor's status. */
export type RevisionPredecessorStatusWeb =
  Schemas['AdminMadeItemSettingsResponse']['revision_predecessor_status_web']

export type RevisionPredecessorStatusPdm =
  Schemas['AdminMadeItemSettingsResponse']['revision_predecessor_status_pdm']

/**
 * One row of the revision field policy. Two tabs each edit one column
 * and merge it into the full list (see mergeRevisionFieldPolicy).
 */
export type RevisionFieldPolicyEntry = Schemas['RevisionFieldPolicyEntryResponse']

export type AdminMadeItemSettings = Schemas['AdminMadeItemSettingsResponse']

/**
 * Omitted fields stay unchanged. The backend takes any string for the
 * predecessor statuses and rejects an unknown one itself.
 */
export type UpdateMadeItemSettingsCommand = Omit<
  Schemas['UpdateMadeItemSettingsRequest'],
  'revision_predecessor_status_web' | 'revision_predecessor_status_pdm'
> & {
  revision_predecessor_status_web?: RevisionPredecessorStatusWeb | null
  revision_predecessor_status_pdm?: RevisionPredecessorStatusPdm | null
}

export type AdminProductionSettings = Schemas['AdminProductionSettingsResponse']

/**
 * One read-only row of the ownership table. `mappable` gates the custom
 * property input, `policy_applicable` the revision policy checkboxes, and
 * `label_of` names the field a label row describes.
 */
export type ItemFieldOwnership = Schemas['ItemFieldOwnershipResponse']

/** Owner of one item field, see docs/FIELD_OWNERSHIP.md. */
export type ItemFieldOwner = ItemFieldOwnership['owner']

export type ItemFieldsTable = Schemas['ItemFieldsResponse']

/**
 * Required-field names per kind. Fixed keys instead of the generated index
 * signature, so the lists are never `undefined`. A type alias rather than an
 * interface, so it still satisfies that index signature in a request body.
 */
export type PdmRequiredFieldsByKind = {
  made: string[]
  bought: string[]
}

/** Whether the server holds a PDM session token, and who obtained it. */
export type PdmSession = Schemas['PdmSessionResponse']

/**
 * One watched vault folder (see docs/reference/pdm-settings.md). Used
 * for requests too, since every field is always sent back. The backend
 * stores whatever match_by a folder other than a documents folder sends, so
 * it is narrowed to the values the form offers.
 */
export type PdmWatchedFolder = Omit<Schemas['PdmWatchedFolderResponse'], 'match_by'> & {
  match_by: 'datacard' | 'filename' | null
}

/**
 * The item file categories a synced document can be routed into.
 * `image_and_thumbnail` stores an exported image as the item's CAD
 * rendering, one of its pictures rather than a file.
 */
export const PDM_DOCUMENT_CATEGORIES = [
  'image_and_thumbnail',
  'step',
  'mesh',
  'drawing',
  'dxf',
  'pdf',
] as const

export type PdmDocumentCategory = (typeof PDM_DOCUMENT_CATEGORIES)[number]

/**
 * The PDM settings (described in docs/reference/pdm-settings.md) plus the
 * read-only ownership table, with the loosely generated fields narrowed to
 * this file's types.
 */
export type AdminPdmSettings = Omit<
  Schemas['AdminPdmSettingsResponse'],
  'watched_folders' | 'required_fields' | 'locked_required_fields' | 'required_field_rules'
> & {
  watched_folders: PdmWatchedFolder[]
  required_fields: PdmRequiredFieldsByKind
  locked_required_fields: PdmRequiredFieldsByKind
  required_field_rules: PdmRequiredFieldsByKind
}

export interface AllAdminSettings {
  host: AdminHostSettings
  mail: AdminMailSettings
  auth: AdminAuthSettings
  storage: AdminStorageSettings
  security: AdminSecuritySettings
  features: AdminFeatureSettings
  general: AdminGeneralSettings
  branding: AdminBrandingSettings
  notifications: AdminNotificationSettings
  maintenance: AdminMaintenanceSettings
  banner: AdminBannerSettings
  retention: AdminRetentionSettings
  orders: AdminOrderSettings
  made_items: AdminMadeItemSettings
  production: AdminProductionSettings
  pdm: AdminPdmSettings
}

export type AdminSettingsAuditEntry = Schemas['AdminSettingsAuditEntryResponse']
export type SecurityEvent = Schemas['SecurityEventResponse']
export type SecurityEventType = Schemas['SecurityEventType']
export type SecurityEventOutcome = Schemas['SecurityEventOutcome']

// ── Update command types ──────────────────────────────────────────────

export type UpdateMailSettingsCommand = Schemas['UpdateMailSettingsRequest']

export type UpdatePdmSettingsCommand = Omit<
  Schemas['UpdatePdmSettingsRequest'],
  'watched_folders' | 'required_fields'
> & {
  watched_folders?: PdmWatchedFolder[] | null
  required_fields?: PdmRequiredFieldsByKind | null
}

/**
 * One vault user for the "Match PDM Users" dialog. `proposed_user_id` is a
 * guess that is preselected but never saved on its own, and the service
 * account can never be linked.
 */
export type PdmUser = Schemas['PdmUserResponse']

/**
 * One entry of `POST /admin/settings/pdm/users/link`. `user_id: null`
 * unlinks.
 */
export type LinkPdmUserEntry = Schemas['LinkPdmUserEntryRequest']

export type LinkPdmUsersCommand = Schemas['LinkPdmUsersRequest']

/**
 * Connection fields to probe without saving; a missing password uses the
 * stored one.
 */
export type VerifyPdmConnectionCommand = Schemas['VerifyPdmConnectionRequest']

export type PdmConnectionTestResult = Schemas['PdmConnectionTestResponse']

/**
 * One parameter of a catalogued PDM operation; the console edits body
 * fields as one JSON text.
 */
export type PdmParam = Schemas['PdmParamResponse']

/**
 * One operation of the PDM API console's catalogue. The server fills
 * `vaultName`, so the console renders no field for it.
 */
export type PdmOperation = Schemas['PdmOperationResponse']

/** A mutating operation needs `allow_mutating`, or the backend answers 400. */
export type InvokePdmOperationCommand = Schemas['PdmInvokeRequest']

/**
 * The raw result of one PDM Web API call, `url` with the vault's bearer
 * token never included. Exactly one of `response_json`/`response_text`
 * carries the body, depending on the response's content type.
 */
export type PdmInvokeResult = Schemas['PdmInvokeResponse']

/** One state of a PDM workflow. */
export type PdmWorkflowState = Schemas['PdmWorkflowStateResponse']

/** One PDM workflow with its states, for the state pickers. */
export type PdmWorkflow = Schemas['PdmWorkflowResponse']

/** One subfolder for the folder picker's drill-down. */
export type PdmFolder = Schemas['PdmFolderResponse']

/**
 * `accepted` means the poll was queued, not that it has run yet. The
 * scheduler's next tick (within 60 seconds) picks it up.
 */
export type PdmPollResult = Schemas['PdmPollResponse']

/** Sync state of a snapshot row, separate from an item's own sync state. */
export type PdmFileSyncState = Schemas['PdmFileSyncState']

/**
 * `document` is a file from a documents folder attached to an item. The
 * backend types the persisted file kinds as plain strings, so they are
 * narrowed here and on the sync run entries and findings.
 */
export type PdmFileKind = 'made' | 'bought' | 'document'

/**
 * One row of the pending list; the parked payload itself never leaves the
 * API.
 */
export type PdmFileSnapshot = Omit<Schemas['PdmFileSnapshotResponse'], 'kind' | 'item_kind'> & {
  kind: PdmFileKind | null
  /** The catalogue `item_id` belongs to, also for a `document` row. */
  item_kind: 'made' | 'bought' | null
}

// The backend types these filters as plain strings; the UI only sends the
// closed unions it renders.
export type PdmFileSnapshotFilterParams = Omit<
  QueryOf<'/admin/settings/pdm/files'>,
  'sync_state' | 'kind'
> & {
  sync_state?: PdmFileSyncState
  kind?: PdmFileKind
}

/** `accepted` means the refresh was queued, not that it has run yet. */
export type PdmFileRetryResult = Schemas['PdmFileRetryResponse']

/** What started a sync run. */
export type PdmSyncTrigger = Schemas['PdmSyncTrigger']

/**
 * Action of one sync run entry; write-back, document and thumbnail
 * outcomes are separate entries after the ingest one. The backend persists
 * it as a plain string, so it is narrowed here.
 */
export type PdmSyncEntryAction =
  | 'created'
  | 'revised'
  | 'updated'
  | 'status'
  | 'claimed'
  | 'skipped'
  | 'conflict'
  | 'missing'
  | 'error'
  | 'writeback'
  | 'writeback_error'
  | 'document'
  | 'document_error'
  | 'thumbnail'
  | 'thumbnail_error'

/**
 * One row of the admin "View sync log" dialog's runs list. `finished_at`
 * null means the run is still in progress.
 */
export type PdmSyncRun = Schemas['PdmSyncRunResponse']

/** The trigger filter is narrowed to the closed union, as on PdmSyncRun. */
export type PdmSyncRunFilterParams = Omit<QueryOf<'/admin/settings/pdm/runs'>, 'trigger'> & {
  trigger?: PdmSyncTrigger[]
}

/**
 * One row of a sync run's entries list. `kind` is null when the file's
 * made/bought kind was never resolved (e.g. an error before ingest
 * classified it).
 */
export type PdmSyncRunEntry = Omit<Schemas['PdmSyncRunEntryResponse'], 'kind' | 'action'> & {
  kind: PdmFileKind | null
  action: PdmSyncEntryAction
}

/**
 * What the PDM sync is doing right now, for the "Synchronize with PDM"
 * button and its activity dialog. `run` is the poll in progress, null when
 * none runs; `requested` means a synchronisation waits for the scheduler.
 */
export type PdmSyncActivity = Omit<Schemas['PdmSyncActivityResponse'], 'recent_entries'> & {
  recent_entries: PdmSyncRunEntry[]
}

/** The action and kind filters are narrowed to the closed unions, as on PdmSyncRunEntry. */
export type PdmSyncRunEntryFilterParams = Omit<
  QueryOf<'/admin/settings/pdm/runs/{run_id}/entries'>,
  'action' | 'kind'
> & {
  action?: PdmSyncEntryAction
  kind?: PdmFileKind
}

// ── Reconciliation report ────────────────────────────────────────────────

/**
 * The reconciliation categories (see docs/reference/pdm-admin.md section 7),
 * in the order the dialog's tiles always render them, even at zero.
 */
export const PDM_RECONCILIATION_CATEGORIES = [
  'orphaned_cad_row',
  'stuck_file',
  'revision_lag',
  'duplicate_part_number',
  'kind_mismatch',
  'document_missing',
  'document_unmatched',
  'unclaimed_match',
  'writeback_drift',
  'status_mismatch',
  'replaced_without_successor',
  'successor_without_replaced',
  'part_number_drift',
] as const

export type PdmReconciliationCategory = (typeof PDM_RECONCILIATION_CATEGORIES)[number]

/** `warning` resolves itself on the next ingest; `error` needs a person. */
export type PdmReconciliationSeverity = Schemas['PdmReconciliationSeverity']

/** One finding; `count` is how many files or rows it stands for. */
export type PdmReconciliationFinding = Omit<Schemas['PdmReconciliationFindingResponse'], 'kind'> & {
  kind: PdmFileKind | null
}

/** The category and kind filters are narrowed to the closed unions, as on the finding. */
export type PdmReconciliationFindingFilterParams = Omit<
  QueryOf<'/admin/settings/pdm/reconciliation/findings'>,
  'category' | 'kind'
> & {
  category?: PdmReconciliationCategory
  kind?: PdmFileKind
}

/** The latest run, null if none, plus per-category sums of `count`. */
export type PdmReconciliationSummary = Schemas['PdmReconciliationReportResponse']

/** `accepted` means queued; the next scheduler tick runs it. */
export type PdmReconcileResult = Schemas['PdmReconcileResponse']

export type UpdateProductionSettingsCommand = Schemas['UpdateProductionSettingsRequest']

export type BackupEntry = Schemas['BackupEntryResponse']

export type BackupWarning = Schemas['BackupWarning']

export type BackupTrigger = Schemas['BackupRunTrigger']

export type BackupRunStatus = Schemas['BackupRunStatus']

export type BackupRunEntry = Schemas['BackupRunEntryResponse']

export type BackupList = Schemas['BackupListResponse']

export type RestoreFilesCommand = Schemas['RestoreFilesRequest']

export type RestoreFilesResult = Schemas['RestoreFilesResponse']

export type LogResponse = Schemas['LogEntryResponse']

export type LogFilterParams = QueryOf<'/logs'>

/** One page of log entries; the route returns only the items and the total. */
export type LogEntriesResponse = Schemas['LogEntriesResponse']

// ── Time tracking ───────────────────────────────────────────────────────

/** Loaded on its own by the time tracking tab, it is not part of the aggregate. */
export type AdminTimeTrackingSettings = Schemas['AdminTimeTrackingSettingsResponse']
export type TimeTrackingCredentialHolder = Schemas['TimeTrackingCredentialHolderResponse']
export type AdminDataImportSettings = Schemas['AdminDataImportSettingsResponse']
export type AdminEdpSettings = Schemas['AdminEdpSettingsResponse']
export type UpdateEdpSettingsCommand = Schemas['UpdateEdpSettingsRequest']
export type VerifyEdpConnectionCommand = Schemas['VerifyEdpConnectionRequest']
export type EdpConnectionTestResult = Schemas['EdpConnectionTestResponse']
export type DataImportProfileSettings = Schemas['DataImportProfileResponse']
export type UpdateDataImportSettingsCommand = Schemas['UpdateDataImportSettingsRequest']

/** Omitted fields keep the stored value; "" clears an optional one. */
export type UpdateTimeTrackingSettingsCommand = Schemas['UpdateTimeTrackingSettingsRequest']

/** Unsaved values to probe; omitted fields use the stored settings. */
export type VerifyTimeTrackingServiceCommand = Schemas['VerifyTimeTrackingServiceRequest']

export type TimeTrackingServiceTestResult = Schemas['TimeTrackingServiceTestResponse']

export type ConfirmTimeTrackingKeyCommand = Schemas['ConfirmTimeTrackingKeyRequest']

export type PurgeTimeTrackingCredentialsResult = Schemas['PurgeTimeTrackingCredentialsResponse']

// ── Stock service ───────────────────────────────────────────────────────

/** Loaded on its own by the stock service tab, it is not part of the aggregate. */
export type AdminStockSettings = Schemas['AdminStockSettingsResponse']

/** Omitted fields keep the stored value; an empty API key clears it. */
export type UpdateStockSettingsCommand = Schemas['UpdateStockSettingsRequest']

/** Unsaved values to probe; omitted fields use the stored settings. */
export type VerifyStockServiceCommand = Schemas['VerifyStockServiceRequest']

export type StockServiceTestResult = Schemas['StockServiceTestResponse']

/** The add-in language of the PDM settings; '' follows the instance's default language. */
export type PdmAddinLanguage = Schemas['Language'] | ''
