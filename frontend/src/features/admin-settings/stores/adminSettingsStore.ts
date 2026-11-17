import { defineStore } from 'pinia'
import { ref } from 'vue'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getAllAdminSettings } from '../api/getAllAdminSettings'
import { updateAuthSettings } from '../api/updateAuthSettings'
import { updateMailSettings } from '../api/updateMailSettings'
import { getMailTemplates } from '../api/getMailTemplates'
import { updateMailTemplates } from '../api/updateMailTemplates'
import { verifyLdapConnection } from '../api/verifyLdapConnection'
import { updateStorageSettings } from '../api/updateStorageSettings'
import { testStorage as testStorageApi } from '../api/testStorage'
import { updateSecuritySettings } from '../api/updateSecuritySettings'
import { updateFeatureSettings } from '../api/updateFeatureSettings'
import { updateGeneralSettings } from '../api/updateGeneralSettings'
import { uploadCompanyLogo } from '../api/uploadCompanyLogo'
import { deleteCompanyLogo } from '../api/deleteCompanyLogo'
import { updateBrandingSettings } from '../api/updateBrandingSettings'
import { uploadLoginBackgroundVideo } from '../api/uploadLoginBackgroundVideo'
import { deleteLoginBackgroundVideo } from '../api/deleteLoginBackgroundVideo'
import { uploadBrandingLogo } from '../api/uploadBrandingLogo'
import { deleteBrandingLogo } from '../api/deleteBrandingLogo'
import { uploadBrandingFavicon } from '../api/uploadBrandingFavicon'
import { deleteBrandingFavicon } from '../api/deleteBrandingFavicon'
import { updateNotificationSettings } from '../api/updateNotificationSettings'
import { updateMaintenanceSettings } from '../api/updateMaintenanceSettings'
import { updateBannerSettings } from '../api/updateBannerSettings'
import { updateRetentionSettings } from '../api/updateRetentionSettings'
import { updateOrderSettings } from '../api/updateOrderSettings'
import { updateMadeItemSettings } from '../api/updateMadeItemSettings'
import { updateProductionSettings } from '../api/updateProductionSettings'
import { updatePdmSettings } from '../api/updatePdmSettings'
import { verifyPdmConnection as verifyPdmConnectionApi } from '../api/verifyPdmConnection'
import { getPdmOperations as getPdmOperationsApi } from '../api/getPdmOperations'
import { invokePdmOperation as invokePdmOperationApi } from '../api/invokePdmOperation'
import { getPdmWorkflows as getPdmWorkflowsApi } from '../api/getPdmWorkflows'
import { getPdmFolders as getPdmFoldersApi } from '../api/getPdmFolders'
import { requestPdmPoll as requestPdmPollApi } from '../api/requestPdmPoll'
import { listBackups as listBackupsApi } from '../api/listBackups'
import { runBackupNow as runBackupNowApi } from '../api/runBackupNow'
import { restoreFiles as restoreFilesApi } from '../api/restoreFiles'
import { downloadBackup as downloadBackupApi } from '../api/downloadBackup'
import { getDataImportSettings } from '../api/getDataImportSettings'
import { updateDataImportSettings } from '../api/updateDataImportSettings'
import {
  getEdpSettings,
  testEdpConnection,
  updateEdpSettings,
} from '../api/eplanDataPortalSettingsApi'
import {
  confirmTimeTrackingKey as confirmTimeTrackingKeyApi,
  getTimeTrackingSettings,
  purgeTimeTrackingCredentials as purgeTimeTrackingCredentialsApi,
  testTimeTrackingService as testTimeTrackingServiceApi,
  updateTimeTrackingSettings,
} from '../api/timeTrackingSettingsApi'
import {
  getStockSettings,
  testStockService as testStockServiceApi,
  updateStockSettings,
} from '../api/stockSettingsApi'

