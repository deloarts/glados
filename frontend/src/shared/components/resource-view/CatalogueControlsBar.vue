<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import ControlsBar from './ControlsBar.vue'

// The New/Edit toolbar shared by the bought/made/source-item catalogue
// views. Each feature keeps its own create-form dialog and edit store next to
// this bar, and puts its import button after New and its Export button after
// Edit through the slots. Only the button row and i18n lookup pattern is
// common enough to share, and the create form differs per item type so it
// stays in the caller.
const props = withDefaults(
  defineProps<{
    /** e.g. `boughtItems.catalogue.controls`, resolves `${i18nPrefix}.new` etc. */
    i18nPrefix: string
    canWrite: boolean
    /**
     * Why New and Edit are disabled, usually the missing permission, shown
     * as their tooltip on a wrapping span, since a disabled button shows none.
     */
    writeBlocked?: string
    editMode: boolean
    /**
     * made/bought items hide the New button entirely (not merely
     * disable it) once the resolved numbering policy says web creation is
     * off for that kind. Context-menu entry points are not covered by this prop.
     * Defaults to true so callers that don't pass it (source items, which
     * have no such policy) are unaffected.
     */
    showCreate?: boolean
  }>(),
  { showCreate: true },
)

const emit = defineEmits<{
  create: []
  'toggle-edit': []
}>()

const { t } = useI18n()

function tt(key: string): string {
  return t(`${props.i18nPrefix}.${key}`)
}
</script>

<template>
  <ControlsBar>
    <template #start>
      <span v-if="showCreate" v-tooltip="(!canWrite && writeBlocked) || undefined">
        <Button
          :label="tt('new')"
          icon="mdi mdi-plus"
          severity="contrast"
          text
          :disabled="!canWrite"
          @click="emit('create')"
        />
      </span>
      <slot name="after-create" />
      <span v-tooltip="(!canWrite && writeBlocked) || undefined">
        <Button
          :label="tt('edit')"
          icon="mdi mdi-pencil"
          severity="contrast"
          :text="!editMode"
          :disabled="!canWrite"
          @click="emit('toggle-edit')"
        />
      </span>
      <slot name="after-edit" />
    </template>
    <template #handbook>
      <!-- Forwarded rather than rendered here: the caller supplies its own
           HelpButton, since only it knows which doc explains its view. -->
      <slot name="handbook" />
    </template>
  </ControlsBar>
</template>
