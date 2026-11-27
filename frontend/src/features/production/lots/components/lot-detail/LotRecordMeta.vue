<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'

import type { ChangedBy } from '../../composables/useChangedByUser'
import type { PublicUser } from '@/core/types/userResponse'

defineProps<{
  creator: PublicUser | null
  created: string
  changed: string | null
  changedBy: ChangedBy
}>()

const { t } = useI18n()
</script>

<template>
  <div class="record-meta">
    <div class="meta-item">
      <UserAvatarPreview :user="creator" />
      <span class="field-sublabel"
        >{{ t('madeItems.catalogue.columns.created') }}: {{ formatISODateTime(created) }}</span
      >
    </div>
    <div v-if="changed" class="meta-item">
      <UserAvatarPreview v-if="changedBy.user" :user="changedBy.user" />
      <span class="field-sublabel">
        {{ t('madeItems.catalogue.columns.changed') }}: {{ formatISODateTime(changed) }}
        <template v-if="!changedBy.user && changedBy.name">({{ changedBy.name }})</template>
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.record-meta {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
  // Pinned to the card bottom; needs a flex column parent with a definite
  // height.
  margin-top: auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--p-content-border-color);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
