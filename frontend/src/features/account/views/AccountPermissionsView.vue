<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { PERMISSION_GROUPS } from '@/shared/utils/permissionGroups'
import type { PermissionEntry } from '@/shared/utils/permissionGroups'

const { t } = useI18n()
const userStore = useCurrentUserStore()

const userPermissions = computed(() => new Set(userStore.user?.permissions ?? []))
const isSystemUser = computed(() => userStore.user?.is_systemuser ?? false)

function has(entry: PermissionEntry): boolean {
  return entry.alwaysGranted === true || isSystemUser.value || userPermissions.value.has(entry.key)
}
</script>

<template>
  <PageLayout :card="false">
    <template #controls>
      <ControlsBar>
        <template #handbook>
          <HelpButton slug="account/notifications" anchor="permissions" rounded />
        </template>
      </ControlsBar>
    </template>
    <div class="permissions-layout">
      <Message v-if="isSystemUser" severity="info" :closable="false" icon="mdi mdi-shield-star">
        <strong>{{ t('accountMe.permissions.systemUser.title') }}</strong>
        {{ t('accountMe.permissions.systemUser.description') }}
      </Message>

      <div class="groups-grid">
        <SectionCard
          v-for="group in PERMISSION_GROUPS"
          :key="group.titleKey"
          :title="t(group.titleKey)"
          :icon="group.icon"
          flush
        >
          <div class="permission-list">
            <div
              v-for="entry in group.permissions"
              :key="entry.key"
              :data-permission="entry.key"
              class="permission-row"
              :class="{
                'permission-row--granted': has(entry),
                'permission-row--denied': !has(entry),
              }"
            >
              <i
                class="mdi permission-status-icon"
                :class="has(entry) ? 'mdi-check-circle' : 'mdi-lock-outline'"
                aria-hidden="true"
              />
              <div class="permission-info">
                <span class="permission-label">{{ permissionLabel(t, entry.key) }}</span>
                <span class="permission-desc">{{ t(entry.descriptionKey) }}</span>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  </PageLayout>
</template>

<style scoped lang="scss">
.permissions-layout {
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

// ── Groups grid ───────────────────────────────────────────────────────────────

.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(22rem, 1fr));
  gap: var(--space-3);
  align-items: start;
}

// ── Permission rows ───────────────────────────────────────────────────────────

.permission-list {
  display: flex;
  flex-direction: column;
}

.permission-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);

  & + & {
    border-top: 1px solid var(--p-content-border-color);
  }

  &.permission-row--granted .permission-status-icon {
    color: var(--p-green-500);
  }

  &.permission-row--denied {
    opacity: 0.5;

    .permission-status-icon {
      color: var(--p-text-muted-color);
    }
  }
}

.permission-status-icon {
  font-size: var(--font-size-md);
  flex-shrink: 0;
  margin-top: var(--space-1);
}

.permission-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.permission-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.permission-desc {
  font-size: var(--font-size-sm);
  line-height: 1.35;
}
.p-dark .permissions-layout {
  .permission-row + .permission-row {
    border-top-color: var(--p-surface-700);
  }
}
</style>
