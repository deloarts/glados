<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import ControlsBar from './ControlsBar.vue'

// The New Demand toolbar shared by the bought/made/source-item demands views.
// That's as far as the three actually agree: bought and made add a
// batch-import button, bought and source both add a "manage orders" panel
// toggle, made adds "manage lots"/"auto-assign" behind the production
// planning flag instead. All of that is real, feature-specific behaviour that
// stays with the caller via the actions slot rather than being forced into
// shared props.
const props = defineProps<{
  /** e.g. `boughtItems.demands.controls`, which resolves `${i18nPrefix}.new`. */
  i18nPrefix: string
  canCreate: boolean
  /**
   * Why New is disabled, usually the missing permission, shown as its
   * tooltip on a wrapping span, since a disabled button shows none.
   */
  createBlocked?: string
}>()

const emit = defineEmits<{
  create: []
}>()

const { t } = useI18n()

function tt(key: string): string {
  return t(`${props.i18nPrefix}.${key}`)
}
</script>

<template>
  <ControlsBar>
    <template #start>
      <span v-tooltip="(!canCreate && createBlocked) || undefined">
        <Button
          :label="tt('new')"
          icon="mdi mdi-plus"
          severity="contrast"
          text
          :disabled="!canCreate"
          @click="emit('create')"
        />
      </span>
      <slot name="actions" />
    </template>
    <template #handbook>
      <!-- Forwarded rather than rendered here: the caller supplies its own
           HelpButton, since only it knows which doc explains its view. -->
      <slot name="handbook" />
    </template>
  </ControlsBar>
</template>
