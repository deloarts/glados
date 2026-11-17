<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { useSequencesViewStore } from '../stores/sequencesViewStore'

/**
 * The Sequences tab's entries in the product page's controls bar: New
 * Sequence and the product's variants. Rendered inside the bar's start
 * slot. New Sequence stays visible without the rights to create one and
 * says what is missing.
 */
const props = defineProps<{ productArchived: boolean }>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const view = useSequencesViewStore()

const createBlocked = computed(() => {
  if (!hasPermission(Permission.WRITE_SEQUENCES)) {
    return t('sequences.permissionMissing', { permission: permissionLabel(t, Permission.WRITE_SEQUENCES) })
  }
  return props.productArchived ? t('sequences.productArchived') : ''
})
</script>

<template>
  <span v-tooltip.bottom="createBlocked">
    <Button
      :label="t('sequences.actions.create')"
      icon="mdi mdi-plus"
      severity="contrast"
      text
      :disabled="createBlocked !== ''"
      data-testid="sequence-create"
      @click="view.requestCreate()"
    />
  </span>
  <Button
    :label="t('sequences.variants.title')"
    icon="mdi mdi-format-list-numbered"
    severity="contrast"
    text
    data-testid="sequence-variants"
    @click="view.requestVariants()"
  />
</template>
