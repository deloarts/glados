<script setup lang="ts">
// The permissions column of the user dialog: the direct grants, with the
// permissions the selected groups grant shown checked and disabled, since
// only the group can take them away.
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useUserGroupsStore } from '../stores/userGroupsStore'
import PermissionChecklist from './PermissionChecklist.vue'

const props = defineProps<{
  groupIds: number[]
}>()

/** The direct grants only; the groups add theirs on top. */
const permissions = defineModel<string[]>('permissions', { required: true })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const groupsStore = useUserGroupsStore()

/** Every permission the selected groups grant, with the names of the groups granting it. */
const inheritedPermissions = computed<Map<string, string[]>>(() => {
  const byPermission = new Map<string, string[]>()
  for (const groupId of props.groupIds) {
    const group = groupsStore.getById(groupId)
    if (!group) continue
    for (const perm of group.permissions) {
      byPermission.set(perm, [...(byPermission.get(perm) ?? []), group.name])
    }
  }
  return byPermission
})
</script>

<template>
  <aside class="permissions-panel">
    <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions the group below, which names it through aria-labelledby -->
    <label :id="`${uid}-permissions`">{{ t('settings.users.fields.permissions') }}</label>
    <div class="permissions-list">
      <PermissionChecklist
        v-model:permissions="permissions"
        id-prefix="perm"
        :labelledby="`${uid}-permissions`"
        :inherited="inheritedPermissions"
      />
    </div>
  </aside>
</template>

<style scoped lang="scss">
// min-height: 0 lets the list scroll instead of stretching the dialog.
// Size containment keeps the long list from growing the row, so the panel
// is exactly as tall as the fields beside it and the list scrolls inside.
.permissions-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  min-height: 0;
  contain: size;

  > label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.permissions-list {
  padding: var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

// Below the dialog's two-column width the panel drops below the fields,
// with an explicit height cap.
@media (max-width: $bp-lg) {
  .permissions-panel {
    contain: none;
  }

  .permissions-list {
    flex: none;
    max-height: 20rem;
  }
}
</style>
