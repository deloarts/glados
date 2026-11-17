<!--
  The "match PDM users" dialog: every vault user next to a Glados user picker,
  preselected with the existing link or the backend's proposal, which is marked
  as a guess. Several vault users may share a Glados user. Saving sends every
  row in one batch, since LinkPdmUsers treats unchanged rows as no-ops. The tab
  mounts it only while open (v-if), so every opening starts from a fresh load.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { extractApiError } from '@/core/utils/errors'
import { usePdmUsersStore } from '../../stores/pdmUsersStore'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { PdmUser } from '../../types/adminSettingsTypes'

const UNLINKED = 0

const { t } = useI18n()
const appToast = useAppToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const store = usePdmUsersStore()
const usersStore = useUsersStore()

const visible = defineModel<boolean>('visible', { required: true })

// Keyed by pdm_user_id; UNLINKED (0, never a real Glados user id) stands
// in for "not linked" so the Select can use a plain number model without
// juggling null through OpenVue's own option-value plumbing.
const selection = reactive<Record<number, number>>({})

function seedSelection(users: PdmUser[]): void {
  for (const user of users) {
    selection[user.pdm_user_id] = user.linked_user_id ?? user.proposed_user_id ?? UNLINKED
  }
}

const saving = ref(false)

// store.refresh() (useSequencedFetch) never throws; a failure lands in
// store.error instead, checked explicitly below. usersStore.ensureLoaded()
// (the shared Glados-user picker list) can throw, so both failure shapes
// end up as the same toast rather than one being silently swallowed.
async function load(): Promise<void> {
  try {
    await usersStore.ensureLoaded()
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.pdmUsers.loadFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
    return
  }

  await store.refresh()
  if (store.error) {
    appToast.error(t('adminSettings.pdmUsers.loadFailed'), store.error)
    return
  }
  seedSelection(store.items)
}

onMounted(load)

const userOptions = computed(() => [
  { text: t('adminSettings.pdmUsers.unlinkedOption'), value: UNLINKED },
  ...usersStore.userOptions,
])

function isProposed(user: PdmUser): boolean {
  return user.linked_user_id === null && user.proposed_user_id !== null
}

// How many rows currently pick each Glados user id, from the live
// `selection` state rather than the last-loaded `linked_user_id`, so the
// badge updates as the admin picks, not only after a save/reload. Purely
// informational: several vault users sharing one Glados user is allowed,
// see this file's own docstring.
const linkCounts = computed<Record<number, number>>(() => {
  const counts: Record<number, number> = {}
  for (const userId of Object.values(selection)) {
    if (userId === UNLINKED) continue
    counts[userId] = (counts[userId] ?? 0) + 1
  }
  return counts
})

/**
 * How many rows (including this one) currently pick the same Glados user
 * as `pdmUserId`'s row: 0 or 1 when unlinked or picked by no one else.
 */
function linkCount(pdmUserId: number): number {
  const picked = selection[pdmUserId]
  if (picked === undefined || picked === UNLINKED) return 0
  return linkCounts.value[picked] ?? 0
}

async function onSave(): Promise<void> {
  saving.value = true
  try {
    const links = store.items.map((user) => {
      const picked = selection[user.pdm_user_id] ?? UNLINKED
      return {
        pdm_user_id: user.pdm_user_id,
        user_id: picked === UNLINKED ? null : picked,
      }
    })
    await store.save(links)
    seedSelection(store.items)
    appToast.success(t('adminSettings.pdmUsers.saved'))
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.pdmUsers.saveFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('adminSettings.pdmUsers.dialogTitle')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <p class="hint">{{ t('adminSettings.pdmUsers.hint') }}</p>

    <DataTable
      :value="store.items"
      data-key="pdm_user_id"
      scrollable
      scroll-height="24rem"
      size="small"
      :loading="store.loading"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <template #empty>
        <EmptyState :message="t('adminSettings.pdmUsers.empty')" />
      </template>

      <Column :header="t('adminSettings.pdmUsers.columns.pdmUsername')" style="width: 12rem">
        <template #body="{ data }: { data: PdmUser }">
          <div class="username-cell">
            <span>{{ data.username }}</span>
            <Tag
              v-if="data.is_service_account"
              severity="secondary"
              :value="t('adminSettings.pdmUsers.serviceAccountTag')"
            />
          </div>
        </template>
      </Column>

      <Column field="full_name" :header="t('adminSettings.pdmUsers.columns.fullName')" style="width: 12rem" />

      <Column :header="t('adminSettings.pdmUsers.columns.gladosUser')">
        <template #body="{ data }: { data: PdmUser }">
          <div class="glados-user-cell">
            <Select
              v-model="selection[data.pdm_user_id]"
              :aria-label="t('adminSettings.pdmUsers.columns.gladosUser')"
              :options="userOptions"
              option-label="text"
              option-value="value"
              :disabled="!canWrite"
              fluid
            />
            <Tag
              v-if="isProposed(data)"
              severity="info"
              :value="t('adminSettings.pdmUsers.proposedTag')"
            />
            <Tag
              v-if="linkCount(data.pdm_user_id) > 1"
              severity="contrast"
              :value="`×${linkCount(data.pdm_user_id)}`"
              v-tooltip.top="
                t('adminSettings.pdmUsers.multipleLinksTag', { count: linkCount(data.pdm_user_id) })
              "
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('adminSettings.pdmUsers.save')"
        :disabled="!canWrite"
        :loading="saving"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.hint {
  margin: 0 0 var(--space-3);
}

.username-cell,
.glados-user-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
</style>
