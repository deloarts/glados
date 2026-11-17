<script setup lang="ts">
// The avatar field of the user dialog: the picture or the initials, and the
// upload and remove buttons while file storage is enabled. Picking a file
// and removing the picture are handed up to the dialog.
import { ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'

defineProps<{
  avatarUrl: string | null
  initials: string
  uploading: boolean
  deleting: boolean
}>()

const emit = defineEmits<{
  select: [event: Event]
  remove: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const hostStore = useHostStore()

const input = ref<HTMLInputElement | null>(null)
</script>

<template>
  <div class="field field-wide">
    <label :for="`${uid}-avatar`">{{ t('settings.users.fields.avatar') }}</label>
    <div class="avatar-cell">
      <div class="avatar-preview">
        <img v-if="avatarUrl" :src="avatarUrl" class="avatar-image" alt="avatar" />
        <div v-else class="avatar-initials">{{ initials }}</div>
      </div>
      <template v-if="hostStore.storageEnabled">
        <input
          ref="input"
          :id="`${uid}-avatar`"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          class="avatar-file-input"
          @change="emit('select', $event)"
        />
        <Button
          :label="t('settings.users.fields.avatarUpload')"
          icon="mdi mdi-upload"
          severity="contrast"
          outlined
          size="small"
          :loading="uploading"
          @click="input?.click()"
        />
        <Button
          v-if="avatarUrl"
          :label="t('settings.users.fields.avatarRemove')"
          icon="mdi mdi-delete-outline"
          severity="danger"
          outlined
          size="small"
          :loading="deleting"
          @click="emit('remove')"
        />
      </template>
      <span v-else class="storage-hint">
        <i class="mdi mdi-information-outline" aria-hidden="true" />
        {{ t('settings.users.fields.avatarStorageDisabled') }}
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
// The field and label styles match the dialog's other fields; the root's
// grid placement comes from the dialog's .field-wide.
.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.avatar-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.avatar-preview {
  flex-shrink: 0;
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  overflow: hidden;
  background-color: var(--p-primary-500);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-initials {
  font-size: var(--font-size-md);
  font-weight: 700;
  color: var(--on-accent);
  letter-spacing: 0.05em;
}

.avatar-file-input {
  display: none;
}

.storage-hint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
