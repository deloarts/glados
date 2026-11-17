<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { isImportable, type MailTemplateImportRow } from '../utils/mailTemplateFile'
import type { MailTemplateKind } from '../types/adminSettingsTypes'
import type { Schemas } from '@/core/api/generated'

/**
 * Shows what importing the picked mail template files would do, one row per
 * file, and saves the importable ones when the admin confirms. Each kind is
 * saved with the editor's own call, so an import is audited like an edit.
 */
const props = defineProps<{ rows: MailTemplateImportRow[] }>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const appToast = useAppToast()
const store = useAdminSettingsStore()

const importable = computed(() => props.rows.filter(isImportable))

const STATUS_SEVERITY: Record<MailTemplateImportRow['status'], string> = {
  new: 'success',
  replaces: 'warn',
  badName: 'danger',
  unknownKind: 'danger',
  unknownLanguage: 'danger',
  duplicate: 'secondary',
}

function kindLabel(kind: string | null): string {
  return kind ? t(`adminSettings.mail.templates.${kind}.label`) : ''
}

const saving = ref(false)

async function onImport(): Promise<void> {
  const byKind = new Map<string, MailTemplateImportRow[]>()
  for (const row of importable.value) {
    byKind.set(row.kind!, [...(byKind.get(row.kind!) ?? []), row])
  }
  saving.value = true
  let saved = 0
  try {
    for (const [kind, rows] of byKind) {
      try {
        await store.saveMailTemplates(kind as MailTemplateKind, {
          entries: rows.map((row) => ({
            language: row.language as Schemas['Language'],
            subject: row.subject,
            body: row.body,
          })),
        })
        saved += rows.length
      } catch {
        appToast.error(t('templateFiles.importFailed'), t('templateFiles.mail.saveFailed', { kind: kindLabel(kind) }))
        return
      }
    }
  } finally {
    // A kind's save answers with the saved languages only, so the full list
    // is fetched again, also after a partial import.
    await store.fetchMailTemplates()
    saving.value = false
  }
  appToast.success(t('templateFiles.mail.importedCount', saved))
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('templateFiles.mail.dialogTitle')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <div class="import-content">
      <p class="hint">{{ t('templateFiles.mail.intro') }}</p>
      <DataTable :value="rows" size="small" data-testid="mail-import-rows">
        <Column :header="t('templateFiles.mail.columns.file')" field="fileName" />
        <Column :header="t('templateFiles.mail.columns.template')">
          <template #body="{ data }: { data: MailTemplateImportRow }">{{ kindLabel(data.kind) }}</template>
        </Column>
        <Column :header="t('templateFiles.mail.columns.language')" field="language" />
        <Column :header="t('templateFiles.mail.columns.status')">
          <template #body="{ data }: { data: MailTemplateImportRow }">
            <Tag
              :value="t(`templateFiles.mail.status.${data.status}`)"
              :severity="STATUS_SEVERITY[data.status]"
            />
          </template>
        </Column>
      </DataTable>
      <Message v-if="importable.length === 0" severity="warn">
        {{ t('templateFiles.mail.nothingToImport') }}
      </Message>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" outlined :disabled="saving" @click="visible = false" />
      <Button
        :label="t('templateFiles.mail.importAction', importable.length)"
        icon="mdi mdi-file-import-outline"
        :loading="saving"
        :disabled="importable.length === 0"
        data-testid="mail-import-confirm"
        @click="onImport"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.import-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.hint {
  margin: 0;
}
</style>
