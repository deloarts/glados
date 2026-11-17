<script setup lang="ts">
/**
 * Preview/Download/[Replace]/Delete button row for one occupied file slot.
 *
 * Used by both FilesSection's singleton grid (which also offers Replace)
 * and its multi-row list (which doesn't).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    previewable: boolean
    canEdit: boolean
    deleting: boolean
    /** Only the singleton grid offers in-place replace. */
    showReplace?: boolean
    /**
     * True for a file PDM owns (`from_pdm`): the server would still allow
     * replacing or deleting it, but the next sync would just restore it, so
     * both actions are disabled here rather than letting the admin fight
     * the sync. Preview/download stay enabled either way.
     */
    locked?: boolean
    /**
     * Tooltip/aria-label shown on the disabled replace/delete buttons
     * while `locked` is true, explaining why they don't work.
     */
    lockedTooltip?: string
    /**
     * Why the user may not change the files, naming the missing permission.
     * While `canEdit` is false and this is set, Replace and Delete stay
     * visible but disabled with this tooltip; without it they are hidden.
     */
    missingHint?: string
  }>(),
  { showReplace: false, locked: false, lockedTooltip: '', missingHint: '' },
)

defineEmits<{
  preview: []
  download: []
  replace: []
  delete: []
}>()

const { t } = useI18n()

const showEdit = computed(() => props.canEdit || props.missingHint !== '')
const blocked = computed(() => (props.canEdit ? '' : props.missingHint))
</script>

<template>
  <div class="file-action-buttons">
    <Button
      v-if="previewable"
      icon="mdi mdi-eye-outline"
      size="small"
      text
      rounded
      severity="secondary"
      v-tooltip.focus="t('common.files.preview')"
      :aria-label="t('common.files.preview')"
      data-testid="file-preview"
      @click="$emit('preview')"
    />
    <Button
      icon="mdi mdi-download-outline"
      size="small"
      text
      rounded
      severity="secondary"
      v-tooltip.focus="t('common.files.download')"
      :aria-label="t('common.files.download')"
      data-testid="file-download"
      @click="$emit('download')"
    />
    <span v-if="showReplace && showEdit" v-tooltip.top="blocked || undefined">
      <Button
        icon="mdi mdi-upload-outline"
        size="small"
        text
        rounded
        severity="secondary"
        :disabled="locked || !canEdit"
        v-tooltip.focus="locked ? props.lockedTooltip : t('common.files.replaceHint')"
        :aria-label="locked ? props.lockedTooltip : t('common.files.replaceHint')"
        data-testid="file-replace"
        @click="$emit('replace')"
      />
    </span>
    <span v-if="showEdit" v-tooltip.top="blocked || undefined">
      <Button
        icon="mdi mdi-delete-outline"
        size="small"
        text
        rounded
        severity="danger"
        :disabled="locked || !canEdit"
        :loading="deleting"
        v-tooltip.focus="locked ? props.lockedTooltip : t('common.delete')"
        :aria-label="locked ? props.lockedTooltip : t('common.delete')"
        data-testid="file-delete"
        @click="$emit('delete')"
      />
    </span>
  </div>
</template>

<style scoped>
.file-action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-1);
}
</style>
