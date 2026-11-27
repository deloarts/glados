import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type {
  AdminAuthSettings,
  AdminBannerSettings,
  AdminBrandingSettings,
  AdminFeatureSettings,
  AdminGeneralSettings,
  AdminHostSettings,
  AdminMadeItemSettings,
  AdminMailSettings,
  AdminMaintenanceSettings,
  AdminMailTemplatesResponse,
  AdminNotificationSettings,
  AdminOrderSettings,
  AdminPdmSettings,
  AdminPlanningSettings,
  AdminProductionSettings,
  AdminRetentionSettings,
  AdminSecuritySettings,
  AdminStorageSettings,
  AllAdminSettings,
  BackupList,
  InvokePdmOperationCommand,
  MailTemplateKindGroup,
  PdmConnectionTestResult,
  PdmFolder,
  PdmInvokeResult,
  PdmOperation,
  PdmPollResult,
  PdmWorkflow,
  RestoreFilesResult,
  UpdateAuthSettingsCommand,
  UpdateBannerSettingsCommand,
  UpdateBrandingSettingsCommand,
  UpdateMaintenanceSettingsCommand,
  UpdateMailSettingsCommand,
  UpdateMailTemplatesCommand,
  UpdateNotificationSettingsCommand,
  UpdateRetentionSettingsCommand,
  UpdateSecuritySettingsCommand,
  UpdateStorageSettingsCommand,
  VerifyLdapConnectionCommand,
  VerifyPdmConnectionCommand,
} from '../../types/adminSettingsTypes'

const getAllAdminSettingsMock = vi.fn<() => Promise<AllAdminSettings>>()
const updateAuthSettingsMock = vi.fn<(cmd: UpdateAuthSettingsCommand) => Promise<AdminAuthSettings>>()
const updateMailSettingsMock = vi.fn<(cmd: UpdateMailSettingsCommand) => Promise<AdminMailSettings>>()
const getMailTemplatesMock = vi.fn<() => Promise<AdminMailTemplatesResponse>>()
const updateMailTemplatesMock =
  vi.fn<
    (kind: string, cmd: UpdateMailTemplatesCommand) => Promise<MailTemplateKindGroup>
  >()
const verifyLdapConnectionMock = vi.fn<(cmd: VerifyLdapConnectionCommand) => Promise<void>>()
const updateStorageSettingsMock =
  vi.fn<(cmd: UpdateStorageSettingsCommand) => Promise<AdminStorageSettings>>()
const testStorageMock = vi.fn<(cmd: UpdateStorageSettingsCommand) => Promise<void>>()
const updateSecuritySettingsMock =
  vi.fn<(cmd: UpdateSecuritySettingsCommand) => Promise<AdminSecuritySettings>>()
const updateFeatureSettingsMock = vi.fn<(cmd: unknown) => Promise<AdminFeatureSettings>>()
const updateGeneralSettingsMock = vi.fn<(cmd: unknown) => Promise<AdminGeneralSettings>>()
const uploadCompanyLogoMock = vi.fn<(file: File) => Promise<AdminGeneralSettings>>()
const deleteCompanyLogoMock = vi.fn<() => Promise<AdminGeneralSettings>>()
const updateBrandingSettingsMock =
  vi.fn<(cmd: UpdateBrandingSettingsCommand) => Promise<AdminBrandingSettings>>()
const uploadLoginBackgroundVideoMock = vi.fn<(file: File) => Promise<AdminBrandingSettings>>()
const deleteLoginBackgroundVideoMock = vi.fn<() => Promise<AdminBrandingSettings>>()
const uploadBrandingLogoMock = vi.fn<(file: File) => Promise<AdminBrandingSettings>>()
const deleteBrandingLogoMock = vi.fn<() => Promise<AdminBrandingSettings>>()
const uploadBrandingFaviconMock = vi.fn<(file: File) => Promise<AdminBrandingSettings>>()
const deleteBrandingFaviconMock = vi.fn<() => Promise<AdminBrandingSettings>>()
const updateNotificationSettingsMock =
  vi.fn<(cmd: UpdateNotificationSettingsCommand) => Promise<AdminNotificationSettings>>()
const updateMaintenanceSettingsMock =
  vi.fn<(cmd: UpdateMaintenanceSettingsCommand) => Promise<AdminMaintenanceSettings>>()
const updateBannerSettingsMock =
  vi.fn<(cmd: UpdateBannerSettingsCommand) => Promise<AdminBannerSettings>>()
const updateRetentionSettingsMock =
  vi.fn<(cmd: UpdateRetentionSettingsCommand) => Promise<AdminRetentionSettings>>()
const updateOrderSettingsMock = vi.fn<(cmd: unknown) => Promise<AdminOrderSettings>>()
const updateMadeItemSettingsMock = vi.fn<(cmd: unknown) => Promise<AdminMadeItemSettings>>()
const updateProductionSettingsMock = vi.fn<(cmd: unknown) => Promise<AdminProductionSettings>>()
const updatePdmSettingsMock = vi.fn<(cmd: unknown) => Promise<AdminPdmSettings>>()
const verifyPdmConnectionMock =
  vi.fn<(cmd: VerifyPdmConnectionCommand) => Promise<PdmConnectionTestResult>>()
const getPdmOperationsMock = vi.fn<() => Promise<PdmOperation[]>>()
const invokePdmOperationMock =
  vi.fn<(operationId: string, cmd: InvokePdmOperationCommand) => Promise<PdmInvokeResult>>()
const getPdmWorkflowsMock = vi.fn<() => Promise<PdmWorkflow[]>>()
const getPdmFoldersMock = vi.fn<(parentId: number) => Promise<PdmFolder[]>>()
const requestPdmPollMock = vi.fn<() => Promise<PdmPollResult>>()
const listBackupsMock = vi.fn<() => Promise<BackupList>>()
const runBackupNowMock = vi.fn<() => Promise<void>>()
const restoreFilesMock = vi.fn<(snapshotKey: string) => Promise<RestoreFilesResult>>()
const downloadBackupMock = vi.fn<(key: string) => Promise<void>>()

