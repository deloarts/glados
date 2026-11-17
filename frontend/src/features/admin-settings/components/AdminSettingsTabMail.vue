<script setup lang="ts">
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useSettingsSave } from '../composables/useSettingsSave'
import { sendTestMail } from '../api/sendTestMail'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import MailTemplateEditorDialog from './MailTemplateEditorDialog.vue'
import MailTemplateImportDialog from './MailTemplateImportDialog.vue'
import { pickFiles } from '@/shared/composables/useTemplateFileTransfer'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { planMailTemplateImport, type MailTemplateImportRow } from '../utils/mailTemplateFile'
import type { AdminMailTemplate, MailTemplateFamily, MailTemplateKind } from '../types/adminSettingsTypes'
import type { Schemas } from '@/core/api/generated'
import { extractApiError } from '@/core/utils/errors'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const hostStore = useHostStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)
// Without write:settings the tab's controls stay visible but disabled,
// naming the missing permission.
const writeBlocked = useMissingPermission().missing(Permission.WRITE_SETTINGS)

interface Form {
  enabled: boolean
  host: string
  port: number
  user: string
  password: string
  from_address: string
  from_display_name: string
  reply_to: string
  use_tls: boolean
  use_ssl: boolean
  verify_certificate: boolean
  password_configured: boolean
  alert_recipients: string[]
  send_limit_per_hour: number
  send_lock_minutes: number
  attachment_limit_mb: number
}

const form = reactive<Form>({
  enabled: false,
  host: '',
  port: 587,
  user: '',
  password: '',
  from_address: '',
  from_display_name: '',
  reply_to: '',
  use_tls: true,
  use_ssl: false,
  verify_certificate: true,
  password_configured: false,
  alert_recipients: [],
  send_limit_per_hour: 20,
  send_lock_minutes: 60,
  attachment_limit_mb: 10,
})

watch(
  () => store.settings?.mail,
  (mail) => {
    if (!mail) return
    form.enabled = mail.enabled
    form.host = mail.host
    form.port = mail.port
    form.user = mail.user
    form.password = ''
    form.from_address = mail.from_address ?? ''
    form.from_display_name = mail.from_display_name
    form.reply_to = mail.reply_to ?? ''
    form.use_tls = mail.use_tls
    form.use_ssl = mail.use_ssl
    form.verify_certificate = mail.verify_certificate
    form.password_configured = mail.password_configured
    form.alert_recipients = [...mail.alert_recipients]
    form.send_limit_per_hour = mail.send_limit_per_hour
    form.send_lock_minutes = mail.send_lock_minutes
    form.attachment_limit_mb = mail.attachment_limit_mb
  },
  { immediate: true },
)

const { saving, onSave } = useSettingsSave(() =>
  store.saveMail({
    enabled: form.enabled,
    host: form.host.trim(),
    port: form.port,
    user: form.user.trim(),
    password: form.password.trim() || null,
    from_address: form.from_address.trim() || null,
    from_display_name: form.from_display_name.trim(),
    reply_to: form.reply_to.trim() || null,
    use_tls: form.use_tls,
    use_ssl: form.use_ssl,
    verify_certificate: form.verify_certificate,
    alert_recipients: form.alert_recipients,
    send_limit_per_hour: form.send_limit_per_hour,
    send_lock_minutes: form.send_lock_minutes,
    attachment_limit_mb: form.attachment_limit_mb,
  }),
)

// ── Alert recipients ────────────────────────────────────────────────────
// A Tag per entry with an add row. The client check is a light sanity check;
// the backend validates.
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const recipientInput = ref('')

function addRecipient() {
  const email = recipientInput.value.trim()
  if (!email) return

  if (!EMAIL_SHAPE.test(email)) {
    appToast.error(t('adminSettings.mail.invalidRecipient', { email }))
    return
  }

  if (!form.alert_recipients.includes(email)) {
    form.alert_recipients.push(email)
  }
  recipientInput.value = ''
}

