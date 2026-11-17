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
  'default-calendar': []
  downtimes: []
}>()
</script>

<template>
  <ControlsBar>
    <template #start>
      <Button
        :label="t('productionMachines.controls.new')"
        icon="mdi mdi-plus"
        severity="contrast"
        text
        :disabled="!canWrite"
        @click="emit('create')"
      />
      <Button
        :label="t('productionMachines.calendar.editDefault')"
        icon="mdi mdi-calendar-clock"
        severity="contrast"
        text
        @click="emit('default-calendar')"
      />
      <Button
        :label="t('productionMachines.downtime.button')"
        icon="mdi mdi-alert-octagon-outline"
        severity="contrast"
        text
        @click="emit('downtimes')"
      />
    </template>
    <template #handbook>
      <HelpButton rounded />
    </template>
  </ControlsBar>
</template>
