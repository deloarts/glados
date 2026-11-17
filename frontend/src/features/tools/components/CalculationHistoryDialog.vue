<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { revisionLabel } from '@/shared/documents'
import { ReportDistribution } from '@/shared/reports'
import { getCalculationRevisions } from '../api/getCalculationRevisions'
import type { CalculationResponse, CalculationSummaryResponse } from '../types/calculation'

/**
 * Every revision of a calculation, newest first, each one to open, and its
 * distribution: where reports of it went.
 */

const props = defineProps<{ calculation: CalculationResponse }>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{ open: [publicId: string] }>()

const { t } = useI18n()

const revisions = ref<CalculationSummaryResponse[]>([])

watch(visible, async (open) => {
  if (open) revisions.value = await getCalculationRevisions(props.calculation.id).catch(() => [])
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('tools.calculations.history.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
    :breakpoints="{ '960px': '95vw' }"
  >
    <Tabs value="revisions">
      <TabList>
        <Tab value="revisions">{{ t('tools.calculations.history.revisions') }}</Tab>
        <Tab value="distribution" data-testid="calc-history-distribution">{{ t('reports.distribution.title') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="revisions">
          <DataTable :value="revisions" data-key="id" size="small" data-testid="calc-history-table">
            <Column :header="t('tools.calculations.history.revision')" style="width: 8rem">
              <template #body="{ data }: { data: CalculationSummaryResponse }">
                <span :class="{ current: data.id === calculation.id }">{{ revisionLabel(data, t) }}</span>
              </template>
            </Column>
            <Column :header="t('tools.calculations.history.reason')">
              <template #body="{ data }: { data: CalculationSummaryResponse }">
                {{ data.revision_reason ?? t('tools.calculations.history.firstRevision') }}
              </template>
            </Column>
            <Column :header="t('tools.calculations.history.author')" style="width: 14rem">
              <template #body="{ data }: { data: CalculationSummaryResponse }">
                <UserDateCell :date="data.created" :user-id="data.creator_id" :name="data.creator_full_name" />
              </template>
            </Column>
            <Column style="width: 4rem">
              <template #body="{ data }: { data: CalculationSummaryResponse }">
                <Button
                  v-tooltip.bottom="t('tools.calculations.actions.open')"
                  :aria-label="t('tools.calculations.actions.open')"
                  icon="mdi mdi-open-in-app"
                  size="small"
                  text
                  :disabled="data.id === calculation.id"
                  @click="emit('open', data.public_id)"
                />
              </template>
            </Column>
          </DataTable>
        </TabPanel>
        <TabPanel value="distribution">
          <ReportDistribution
            v-if="visible"
            :target="{ document: 'calculation_report', rootPublicId: calculation.public_id }"
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
</style>
