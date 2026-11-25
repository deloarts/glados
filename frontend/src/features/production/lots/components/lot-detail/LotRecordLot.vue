<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useClipboard } from '@/core/composables/useClipboard'
import { formatISODateTime } from '@/core/utils/dates'
import { formatDecimal } from '@/core/utils/numbers'
import { lotPrioritySeverity, lotStatusSeverity } from '../../../utils/lotStatus'
import { useChangedByUser } from '../../composables/useChangedByUser'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import LotRecordMeta from './LotRecordMeta.vue'

import type { LotResponse } from '../../../types/productionLotsResponse'
import type { LotChangelogEntry } from '../../types/lotChangelogResponse'
import type { SourceItemDemandStatus } from '@/features/source-items'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'
import { supplierMaterialTag } from '../../utils/lotSourceEligibility'

const props = withDefaults(
  defineProps<{
    lot: LotResponse
    changelog: LotChangelogEntry[]
    variant?: 'dialog' | 'page'
  }>(),
  { variant: 'dialog' },
)

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const router = useRouter()
// The dialog variant swaps the singleton dialog's lot; the page variant
// navigates instead of stacking the dialog on itself.
const { openLotDetail } = useLotDetail()

function switchTo(lotId: number): void {
  if (props.variant === 'page') {
    void router.push(`/production/lots/${lotId}`)
    return
  }
  openLotDetail(lotId)
}

const { resolve } = useChangedByUser()
const changedBy = computed(() => resolve(props.changelog))

// Empty when the lot has no raw-material demand.
const demandStatus = computed(() =>
  props.lot.demand_status ? (props.lot.demand_status as SourceItemDemandStatus) : null,
)

const supplierTag = computed(() => supplierMaterialTag(props.lot))
const remaining = computed(() => props.lot.quantity - props.lot.quantity_completed)
const quantityScrapped = computed(() => props.lot.quantity_scrapped ?? 0)
</script>

<template>
  <Panel
    :header="t('production.lots.detail.record.lot.title')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <div class="lot-layout">
      <!-- The footer scrolls with the fields; margin-top: auto keeps it at the
           bottom when the fields are short. -->
      <div class="card-scroll-body card-scroll-body--with-meta">
        <div class="detail-grid">
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.lot.lotNumber') }}</span>
            <span class="field-value">{{ lot.lot_number }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.lot.status') }}</span>
            <Tag
              :value="t(`production.lots.status.${lot.status}`)"
              :severity="lotStatusSeverity[lot.status]"
            />
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.lot.priority') }}</span>
            <Tag
              :value="t(`production.lots.priority.${lot.priority}`)"
              :severity="lotPrioritySeverity[lot.priority]"
            />
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.lot.quantity') }}</span>
            <span class="field-value">
              {{ formatDecimal(lot.quantity_completed) }} / {{ formatDecimal(lot.quantity) }}
              <span class="field-sublabel"
                >({{
                  t('production.lots.detail.record.lot.remaining', {
                    count: formatDecimal(remaining),
                  })
                }})</span
              >
              <span v-if="quantityScrapped > 0" class="field-sublabel field-sublabel-scrap">{{
                t('production.lots.detail.record.lot.quantityScrapped', {
                  count: formatDecimal(quantityScrapped),
                })
              }}</span>
            </span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.lot.requiredDelivery')
            }}</span>
            <span class="field-value">{{
              lot.required_delivery_date ?? getEmptyPlaceholder()
            }}</span>
          </div>
          <div v-if="lot.completed_at" class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.lot.completedAt')
            }}</span>
            <span class="field-value">{{ formatISODateTime(lot.completed_at) }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.lot.demandStatus')
            }}</span>
            <Tag
              v-if="demandStatus"
              :value="t(`sourceItems.demands.status.${demandStatus}`)"
              :severity="DEMAND_STATUS_SEVERITY[demandStatus]"
            />
            <!-- The raw-material demand only exists once the source is approved,
                 so a pending approval is not the same as needing no material. -->
            <Tag
              v-else-if="lot.source_approval_status === 'pending'"
              :value="t('production.lots.detail.record.lot.approvalPending')"
              severity="warn"
            />
            <!-- A supplier brings the material of the first position. -->
            <Tag
              v-else-if="supplierTag"
              :value="t(supplierTag.labelKey)"
              :severity="supplierTag.severity"
              v-tooltip.top="t(supplierTag.tooltipKey)"
            />
            <span v-else class="field-value">{{
              t('production.lots.detail.record.lot.noDemand')
            }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.lot.alteration') }}</span>
            <span class="field-value">{{
              lot.is_alteration
                ? t('production.lots.detail.record.lot.alterationYes')
                : t('production.lots.detail.record.lot.alterationNo')
            }}</span>
          </div>
          <div v-if="lot.origin_lot_id" class="field field-wide">
            <span
              class="field-value field-link"
              role="button"
              tabindex="0"
              @click="switchTo(lot.origin_lot_id!)"
              @keydown.enter="switchTo(lot.origin_lot_id!)"
              >{{
                t(`production.lots.detail.record.lot.origin.${lot.origin_disposition}`, {
                  lotNumber: lot.origin_lot_number,
                })
              }}</span
            >
          </div>
          <div v-if="lot.follow_up_lots?.length" class="field field-wide">
            <span
              v-for="followUp in lot.follow_up_lots"
              :key="followUp.id"
              class="field-value field-link follow-up-line"
              role="button"
              tabindex="0"
              @click="switchTo(followUp.id)"
              @keydown.enter="switchTo(followUp.id)"
              >{{
                t(`production.lots.detail.record.lot.followUp.${followUp.disposition}`, {
                  lotNumber: followUp.lot_number,
                  quantity: formatDecimal(followUp.quantity),
                })
              }}</span
            >
          </div>
          <div class="field">
            <span class="field-label">{{ t('production.lots.detail.record.lot.publicId') }}</span>
            <span
              class="field-value field-uuid field-link"
              role="button"
              tabindex="0"
              v-tooltip.top="t('common.copyUuid')"
              @click="copyToClipboard(lot.public_id)"
              @keydown.enter="copyToClipboard(lot.public_id)"
              >{{ lot.public_id }}</span
            >
          </div>
          <div class="field field-wide">
            <span class="field-label">{{ t('production.lots.detail.record.lot.note') }}</span>
            <span class="field-value field-note">{{ lot.note || getEmptyPlaceholder() }}</span>
          </div>
        </div>

        <LotRecordMeta
          :creator="lot.creator"
          :created="lot.created.slice(0, 10)"
          :changed="lot.changed?.slice(0, 10) ?? null"
          :changed-by="changedBy"
        />
      </div>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
// min-height: 0 so the scroll body can shrink and scroll.
.lot-layout {
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

.field-sublabel-scrap {
  color: var(--p-red-500);
  font-weight: 600;
}

.field-note {
  white-space: pre-line;
}

.field-uuid {
  font-family: monospace;
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.field-link {
  cursor: pointer;

  &:hover {
    color: var(--p-primary-color);
    text-decoration: underline;
  }
}

.follow-up-line {
  display: block;
}
</style>
