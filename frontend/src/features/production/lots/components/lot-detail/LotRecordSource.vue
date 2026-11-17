<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useClipboard } from '@/core/composables/useClipboard'
import { formatDecimal } from '@/core/utils/numbers'
import { safeHref } from '@/shared/utils/isSafeHttpUrl'
import { catalogueStatusSeverity } from '../../utils/catalogueStatus'
import { useUsersStore } from '@/core/stores/usersStore'
import { getSourceItemChangelog } from '@/features/source-items'
import { getBoughtItemChangelog } from '@/features/bought-items'
import { getMadeItemChangelog } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { useChangedByUser } from '../../composables/useChangedByUser'
import { useMaterialSourceChange } from '../../composables/useMaterialSourceChange'
import LotRecordMeta from './LotRecordMeta.vue'
import LotRecordSourceDemand from './LotRecordSourceDemand.vue'

import type { LotResponse } from '../../../types/productionLotsResponse'
import type { LotSourceItem } from '../../composables/useLotRecordData'
import type { ChangelogEntryLike } from '../../composables/useChangedByUser'
import type { SourceItemDemandResponse } from '@/features/source-items'
import type {
  SourceItemAllocationResponse,
  SourceItemDemandSummaryResponse,
} from '@/features/source-items'
import type { OrderResponse } from '@/features/orders'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import { localizeLabel } from '@/shared/utils/localizeLabel'

const props = withDefaults(
  defineProps<{
    lot: LotResponse
    sourceItem: LotSourceItem | null
    sourceItemDemand: SourceItemDemandResponse | null
    sourceItemDemandArrived: number
    summary: SourceItemDemandSummaryResponse | null
    allocations: SourceItemAllocationResponse[]
    sourceOrder: OrderResponse | null
    manageMode: boolean
    canWrite: boolean
    canApprove?: boolean
  }>(),
  { canApprove: false },
)

defineEmits<{
  'view-source-item': []
  'change-source': []
  'view-demand': []
  'create-demand': []
  'approve-source': []
  'reject-source': []
}>()

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const usersStore = useUsersStore()
const { format: madeItemLabel } = useMadeItemLabel()

// Each source kind has its own changelog endpoint.
function fetchChangelog(item: LotSourceItem): Promise<ChangelogEntryLike[]> {
  if (item.kind === 'bought') return getBoughtItemChangelog(item.item.id)
  if (item.kind === 'source') return getSourceItemChangelog(item.item.id)
  return getMadeItemChangelog(item.item.id)
}

const changelogEntries = ref<ChangelogEntryLike[]>([])

watch(
  () => (props.sourceItem ? `${props.sourceItem.kind}:${props.sourceItem.item.id}` : null),
  async () => {
    changelogEntries.value = []
    if (!props.sourceItem) return
    changelogEntries.value = await fetchChangelog(props.sourceItem)
  },
  { immediate: true },
)

const { resolve } = useChangedByUser()
const changedBy = computed(() => resolve(changelogEntries.value))

const hasNothingToShow = computed(() => !props.sourceItem && !props.lot.is_alteration)

const { sourceChangeBlocked } = useMaterialSourceChange(
  () => props.lot,
  () => props.canWrite,
)

// Only meaningful when sourced from stock (a source item), since a bought or
// made-item source has no separate "material" field to disagree with.
const materialMismatch = computed(() => {
  if (props.sourceItem?.kind !== 'source') return false
  const expected = props.lot.made_item_material
  const actual = props.sourceItem.item.material
  if (!expected || !actual) return false
  return expected.trim().toLowerCase() !== actual.trim().toLowerCase()
})

const bought = computed(() => (props.sourceItem?.kind === 'bought' ? props.sourceItem.item : null))
const source = computed(() => (props.sourceItem?.kind === 'source' ? props.sourceItem.item : null))
const made = computed(() => (props.sourceItem?.kind === 'made' ? props.sourceItem.item : null))

// Present on all three catalogue types.
const common = computed(() => {
  const item = props.sourceItem?.item
  if (!item) return null
  return {
    status: item.status,
    note: item.note,
    publicId: item.public_id,
    archived: item.archived,
    successorItemId: item.successor_item_id,
  }
})

// Source items carry only an approver_id.
const approver = computed(() => {
  const id = source.value?.approver_id ?? null
  return id === null ? null : (usersStore.getById(id) ?? null)
})

const weblink = computed(() => bought.value?.weblink ?? made.value?.weblink ?? null)

// A weblink becomes a link only when it is an absolute http(s) URL; any other stored value shows as text.
const weblinkHref = computed(() => safeHref(weblink.value))

const madeProcesses = computed(() =>
  made.value ? (made.value.processes ?? []).map((p) => localizeLabel(p.fabrication_method_name)).join(', ') : '',
)
</script>