function removeRecipient(email: string) {
  form.alert_recipients = form.alert_recipients.filter((e) => e !== email)
}

// ── Templates ────────────────────────────────────────────────────────────
// Display order: all fourteen kinds, since every one of them has a send
// (account_deactivated etc. via handle_event_notifications, order_canceled
// via the cancel-order "notify supplier" flow, schedule_error and
// disk_space_warning via mail.alert_recipients, meeting_notes as the text
// the meeting's send dialog starts from). Nothing here needs special-casing per kind:
// family/variables come from the fetched group, configured from its
// entries, so a new kind only ever means adding it to this list.
interface TemplateRow {
  kind: MailTemplateKind
  group: 'user' | 'supplier' | 'customer' | 'system'
}

const TEMPLATE_ROWS: TemplateRow[] = [
  { kind: 'welcome', group: 'user' },
  { kind: 'account_deactivated', group: 'user' },
  { kind: 'permissions_changed', group: 'user' },
  { kind: 'project_assigned', group: 'user' },
  { kind: 'product_assigned', group: 'user' },
  { kind: 'supplier_lines_to_settle', group: 'user' },
  { kind: 'request', group: 'supplier' },
  { kind: 'order', group: 'supplier' },
  { kind: 'order_canceled', group: 'supplier' },
  { kind: 'meeting_notes', group: 'customer' },
  { kind: 'notification_digest', group: 'system' },
  { kind: 'test_mail', group: 'system' },
  { kind: 'schedule_error', group: 'system' },
  { kind: 'disk_space_warning', group: 'system' },
]

const TEMPLATE_GROUPS = ['user', 'supplier', 'customer', 'system'] as const

function rowsFor(group: (typeof TEMPLATE_GROUPS)[number]): TemplateRow[] {
  return TEMPLATE_ROWS.filter((r) => r.group === group)
}

// Two-letter codes for the per-language status Tags (EN, DE, ...). The
// language codes themselves (enGB, deAT) are what LANG_LABELS elsewhere
// spells out in full; a compact Tag has no room for that.
function langCode(language: string): string {
  return language.slice(0, 2).toUpperCase()
}

// One group per kind (family/variables/default_subject + that kind's
// language rows), never a flat list, see MailTemplateKindGroup. A kind
// absent from the response entirely shouldn't happen (the backend's spec
// registry always has all twelve), but every reader here tolerates it
// rather than crashing: `groupFor` returns undefined, and every caller below
// treats that the same as a kind with no stored template: unconfigured status
// Tags, generic 'system'/no-chips defaults if it's ever actually opened.
function groupFor(kind: MailTemplateKind) {
  return store.mailTemplates.find((g) => g.kind === kind)
}

function entryFor(kind: MailTemplateKind, language: string): AdminMailTemplate | undefined {
  return groupFor(kind)?.entries.find((e) => e.language === language)
}

function isConfigured(kind: MailTemplateKind, language: string): boolean {
  return entryFor(kind, language)?.configured ?? false
}

/**
 * Materializes the kind x language grid client-side from hostStore.languages,
 * so a pair without a stored template, which is every pair on a fresh
 * install, renders unconfigured rather than being absent from the grid.
 */
function entriesFor(kind: MailTemplateKind): AdminMailTemplate[] {
  return hostStore.languages.map((language) => {
    const existing = entryFor(kind, language)
    if (existing) return existing
    return {
      id: 0,
      public_id: '',
      kind,
      // hostStore.languages only ever lists values from this closed wire
      // vocabulary; hostStore itself keeps the list as plain strings (out
      // of scope here), so the value is cast at this boundary rather than
      // threading a narrower type through it.
      language: language as Schemas['Language'],
      subject: '',
      body: '',
      configured: false,
    }
  })
}

