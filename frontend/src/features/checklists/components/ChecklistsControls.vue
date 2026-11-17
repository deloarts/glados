<script setup lang="ts">
import { computed } from 'vue'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { HelpButton } from '@/shared/help'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import NewChecklistButton from './NewChecklistButton.vue'

/** The actions above the checklists table: New Checklist on the left, like the catalogue's New. */

const { hasPermission } = usePermissions()
const canCreate = computed(() => hasPermission(Permission.WRITE_CHECKLISTS))
</script>

<template>
  <ControlsBar data-testid="checklists-controls">
    <template #start>
      <NewChecklistButton :disabled="!canCreate" />
    </template>
    <template #handbook>
      <HelpButton rounded slug="workspace/document-revisions" />
    </template>
  </ControlsBar>
</template>
