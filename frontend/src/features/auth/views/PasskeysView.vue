<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { storeToRefs } from 'pinia'

import { useAppToast } from '@/core/composables/useAppToast'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { extractApiErrorCode } from '@/core/utils/errors'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { HelpButton } from '@/shared/help'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'

import {
  deleteAllMyPasskeys,
  deleteMyPasskey,
  fetchMyPasskeys,
  renameMyPasskey,
  type PasskeySummary,
} from '../api/passkeys'
import { setUpPasskeyOnThisDevice } from '../utils/passkeySetup'
import { findRememberedUser, forgetPasskey, forgetPasskeysOf } from '../utils/rememberedUsers'
import {
  passkeyPromptDismissed,
  passkeysSupported,
  platformAuthenticatorKind,
} from '../utils/webauthn'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const userStore = useCurrentUserStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const passkeys = ref<PasskeySummary[]>([])
const loading = ref(false)

// The system user's 2FA is mandatory and a passkey would skip it, and the
// browser refuses WebAuthn outside https and localhost.
const addDisabledReason = computed(() => {
  if (userStore.user?.is_systemuser) return t('account.passkeys.systemUser')
  if (!passkeysSupported()) return t('account.passkeys.unsupported')
  return null
})

// Which row this device registered, as remembered for the next login.
const thisDevicePasskey = computed(() => {
  const username = userStore.user?.username
  return username ? (findRememberedUser(username)?.passkeyPublicId ?? null) : null
})