// The dialog is always mounted (never behind a v-if) so its own
// `watch(visible, ...)` sees a real false -> true transition on every open,
// matching the rest of the codebase's dialog convention; see
// WebhookFormDialog.spec.ts's "mount closed first, then open" comment.
// editingKind therefore needs a valid placeholder before anything has been
// opened; TEMPLATE_ROWS[0] is arbitrary and never seen while editorVisible
// is false.
const editorVisible = ref(false)
const editingKind = ref<MailTemplateKind>(TEMPLATE_ROWS[0]!.kind)

const editingFamily = computed<MailTemplateFamily>(() => groupFor(editingKind.value)?.family ?? 'system')
const editingVariables = computed<string[]>(() => groupFor(editingKind.value)?.variables ?? [])
const editingEntries = computed<AdminMailTemplate[]>(() => entriesFor(editingKind.value))

function openEditor(kind: MailTemplateKind) {
  editingKind.value = kind
  editorVisible.value = true
}

onMounted(() => {
  void store.fetchMailTemplates()
})

// ── Template import ──
// The picked files are planned against the enabled languages and the
// configured templates, and the review dialog saves what the admin confirms.

const importRows = ref<MailTemplateImportRow[]>([])
const importVisible = ref(false)

const importBlocked = computed(() =>
  canWrite ? '' : t('common.permissionMissing', { permission: permissionLabel(t, Permission.WRITE_SETTINGS) }),
)

async function onImportTemplates(): Promise<void> {
  const files = await pickFiles('.html,.htm', true)
  if (files.length === 0) return
  try {
    const picked = await Promise.all(files.map(async (file) => ({ name: file.name, text: await file.text() })))
    importRows.value = planMailTemplateImport(
      picked,
      TEMPLATE_ROWS.map((row) => row.kind),
      hostStore.languages,
      (kind, language) => isConfigured(kind as MailTemplateKind, language),
    )
    importVisible.value = true
  } catch {
    appToast.error(t('templateFiles.importFailed'), t('templateFiles.errors.readFailed', { file: files.map((f) => f.name).join(', ') }))
  }
}

const testMailVisible = ref(false)
const testMailRecipient = ref('')
const sendingTest = ref(false)

function openTestMailDialog() {
  testMailRecipient.value = ''
  testMailVisible.value = true
}