vi.mock('../../api/getAllAdminSettings', () => ({ getAllAdminSettings: () => getAllAdminSettingsMock() }))
vi.mock('../../api/updateAuthSettings', () => ({
  updateAuthSettings: (cmd: UpdateAuthSettingsCommand) => updateAuthSettingsMock(cmd),
}))
vi.mock('../../api/updateMailSettings', () => ({
  updateMailSettings: (cmd: UpdateMailSettingsCommand) => updateMailSettingsMock(cmd),
}))
vi.mock('../../api/getMailTemplates', () => ({ getMailTemplates: () => getMailTemplatesMock() }))
vi.mock('../../api/updateMailTemplates', () => ({
  updateMailTemplates: (kind: string, cmd: UpdateMailTemplatesCommand) =>
    updateMailTemplatesMock(kind, cmd),
}))
vi.mock('../../api/verifyLdapConnection', () => ({
  verifyLdapConnection: (cmd: VerifyLdapConnectionCommand) => verifyLdapConnectionMock(cmd),
}))
vi.mock('../../api/updateStorageSettings', () => ({
  updateStorageSettings: (cmd: UpdateStorageSettingsCommand) => updateStorageSettingsMock(cmd),
}))
vi.mock('../../api/testStorage', () => ({
  testStorage: (cmd: UpdateStorageSettingsCommand) => testStorageMock(cmd),
}))
vi.mock('../../api/updateSecuritySettings', () => ({
  updateSecuritySettings: (cmd: UpdateSecuritySettingsCommand) => updateSecuritySettingsMock(cmd),
}))
vi.mock('../../api/updateFeatureSettings', () => ({
  updateFeatureSettings: (cmd: unknown) => updateFeatureSettingsMock(cmd),
}))
vi.mock('../../api/updateGeneralSettings', () => ({
  updateGeneralSettings: (cmd: unknown) => updateGeneralSettingsMock(cmd),
}))
vi.mock('../../api/uploadCompanyLogo', () => ({
  uploadCompanyLogo: (file: File) => uploadCompanyLogoMock(file),
}))
vi.mock('../../api/deleteCompanyLogo', () => ({ deleteCompanyLogo: () => deleteCompanyLogoMock() }))
vi.mock('../../api/updateBrandingSettings', () => ({
  updateBrandingSettings: (cmd: UpdateBrandingSettingsCommand) => updateBrandingSettingsMock(cmd),
}))
vi.mock('../../api/uploadLoginBackgroundVideo', () => ({
  uploadLoginBackgroundVideo: (file: File) => uploadLoginBackgroundVideoMock(file),
}))
vi.mock('../../api/deleteLoginBackgroundVideo', () => ({
  deleteLoginBackgroundVideo: () => deleteLoginBackgroundVideoMock(),
}))
vi.mock('../../api/uploadBrandingLogo', () => ({
  uploadBrandingLogo: (file: File) => uploadBrandingLogoMock(file),
}))
vi.mock('../../api/deleteBrandingLogo', () => ({ deleteBrandingLogo: () => deleteBrandingLogoMock() }))
vi.mock('../../api/uploadBrandingFavicon', () => ({
  uploadBrandingFavicon: (file: File) => uploadBrandingFaviconMock(file),
}))
vi.mock('../../api/deleteBrandingFavicon', () => ({
  deleteBrandingFavicon: () => deleteBrandingFaviconMock(),
}))
vi.mock('../../api/updateNotificationSettings', () => ({
  updateNotificationSettings: (cmd: UpdateNotificationSettingsCommand) =>
    updateNotificationSettingsMock(cmd),
}))
vi.mock('../../api/updateMaintenanceSettings', () => ({
  updateMaintenanceSettings: (cmd: UpdateMaintenanceSettingsCommand) =>
    updateMaintenanceSettingsMock(cmd),
}))
vi.mock('../../api/updateBannerSettings', () => ({
  updateBannerSettings: (cmd: UpdateBannerSettingsCommand) => updateBannerSettingsMock(cmd),
}))
vi.mock('../../api/updateRetentionSettings', () => ({
  updateRetentionSettings: (cmd: UpdateRetentionSettingsCommand) => updateRetentionSettingsMock(cmd),
}))
vi.mock('../../api/updateOrderSettings', () => ({
  updateOrderSettings: (cmd: unknown) => updateOrderSettingsMock(cmd),
}))
vi.mock('../../api/updateMadeItemSettings', () => ({
  updateMadeItemSettings: (cmd: unknown) => updateMadeItemSettingsMock(cmd),
}))
vi.mock('../../api/updateProductionSettings', () => ({
  updateProductionSettings: (cmd: unknown) => updateProductionSettingsMock(cmd),
}))
vi.mock('../../api/updatePdmSettings', () => ({
  updatePdmSettings: (cmd: unknown) => updatePdmSettingsMock(cmd),
}))
vi.mock('../../api/verifyPdmConnection', () => ({
  verifyPdmConnection: (cmd: VerifyPdmConnectionCommand) => verifyPdmConnectionMock(cmd),
}))
vi.mock('../../api/getPdmOperations', () => ({ getPdmOperations: () => getPdmOperationsMock() }))
vi.mock('../../api/invokePdmOperation', () => ({
  invokePdmOperation: (operationId: string, cmd: InvokePdmOperationCommand) =>
    invokePdmOperationMock(operationId, cmd),
}))
vi.mock('../../api/getPdmWorkflows', () => ({ getPdmWorkflows: () => getPdmWorkflowsMock() }))
vi.mock('../../api/getPdmFolders', () => ({
  getPdmFolders: (parentId: number) => getPdmFoldersMock(parentId),
}))
vi.mock('../../api/requestPdmPoll', () => ({ requestPdmPoll: () => requestPdmPollMock() }))
vi.mock('../../api/listBackups', () => ({ listBackups: () => listBackupsMock() }))
vi.mock('../../api/runBackupNow', () => ({ runBackupNow: () => runBackupNowMock() }))
vi.mock('../../api/restoreFiles', () => ({
  restoreFiles: (snapshotKey: string) => restoreFilesMock(snapshotKey),
}))
vi.mock('../../api/downloadBackup', () => ({
  downloadBackup: (key: string) => downloadBackupMock(key),
}))

import { useAdminSettingsStore } from '../adminSettingsStore'

// ── Factories ─────────────────────────────────────────────────────────────
// One factory per AllAdminSettings sub-domain, each producing a minimal but
// fully valid object: only fields the store's own logic branches on
// (mail.enabled, banner.severity, ...) carry meaningful values; everything
// else is a plain placeholder.

function makeHostSettings(overrides: Partial<AdminHostSettings> = {}): AdminHostSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    domain: 'glados.example.com',
    ...overrides,
  }
}

function makeMailSettings(overrides: Partial<AdminMailSettings> = {}): AdminMailSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enabled: true,
    host: 'smtp.example.com',
    port: 587,
    user: 'mailer',
    password_configured: true,
    from_address: 'noreply@example.com',
    from_display_name: '',
    reply_to: null,
    use_tls: true,
    use_ssl: false,
    verify_certificate: true,
    alert_recipients: [],
    send_limit_per_hour: 20,
    send_lock_minutes: 60,
    attachment_limit_mb: 10,
    ...overrides,
  }
}

function makeAuthSettings(overrides: Partial<AdminAuthSettings> = {}): AdminAuthSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    ldap_enabled: false,
    ldap_host: '',
    ldap_port: 389,
    ldap_use_ssl: false,
    ldap_start_tls: false,
    ldap_verify_certificate: true,
    ldap_domain: '',
    ldap_timeout_seconds: 5,
    ...overrides,
  }
}

function makeStorageSettings(overrides: Partial<AdminStorageSettings> = {}): AdminStorageSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    provider: 'local',
    enabled: true,
    endpoint_url: null,
    public_endpoint_url: null,
    bucket_name: null,
    access_key: null,
    secret_key_configured: false,
    region: null,
    use_ssl: true,
    backup_enabled: false,
    backup_path: null,
    backup_cron: null,
    backup_retention_count: 7,
    disk_warning_percent: 90,
    ...overrides,
  }
}

function makeSecuritySettings(overrides: Partial<AdminSecuritySettings> = {}): AdminSecuritySettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enforce_totp: false,
    allow_rfid_login: true,
    allow_local_login: true,
    enable_api_key_auth: false,
    min_password_length: 8,
    session_timeout_minutes: 1440,
    totp_trusted_device_days: 30,
    max_login_attempts: 0,
    lockout_duration_minutes: 15,
    token_max_lifetime_days: 3650,
    session_max_lifetime_days: 30,
    enable_terminals: true,
    enable_infoscreen_weather: true,
    terminal_allowed_ips: [],
    ...overrides,
  }
}

