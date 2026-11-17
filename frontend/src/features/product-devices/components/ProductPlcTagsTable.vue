<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { extractApiError } from '@/core/utils/errors'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { deleteManualPlcTag, getProductPlcTags } from '../api/plcTagsApi'
import { useProductDevicesViewStore } from '../stores/productDevicesViewStore'
import type { PlcTag, PlcTagList } from '../types/productDevice'
import { writePlcTagExportFile } from '../utils/plcTagExport'
import PlcTagDialog from './PlcTagDialog.vue'

/**
 * The PLC tags of a product as its PLC environment names them, one row per
 * device signal: tag name, address, signal type, device and comment, with a
 * mark on a tag that is too long, shared by two signals or still without an
 * address. Renaming a built tag stores the name on its signal; manual tags
 * that belong to no device are added, edited and deleted here. Export and
 * Add Tag sit in the controls bar. Follows changes to the devices live.
 */
const props = defineProps<{ productId: number; productNumber: string; canEdit: boolean }>()

const { t } = useI18n()
const toast = useAppToast()
const { exportRequests, addTagRequests } = storeToRefs(useProductDevicesViewStore())
const { ask } = useConfirmAsync()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const list = ref<PlcTagList | null>(null)
const loading = ref(false)
watchLoadingBar(loading)

async function load(quiet = false): Promise<void> {
  if (!quiet) loading.value = true
  try {
    list.value = await getProductPlcTags(props.productId)
  } finally {
    loading.value = false
  }
}

onMounted(() => void load().catch(() => {}))
useLiveRefresh([LiveResource.PRODUCT_DEVICES], () => load(true), {
  filter: (signal) => signal.action === 'bulk' || signal.id === props.productId,
})

// Names can repeat, so each row gets a key of its own.
const tags = computed(() =>
  (list.value?.tags ?? []).map((tag) => ({
    ...tag,
    key: tag.manual_id !== null ? `m${tag.manual_id}` : `${tag.component_id}.${tag.signal_index}`,
  })),
)
const problems = computed(() => tags.value.filter((tag) => tag.too_long || tag.duplicate || !tag.address).length)

function marks(tag: PlcTag): Array<{ key: string; severity: 'danger' | 'warn' | 'secondary' }> {
  const result: Array<{ key: string; severity: 'danger' | 'warn' | 'secondary' }> = []
  if (tag.duplicate) result.push({ key: 'duplicate', severity: 'danger' })
  if (tag.too_long) result.push({ key: 'tooLong', severity: 'warn' })
  if (!tag.address) result.push({ key: 'noAddress', severity: 'secondary' })
  if (tag.overridden) result.push({ key: 'overridden', severity: 'secondary' })
  return result
}

// ── Editing ───────────────────────────────────────────────────────────

const dialogVisible = ref(false)
const editing = ref<PlcTag | undefined>(undefined)
const noRights = computed(() => (props.canEdit ? '' : t('productDevices.tags.noRights')))

function edit(tag?: PlcTag): void {
  editing.value = tag
  dialogVisible.value = true
}

watch(addTagRequests, () => {
  if (props.canEdit) edit()
})

async function remove(tag: PlcTag): Promise<void> {
  if (tag.manual_id === null) return
  const go = await ask({
    group: 'plc-tags',
    header: t('productDevices.tags.deleteTitle'),
    message: t('productDevices.tags.deleteMessage', { name: tag.name }),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.delete'), severity: 'danger' },
  })
  if (!go) return
  try {
    await deleteManualPlcTag(tag.manual_id)
    await load(true)
  } catch (e) {
    toast.error(tag.name, extractApiError(e) ?? t('productDevices.tags.saveFailed'))
  }
}

watch(exportRequests, async () => {
  if (!list.value?.environment) return
  try {
    await writePlcTagExportFile(list.value, props.productNumber)
  } catch (e) {
    toast.error(t('productDevices.tags.title'), extractApiError(e) ?? t('productDevices.tags.exportFailed'))
  }
})
</script>

