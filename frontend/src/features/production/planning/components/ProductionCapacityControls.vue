<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import AutoPlanDialog from '../../components/AutoPlanDialog.vue'
import { useAutoPlanRunStore } from '../../stores/autoPlanRunStore'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

const dateRange = defineModel<[Date, Date]>('dateRange', { required: true })

const emit = defineEmits<{
  applied: []
}>()

const { t } = useI18n()
const { missing } = useMissingPermission()
const autoPlanRunStore = useAutoPlanRunStore()

// The tooltip of the disabled Auto-Plan button, '' when the user may run it.
const autoPlanBlocked = computed(() => missing(Permission.WRITE_PRODUCTION_ORDERS))

const showAutoPlan = ref(false)
</script>

<template>
  <ControlsBar>
    <template #start>
      <DatePicker
        v-model="dateRange"
        selection-mode="range"
        show-button-bar
        :placeholder="t('productionSchedule.dateRange')"
      />
      <!-- anyRunActive covers a run started by anyone; status ===
           'running' additionally covers the moment right after THIS tab's
           own run() call, before the live-signal round trip has caught
           activeRun up to it. Without it, the icon would lag a beat on the
           runner's own click. The span carries the tooltip, since a
           disabled button shows none of its own. -->
      <span v-tooltip="autoPlanBlocked || undefined">
        <Button
          :label="t('productionSchedule.autoPlan.trigger')"
          :icon="
            autoPlanRunStore.anyRunActive || autoPlanRunStore.status === 'running'
              ? 'mdi mdi-loading mdi-spin'
              : 'mdi mdi-calendar-sync'
          "
          severity="contrast"
          text
          :disabled="autoPlanBlocked !== ''"
          data-testid="auto-plan"
          @click="showAutoPlan = true"
        />
      </span>
    </template>
    <template #handbook>
      <HelpButton rounded />
    </template>
  </ControlsBar>

  <AutoPlanDialog v-model:visible="showAutoPlan" @applied="emit('applied')" />
</template>