import type {
  AllAdminSettings,
  UpdateAuthSettingsCommand,
  UpdateMailSettingsCommand,
  MailTemplateKindGroup,
  MailTemplateKind,
  UpdateMailTemplatesCommand,
  VerifyLdapConnectionCommand,
  UpdateStorageSettingsCommand,
  UpdateSecuritySettingsCommand,
  UpdateFeatureSettingsCommand,
  UpdateGeneralSettingsCommand,
  UpdateBrandingSettingsCommand,
  UpdateNotificationSettingsCommand,
  UpdateMaintenanceSettingsCommand,
  UpdateBannerSettingsCommand,
  UpdateRetentionSettingsCommand,
  UpdateOrderSettingsCommand,
  UpdateMadeItemSettingsCommand,
  UpdateProductionSettingsCommand,
  UpdatePdmSettingsCommand,
  VerifyPdmConnectionCommand,
  PdmConnectionTestResult,
  PdmOperation,
  InvokePdmOperationCommand,
  PdmInvokeResult,
  PdmWorkflow,
  PdmFolder,
  PdmPollResult,
  BackupList,
  RestoreFilesResult,
  AdminTimeTrackingSettings,
  UpdateTimeTrackingSettingsCommand,
  ConfirmTimeTrackingKeyCommand,
  AdminDataImportSettings,
  UpdateDataImportSettingsCommand,
  AdminEdpSettings,
  EdpConnectionTestResult,
  UpdateEdpSettingsCommand,
  VerifyEdpConnectionCommand,
  VerifyTimeTrackingServiceCommand,
  TimeTrackingServiceTestResult,
  PurgeTimeTrackingCredentialsResult,
  AdminStockSettings,
  UpdateStockSettingsCommand,
  VerifyStockServiceCommand,
  StockServiceTestResult,
} from '../types/adminSettingsTypes'

