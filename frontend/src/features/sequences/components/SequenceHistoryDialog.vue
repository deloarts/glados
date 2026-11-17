<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import type { SequenceSummaryResponse } from '../types/sequence'
import SequenceStatusTag from './SequenceStatusTag.vue'

/** Every revision of a sequence, newest first, each one to open. */
defineProps<{
  revisions: readonly SequenceSummaryResponse[]
  currentId: number
}>()

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ open: [id: number] }>()

const { t } = useI18n()
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('sequences.actions.history')"
    :style="{ width: 'var(--dialog-width-lg)' }"
    :breakpoints="{ '960px': '95vw' }"
  >
    <DataTable :value="[...revisions]" data-key="id" size="small" data-testid="sequence-history-table">
      <Column :header="t('documents.table.revision')" style="width: 6rem">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <span :class="{ current: data.id === currentId }">{{ data.revision }}</span>
        </template>
      </Column>
      <Column :header="t('sequences.history.reason')">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          {{ data.revision_reason ?? t('sequences.history.firstRevision') }}
        </template>
      </Column>
      <Column :header="t('sequences.list.status')" style="width: 10rem">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <SequenceStatusTag :sequence="data" />
        </template>
      </Column>
      <Column :header="t('sequences.list.author')" style="width: 13rem">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <UserDateCell :date="data.created" :user-id="data.creator_id" :name="data.creator_full_name" />
        </template>
      </Column>
      <Column style="width: 3rem">
        <template #body="{ data }: { data: SequenceSummaryResponse }">
          <Button
            v-tooltip.bottom="t('documents.menu.open')"
            :aria-label="t('documents.menu.open')"
            icon="mdi mdi-open-in-app"
            size="small"
            text
            :disabled="data.id === currentId"
            @click="emit('open', data.id)"
          />
        </template>
      </Column>
    </DataTable>
  </Dialog>
</template>

<style scoped lang="scss">
.current {
  font-weight: 600;
}
</style>
