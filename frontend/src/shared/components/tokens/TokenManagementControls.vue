<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'

import TokenFormDialog from './TokenFormDialog.vue'
import type { TokenStoreInstance } from '@/shared/stores/createTokenStore'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()

// `canCreate` needs an explicit `undefined` default. Vue casts an absent
// optional boolean prop to `false`, which would make the `canCreate ?? canManage`
// fallback below resolve to `false` instead of falling through, disabling the
// create button on every surface that omits the prop.
const props = withDefaults(
  defineProps<{
    store: TokenStoreInstance
    canManage: boolean
    i18nPrefix: string
    // Falls back to canManage when unset: only the system-user PAT view (which
    // can revoke but never create) needs to pull these apart.
    canCreate?: boolean
    // Personal access tokens only: a second button that opens the same
    // create dialog pre-filled for the SolidWorks add-in. Unset (the API-key
    // tab's default) keeps that dialog concept out of a surface it does not
    // apply to.
    showCreateAddin?: boolean
    // Personal access tokens only: the equivalent shortcut for the PDM vault
    // add-in, which each vault user signs in to with their own token.
    // Callers hide both add-in buttons when PDM is switched off.
    showCreatePdmAddin?: boolean
    // The tooltip of the disabled create buttons that names the missing
    // permission, and '' while creating is allowed or blocked for a reason
    // the page explains itself.
    createBlocked?: string
    // The same for Revoke All, while the manage permission is missing.
    manageBlocked?: string
  }>(),
  { canCreate: undefined, createBlocked: '', manageBlocked: '' },
)

const showCreateForm = ref(false)
// Which preset the dialog opens with, rather than one flag per shortcut.
const createVariant = ref<'plain' | 'addin' | 'pdmAddin'>('plain')

function tt(key: string, params?: Record<string, unknown>): string {
  return t(`${props.i18nPrefix}.${key}`, params ?? {})
}

function openCreate(variant: 'plain' | 'addin' | 'pdmAddin'): void {
  createVariant.value = variant
  showCreateForm.value = true
}

function onRevokeAll(): void {
  async function onAccept(): Promise<void> {
    try {
      const count = await props.store.revokeAll()
      appToast.success(tt('revokedAll', { count }))
    } catch {
      appToast.error(tt('errors.unknown'))
    }
  }

  confirm.require({
    message: tt('revokeAllConfirm'),
    header: tt('revokeAllButton'),
    icon: 'mdi mdi-cancel',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: tt('revokeAllButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>
  <ControlsBar>
    <template #start>
      <!-- Each span carries the tooltip, since a disabled button shows
           none of its own. -->
      <span v-tooltip.bottom="createBlocked || undefined">
        <Button
          :label="tt('createButton')"
          icon="mdi mdi-plus"
          severity="contrast"
          text
          :disabled="!(canCreate ?? canManage)"
          data-testid="token-create"
          @click="openCreate('plain')"
        />
      </span>
      <span v-if="showCreateAddin" v-tooltip.bottom="createBlocked || undefined">
        <Button
          :label="tt('createAddinButton')"
          icon="mdi mdi-puzzle-outline"
          severity="contrast"
          text
          :disabled="!(canCreate ?? canManage)"
          data-testid="token-create-addin"
          @click="openCreate('addin')"
        />
      </span>
      <span v-if="showCreatePdmAddin" v-tooltip.bottom="createBlocked || undefined">
        <Button
          :label="tt('createPdmAddinButton')"
          icon="mdi mdi-database-sync-outline"
          severity="contrast"
          text
          :disabled="!(canCreate ?? canManage)"
          data-testid="token-create-pdm-addin"
          @click="openCreate('pdmAddin')"
        />
      </span>
      <!-- A caller's own create action with its own dialog, such as the
           API key tab's terminal key. -->
      <slot name="start-extra" />
      <span v-tooltip.bottom="manageBlocked || undefined">
        <Button
          :label="tt('revokeAllButton')"
          icon="mdi mdi-cancel"
          severity="danger"
          text
          :disabled="!canManage || store.tokens.length === 0"
          data-testid="token-revoke-all"
          @click="onRevokeAll"
        />
      </span>
      <Button
        :label="t('common.clear')"
        icon="mdi mdi-filter-off-outline"
        severity="contrast"
        text
        :disabled="!store.hasActiveFilters"
        @click="store.clearFilters()"
      />
    </template>
    <template #handbook>
      <!-- Forwarded rather than rendered here: the caller supplies its own
           HelpButton with whatever slug it needs, since PATs and API keys
           have their own docs. -->
      <slot name="handbook" />
    </template>
  </ControlsBar>

  <TokenFormDialog
    v-model:visible="showCreateForm"
    :store="store"
    :i18n-prefix="i18nPrefix"
    :addin="createVariant === 'addin'"
    :pdm-addin="createVariant === 'pdmAddin'"
  />
</template>