async function onSendTestMail() {
  sendingTest.value = true
  try {
    await sendTestMail(testMailRecipient.value.trim())
    appToast.success(t('adminSettings.mail.testMailSent'))
    testMailVisible.value = false
  } catch (err: unknown) {
    appToast.error(t('adminSettings.mail.testMailError'), extractApiError(err) ?? undefined)
  } finally {
    sendingTest.value = false
  }
}
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            :loading="saving"
            :disabled="!canWrite"
            @click="onSave"
          />
          <Button
            :label="t('adminSettings.mail.sendTestMail')"
            icon="mdi mdi-email-fast-outline"
            severity="contrast"
            text
            :disabled="!canWrite || !form.enabled"
            @click="openTestMailDialog"
          />
          <span v-tooltip.bottom="importBlocked">
            <Button
              :label="t('templateFiles.mail.importTemplates')"
              icon="mdi mdi-file-import-outline"
              severity="contrast"
              text
              :disabled="!canWrite"
              data-testid="mail-import-templates"
              @click="onImportTemplates"
            />
          </span>
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.mail.providerSection') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enabled`">{{ t('adminSettings.mail.enabled') }}</label>
        <ToggleSwitch v-model="form.enabled" :input-id="`${uid}-enabled`" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label :for="`${uid}-host`">{{ t('adminSettings.mail.host') }}</label>
        <InputText v-model="form.host" :id="`${uid}-host`" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label :for="`${uid}-port`">{{ t('adminSettings.mail.port') }}</label>
        <InputNumber
          v-model="form.port"
          :input-id="`${uid}-port`"
          :disabled="!canWrite"
          :min="1"
          :max="65535"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-user`">{{ t('adminSettings.mail.user') }}</label>
        <InputText v-model="form.user" :id="`${uid}-user`" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label :for="`${uid}-password`">{{ t('adminSettings.mail.password') }}</label>
        <InputText
          v-model="form.password"
          :id="`${uid}-password`"
          type="password"
          :disabled="!canWrite"
          :placeholder="
            form.password_configured
              ? t('adminSettings.mail.passwordConfigured')
              : t('adminSettings.mail.passwordPlaceholder')
          "
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-from-address`">{{ t('adminSettings.mail.fromAddress') }}</label>
        <InputText v-model="form.from_address" :id="`${uid}-from-address`" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label :for="`${uid}-from-display-name`">
          {{ t('adminSettings.mail.fromDisplayName') }}
          <small class="hint">{{ t('adminSettings.mail.fromDisplayNameHint') }}</small>
        </label>
        <InputText
          v-model="form.from_display_name"
          :id="`${uid}-from-display-name`"
          maxlength="128"
          :disabled="!canWrite"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-reply-to`">
          {{ t('adminSettings.mail.replyTo') }}
          <small class="hint">{{ t('adminSettings.mail.replyToHint') }}</small>
        </label>
        <InputText v-model="form.reply_to" :id="`${uid}-reply-to`" :disabled="!canWrite" />
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-use-tls`">{{ t('adminSettings.mail.useTls') }}</label>
        <ToggleSwitch v-model="form.use_tls" :input-id="`${uid}-use-tls`" :disabled="!canWrite" />
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-use-ssl`">{{ t('adminSettings.mail.useSsl') }}</label>
        <ToggleSwitch v-model="form.use_ssl" :input-id="`${uid}-use-ssl`" :disabled="!canWrite" />
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-verify-certificate`">
          {{ t('adminSettings.mail.verifyCertificate') }}
          <span class="hint">{{ t('adminSettings.mail.verifyCertificateHint') }}</span>
        </label>
        <ToggleSwitch v-model="form.verify_certificate" :input-id="`${uid}-verify-certificate`" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label :for="`${uid}-alert-recipients`">{{ t('adminSettings.mail.alertRecipients') }}</label>
        <div class="recipient-list">
          <Tag
            v-for="email in form.alert_recipients"
            :key="email"
            :value="email"
            severity="secondary"
            class="recipient-tag"
          >
            <template #default>
              {{ email }}
              <span v-tooltip.top="writeBlocked || undefined">
                <Button
                  icon="mdi mdi-close"
                  text
                  rounded
                  size="small"
                  class="recipient-remove"
                  :disabled="!canWrite"
                  :aria-label="t('adminSettings.mail.removeRecipient', { email })"
                  @click="removeRecipient(email)"
                />
              </span>
            </template>
          </Tag>
          <div class="recipient-add-row" v-tooltip.top="writeBlocked || undefined">
            <InputText
              v-model="recipientInput"
              :id="`${uid}-alert-recipients`"
              type="email"
              :disabled="!canWrite"
              :placeholder="t('adminSettings.mail.alertRecipientsPlaceholder')"
              @keydown.enter.prevent="addRecipient"
            />
            <Button
              icon="mdi mdi-plus"
              severity="secondary"
              :disabled="!canWrite"
              :aria-label="t('adminSettings.mail.addRecipient')"
              @click="addRecipient"
            />
          </div>
        </div>
        <small class="hint">{{ t('adminSettings.mail.alertRecipientsHint') }}</small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.mail.sendingLimitsSection') }}</p>
      <div class="field-row">
        <label :for="`${uid}-send-limit-per-hour`">
          {{ t('adminSettings.mail.sendLimitPerHour') }}
          <small class="hint">{{ t('adminSettings.mail.sendLimitPerHourHint') }}</small>
        </label>
        <InputNumber
          v-model="form.send_limit_per_hour"
          :input-id="`${uid}-send-limit-per-hour`"
          :disabled="!canWrite"
          :min="1"
          :max="1000"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-send-lock-minutes`">
          {{ t('adminSettings.mail.sendLockMinutes') }}
          <small class="hint">{{ t('adminSettings.mail.sendLockMinutesHint') }}</small>
        </label>
        <InputNumber
          v-model="form.send_lock_minutes"
          :input-id="`${uid}-send-lock-minutes`"
          :disabled="!canWrite"
          :min="1"
          :max="1440"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-attachment-limit-mb`">
          {{ t('adminSettings.mail.attachmentLimitMb') }}
          <small class="hint">{{ t('adminSettings.mail.attachmentLimitMbHint') }}</small>
        </label>
        <InputNumber
          v-model="form.attachment_limit_mb"
          :input-id="`${uid}-attachment-limit-mb`"
          :disabled="!canWrite"
          :min="1"
          :max="100"
          :use-grouping="false"
          suffix=" MB"
          data-testid="mail-attachment-limit"
        />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.mail.templatesSection') }}</p>
      <small class="hint templates-hint">{{ t('adminSettings.mail.templatesSectionHint') }}</small>

      <template v-for="group in TEMPLATE_GROUPS" :key="group">
        <p class="template-group-label">{{ t(`adminSettings.mail.templates.groups.${group}`) }}</p>
        <div
          v-for="row in rowsFor(group)"
          :key="row.kind"
          class="field-row template-row"
        >
          <span class="field-caption">
            {{ t(`adminSettings.mail.templates.${row.kind}.label`) }}
            <small class="hint">{{ t(`adminSettings.mail.templates.${row.kind}.hint`) }}</small>
          </span>
          <div class="template-status">
            <Tag
              v-for="language in hostStore.languages"
              :key="language"
              :value="langCode(language)"
              :severity="isConfigured(row.kind, language) ? 'success' : 'secondary'"
              v-tooltip.focus="
                isConfigured(row.kind, language)
                  ? t('adminSettings.mail.templates.configured')
                  : t('adminSettings.mail.templates.notConfigured')
              "
            />
            <Button
              :label="t('adminSettings.mail.templates.edit')"
              icon="mdi mdi-pencil"
              text
              size="small"
              @click="openEditor(row.kind)"
            />
          </div>
        </div>
      </template>
    </div>
  </AdminSettingsTabShell>

  <MailTemplateEditorDialog
    v-model:visible="editorVisible"
    :kind="editingKind"
    :family="editingFamily"
    :variables="editingVariables"
    :entries="editingEntries"
  />

  <MailTemplateImportDialog v-model:visible="importVisible" :rows="importRows" />

  <Dialog
    v-model:visible="testMailVisible"
    :header="t('adminSettings.mail.testMailDialog.header')"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="dialog-field">
      <label :for="`${uid}-recipient`">{{ t('adminSettings.mail.testMailDialog.recipient') }}</label>
      <InputText
        v-model="testMailRecipient"
        :id="`${uid}-recipient`"
        type="email"
        :placeholder="t('adminSettings.mail.testMailDialog.recipientPlaceholder')"
        fluid
        autofocus
        @keydown.enter="onSendTestMail"
      />
    </div>
    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="contrast"
        text
        @click="testMailVisible = false"
      />
      <Button
        :label="t('adminSettings.mail.testMailDialog.send')"
        icon="mdi mdi-send"
        :loading="sendingTest"
        :disabled="!testMailRecipient.trim()"
        @click="onSendTestMail"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.dialog-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.templates-hint {
  margin-top: -0.5rem;
  display: block;
}

.template-group-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--p-text-muted-color);
  margin: var(--space-2) 0 0;

  &:first-of-type {
    margin-top: 0;
  }
}

.template-row {
  align-items: center;
}

.template-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.recipient-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.recipient-tag {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
}

.recipient-remove {
  width: 1.5rem;
  height: 1.5rem;
  opacity: 0.7;

  &:hover {
    opacity: 1;
  }
}

.recipient-add-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
</style>
