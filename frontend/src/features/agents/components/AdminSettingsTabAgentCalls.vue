<script setup lang="ts">
// Every call AI agents made through the MCP surface, those of API keys
// included, with the token's owner. Read only; revoking a token happens on
// its owner's token page or, for an API key, on the API keys tab.
import { computed, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { AdminSettingsTabShell } from '@/features/admin-settings'
import AgentCallsTable from './AgentCallsTable.vue'

const { t } = useI18n()
const table = useTemplateRef<InstanceType<typeof AgentCallsTable>>('table')
const loading = computed(() => table.value?.loading ?? false)
</script>

<template>
  <AdminSettingsTabShell table>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.reload')"
            icon="mdi mdi-refresh"
            severity="contrast"
            text
            :loading="loading"
            @click="table?.reload()"
          />
        </template>
      </Toolbar>
    </template>

    <AgentCallsTable ref="table" admin />
  </AdminSettingsTabShell>
</template>