export const useAdminSettingsStore = defineStore('adminSettings', () => {
  // Several unrelated dialogs (the Admin Settings page itself, AutoPlanDialog,
  // MachineCalendarDialog, ...) each call fetch() independently, sometimes
  // around the same time, so calls are sequenced: a slower call started
  // earlier can't resolve after a faster later one and overwrite `settings`
  // with stale data.
  const { loading, run: runFetch } = useSequencedFetch(getAllAdminSettings)
  const { run: runFetchMailTemplates } = useSequencedFetch(getMailTemplates)
  const settings = ref<AllAdminSettings | null>(null)
  // Separate from `settings`: bodies are multi-KB and every settings tab
  // triggers fetch(), so this is loaded only by the Mail tab itself and
  // fetch()/the aggregate response never touch it. One group per kind (see
  // MailTemplateKindGroup), never a flat list of language rows: family,
  // variables, and default_subject live once per kind, not duplicated per
  // row.
  const mailTemplates = ref<MailTemplateKindGroup[]>([])
  // Cached for the store's lifetime: the catalogue only changes on a
  // backend deploy, so the API console's group filter/search work against
  // one fetch even if the panel is closed and reopened repeatedly.
  const pdmOperations = ref<PdmOperation[]>([])
  // Cached the same way: the vault's workflow/state list rarely changes,
  // so the released-states/obsolete-states MultiSelects share one fetch
  // across mounts of PdmSyncSection. Stays empty (and so retryable) on a
  // failed load.
  const pdmWorkflows = ref<PdmWorkflow[]>([])
  // Not part of the aggregate: loaded by the time tracking tab itself,
  // since it carries the list of credential holders and no other tab needs it.
  const { loading: timeTrackingLoading, run: runFetchTimeTracking } =
    useSequencedFetch(getTimeTrackingSettings)
  const timeTracking = ref<AdminTimeTrackingSettings | null>(null)
  // Not part of the aggregate either: only the Data import tab reads it.
  const { loading: dataImportLoading, run: runFetchDataImport } =
    useSequencedFetch(getDataImportSettings)
  const dataImport = ref<AdminDataImportSettings | null>(null)
  // Loaded by the EPLAN Data Portal tab itself.
  const { loading: edpLoading, run: runFetchEdp } = useSequencedFetch(getEdpSettings)
  const edp = ref<AdminEdpSettings | null>(null)
  // Not part of the aggregate either: only the stock service tab reads it.
  const { loading: stockLoading, run: runFetchStock } = useSequencedFetch(getStockSettings)
  const stock = ref<AdminStockSettings | null>(null)

  async function fetch() {
    const result = await runFetch()
    if (result) settings.value = result
  }

  async function saveMail(cmd: UpdateMailSettingsCommand) {
    const result = await updateMailSettings(cmd)
    if (settings.value) settings.value.mail = result
    return result
  }

  // A failed fetch resolves to `undefined` rather than throwing (see
  // useSequencedFetch). AdminSettingsTabMail.vue's onMounted calls this
  // without awaiting or catching, so a rejection here would otherwise
  // surface as an unhandled promise rejection.
  async function fetchMailTemplates(): Promise<MailTemplateKindGroup[] | undefined> {
    const result = await runFetchMailTemplates()
    if (!result) return undefined

    mailTemplates.value = result.kinds
    return result.kinds
  }

  /**
   * Kind-scoped save: the PUT response is a single MailTemplateKindGroup
   * for `kind` (not a list), so the cache replaces just that one group
   * rather than the whole array.
   */
  async function saveMailTemplates(kind: MailTemplateKind, cmd: UpdateMailTemplatesCommand) {
    const result = await updateMailTemplates(kind, cmd)
    mailTemplates.value = [...mailTemplates.value.filter((g) => g.kind !== kind), result]
    return result
  }

  async function saveAuth(cmd: UpdateAuthSettingsCommand) {
    const result = await updateAuthSettings(cmd)
    if (settings.value) settings.value.auth = result
    return result
  }

  async function verifyLdap(cmd: VerifyLdapConnectionCommand): Promise<void> {
    await verifyLdapConnection(cmd)
  }

  async function saveStorage(cmd: UpdateStorageSettingsCommand) {
    const result = await updateStorageSettings(cmd)
    if (settings.value) settings.value.storage = result
    return result
  }

  async function testStorage(cmd: UpdateStorageSettingsCommand): Promise<void> {
    await testStorageApi(cmd)
  }

  async function saveSecurity(cmd: UpdateSecuritySettingsCommand) {
    const result = await updateSecuritySettings(cmd)
    if (settings.value) settings.value.security = result
    return result
  }

  async function saveFeatures(cmd: UpdateFeatureSettingsCommand) {
    const result = await updateFeatureSettings(cmd)
    if (settings.value) settings.value.features = result
    return result
  }

  async function uploadCompanyLogoFile(file: File) {
    const result = await uploadCompanyLogo(file)
    if (settings.value) settings.value.general = result
    return result
  }

  async function removeCompanyLogo() {
    const result = await deleteCompanyLogo()
    if (settings.value) settings.value.general = result
    return result
  }

  async function saveGeneral(cmd: UpdateGeneralSettingsCommand) {
    const result = await updateGeneralSettings(cmd)
    if (settings.value) settings.value.general = result
    return result
  }

  async function saveBranding(cmd: UpdateBrandingSettingsCommand) {
    const result = await updateBrandingSettings(cmd)
    if (settings.value) settings.value.branding = result
    return result
  }

  async function uploadLoginVideo(file: File) {
    const result = await uploadLoginBackgroundVideo(file)
    if (settings.value) settings.value.branding = result
    return result
  }

  async function deleteLoginVideo() {
    const result = await deleteLoginBackgroundVideo()
    if (settings.value) settings.value.branding = result
    return result
  }

  async function uploadLogo(file: File) {
    const result = await uploadBrandingLogo(file)
    if (settings.value) settings.value.branding = result
    return result
  }

  async function deleteLogo() {
    const result = await deleteBrandingLogo()
    if (settings.value) settings.value.branding = result
    return result
  }

  async function uploadFavicon(file: File) {
    const result = await uploadBrandingFavicon(file)
    if (settings.value) settings.value.branding = result
    return result
  }

  async function deleteFavicon() {
    const result = await deleteBrandingFavicon()
    if (settings.value) settings.value.branding = result
    return result
  }

  async function saveNotifications(cmd: UpdateNotificationSettingsCommand) {
    const result = await updateNotificationSettings(cmd)
    if (settings.value) settings.value.notifications = result
    return result
  }

  async function saveMaintenance(cmd: UpdateMaintenanceSettingsCommand) {
    const result = await updateMaintenanceSettings(cmd)
    if (settings.value) settings.value.maintenance = result
    return result
  }

  async function saveBanner(cmd: UpdateBannerSettingsCommand) {
    const result = await updateBannerSettings(cmd)
    if (settings.value) settings.value.banner = result
    return result
  }

  async function saveRetention(cmd: UpdateRetentionSettingsCommand) {
    const result = await updateRetentionSettings(cmd)
    if (settings.value) settings.value.retention = result
    return result
  }

  async function saveOrders(cmd: UpdateOrderSettingsCommand) {
    const result = await updateOrderSettings(cmd)
    if (settings.value) settings.value.orders = result
    return result
  }

  async function saveMadeItems(cmd: UpdateMadeItemSettingsCommand) {
    const result = await updateMadeItemSettings(cmd)
    if (settings.value) settings.value.made_items = result
    return result
  }

  async function saveProduction(cmd: UpdateProductionSettingsCommand) {
    const result = await updateProductionSettings(cmd)
    if (settings.value) settings.value.production = result
    return result
  }

  async function savePdm(cmd: UpdatePdmSettingsCommand) {
    const result = await updatePdmSettings(cmd)
    if (settings.value) settings.value.pdm = result
    return result
  }

  /**
   * Probes the given (not-yet-saved) connection. Nothing is cached here;
   * the caller (PdmConnectionSection's test button) reads the result
   * directly for its toast.
   */
  async function verifyPdm(cmd: VerifyPdmConnectionCommand): Promise<PdmConnectionTestResult> {
    return verifyPdmConnectionApi(cmd)
  }

  async function loadPdmOperations(): Promise<PdmOperation[]> {
    if (pdmOperations.value.length === 0) {
      pdmOperations.value = await getPdmOperationsApi()
    }
    return pdmOperations.value
  }

  async function invokePdmOperation(
    operationId: string,
    cmd: InvokePdmOperationCommand,
  ): Promise<PdmInvokeResult> {
    return invokePdmOperationApi(operationId, cmd)
  }

  async function loadPdmWorkflows(): Promise<PdmWorkflow[]> {
    if (pdmWorkflows.value.length === 0) {
      pdmWorkflows.value = await getPdmWorkflowsApi()
    }
    return pdmWorkflows.value
  }

  /**
   * Not cached, unlike loadPdmWorkflows/loadPdmOperations: every folder
   * has its own subfolder list, so each drill-down step in
   * PdmFolderPickerDialog is its own fetch.
   */
  async function loadPdmFolders(parentId: number): Promise<PdmFolder[]> {
    return getPdmFoldersApi(parentId)
  }

  async function requestPdmPoll(): Promise<PdmPollResult> {
    return requestPdmPollApi()
  }

  async function fetchTimeTracking(): Promise<AdminTimeTrackingSettings | undefined> {
    const result = await runFetchTimeTracking()
    if (result) timeTracking.value = result
    return result
  }

  async function saveTimeTracking(
    cmd: UpdateTimeTrackingSettingsCommand,
  ): Promise<AdminTimeTrackingSettings> {
    const result = await updateTimeTrackingSettings(cmd)
    timeTracking.value = result
    return result
  }

  /** Tests the given, possibly unsaved, service; nothing is cached. */
  async function testTimeTrackingService(
    cmd: VerifyTimeTrackingServiceCommand,
  ): Promise<TimeTrackingServiceTestResult> {
    return testTimeTrackingServiceApi(cmd)
  }

  async function confirmTimeTrackingKey(
    cmd: ConfirmTimeTrackingKeyCommand,
  ): Promise<AdminTimeTrackingSettings> {
    const result = await confirmTimeTrackingKeyApi(cmd)
    timeTracking.value = result
    return result
  }

  async function purgeTimeTrackingCredentials(): Promise<PurgeTimeTrackingCredentialsResult> {
    const result = await purgeTimeTrackingCredentialsApi()
    if (timeTracking.value) timeTracking.value = { ...timeTracking.value, credential_holders: [] }
    return result
  }

  async function fetchDataImport(): Promise<AdminDataImportSettings | undefined> {
    const result = await runFetchDataImport()
    if (result) dataImport.value = result
    return result
  }

  async function saveDataImport(
    cmd: UpdateDataImportSettingsCommand,
  ): Promise<AdminDataImportSettings> {
    const result = await updateDataImportSettings(cmd)
    dataImport.value = result
    return result
  }

  async function fetchEdp(): Promise<AdminEdpSettings | undefined> {
    const result = await runFetchEdp()
    if (result) edp.value = result
    return result
  }

  async function saveEdp(cmd: UpdateEdpSettingsCommand): Promise<AdminEdpSettings> {
    const result = await updateEdpSettings(cmd)
    edp.value = result
    return result
  }

  /** Probes the given, possibly unsaved, connection; nothing is cached. */
  async function testEdp(cmd: VerifyEdpConnectionCommand): Promise<EdpConnectionTestResult> {
    return testEdpConnection(cmd)
  }

  async function fetchStock(): Promise<AdminStockSettings | undefined> {
    const result = await runFetchStock()
    if (result) stock.value = result
    return result
  }

  async function saveStock(cmd: UpdateStockSettingsCommand): Promise<AdminStockSettings> {
    const result = await updateStockSettings(cmd)
    stock.value = result
    return result
  }

  /** Tests the given, possibly unsaved, service; nothing is cached. */
  async function testStockService(cmd: VerifyStockServiceCommand): Promise<StockServiceTestResult> {
    return testStockServiceApi(cmd)
  }

  async function fetchBackups(): Promise<BackupList> {
    return listBackupsApi()
  }

  async function triggerBackupNow(): Promise<void> {
    await runBackupNowApi()
  }

  async function restoreFileSnapshot(snapshotKey: string): Promise<RestoreFilesResult> {
    return restoreFilesApi(snapshotKey)
  }

  async function downloadBackup(key: string): Promise<void> {
    await downloadBackupApi(key)
  }

  return {
    loading,
    settings,
    mailTemplates,
    pdmOperations,
    pdmWorkflows,
    timeTracking,
    timeTrackingLoading,
    dataImport,
    dataImportLoading,
    edp,
    edpLoading,
    stock,
    stockLoading,
    fetch,
    saveMail,
    fetchMailTemplates,
    saveMailTemplates,
    saveAuth,
    verifyLdap,
    saveStorage,
    testStorage,
    saveSecurity,
    saveFeatures,
    saveGeneral,
    uploadCompanyLogoFile,
    removeCompanyLogo,
    saveBranding,
    uploadLoginVideo,
    deleteLoginVideo,
    uploadLogo,
    deleteLogo,
    uploadFavicon,
    deleteFavicon,
    saveNotifications,
    saveMaintenance,
    saveBanner,
    saveRetention,
    saveOrders,
    saveMadeItems,
    saveProduction,
    savePdm,
    verifyPdm,
    loadPdmOperations,
    invokePdmOperation,
    loadPdmWorkflows,
    loadPdmFolders,
    requestPdmPoll,
    fetchTimeTracking,
    fetchDataImport,
    saveDataImport,
    fetchEdp,
    saveEdp,
    testEdp,
    fetchStock,
    saveStock,
    testStockService,
    saveTimeTracking,
    testTimeTrackingService,
    confirmTimeTrackingKey,
    purgeTimeTrackingCredentials,
    fetchBackups,
    triggerBackupNow,
    restoreFileSnapshot,
    downloadBackup,
  }
})