function makeFeatureSettings(overrides: Partial<AdminFeatureSettings> = {}): AdminFeatureSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enable_email_notifications: true,
    enable_production_planning: true,
    allow_private_webhooks: false,
    enable_calculations: true,
    enable_checklists: true,
    enable_devices: true,
    enable_sequences: true,
    enable_todos: true,
    ...overrides,
  }
}

function makeGeneralSettings(overrides: Partial<AdminGeneralSettings> = {}): AdminGeneralSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    company_name: null,
    company_legal_name: null,
    has_company_logo: false,
    contact_email: null,
    imprint_url: null,
    privacy_url: null,
    support_url: null,
    product_number_pattern: '',
    project_number_pattern: '',
    allow_headless_projects: false,
    empty_value_placeholder: '-',
    office_launcher_enabled: false,
    office_sharepoint_url: '',
    default_language: 'enGB',
    default_timezone: 'Europe/Vienna',
    default_date_format: 'iso',
    currency: 'EUR',
    ...overrides,
  }
}

function makeBrandingSettings(overrides: Partial<AdminBrandingSettings> = {}): AdminBrandingSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    app_name: 'Glados',
    app_description: null,
    footer_text: null,
    has_logo: false,
    has_favicon: false,
    has_login_background_video: false,
    ...overrides,
  }
}

function makeNotificationSettings(
  overrides: Partial<AdminNotificationSettings> = {},
): AdminNotificationSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    webhook_timeout_seconds: 10,
    ...overrides,
  }
}

function makeMaintenanceSettings(
  overrides: Partial<AdminMaintenanceSettings> = {},
): AdminMaintenanceSettings {
  return { id: 1,
    public_id: '11111111-1111-1111-1111-111111111111', enabled: false, message: null, allowed_ips: [], ...overrides }
}

function makeBannerSettings(overrides: Partial<AdminBannerSettings> = {}): AdminBannerSettings {
  return {
    id: 1,
    public_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    enabled: false,
    text: '',
    severity: 'info',
    shows_from: null,
    shows_until: null,
    dismissable: true,
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeRetentionSettings(overrides: Partial<AdminRetentionSettings> = {}): AdminRetentionSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    log_retention_days: 30,
    audit_retention_days: 90,
    soft_delete_cleanup_days: 30,
    meeting_retention_days: 0,
    ...overrides,
  }
}

function makeOrderSettings(overrides: Partial<AdminOrderSettings> = {}): AdminOrderSettings {
  return {
    over_delivery_tolerance_percent: 0,
    under_delivery_tolerance_percent: 0,
    quote_request_number_format: 'RFQ-{yy}-{seq:05d}',
    quote_request_number_example: 'RFQ-26-00001',
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    order_number_format: 'ORD-{yy}-{seq:05d}',
    example: 'ORD-26-00001',
    part_number_format: 'PUR-{yy}-{seq:05d}',
    part_number_example: 'PUR-26-00001',
    part_number_auto: true,
    part_number_editable: false,
    web_creation_allowed: true,
    pdm_part_number_pattern: '',
    ...overrides,
  }
}

function makeMadeItemSettings(overrides: Partial<AdminMadeItemSettings> = {}): AdminMadeItemSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    item_number_format: 'FAB-{yy}-{seq:05d}',
    lot_number_format: 'LOT-{yy}-{seq:05d}',
    example: 'FAB-26-00001',
    lot_example: 'LOT-26-00001',
    calculation_number_format: 'CAL-{yy}-{seq:04d}',
    checklist_number_format: 'CHK-{yy}-{seq:04d}',
    sequence_number_format: 'SEQ-{yy}-{seq:04d}',
    meeting_number_format: 'MTG-{yy}-{seq:04d}',
    calculation_example: 'CAL-26-0001',
    checklist_example: 'CHK-26-0001',
    sequence_example: 'SEQ-26-0001',
    meeting_example: 'MTG-26-0001',
    part_number_auto: true,
    part_number_editable: false,
    revision_start: '0',
    revision_separator: ':',
    revision_skip_ambiguous_letters: false,
    revision_only_newest_editable: true,
    revision_predecessor_status_web: 'ask',
    revision_predecessor_status_pdm: 'replaced',
    revision_field_policy: [
      { field: 'article_name', web_requires_revision: true, pdm_update_in_place: false },
    ],
    web_creation_allowed: true,
    pdm_part_number_pattern: '',
    ...overrides,
  }
}

function makeProductionSettings(
  overrides: Partial<AdminProductionSettings> = {},
): AdminProductionSettings {
  return {
    frozen_window_hours: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    production_order_number_format: 'PON-{yy}-{seq:05d}',
    default_weekly_hours: {},
    default_external_lead_days: 0,
    response_time_days: 1,
    internal_handoff_minutes: 0,
    external_safety_margin_days: 2,
    example: 'PON-26-00001',
    require_qa: false,
    default_inspection_method_id: null,
    require_source_item_approval: false,
    assign_approved_material_to_item: false,
    overwrite_item_material_on_approval: false,
    external_first_step_needs_no_material: true,
    ...overrides,
  }
}

