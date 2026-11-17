<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { ReportDistribution } from '@/shared/reports'
import type { ChecklistSummaryResponse } from '../types/checklist'
import { completionOf, VERDICT_SEVERITY } from '../utils/owner'
import ChecklistStatusTag from './ChecklistStatusTag.vue'

/**
 * Every revision of a checklist, newest first, each one to open or compare,
 * and its distribution: where reports of it went.
 */

const props = defineProps<{
  revisions: readonly ChecklistSummaryResponse[]
  currentId: number
  publicId: string
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  open: [id: number]
  compare: [id: number]
}>()

const { t } = useI18n()
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('checklists.actions.history')"
    :style="{ width: 'var(--dialog-width-lg)' }"
    :breakpoints="{ '960px': '95vw' }"
  >
    <Tabs value="revisions">
      <TabList>
        <Tab value="revisions">{{ t('checklists.history.title') }}</Tab>
        <Tab value="distribution" data-testid="cl-history-distribution">{{ t('reports.distribution.title') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="revisions">
    <DataTable :value="[...revisions]" data-key="id" size="small" data-testid="cl-history-table">
      <Column :header="t('checklists.history.revision')" style="width: 6rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <span :class="{ current: data.id === currentId }">{{ data.revision }}</span>
        </template>
      </Column>
      <Column :header="t('checklists.history.reason')">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          {{ data.revision_reason ?? t('checklists.history.firstRevision') }}
        </template>
      </Column>
      <Column :header="t('checklists.list.result')" style="width: 11rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <Tag :value="t(`checklists.verdicts.${data.verdict}`)" :severity="VERDICT_SEVERITY[data.verdict]" />
          <span class="completion">{{ t('checklists.list.completion', { percent: completionOf(data) }) }}</span>
        </template>
      </Column>
      <Column :header="t('checklists.list.status')" style="width: 9rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <ChecklistStatusTag :checklist="data" />
        </template>
      </Column>
      <Column :header="t('checklists.list.author')" style="width: 12rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <UserDateCell :date="data.created" :user-id="data.creator_id" :name="data.creator_full_name" />
        </template>
      </Column>
      <Column style="width: 6rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <div class="row-actions">
            <Button
              v-tooltip.bottom="t('checklists.actions.open')"
              :aria-label="t('checklists.actions.open')"
              icon="mdi mdi-open-in-app"
              size="small"
              text
              :disabled="data.id === currentId"
              @click="emit('open', data.id)"
            />
            <Button
              v-tooltip.bottom="t('checklists.history.compareWith')"
              :aria-label="t('checklists.history.compareWith')"
              icon="mdi mdi-compare-horizontal"
              size="small"
              severity="secondary"
              text
              :disabled="data.id === currentId"
              @click="emit('compare', data.id)"
            />
          </div>
        </template>
      </Column>
    </DataTable>
        </TabPanel>
        <TabPanel value="distribution">
          <ReportDistribution
            v-if="visible"
            :target="{ document: 'checklist_report', rootPublicId: props.publicId }"
          />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </Dialog>
</template>

<style scoped lang="scss">
.current {
  font-weight: 600;
}

.completion {
  margin-left: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-actions {
  justify-content: flex-end;
}
</style>
