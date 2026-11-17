<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'

const { t } = useI18n()
const { hasPermission } = usePermissions()

const canWrite = computed(() => hasPermission(Permission.WRITE_MACHINES))

const emit = defineEmits<{
  create: []
}>()
</script>

<template>
  <ControlsBar>
    <template #start>
      <Button
        :label="t('productionMachinePools.controls.new')"
        icon="mdi mdi-plus"
        severity="contrast"
        text
        :disabled="!canWrite"
        @click="emit('create')"
      />
    </template>
    <template #handbook>
      <HelpButton rounded />
    </template>
  </ControlsBar>
</template>