<template>
  <Panel
    :header="t('production.lots.detail.record.source.title')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <div v-if="hasNothingToShow" class="empty-note">
      {{ t('production.lots.detail.record.source.none') }}
    </div>

    <div class="source-layout">
      <!-- Everything above LotRecordMeta scrolls; the meta footer is a
           sibling so it stays pinned to the card's bottom edge. -->
      <div class="card-scroll-body">
        <div v-if="sourceItem" class="detail-grid">
          <div class="field field-wide">
            <span class="field-label">{{ t('production.lots.detail.record.source.item') }}</span>
            <span
              class="field-value field-link"
              role="button"
              tabindex="0"
              @click="$emit('view-source-item')"
              @keydown.enter="$emit('view-source-item')"
              >{{ lot.source_label }}</span
            >
            <i
              v-if="materialMismatch"
              class="mdi mdi-alert material-mismatch-warning"
              v-tooltip.bottom="
                t('production.lots.detail.rawMaterial.materialMismatchTooltip', {
                  expected: lot.made_item_material,
                  actual: source?.material ?? '',
                })
              "
            />
            <span v-if="lot.source_sublabel" class="field-sublabel">{{ lot.source_sublabel }}</span>
          </div>

          <!-- ── Bought item ──────────────────────────────────────────── -->
          <template v-if="bought">
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.partNumber')
              }}</span>
              <span class="field-value">{{ bought.part_number ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.articleName')
              }}</span>
              <span class="field-value">{{ bought.article_name }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.manufacturer')
              }}</span>
              <span class="field-value">{{
                bought.manufacturer_name || getEmptyPlaceholder()
              }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.orderCode1')
              }}</span>
              <span class="field-value">{{ bought.order_code_1 || getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.orderCode2')
              }}</span>
              <span class="field-value">{{ bought.order_code_2 ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.source.gtin') }}</span>
              <span class="field-value">{{ bought.gtin ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.source.ean') }}</span>
              <span class="field-value">{{ bought.ean ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.tariffNumber')
              }}</span>
              <span class="field-value">{{ bought.tariff_number ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.source.mass') }}</span>
              <span class="field-value">{{ formatDecimal(bought.mass) }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.dataSource')
              }}</span>
              <span class="field-value">{{
                bought.data_source
                  ? t(`boughtItems.catalogue.dataSources.${bought.data_source}`)
                  : getEmptyPlaceholder()
              }}</span>
            </div>
            <div v-if="bought.article_groups?.length" class="field field-wide">
              <span class="field-label">{{
                t('production.lots.detail.record.source.articleGroups')
              }}</span>
              <div class="groups">
                <LabelTag
                  v-for="group in bought.article_groups"
                  :key="group.id"
                  :label="group"
                />
              </div>
            </div>
          </template>

          <!-- ── Source item (stock) ────────────────────────────────────── -->
          <template v-else-if="source">
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.source.type') }}</span>
              <span class="field-value">{{ localizeLabel(source.type_name) }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.material')
              }}</span>
              <span class="field-value">{{ source.material }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.dimension')
              }}</span>
              <span class="field-value">{{ source.dimension ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.source.mass') }}</span>
              <span class="field-value">{{ formatDecimal(source.mass) }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.manufacturer')
              }}</span>
              <span class="field-value">{{
                source.manufacturer_name || getEmptyPlaceholder()
              }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.approver')
              }}</span>
              <UserAvatarPreview :user="approver" />
            </div>
          </template>

          <!-- ── Made item (rework / alteration source) ───────────────── -->
          <template v-else-if="made">
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.partNumber')
              }}</span>
              <span class="field-value">{{ madeItemLabel(made.part_number, made.revision) }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.articleName')
              }}</span>
              <span class="field-value">{{ made.article_name }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.revision')
              }}</span>
              <span class="field-value">{{ made.revision }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.revisionDate')
              }}</span>
              <span class="field-value">{{ made.revision_date ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.material')
              }}</span>
              <span class="field-value">{{ made.material ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.source.mass') }}</span>
              <span class="field-value">{{ formatDecimal(made.mass) }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.baseSize')
              }}</span>
              <span class="field-value">{{ made.base_size ?? getEmptyPlaceholder() }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.dataSource')
              }}</span>
              <span class="field-value">{{
                made.data_source
                  ? t(`madeItems.catalogue.dataSources.${made.data_source}`)
                  : getEmptyPlaceholder()
              }}</span>
            </div>
            <div v-if="made.revision_note" class="field field-wide">
              <span class="field-label">{{
                t('production.lots.detail.record.source.revisionNote')
              }}</span>
              <span class="field-value field-multiline">{{ made.revision_note }}</span>
            </div>
            <div v-if="made.source_label" class="field field-wide">
              <span class="field-label">{{
                t('production.lots.detail.record.source.ownSource')
              }}</span>
              <span class="field-value"
                >{{ made.source_label }}
                <span v-if="made.source_sublabel" class="field-sublabel">{{
                  made.source_sublabel
                }}</span></span
              >
            </div>
            <div v-if="madeProcesses" class="field field-wide">
              <span class="field-label">{{
                t('production.lots.detail.record.source.processes')
              }}</span>
              <span class="field-value">{{ madeProcesses }}</span>
            </div>
            <div v-if="made.article_groups?.length" class="field field-wide">
              <span class="field-label">{{
                t('production.lots.detail.record.source.articleGroups')
              }}</span>
              <div class="groups">
                <LabelTag
                  v-for="group in made.article_groups"
                  :key="group.id"
                  :label="group"
                />
              </div>
            </div>
          </template>

          <!-- ── Shared across all three catalogue types ──────────────── -->
          <template v-if="common">
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.status')
              }}</span>
              <Tag
                :value="t(`production.lots.detail.record.source.statusValues.${common.status}`)"
                :severity="catalogueStatusSeverity[common.status]"
              />
            </div>
            <div v-if="common.successorItemId !== null" class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.source.successor')
              }}</span>
              <span class="field-value">#{{ common.successorItemId }}</span>
            </div>
            <div v-if="weblink" class="field field-wide">
              <span class="field-label">{{
                t('production.lots.detail.record.source.weblink')
              }}</span>
              <a
                v-if="weblinkHref"
                :href="weblinkHref"
                target="_blank"
                rel="noopener noreferrer"
                class="field-value field-link field-break"
                >{{ weblink }}</a
              >
              <span v-else class="field-value field-break">{{ weblink }}</span>
            </div>
            <div class="field field-wide">
              <span class="field-label">{{ t('production.lots.detail.record.source.note') }}</span>
              <span class="field-value field-multiline">{{
                common.note || getEmptyPlaceholder()
              }}</span>
            </div>
            <div class="field field-wide">
              <span class="field-label">{{
                t('production.lots.detail.record.source.publicId')
              }}</span>
              <span
                class="field-value field-uuid field-link"
                role="button"
                tabindex="0"
                v-tooltip.top="t('common.copyUuid')"
                @click="copyToClipboard(common.publicId)"
                @keydown.enter="copyToClipboard(common.publicId)"
                >{{ common.publicId }}</span
              >
            </div>
            <div v-if="common.archived" class="field field-wide">
              <Tag :value="t('common.archivedTag')" severity="warn" icon="mdi mdi-archive-outline" />
            </div>
          </template>
        </div>

        <Divider v-if="sourceItem" />

        <LotRecordSourceDemand
          :lot="lot"
          :source-item-demand="sourceItemDemand"
          :source-item-demand-arrived="sourceItemDemandArrived"
          :summary="summary"
          :allocations="allocations"
          :source-order="sourceOrder"
          :manage-mode="manageMode"
          :can-write="canWrite"
          :can-approve="canApprove"
          @view-demand="$emit('view-demand')"
          @create-demand="$emit('create-demand')"
          @approve-source="$emit('approve-source')"
          @reject-source="$emit('reject-source')"
        />
      </div>

      <LotRecordMeta
        v-if="sourceItem"
        :creator="sourceItem.item.creator"
        :created="sourceItem.item.created"
        :changed="sourceItem.item.changed"
        :changed-by="changedBy"
      />

      <Tag
        v-else-if="lot.is_alteration"
        :value="t('production.lots.detail.rawMaterial.alteration')"
        severity="secondary"
      />

      <div v-if="manageMode" class="manage-actions">
        <span v-tooltip.top="sourceChangeBlocked || undefined">
          <Button
            icon="mdi mdi-swap-horizontal"
            size="small"
            severity="secondary"
            outlined
            :label="t('production.lots.detail.materialSource.change')"
            :disabled="sourceChangeBlocked !== ''"
            @click="$emit('change-source')"
          />
        </span>
      </div>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
// min-height: 0 so .card-scroll-body inside can shrink below its content
// and scroll, rather than forcing this wrapper to grow.
.source-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.field-multiline {
  white-space: pre-line;
}

.field-break {
  overflow-wrap: anywhere;
}

.field-uuid {
  font-family: monospace;
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.field-link {
  cursor: pointer;
  width: fit-content;
  color: inherit;
  text-decoration: none;

  &:hover {
    color: var(--p-primary-color);
    text-decoration: underline;
  }
}

.material-mismatch-warning {
  color: var(--p-orange-500);
  cursor: help;
}

.groups {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.manage-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-1);
}
</style>