<template>
  <div class="tags-view">
    <Message v-if="list && !list.environment" severity="warn" data-testid="plc-tags-no-environment">
      {{ t('productDevices.tags.noEnvironment') }}
    </Message>
    <p v-else-if="list?.environment" class="summary">
      {{
        t('productDevices.tags.summary', {
          environment: list.environment.name,
          count: tags.length,
          max: list.environment.max_tag_length,
        })
      }}
      <span v-if="problems > 0" class="problems">{{ t('productDevices.tags.problems', { count: problems }) }}</span>
    </p>
    <DataTable
      :value="tags"
      data-key="key"
      size="small"
      scrollable
      scroll-height="flex"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      class="tags-table"
      data-testid="plc-tags-table"
    >
      <template #empty><EmptyState /></template>
      <Column header="#" style="width: 3rem" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('productDevices.tags.columns.name')">
        <template #body="{ data }: { data: PlcTag }">
          <Tag v-if="data.manual_id !== null" :value="t('productDevices.tags.manual')" severity="info" class="manual" />
          <code>{{ data.name }}</code>
          <span class="length">{{ data.name.length }}</span>
        </template>
      </Column>
      <Column :header="t('productDevices.tags.columns.address')" style="width: 8rem">
        <template #body="{ data }: { data: PlcTag }">
          <code v-if="data.address">{{ data.address }}</code>
          <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column :header="t('productDevices.tags.columns.type')" style="width: 7rem">
        <template #body="{ data }: { data: PlcTag }">
          {{ data.signal_type.toUpperCase() }}
          <i v-if="data.safety" v-tooltip.bottom="t('productDevices.devices.fields.signalSafety')" class="mdi mdi-shield-alert safety" />
        </template>
      </Column>
      <Column :header="t('productDevices.tags.columns.table')" style="width: 14rem">
        <template #body="{ data }: { data: PlcTag }">{{ data.tag_table }}</template>
      </Column>
      <Column :header="t('productDevices.tags.columns.comment')">
        <template #body="{ data }: { data: PlcTag }">{{ data.comment }}</template>
      </Column>
      <Column style="width: 5.5rem">
        <template #body="{ data }: { data: PlcTag }">
          <div class="actions">
            <span v-tooltip.bottom="noRights || t('productDevices.tags.editTag')">
              <Button
                icon="mdi mdi-pencil"
                :aria-label="t('productDevices.tags.editTag')"
                severity="secondary"
                text
                size="small"
                :disabled="!canEdit"
                data-testid="plc-tag-edit"
                @click="edit(data)"
              />
            </span>
            <span v-if="data.manual_id !== null" v-tooltip.bottom="noRights || t('common.delete')">
              <Button
                icon="mdi mdi-delete-outline"
                :aria-label="t('common.delete')"
                severity="secondary"
                text
                size="small"
                :disabled="!canEdit"
                data-testid="plc-tag-delete"
                @click="remove(data)"
              />
            </span>
          </div>
        </template>
      </Column>
      <Column :header="t('productDevices.tags.columns.marks')" style="width: 14rem">
        <template #body="{ data }: { data: PlcTag }">
          <div class="marks">
            <Tag
              v-for="mark in marks(data)"
              :key="mark.key"
              :value="t(`productDevices.tags.marks.${mark.key}`)"
              :severity="mark.severity"
            />
          </div>
        </template>
      </Column>
    </DataTable>
    <PlcTagDialog v-model:visible="dialogVisible" :product-id="productId" :tag="editing" @saved="load(true)" />
    <ConfirmDialog group="plc-tags" />
  </div>
</template>

<style scoped lang="scss">
.tags-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tags-table {
  flex: 1;
  min-height: 0;
}

.summary {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.problems {
  margin-left: var(--space-2);
  color: var(--p-orange-500);
}

.manual {
  margin-right: var(--space-2);
}

.length {
  margin-left: var(--space-2);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.safety {
  margin-left: var(--space-1);
  color: var(--p-red-500);
}

.actions {
  display: flex;
}

.marks {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.muted {
  color: var(--p-text-muted-color);
}
</style>