async function refresh(): Promise<void> {
  loading.value = true
  try {
    passkeys.value = await fetchMyPasskeys()
  } catch {
    appToast.error(t('account.passkeys.errors.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

// ── Add ──────────────────────────────────────────────────────────────────────

const addVisible = ref(false)
const addPassword = ref('')
const addName = ref('')
const adding = ref(false)
const addError = ref<string | null>(null)

function onOpenAdd(): void {
  addPassword.value = ''
  addName.value = t(`login.passkey.deviceName.${platformAuthenticatorKind()}`)
  addError.value = null
  addVisible.value = true
}

async function onAdd(): Promise<void> {
  const user = userStore.user
  if (!user || addPassword.value === '') return

  adding.value = true
  addError.value = null
  try {
    const created = await setUpPasskeyOnThisDevice(addPassword.value, addName.value, user)
    addVisible.value = false
    appToast.success(created.name, t('account.passkeys.added'))
    await refresh()
  } catch (e) {
    if (passkeyPromptDismissed(e)) {
      addError.value = t('account.passkeys.errors.dismissed')
    } else {
      // Match on `code`, never on the translatable `detail` prose.
      switch (extractApiErrorCode(e)) {
        case 'PasswordConfirmationFailedError':
          addError.value = t('account.passkeys.errors.wrongPassword')
          break
        case 'LoginLockedError':
          addError.value = t('login.errors.lockedOut')
          break
        default:
          addError.value = t('account.passkeys.errors.unknown')
      }
    }
  } finally {
    adding.value = false
  }
}

// ── Rename ───────────────────────────────────────────────────────────────────

const renameTarget = ref<PasskeySummary | null>(null)
const renameName = ref('')
const renaming = ref(false)
const renameError = ref<string | null>(null)
const renameVisible = computed({
  get: () => renameTarget.value !== null,
  set: (visible: boolean) => {
    if (!visible) renameTarget.value = null
  },
})
const canRename = computed(
  () =>
    renameName.value.trim() !== '' && renameName.value.trim() !== renameTarget.value?.name,
)

function onOpenRename(passkey: PasskeySummary): void {
  renameName.value = passkey.name
  renameError.value = null
  renameTarget.value = passkey
}

async function onRename(): Promise<void> {
  const target = renameTarget.value
  if (!target || !canRename.value) return

  renaming.value = true
  renameError.value = null
  try {
    const renamed = await renameMyPasskey(target.public_id, renameName.value.trim())
    renameTarget.value = null
    appToast.success(renamed.name, t('account.passkeys.renamed'))
    await refresh()
  } catch {
    renameError.value = t('account.passkeys.errors.unknown')
  } finally {
    renaming.value = false
  }
}

// ── Remove ───────────────────────────────────────────────────────────────────

function onRemove(passkey: PasskeySummary): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteMyPasskey(passkey.public_id)
      forgetPasskey(passkey.public_id)
      appToast.success(passkey.name, t('account.passkeys.removed'))
      await refresh()
    } catch {
      appToast.error(passkey.name, t('account.passkeys.errors.unknown'))
    }
  }

  confirm.require({
    header: t('account.passkeys.removeButton'),
    message: t('account.passkeys.removeConfirm', { name: passkey.name }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('account.passkeys.removeButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

function onRemoveAll(): void {
  async function onAccept(): Promise<void> {
    try {
      const removed = await deleteAllMyPasskeys()
      if (userStore.user) forgetPasskeysOf(userStore.user.username)
      appToast.success(
        t('account.passkeys.title'),
        t('account.passkeys.allRemoved', { count: removed }),
      )
      await refresh()
    } catch {
      appToast.error(t('account.passkeys.title'), t('account.passkeys.errors.unknown'))
    }
  }

  confirm.require({
    header: t('account.passkeys.removeAllButton'),
    message: t('account.passkeys.removeAllConfirm'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('account.passkeys.removeAllButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>

  <PageLayout>
    <template #controls>
      <ControlsBar>
        <template #start>
          <span v-tooltip.bottom="addDisabledReason">
            <Button
              :label="t('account.passkeys.addButton')"
              icon="mdi mdi-plus"
              severity="contrast"
              text
              :disabled="addDisabledReason !== null"
              data-testid="passkeys-add"
              @click="onOpenAdd"
            />
          </span>
          <Button
            :label="t('account.passkeys.removeAllButton')"
            icon="mdi mdi-delete-outline"
            severity="danger"
            text
            :disabled="loading || passkeys.length === 0"
            data-testid="passkeys-remove-all"
            @click="onRemoveAll"
          />
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <template #views>
      <ViewsBar
        id-prefix="passkeys"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="false"
        @sync="refresh()"
      />
    </template>

    <Message v-if="addDisabledReason" severity="info" :closable="false">
      {{ addDisabledReason }}
    </Message>

    <DataTable
      :value="passkeys"
      data-key="public_id"
      :loading="loading"
      size="small"
      scrollable
      scroll-height="flex"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      class="passkeys-table"
    >
      <template #empty>
        <EmptyState :message="t('account.passkeys.empty')" />
      </template>
      <Column header="#" class="column-fit" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('account.passkeys.columns.actions')" class="column-fit">
        <template #body="{ data }: { data: PasskeySummary }">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="t('account.passkeys.renameButton')"
            :aria-label="t('account.passkeys.renameButton')"
            data-testid="passkeys-rename"
            @click="onOpenRename(data)"
          />
          <Button
            icon="mdi mdi-delete-outline"
            size="small"
            severity="danger"
            text
            v-tooltip.top.focus="t('account.passkeys.removeButton')"
            :aria-label="t('account.passkeys.removeButton')"
            @click="onRemove(data)"
          />
        </template>
      </Column>
      <Column :header="t('account.passkeys.columns.name')">
        <template #body="{ data }: { data: PasskeySummary }">
          <span class="name-cell">
            <span class="name">{{ data.name }}</span>
            <Tag
              v-if="data.public_id === thisDevicePasskey"
              :value="t('account.passkeys.thisDevice')"
              severity="success"
            />
            <Tag
              v-if="data.backed_up"
              :value="t('account.passkeys.synced')"
              severity="secondary"
            />
          </span>
        </template>
      </Column>
      <Column :header="t('account.passkeys.columns.added')" class="column-fit">
        <template #body="{ data }: { data: PasskeySummary }">
          {{ formatISODateTime(data.created_at) }}
        </template>
      </Column>
      <Column :header="t('account.passkeys.columns.lastUsed')" class="column-fit">
        <template #body="{ data }: { data: PasskeySummary }">
          <template v-if="data.last_used_at">{{ formatISODateTime(data.last_used_at) }}</template>
          <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
    </DataTable>
  </PageLayout>

  <Dialog
    v-model:visible="addVisible"
    modal
    :header="t('account.passkeys.addDialog.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <form id="passkey-add-form" class="add-form" @submit.prevent="onAdd">
      <div class="field">
        <label for="passkey-name">{{ t('account.passkeys.addDialog.name') }}</label>
        <InputText id="passkey-name" v-model="addName" maxlength="100" fluid />
      </div>
      <div class="field">
        <label for="passkey-password">{{ t('account.passkeys.addDialog.password') }}</label>
        <Password
          id="passkey-password"
          v-model="addPassword"
          :feedback="false"
          toggle-mask
          autocomplete="current-password"
          fluid
        />
        <small class="hint">{{ t('account.passkeys.addDialog.description') }}</small>
      </div>
    </form>

    <template #footer>
      <Message v-if="addError" severity="error" :closable="false" class="footer-error">
        {{ addError }}
      </Message>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="adding"
        @click="addVisible = false"
      />
      <Button
        type="submit"
        form="passkey-add-form"
        :label="t('account.passkeys.addDialog.submit')"
        icon="mdi mdi-plus"
        :loading="adding"
        :disabled="addPassword === ''"
        data-testid="passkeys-add-submit"
      />
    </template>
  </Dialog>

  <Dialog
    v-model:visible="renameVisible"
    modal
    :header="t('account.passkeys.renameDialog.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <form id="passkey-rename-form" class="add-form" @submit.prevent="onRename">
      <div class="field">
        <label for="passkey-rename-name">{{ t('account.passkeys.addDialog.name') }}</label>
        <InputText
          id="passkey-rename-name"
          v-model="renameName"
          maxlength="100"
          autofocus
          fluid
        />
      </div>
    </form>

    <template #footer>
      <Message v-if="renameError" severity="error" :closable="false" class="footer-error">
        {{ renameError }}
      </Message>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="renaming"
        @click="renameVisible = false"
      />
      <Button
        type="submit"
        form="passkey-rename-form"
        :label="t('common.save')"
        icon="mdi mdi-content-save-outline"
        :loading="renaming"
        :disabled="!canRename"
        data-testid="passkeys-rename-submit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.passkeys-table {
  flex: 1;
  min-height: 0;
}

.name-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.name {
  font-weight: 500;
}

.muted {
  color: var(--p-text-muted-color);
}

.add-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.footer-error {
  margin-right: auto;
}
</style>
