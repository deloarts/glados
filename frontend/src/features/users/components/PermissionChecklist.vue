<script setup lang="ts">
// The permission checkboxes of the user and group dialogs, grouped by area
// as on the account page. Hovering a row shows what the permission allows,
// and each checkbox carries the same text as its description for screen
// readers. In the user dialog the permissions a selected group grants are
// shown checked and disabled, since only the group can take them away, and
// a direct grant a group also gives can be dropped from here.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { PERMISSION_GROUPS } from '@/shared/utils/permissionGroups'
import { permissionDescription, permissionLabel } from '@/shared/utils/permissionLabels'

const props = withDefaults(
  defineProps<{
    /** Prefixes the checkbox ids, so each dialog keeps its own. */
    idPrefix: string
    /** The id of the caption that names the list. */
    labelledby: string
    /** Every permission the user's groups grant, with the names of the groups granting it. */
    inherited?: Map<string, string[]>
    disabled?: boolean
  }>(),
  { inherited: () => new Map<string, string[]>(), disabled: false },
)

/** The direct grants only; the groups add theirs on top. */
const permissions = defineModel<string[]>('permissions', { required: true })

const { t } = useI18n()

// Connecting terminals belongs to terminal keys alone, and the backend
// refuses it on a person's account, so it is never offered. The read
// access every user has is not a permission either.
const sections = computed(() =>
  PERMISSION_GROUPS.map((group) => ({
    titleKey: group.titleKey,
    icon: group.icon,
    permissions: group.permissions
      .filter((entry) => !entry.alwaysGranted && entry.key !== Permission.CONNECT_TERMINALS)
      .map((entry) => entry.key),
  })).filter((section) => section.permissions.length > 0),
)

function inputId(perm: string): string {
  return `${props.idPrefix}-${perm}`
}

function descriptionId(perm: string): string {
  return `${inputId(perm)}-desc`
}

function tooltip(perm: string): string {
  const description = permissionDescription(t, perm)
  const groups = props.inherited.get(perm)
  if (!groups) return description
  const names = groups.join(', ')
  const source = permissions.value.includes(perm)
    ? t('settings.users.permissionAlsoDirect', { groups: names })
    : t('settings.users.permissionFromGroups', { groups: names })
  return `${description} ${source}`
}

function dropDirectGrant(perm: string): void {
  permissions.value = permissions.value.filter((p) => p !== perm)
}
</script>

<template>
  <div role="group" :aria-labelledby="labelledby" class="permission-checklist">
    <section v-for="section in sections" :key="section.titleKey" class="permission-section">
      <h3 class="section-title">
        <i :class="['mdi', section.icon]" aria-hidden="true" />
        {{ t(section.titleKey) }}
      </h3>
      <div
        v-for="perm in section.permissions"
        :key="perm"
        v-tooltip.left="{ value: tooltip(perm), showDelay: 300 }"
        class="permission-item"
        :data-testid="`permission-row-${perm}`"
      >
        <span :id="descriptionId(perm)" class="visually-hidden">{{ tooltip(perm) }}</span>
        <!-- Inherited from a group: shown checked and disabled, since
             only the group can take it away. -->
        <template v-if="inherited.has(perm)">
          <Checkbox
            :input-id="inputId(perm)"
            :model-value="true"
            binary
            disabled
            :pt="{ input: { 'aria-describedby': descriptionId(perm) } }"
            :data-testid="`inherited-${perm}`"
          />
          <label :for="inputId(perm)" class="inherited-label">{{ permissionLabel(t, perm) }}</label>
          <Button
            v-if="permissions.includes(perm)"
            type="button"
            icon="mdi mdi-close"
            size="small"
            severity="secondary"
            text
            rounded
            class="drop-direct"
            v-tooltip.top="t('settings.users.dropDirectGrant')"
            :aria-label="t('settings.users.dropDirectGrant')"
            :data-testid="`drop-direct-${perm}`"
            @click="dropDirectGrant(perm)"
          />
        </template>
        <template v-else>
          <Checkbox
            :input-id="inputId(perm)"
            v-model="permissions"
            :value="perm"
            :disabled="disabled"
            :pt="{ input: { 'aria-describedby': descriptionId(perm) } }"
          />
          <label :for="inputId(perm)">{{ permissionLabel(t, perm) }}</label>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.permission-checklist {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.permission-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.permission-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    cursor: pointer;
  }
}

.inherited-label {
  color: var(--p-text-muted-color);
}

// Keeps the row as tall as the others.
.drop-direct {
  width: 1.5rem;
  height: 1.5rem;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
</style>