function makePdmSettings(overrides: Partial<AdminPdmSettings> = {}): AdminPdmSettings {
  return {
    id: 1,
    addin_language: '',
    mutating_operations_enabled: false,
    public_id: '22222222-2222-2222-2222-222222222222',
    set_approver_from_pdm: false,
    made_item_variable_map: {},
    bought_item_variable_map: {},
    item_fields: {
      made: [
        { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
        { field: 'article_name', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
      ],
      bought: [],
    },
    enabled: false,
    base_url: '',
    vault_name: '',
    username: '',
    password_configured: false,
    verify_certificate: true,
    timeout_seconds: 15,
    configured: false,
    session: { active: false, obtained_at: null, user_id: null },
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
    vault_id: '',
    cad_items_read_only: true,
    last_poll_at: null,
    last_poll_error: null,
    last_poll_summary: null,
    writeback_enabled: false,
    made_item_extensions: ['sldprt'],
    bought_item_extensions: ['sldasm', 'sldprt'],
    document_categories: {},
    document_excluded_kinds: {},
    thumbnails_enabled: false,
    stuck_after_days: 7,
    snapshot_counts: {},
    required_fields: { made: [], bought: [] },
    locked_required_fields: {
      made: ['part_number', 'revision', 'article_name'],
      bought: ['part_number', 'revision', 'article_name', 'order_code_1', 'manufacturer_id'],
    },
    required_field_rules: { made: [], bought: [] },
    made_feature_tree_template: '{part_number} Rev{revision} ({article_name})',
    bought_feature_tree_template: '{article_name} - {order_code_1} - {manufacturer_name}',
    ...overrides,
  }
}

function makePlanningSettings(overrides: Partial<AdminPlanningSettings> = {}): AdminPlanningSettings {
  return {
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000031',
    commit_horizon_working_days: 5,
    plan_retention_days: 400,
    booking_quality_since: '2026-11-27T08:00:00Z',
    ...overrides,
  }
}

function makeAllSettings(overrides: Partial<AllAdminSettings> = {}): AllAdminSettings {
  return {
    host: makeHostSettings(),
    mail: makeMailSettings(),
    auth: makeAuthSettings(),
    storage: makeStorageSettings(),
    security: makeSecuritySettings(),
    features: makeFeatureSettings(),
    general: makeGeneralSettings(),
    branding: makeBrandingSettings(),
    notifications: makeNotificationSettings(),
    maintenance: makeMaintenanceSettings(),
    banner: makeBannerSettings(),
    retention: makeRetentionSettings(),
    orders: makeOrderSettings(),
    made_items: makeMadeItemSettings(),
    production: makeProductionSettings(),
    planning: makePlanningSettings(),
    pdm: makePdmSettings(),
    ...overrides,
  }
}

function makeMailGroup(overrides: Partial<MailTemplateKindGroup> = {}): MailTemplateKindGroup {
  return {
    kind: 'welcome',
    family: 'system',
    variables: ['user_name'],
    default_subject: 'Welcome',
    entries: [
      { id: 1, public_id: '33333333-3333-3333-3333-333333333333', kind: 'welcome', language: 'enGB', subject: 'Welcome', body: '<p>Hi</p>', configured: true },
    ],
    ...overrides,
  }
}

/**
 * Seeds a fresh store via a successful fetch(), so save* tests exercise the
 * real `if (settings.value) settings.value.x = result` branch rather than
 * the null-guard path (covered separately below).
 */
async function seededStore() {
  getAllAdminSettingsMock.mockResolvedValueOnce(makeAllSettings())
  const store = useAdminSettingsStore()
  await store.fetch()
  return store
}

const allMocks = [
  getAllAdminSettingsMock,
  updateAuthSettingsMock,
  updateMailSettingsMock,
  getMailTemplatesMock,
  updateMailTemplatesMock,
  verifyLdapConnectionMock,
  updateStorageSettingsMock,
  testStorageMock,
  updateSecuritySettingsMock,
  updateFeatureSettingsMock,
  updateGeneralSettingsMock,
  uploadCompanyLogoMock,
  deleteCompanyLogoMock,
  updateBrandingSettingsMock,
  uploadLoginBackgroundVideoMock,
  deleteLoginBackgroundVideoMock,
  uploadBrandingLogoMock,
  deleteBrandingLogoMock,
  uploadBrandingFaviconMock,
  deleteBrandingFaviconMock,
  updateNotificationSettingsMock,
  updateMaintenanceSettingsMock,
  updateBannerSettingsMock,
  updateRetentionSettingsMock,
  updateOrderSettingsMock,
  updateMadeItemSettingsMock,
  updateProductionSettingsMock,
  updatePdmSettingsMock,
  verifyPdmConnectionMock,
  getPdmOperationsMock,
  invokePdmOperationMock,
  getPdmWorkflowsMock,
  getPdmFoldersMock,
  requestPdmPollMock,
  listBackupsMock,
  runBackupNowMock,
  restoreFilesMock,
  downloadBackupMock,
]

describe('useAdminSettingsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    for (const mock of allMocks) mock.mockReset()
  })

  describe('initial state', () => {
    it('starts with nothing loaded', () => {
      const store = useAdminSettingsStore()
      expect(store.loading).toBe(false)
      expect(store.settings).toBeNull()
      expect(store.mailTemplates).toEqual([])
      expect(store.pdmOperations).toEqual([])
      expect(store.pdmWorkflows).toEqual([])
    })
  })

  describe('fetch', () => {
    it('populates settings and resets loading on success', async () => {
      const all = makeAllSettings()
      getAllAdminSettingsMock.mockResolvedValue(all)
      const store = useAdminSettingsStore()

      await store.fetch()

      expect(store.settings).toEqual(all)
      expect(store.loading).toBe(false)
    })

    it('resets loading and leaves settings null when the request fails', async () => {
      getAllAdminSettingsMock.mockRejectedValueOnce(new Error('network error'))
      const store = useAdminSettingsStore()

      await store.fetch()

      expect(store.loading).toBe(false)
      expect(store.settings).toBeNull()
    })
  })

  describe('saveMail', () => {
    const cmd: UpdateMailSettingsCommand = {
      enabled: true,
      host: 'smtp2.example.com',
      port: 25,
      user: 'mailer2',
      from_display_name: 'Glados',
      reply_to: null,
      use_tls: true,
      use_ssl: false,
      verify_certificate: true,
      alert_recipients: ['ops@example.com'],
      send_limit_per_hour: 10,
      send_lock_minutes: 30,
    }

    it('updates settings.mail and returns the result', async () => {
      const store = await seededStore()
      const result = makeMailSettings({ enabled: false })
      updateMailSettingsMock.mockResolvedValue(result)

      const returned = await store.saveMail(cmd)

      expect(updateMailSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.mail).toEqual(result)
    })

    it('leaves settings.mail unchanged when the request fails', async () => {
      const store = await seededStore()
      updateMailSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveMail(cmd)).rejects.toThrow('422')

      expect(store.settings?.mail).toEqual(makeMailSettings())
    })

    it('does not throw when settings is still null (no fetch yet), and does not seed it either', async () => {
      updateMailSettingsMock.mockResolvedValue(makeMailSettings())
      const store = useAdminSettingsStore()

      const returned = await store.saveMail(cmd)

      expect(returned).toEqual(makeMailSettings())
      expect(store.settings).toBeNull()
    })
  })

  describe('saveAuth', () => {
    const cmd: UpdateAuthSettingsCommand = {
      ldap_enabled: true,
      ldap_host: 'ldap.example.com',
      ldap_port: 636,
      ldap_use_ssl: true,
      ldap_start_tls: false,
      ldap_verify_certificate: true,
      ldap_domain: 'EXAMPLE',
      ldap_timeout_seconds: 10,
    }

    it('updates settings.auth and returns the result', async () => {
      const store = await seededStore()
      const result = makeAuthSettings({ ldap_enabled: true })
      updateAuthSettingsMock.mockResolvedValue(result)

      const returned = await store.saveAuth(cmd)

      expect(updateAuthSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.auth).toEqual(result)
    })

    it('leaves settings.auth unchanged when the request fails', async () => {
      const store = await seededStore()
      updateAuthSettingsMock.mockRejectedValueOnce(new Error('400'))

      await expect(store.saveAuth(cmd)).rejects.toThrow('400')

      expect(store.settings?.auth).toEqual(makeAuthSettings())
    })
  })

  describe('verifyLdap', () => {
    const cmd: VerifyLdapConnectionCommand = {
      ldap_enabled: true,
      ldap_host: 'ldap.example.com',
      ldap_port: 636,
      ldap_use_ssl: true,
      ldap_start_tls: false,
      ldap_verify_certificate: true,
      ldap_domain: 'EXAMPLE',
      ldap_timeout_seconds: 10,
      username: 'binder',
      password: 'secret',
    }

    it('calls verifyLdapConnection and resolves with nothing cached', async () => {
      verifyLdapConnectionMock.mockResolvedValue(undefined)
      const store = useAdminSettingsStore()

      await store.verifyLdap(cmd)

      expect(verifyLdapConnectionMock).toHaveBeenCalledWith(cmd)
    })

    it('rethrows when the probe fails', async () => {
      verifyLdapConnectionMock.mockRejectedValueOnce(new Error('400'))
      const store = useAdminSettingsStore()

      await expect(store.verifyLdap(cmd)).rejects.toThrow('400')
    })
  })

  describe('saveStorage', () => {
    const cmd: UpdateStorageSettingsCommand = {
      provider: 'local',
      enabled: true,
      use_ssl: true,
      backup_enabled: false,
      backup_retention_count: 7,
      disk_warning_percent: 90,
    }

    it('updates settings.storage and returns the result', async () => {
      const store = await seededStore()
      const result = makeStorageSettings({ provider: 's3' })
      updateStorageSettingsMock.mockResolvedValue(result)

      const returned = await store.saveStorage(cmd)

      expect(updateStorageSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.storage).toEqual(result)
    })

    it('leaves settings.storage unchanged when the request fails', async () => {
      const store = await seededStore()
      updateStorageSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveStorage(cmd)).rejects.toThrow('422')

      expect(store.settings?.storage).toEqual(makeStorageSettings())
    })
  })

  describe('testStorage', () => {
    const cmd: UpdateStorageSettingsCommand = {
      provider: 's3',
      enabled: true,
      use_ssl: true,
      backup_enabled: false,
      backup_retention_count: 7,
      disk_warning_percent: 90,
    }

    it('calls testStorage and caches nothing', async () => {
      testStorageMock.mockResolvedValue(undefined)
      const store = useAdminSettingsStore()

      await store.testStorage(cmd)

      expect(testStorageMock).toHaveBeenCalledWith(cmd)
    })

    it('rethrows when the probe fails', async () => {
      testStorageMock.mockRejectedValueOnce(new Error('503'))
      const store = useAdminSettingsStore()

      await expect(store.testStorage(cmd)).rejects.toThrow('503')
    })
  })

  describe('saveSecurity', () => {
    const cmd: UpdateSecuritySettingsCommand = {
      enforce_totp: true,
      allow_rfid_login: false,
      allow_local_login: true,
      enable_api_key_auth: true,
      min_password_length: 12,
      session_timeout_minutes: 60,
      totp_trusted_device_days: 7,
      max_login_attempts: 5,
      lockout_duration_minutes: 30,
      token_max_lifetime_days: 90,
      session_max_lifetime_days: 30,
      enable_terminals: true,
      enable_infoscreen_weather: true,
      terminal_allowed_ips: [],
    }

    it('updates settings.security and returns the result', async () => {
      const store = await seededStore()
      const result = makeSecuritySettings({ enforce_totp: true })
      updateSecuritySettingsMock.mockResolvedValue(result)

      const returned = await store.saveSecurity(cmd)

      expect(updateSecuritySettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.security).toEqual(result)
    })

    it('leaves settings.security unchanged when the request fails', async () => {
      const store = await seededStore()
      updateSecuritySettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveSecurity(cmd)).rejects.toThrow('422')

      expect(store.settings?.security).toEqual(makeSecuritySettings())
    })
  })

  describe('saveFeatures', () => {
    it('updates settings.features and returns the result', async () => {
      const store = await seededStore()
      const result = makeFeatureSettings({ enable_email_notifications: false })
      updateFeatureSettingsMock.mockResolvedValue(result)

      const returned = await store.saveFeatures({ enable_email_notifications: false })

      expect(updateFeatureSettingsMock).toHaveBeenCalledWith({ enable_email_notifications: false })
      expect(returned).toEqual(result)
      expect(store.settings?.features).toEqual(result)
    })

    it('leaves settings.features unchanged when the request fails', async () => {
      const store = await seededStore()
      updateFeatureSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveFeatures({})).rejects.toThrow('422')

      expect(store.settings?.features).toEqual(makeFeatureSettings())
    })
  })

  describe('saveGeneral', () => {
    it('updates settings.general and returns the result', async () => {
      const store = await seededStore()
      const result = makeGeneralSettings({ currency: 'USD' })
      updateGeneralSettingsMock.mockResolvedValue(result)

      const returned = await store.saveGeneral({ currency: 'USD' })

      expect(updateGeneralSettingsMock).toHaveBeenCalledWith({ currency: 'USD' })
      expect(returned).toEqual(result)
      expect(store.settings?.general).toEqual(result)
    })

    it('leaves settings.general unchanged when the request fails', async () => {
      const store = await seededStore()
      updateGeneralSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveGeneral({})).rejects.toThrow('422')

      expect(store.settings?.general).toEqual(makeGeneralSettings())
    })
  })

  describe('company logo', () => {
    it('uploadCompanyLogoFile updates settings.general and returns the result', async () => {
      const store = await seededStore()
      const result = makeGeneralSettings({ has_company_logo: true })
      uploadCompanyLogoMock.mockResolvedValue(result)
      const file = new File(['x'], 'logo.png')

      const returned = await store.uploadCompanyLogoFile(file)

      expect(uploadCompanyLogoMock).toHaveBeenCalledWith(file)
      expect(returned).toEqual(result)
      expect(store.settings?.general).toEqual(result)
    })

    it('uploadCompanyLogoFile leaves settings.general unchanged when the request fails', async () => {
      const store = await seededStore()
      uploadCompanyLogoMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.uploadCompanyLogoFile(new File(['x'], 'logo.png'))).rejects.toThrow('422')

      expect(store.settings?.general).toEqual(makeGeneralSettings())
    })

    it('removeCompanyLogo updates settings.general and returns the result', async () => {
      const store = await seededStore()
      const result = makeGeneralSettings({ has_company_logo: false })
      deleteCompanyLogoMock.mockResolvedValue(result)

      const returned = await store.removeCompanyLogo()

      expect(deleteCompanyLogoMock).toHaveBeenCalled()
      expect(returned).toEqual(result)
      expect(store.settings?.general).toEqual(result)
    })

    it('removeCompanyLogo leaves settings.general unchanged when the request fails', async () => {
      const store = await seededStore()
      deleteCompanyLogoMock.mockRejectedValueOnce(new Error('500'))

      await expect(store.removeCompanyLogo()).rejects.toThrow('500')

      expect(store.settings?.general).toEqual(makeGeneralSettings())
    })
  })

  describe('saveBranding', () => {
    const cmd: UpdateBrandingSettingsCommand = { app_name: 'New Glados' }

    it('updates settings.branding and returns the result', async () => {
      const store = await seededStore()
      const result = makeBrandingSettings({ app_name: 'New Glados' })
      updateBrandingSettingsMock.mockResolvedValue(result)

      const returned = await store.saveBranding(cmd)

      expect(updateBrandingSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.branding).toEqual(result)
    })

    it('leaves settings.branding unchanged when the request fails', async () => {
      const store = await seededStore()
      updateBrandingSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveBranding(cmd)).rejects.toThrow('422')

      expect(store.settings?.branding).toEqual(makeBrandingSettings())
    })
  })

  describe('login background video', () => {
    it('uploadLoginVideo updates settings.branding and returns the result', async () => {
      const store = await seededStore()
      const result = makeBrandingSettings({ has_login_background_video: true })
      uploadLoginBackgroundVideoMock.mockResolvedValue(result)
      const file = new File(['x'], 'bg.mp4')

      const returned = await store.uploadLoginVideo(file)

      expect(uploadLoginBackgroundVideoMock).toHaveBeenCalledWith(file)
      expect(returned).toEqual(result)
      expect(store.settings?.branding).toEqual(result)
    })

    it('uploadLoginVideo leaves settings.branding unchanged when the request fails', async () => {
      const store = await seededStore()
      uploadLoginBackgroundVideoMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.uploadLoginVideo(new File(['x'], 'bg.mp4'))).rejects.toThrow('422')

      expect(store.settings?.branding).toEqual(makeBrandingSettings())
    })

    it('deleteLoginVideo updates settings.branding and returns the result', async () => {
      const store = await seededStore()
      const result = makeBrandingSettings({ has_login_background_video: false })
      deleteLoginBackgroundVideoMock.mockResolvedValue(result)

      const returned = await store.deleteLoginVideo()

      expect(deleteLoginBackgroundVideoMock).toHaveBeenCalled()
      expect(returned).toEqual(result)
      expect(store.settings?.branding).toEqual(result)
    })

    it('deleteLoginVideo leaves settings.branding unchanged when the request fails', async () => {
      const store = await seededStore()
      deleteLoginBackgroundVideoMock.mockRejectedValueOnce(new Error('500'))

      await expect(store.deleteLoginVideo()).rejects.toThrow('500')

      expect(store.settings?.branding).toEqual(makeBrandingSettings())
    })
  })

  describe('branding logo', () => {
    it('uploadLogo updates settings.branding and returns the result', async () => {
      const store = await seededStore()
      const result = makeBrandingSettings({ has_logo: true })
      uploadBrandingLogoMock.mockResolvedValue(result)
      const file = new File(['x'], 'logo.svg')

      const returned = await store.uploadLogo(file)

      expect(uploadBrandingLogoMock).toHaveBeenCalledWith(file)
      expect(returned).toEqual(result)
      expect(store.settings?.branding).toEqual(result)
    })

    it('uploadLogo leaves settings.branding unchanged when the request fails', async () => {
      const store = await seededStore()
      uploadBrandingLogoMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.uploadLogo(new File(['x'], 'logo.svg'))).rejects.toThrow('422')

      expect(store.settings?.branding).toEqual(makeBrandingSettings())
    })

    it('deleteLogo updates settings.branding and returns the result', async () => {
      const store = await seededStore()
      const result = makeBrandingSettings({ has_logo: false })
      deleteBrandingLogoMock.mockResolvedValue(result)

      const returned = await store.deleteLogo()

      expect(deleteBrandingLogoMock).toHaveBeenCalled()
      expect(returned).toEqual(result)
      expect(store.settings?.branding).toEqual(result)
    })

    it('deleteLogo leaves settings.branding unchanged when the request fails', async () => {
      const store = await seededStore()
      deleteBrandingLogoMock.mockRejectedValueOnce(new Error('500'))

      await expect(store.deleteLogo()).rejects.toThrow('500')

      expect(store.settings?.branding).toEqual(makeBrandingSettings())
    })
  })

  describe('branding favicon', () => {
    it('uploadFavicon updates settings.branding and returns the result', async () => {
      const store = await seededStore()
      const result = makeBrandingSettings({ has_favicon: true })
      uploadBrandingFaviconMock.mockResolvedValue(result)
      const file = new File(['x'], 'favicon.ico')

      const returned = await store.uploadFavicon(file)

      expect(uploadBrandingFaviconMock).toHaveBeenCalledWith(file)
      expect(returned).toEqual(result)
      expect(store.settings?.branding).toEqual(result)
    })

    it('uploadFavicon leaves settings.branding unchanged when the request fails', async () => {
      const store = await seededStore()
      uploadBrandingFaviconMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.uploadFavicon(new File(['x'], 'favicon.ico'))).rejects.toThrow('422')

      expect(store.settings?.branding).toEqual(makeBrandingSettings())
    })

    it('deleteFavicon updates settings.branding and returns the result', async () => {
      const store = await seededStore()
      const result = makeBrandingSettings({ has_favicon: false })
      deleteBrandingFaviconMock.mockResolvedValue(result)

      const returned = await store.deleteFavicon()

      expect(deleteBrandingFaviconMock).toHaveBeenCalled()
      expect(returned).toEqual(result)
      expect(store.settings?.branding).toEqual(result)
    })

    it('deleteFavicon leaves settings.branding unchanged when the request fails', async () => {
      const store = await seededStore()
      deleteBrandingFaviconMock.mockRejectedValueOnce(new Error('500'))

      await expect(store.deleteFavicon()).rejects.toThrow('500')

      expect(store.settings?.branding).toEqual(makeBrandingSettings())
    })
  })

  describe('saveNotifications', () => {
    const cmd: UpdateNotificationSettingsCommand = {
      webhook_timeout_seconds: 15,
    }

    it('updates settings.notifications and returns the result', async () => {
      const store = await seededStore()
      const result = makeNotificationSettings({ webhook_timeout_seconds: 15 })
      updateNotificationSettingsMock.mockResolvedValue(result)

      const returned = await store.saveNotifications(cmd)

      expect(updateNotificationSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.notifications).toEqual(result)
    })

    it('leaves settings.notifications unchanged when the request fails', async () => {
      const store = await seededStore()
      updateNotificationSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveNotifications(cmd)).rejects.toThrow('422')

      expect(store.settings?.notifications).toEqual(makeNotificationSettings())
    })
  })

  describe('saveMaintenance', () => {
    const cmd: UpdateMaintenanceSettingsCommand = { enabled: true, allowed_ips: ['10.0.0.1'] }

    it('updates settings.maintenance and returns the result', async () => {
      const store = await seededStore()
      const result = makeMaintenanceSettings({ enabled: true })
      updateMaintenanceSettingsMock.mockResolvedValue(result)

      const returned = await store.saveMaintenance(cmd)

      expect(updateMaintenanceSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.maintenance).toEqual(result)
    })

    it('leaves settings.maintenance unchanged when the request fails', async () => {
      const store = await seededStore()
      updateMaintenanceSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveMaintenance(cmd)).rejects.toThrow('422')

      expect(store.settings?.maintenance).toEqual(makeMaintenanceSettings())
    })
  })

  describe('saveBanner', () => {
    const cmd: UpdateBannerSettingsCommand = {
      enabled: true,
      text: 'Maintenance tonight',
      severity: 'warning',
      shows_from: null,
      shows_until: null,
      dismissable: true,
    }

    it('updates settings.banner and returns the result', async () => {
      const store = await seededStore()
      const result = makeBannerSettings({ enabled: true, severity: 'warning' })
      updateBannerSettingsMock.mockResolvedValue(result)

      const returned = await store.saveBanner(cmd)

      expect(updateBannerSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.banner).toEqual(result)
    })

    it('leaves settings.banner unchanged when the request fails', async () => {
      const store = await seededStore()
      updateBannerSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveBanner(cmd)).rejects.toThrow('422')

      expect(store.settings?.banner).toEqual(makeBannerSettings())
    })
  })

  describe('saveRetention', () => {
    const cmd: UpdateRetentionSettingsCommand = {
      log_retention_days: 60,
      audit_retention_days: 180,
      soft_delete_cleanup_days: 14,
    }

    it('updates settings.retention and returns the result', async () => {
      const store = await seededStore()
      const result = makeRetentionSettings({ log_retention_days: 60 })
      updateRetentionSettingsMock.mockResolvedValue(result)

      const returned = await store.saveRetention(cmd)

      expect(updateRetentionSettingsMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
      expect(store.settings?.retention).toEqual(result)
    })

    it('leaves settings.retention unchanged when the request fails', async () => {
      const store = await seededStore()
      updateRetentionSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveRetention(cmd)).rejects.toThrow('422')

      expect(store.settings?.retention).toEqual(makeRetentionSettings())
    })
  })

  describe('saveOrders', () => {
    it('updates settings.orders and returns the result', async () => {
      const store = await seededStore()
      const result = makeOrderSettings({ part_number_auto: false })
      updateOrderSettingsMock.mockResolvedValue(result)

      const returned = await store.saveOrders({ part_number_auto: false })

      expect(updateOrderSettingsMock).toHaveBeenCalledWith({ part_number_auto: false })
      expect(returned).toEqual(result)
      expect(store.settings?.orders).toEqual(result)
    })

    it('leaves settings.orders unchanged when the request fails', async () => {
      const store = await seededStore()
      updateOrderSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveOrders({})).rejects.toThrow('422')

      expect(store.settings?.orders).toEqual(makeOrderSettings())
    })
  })

  describe('saveMadeItems', () => {
    it('updates settings.made_items and returns the result', async () => {
      const store = await seededStore()
      const result = makeMadeItemSettings({ revision_separator: '-' })
      updateMadeItemSettingsMock.mockResolvedValue(result)

      const returned = await store.saveMadeItems({ revision_separator: '-' })

      expect(updateMadeItemSettingsMock).toHaveBeenCalledWith({ revision_separator: '-' })
      expect(returned).toEqual(result)
      expect(store.settings?.made_items).toEqual(result)
    })

    it('leaves settings.made_items unchanged when the request fails', async () => {
      const store = await seededStore()
      updateMadeItemSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveMadeItems({})).rejects.toThrow('422')

      expect(store.settings?.made_items).toEqual(makeMadeItemSettings())
    })
  })

  describe('saveProduction', () => {
    it('updates settings.production and returns the result', async () => {
      const store = await seededStore()
      const result = makeProductionSettings({ require_qa: true })
      updateProductionSettingsMock.mockResolvedValue(result)

      const returned = await store.saveProduction({ require_qa: true })

      expect(updateProductionSettingsMock).toHaveBeenCalledWith({ require_qa: true })
      expect(returned).toEqual(result)
      expect(store.settings?.production).toEqual(result)
    })

    it('leaves settings.production unchanged when the request fails', async () => {
      const store = await seededStore()
      updateProductionSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.saveProduction({})).rejects.toThrow('422')

      expect(store.settings?.production).toEqual(makeProductionSettings())
    })
  })

  describe('savePdm', () => {
    it('updates settings.pdm and returns the result', async () => {
      const store = await seededStore()
      const result = makePdmSettings({ enabled: true })
      updatePdmSettingsMock.mockResolvedValue(result)

      const returned = await store.savePdm({ enabled: true })

      expect(updatePdmSettingsMock).toHaveBeenCalledWith({ enabled: true })
      expect(returned).toEqual(result)
      expect(store.settings?.pdm).toEqual(result)
    })

    it('leaves settings.pdm unchanged when the request fails', async () => {
      const store = await seededStore()
      updatePdmSettingsMock.mockRejectedValueOnce(new Error('422'))

      await expect(store.savePdm({})).rejects.toThrow('422')

      expect(store.settings?.pdm).toEqual(makePdmSettings())
    })
  })

  describe('verifyPdm', () => {
    const cmd: VerifyPdmConnectionCommand = {
      base_url: 'https://vault.example.com',
      vault_name: 'Glados',
      username: 'svc',
      verify_certificate: true,
      timeout_seconds: 15,
    }

    it('probes the connection and caches nothing', async () => {
      const result: PdmConnectionTestResult = {
        product_name: 'SOLIDWORKS PDM',
        app_version: '2026',
        user_id: 1,
      }
      verifyPdmConnectionMock.mockResolvedValue(result)
      const store = useAdminSettingsStore()

      const returned = await store.verifyPdm(cmd)

      expect(verifyPdmConnectionMock).toHaveBeenCalledWith(cmd)
      expect(returned).toEqual(result)
    })

    it('rethrows when the probe fails', async () => {
      verifyPdmConnectionMock.mockRejectedValueOnce(new Error('400'))
      const store = useAdminSettingsStore()

      await expect(store.verifyPdm(cmd)).rejects.toThrow('400')
    })
  })

  describe('loadPdmOperations', () => {
    const operation: PdmOperation = {
      id: 'get-document',
      method: 'GET',
      path: '/documents/{id}',
      group: 'documents',
      description: 'Fetch a document',
      params: [],
      has_body: false,
      body_example: null,
      mutating: false,
    }

    it('fetches and caches the catalogue on first call', async () => {
      getPdmOperationsMock.mockResolvedValue([operation])
      const store = useAdminSettingsStore()

      const result = await store.loadPdmOperations()

      expect(result).toEqual([operation])
      expect(store.pdmOperations).toEqual([operation])
    })

    it('serves the cache on a second call without refetching', async () => {
      getPdmOperationsMock.mockResolvedValue([operation])
      const store = useAdminSettingsStore()
      await store.loadPdmOperations()

      await store.loadPdmOperations()

      expect(getPdmOperationsMock).toHaveBeenCalledTimes(1)
    })

    it('leaves the cache empty (and so retryable) when the fetch fails', async () => {
      getPdmOperationsMock.mockRejectedValueOnce(new Error('503'))
      const store = useAdminSettingsStore()

      await expect(store.loadPdmOperations()).rejects.toThrow('503')

      expect(store.pdmOperations).toEqual([])

      getPdmOperationsMock.mockResolvedValueOnce([operation])
      await store.loadPdmOperations()
      expect(getPdmOperationsMock).toHaveBeenCalledTimes(2)
      expect(store.pdmOperations).toEqual([operation])
    })
  })

  describe('invokePdmOperation', () => {
    const cmd: InvokePdmOperationCommand = {
      path_params: { id: 1 },
      query: {},
      allow_mutating: false,
    }

    it('invokes the operation and returns the raw result', async () => {
      const result: PdmInvokeResult = {
        method: 'GET',
        url: 'https://vault.example.com/documents/1',
        status_code: 200,
        elapsed_ms: 42,
        content_type: 'application/json',
        response_json: { id: 1 },
        response_text: null,
      }
      invokePdmOperationMock.mockResolvedValue(result)
      const store = useAdminSettingsStore()

      const returned = await store.invokePdmOperation('get-document', cmd)

      expect(invokePdmOperationMock).toHaveBeenCalledWith('get-document', cmd)
      expect(returned).toEqual(result)
    })

    it('rethrows when the invocation fails', async () => {
      invokePdmOperationMock.mockRejectedValueOnce(new Error('502'))
      const store = useAdminSettingsStore()

      await expect(store.invokePdmOperation('get-document', cmd)).rejects.toThrow('502')
    })
  })

  describe('loadPdmWorkflows', () => {
    const workflow: PdmWorkflow = {
      workflow_id: 1,
      workflow_name: 'Made item lifecycle',
      states: [{ state_id: 1, state_name: 'Released' }],
    }

    it('fetches and caches the workflow list on first call', async () => {
      getPdmWorkflowsMock.mockResolvedValue([workflow])
      const store = useAdminSettingsStore()

      const result = await store.loadPdmWorkflows()

      expect(result).toEqual([workflow])
      expect(store.pdmWorkflows).toEqual([workflow])
    })

    it('serves the cache on a second call without refetching', async () => {
      getPdmWorkflowsMock.mockResolvedValue([workflow])
      const store = useAdminSettingsStore()
      await store.loadPdmWorkflows()

      await store.loadPdmWorkflows()

      expect(getPdmWorkflowsMock).toHaveBeenCalledTimes(1)
    })

    it('leaves the cache empty (and so retryable) when the fetch fails', async () => {
      getPdmWorkflowsMock.mockRejectedValueOnce(new Error('503'))
      const store = useAdminSettingsStore()

      await expect(store.loadPdmWorkflows()).rejects.toThrow('503')

      expect(store.pdmWorkflows).toEqual([])
    })
  })

  describe('loadPdmFolders', () => {
    it('never caches: two calls for the same parent both hit the API', async () => {
      const folder: PdmFolder = { id: 2, name: 'Made Parts', path: '\\Made Parts' }
      getPdmFoldersMock.mockResolvedValue([folder])
      const store = useAdminSettingsStore()

      const first = await store.loadPdmFolders(1)
      const second = await store.loadPdmFolders(1)

      expect(first).toEqual([folder])
      expect(second).toEqual([folder])
      expect(getPdmFoldersMock).toHaveBeenCalledTimes(2)
      expect(getPdmFoldersMock).toHaveBeenCalledWith(1)
    })

    it('rethrows when the request fails', async () => {
      getPdmFoldersMock.mockRejectedValueOnce(new Error('503'))
      const store = useAdminSettingsStore()

      await expect(store.loadPdmFolders(1)).rejects.toThrow('503')
    })
  })

  describe('requestPdmPoll', () => {
    it('returns the queued result', async () => {
      requestPdmPollMock.mockResolvedValue({ accepted: true })
      const store = useAdminSettingsStore()

      const result = await store.requestPdmPoll()

      expect(requestPdmPollMock).toHaveBeenCalled()
      expect(result).toEqual({ accepted: true })
    })

    it('rethrows when PDM is not enabled (409)', async () => {
      requestPdmPollMock.mockRejectedValueOnce(new Error('409'))
      const store = useAdminSettingsStore()

      await expect(store.requestPdmPoll()).rejects.toThrow('409')
    })
  })

  describe('backups', () => {
    const backups: BackupList = { db: [], files: [], warnings: [], last_run: null, runs: [] }

    it('fetchBackups returns the list', async () => {
      listBackupsMock.mockResolvedValue(backups)
      const store = useAdminSettingsStore()

      const result = await store.fetchBackups()

      expect(listBackupsMock).toHaveBeenCalled()
      expect(result).toEqual(backups)
    })

    it('fetchBackups rethrows when the request fails', async () => {
      listBackupsMock.mockRejectedValueOnce(new Error('500'))
      const store = useAdminSettingsStore()

      await expect(store.fetchBackups()).rejects.toThrow('500')
    })

    it('triggerBackupNow calls runBackupNow', async () => {
      runBackupNowMock.mockResolvedValue(undefined)
      const store = useAdminSettingsStore()

      await store.triggerBackupNow()

      expect(runBackupNowMock).toHaveBeenCalled()
    })

    it('triggerBackupNow rethrows when the request fails', async () => {
      runBackupNowMock.mockRejectedValueOnce(new Error('500'))
      const store = useAdminSettingsStore()

      await expect(store.triggerBackupNow()).rejects.toThrow('500')
    })

    it('restoreFileSnapshot returns the restored count', async () => {
      const result: RestoreFilesResult = { restored_count: 12 }
      restoreFilesMock.mockResolvedValue(result)
      const store = useAdminSettingsStore()

      const returned = await store.restoreFileSnapshot('snap-1')

      expect(restoreFilesMock).toHaveBeenCalledWith('snap-1')
      expect(returned).toEqual(result)
    })

    it('restoreFileSnapshot rethrows when the request fails', async () => {
      restoreFilesMock.mockRejectedValueOnce(new Error('500'))
      const store = useAdminSettingsStore()

      await expect(store.restoreFileSnapshot('snap-1')).rejects.toThrow('500')
    })

    it('downloadBackup calls the API with the given key', async () => {
      downloadBackupMock.mockResolvedValue(undefined)
      const store = useAdminSettingsStore()

      await store.downloadBackup('db/2026-01-01.sql.gz')

      expect(downloadBackupMock).toHaveBeenCalledWith('db/2026-01-01.sql.gz')
    })

    it('downloadBackup rethrows when the request fails', async () => {
      downloadBackupMock.mockRejectedValueOnce(new Error('404'))
      const store = useAdminSettingsStore()

      await expect(store.downloadBackup('missing')).rejects.toThrow('404')
    })
  })

  describe('mail templates', () => {
    it('fetchMailTemplates populates mailTemplates from the kinds array', async () => {
      const groups = [makeMailGroup({ kind: 'welcome' }), makeMailGroup({ kind: 'order' })]
      getMailTemplatesMock.mockResolvedValue({ kinds: groups })
      const store = useAdminSettingsStore()

      const result = await store.fetchMailTemplates()

      expect(result).toEqual(groups)
      expect(store.mailTemplates).toEqual(groups)
    })

    it('fetchMailTemplates resolves to undefined and leaves mailTemplates empty when the request fails', async () => {
      getMailTemplatesMock.mockRejectedValueOnce(new Error('500'))
      const store = useAdminSettingsStore()

      const result = await store.fetchMailTemplates()

      expect(result).toBeUndefined()
      expect(store.mailTemplates).toEqual([])
    })

    it('saveMailTemplates replaces only the matching kind, leaving the others cached as-is', async () => {
      getMailTemplatesMock.mockResolvedValue({
        kinds: [makeMailGroup({ kind: 'welcome' }), makeMailGroup({ kind: 'order' })],
      })
      const store = useAdminSettingsStore()
      await store.fetchMailTemplates()
      const updatedWelcome = makeMailGroup({ kind: 'welcome', default_subject: 'Hi there' })
      updateMailTemplatesMock.mockResolvedValue(updatedWelcome)

      const cmd: UpdateMailTemplatesCommand = {
        entries: [{ language: 'enGB', subject: 'Hi there', body: '<p>Hi</p>' }],
      }
      const result = await store.saveMailTemplates('welcome', cmd)

      expect(updateMailTemplatesMock).toHaveBeenCalledWith('welcome', cmd)
      expect(result).toEqual(updatedWelcome)
      expect(store.mailTemplates).toEqual([makeMailGroup({ kind: 'order' }), updatedWelcome])
    })

    it('saveMailTemplates leaves mailTemplates unchanged when the request fails', async () => {
      const original = [makeMailGroup({ kind: 'welcome' })]
      getMailTemplatesMock.mockResolvedValue({ kinds: original })
      const store = useAdminSettingsStore()
      await store.fetchMailTemplates()
      updateMailTemplatesMock.mockRejectedValueOnce(new Error('422'))

      await expect(
        store.saveMailTemplates('welcome', { entries: [] }),
      ).rejects.toThrow('422')

      expect(store.mailTemplates).toEqual(original)
    })
  })
})
