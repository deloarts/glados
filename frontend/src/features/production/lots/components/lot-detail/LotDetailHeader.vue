<script setup lang="ts">
// Header row of the lot dialog: state tags on the left, actions on the
// right. The page variant renders the same actions in its own bars. Each
// action shows while the lot's actions offer it.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { hasAction, offersAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useLotPrintMenu } from '../../composables/useLotPrintMenu'

import type { LotStateSignal } from '../../utils/lotStateSummary'
import type { LotStatus } from '../../../types/productionLotsResponse'
import type { LotPrintClassifier } from '../lots-table/useLotPrinting'

const props = withDefaults(
  defineProps<{
    status: LotStatus
    /** The lot's actions, from its response. */
    actions?: readonly string[]
    /** The lot's blocked actions with the permission each lacks, from its response. */
    blockedActions?: Readonly<Record<string, string>>
    stateSignals: LotStateSignal[]
    canWrite: boolean
    canManage: boolean
    manageMode: boolean
    // A lot without an internal or mixed position has nothing to scrap, so the
    // button is hidden.
    canScrapPosition?: boolean
    canScrap?: boolean
    canPrint?: boolean
    // Scrap tags only exist for a lot that has scrapped something.
    hasScrap?: boolean
    isPrinting?: (classifier: LotPrintClassifier) => boolean
  }>(),
  {
    actions: () => [],
    blockedActions: () => ({}),
    canScrapPosition: false,
    canScrap: false,
    canPrint: false,
    hasScrap: false,
    isPrinting: () => false,
  },
)

const emit = defineEmits<{
  print: [classifier: LotPrintClassifier]
  report: []
  'toggle-manage': []
  'open-hold': []
  resume: []
  'open-force-status': [action: 'complete' | 'cancel']
  'open-scrap': []
}>()

const offers = computed(() => ({ actions: props.actions, blocked_actions: props.blockedActions }))

const { t } = useI18n()
// canWrite is write:lots and canScrap write:production_orders; without them
// the lot's actions stay visible, disabled and naming the missing permission.
const { missing, missingForAction } = useMissingPermission()
const writeBlocked = computed(() => (props.canWrite ? '' : missing(Permission.WRITE_LOTS)))
const scrapBlocked = computed(() =>
  props.canScrap ? '' : missing(Permission.WRITE_PRODUCTION_ORDERS),
)

const { printMenuItems } = useLotPrintMenu({
  canPrint: () => props.canPrint,
  hasScrap: () => props.hasScrap,
  isPrinting: (classifier) => props.isPrinting(classifier),
  print: (classifier) => emit('print', classifier),
  openReport: () => emit('report'),
})
</script>

<template>
  <div class="lot-header">
    <div class="lot-header-info">
      <!-- Only the waiting-on summary stays here; lot facts live on the Lot card. -->
      <div v-if="stateSignals.length" class="lot-header-state">
        <Tag
          v-for="signal in stateSignals"
          :key="signal.id"
          :value="t(signal.labelKey, signal.labelParams ?? {})"
          :severity="signal.severity"
          :icon="signal.icon"
          v-tooltip.top="
            signal.tooltipKey
              ? t(signal.tooltipKey, signal.tooltipParams ?? signal.labelParams ?? {})
              : undefined
          "
        />
      </div>
    </div>
    <div class="lot-header-actions">
      <!-- Docket is the everyday print, so it is the button itself; the
           label and scrap tag sit behind the dropdown. -->
      <SplitButton
        v-if="canPrint"
        :label="t('production.lots.detail.print.docket')"
        icon="mdi mdi-printer-outline"
        severity="secondary"
        outlined
        :model="printMenuItems"
        :loading="isPrinting('lot_docket')"
        @click="emit('print', 'lot_docket')"
      />
      <Button
        v-else
        :label="t('production.lots.report.print')"
        icon="mdi mdi-file-certificate-outline"
        severity="secondary"
        outlined
        data-testid="lot-inspection-report"
        @click="emit('report')"
      />
      <span v-tooltip.top="writeBlocked || undefined">
        <Button
          :label="
            manageMode ? t('production.lots.detail.manage.exit') : t('production.lots.detail.manage.enter')
          "
          :icon="manageMode ? 'mdi mdi-eye-outline' : 'mdi mdi-cog-outline'"
          severity="secondary"
          :outlined="!manageMode"
          :disabled="!canWrite"
          data-testid="lot-header-manage-toggle"
          @click="emit('toggle-manage')"
        />
      </span>
      <span v-if="hasAction(offers, 'hold')" v-tooltip.top="writeBlocked || undefined">
        <Button
          :label="t('production.lots.detail.hold')"
          icon="mdi mdi-pause-circle-outline"
          severity="warn"
          outlined
          :disabled="!canWrite"
          @click="emit('open-hold')"
        />
      </span>
      <span v-if="hasAction(offers, 'resume')" v-tooltip.top="writeBlocked || undefined">
        <Button
          :label="t('production.lots.detail.resume')"
          icon="mdi mdi-play-circle-outline"
          :disabled="!canWrite"
          @click="emit('resume')"
        />
      </span>
      <span
        v-if="canScrapPosition && hasAction(offers, 'scrap')"
        v-tooltip.top="scrapBlocked || undefined"
      >
        <Button
          :label="t('production.lots.detail.scrapPieces')"
          icon="mdi mdi-delete-alert-outline"
          severity="danger"
          outlined
          :disabled="!canScrap"
          @click="emit('open-scrap')"
        />
      </span>
      <span
        v-if="offersAction(offers, 'force_complete')"
        v-tooltip.top="writeBlocked || missingForAction(offers, 'force_complete') || undefined"
      >
        <Button
          :label="t('production.lots.detail.complete')"
          icon="mdi mdi-check-circle-outline"
          severity="success"
          outlined
          :disabled="!hasAction(offers, 'force_complete') || !canWrite"
          @click="emit('open-force-status', 'complete')"
        />
      </span>
      <span
        v-if="offersAction(offers, 'cancel')"
        v-tooltip.top="writeBlocked || missingForAction(offers, 'cancel') || undefined"
      >
        <Button
          :label="t('production.lots.detail.cancel')"
          icon="mdi mdi-close-circle-outline"
          severity="danger"
          outlined
          :disabled="!hasAction(offers, 'cancel') || !canWrite"
          @click="emit('open-force-status', 'cancel')"
        />
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.lot-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
}

.lot-header-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1;
}

.lot-header-state {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.lot-header-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}
</style>
