<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { HelpButton } from '@/shared/help'
import { GANTT_RESOLUTIONS } from '../utils/productionPlanningScales'
import type { GanttResolution } from '../utils/productionPlanningScales'

const resolution = defineModel<GanttResolution>('resolution', { required: true })

const { t } = useI18n()
</script>

<template>
  <Toolbar>
    <template #start>
      <Button
        v-for="option in GANTT_RESOLUTIONS"
        :key="option"
        :label="t(`productionPlanning.resolution.${option}`)"
        severity="contrast"
        :text="resolution !== option"
        @click="resolution = option"
      />
    </template>
    <template #end>
      <HelpButton rounded />
    </template>
  </Toolbar>
</template>
