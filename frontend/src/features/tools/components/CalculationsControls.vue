<script setup lang="ts">
import { computed } from 'vue'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { HelpButton } from '@/shared/help'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import NewCalculationButton from './NewCalculationButton.vue'

/** The actions above a calculations table: New Calculation on the left, like the catalogue's New. */

defineProps<{
  /** `project:<id>:<label>` or `product:<id>:<label>`, preselected when saving. */
  owner?: string | null
}>()

const { hasPermission } = usePermissions()
const canCreate = computed(() => hasPermission(Permission.WRITE_CALCULATIONS))
</script>

<template>
  <ControlsBar data-testid="calculations-controls">
    <template #start>
      <NewCalculationButton :owner="owner" :disabled="!canCreate" />
    </template>
    <template #handbook>
      <HelpButton rounded slug="workspace/document-revisions" />
    </template>
  </ControlsBar>
</template>
