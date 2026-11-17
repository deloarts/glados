<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'
import LotDetailContent from '../components/LotDetailContent.vue'
import { Permission } from '@/core/auth/permissions'
import { hasAction, offersAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { lotStatusSeverity } from '../../utils/lotStatus'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useLotPrintMenu } from '../composables/useLotPrintMenu'
import { useMadeItemLabel } from '@/features/made-items'
import { usePageTitle } from '@/core/composables/usePageTitle'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const lotDialog = useLotDetail()
const { format: madeItemLabel } = useMadeItemLabel()

// A computed, since navigating lot to lot keeps the route and must reload.
const lotId = computed(() => Number(route.params.id))

const content = ref<InstanceType<typeof LotDetailContent> | null>(null)

const lot = computed(() => content.value?.lot ?? null)
const loading = computed(() => content.value?.loading ?? false)
const stateSignals = computed(() => content.value?.stateSignals ?? [])
const canWrite = computed(() => content.value?.canWrite ?? false)
const canScrap = computed(() => content.value?.canScrap ?? false)
const canScrapPosition = computed(() => content.value?.canScrapPosition ?? false)
const canPrint = computed(() => content.value?.canPrint ?? false)
const manageMode = computed(() => content.value?.manageMode ?? false)
// The lot's actions stay visible without the rights for them, disabled and
// naming the missing permission.
const { missing, missingForAction } = useMissingPermission()
// Ending a lot needs write:lots like any lot change, and manage:lots on top.
const lotWriteBlocked = computed(() => (canWrite.value ? '' : missing(Permission.WRITE_LOTS)))
const writeBlocked = computed(() => (canWrite.value ? '' : missing(Permission.WRITE_LOTS)))
const scrapBlocked = computed(() =>
  canScrap.value ? '' : missing(Permission.WRITE_PRODUCTION_ORDERS),
)

const { printMenuItems } = useLotPrintMenu({
  canPrint: () => canPrint.value,
  hasScrap: () => (lot.value?.quantity_scrapped ?? 0) > 0,
  isPrinting: (classifier) => content.value?.isPrinting(classifier) ?? false,
  print: (classifier) => void content.value?.printLot(classifier),
  openReport: () => content.value?.openInspectionReport(),
})

// The app-wide lot dialog can open over this page and clears the shared
// store on close, so the page reloads when it closes.
watch(lotDialog.visible, (isVisible) => {
  if (!isVisible) void content.value?.reload()
})

const pageHeading = computed(() => (lot.value ? lot.value.lot_number : t('pageTitles.lotDetail')))
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })
</script>

<template>
  <PageLayout wrap-menu>
    <template #info>
      <InfoBar>
        <template v-if="lot">
          <span class="lot-number">{{ lot.lot_number }}</span>
          <span class="info-sep" />
          <Tag
            :value="t(`production.lots.status.${lot.status}`)"
            :severity="lotStatusSeverity[lot.status]"
          />
          <span class="info-sep" />
          <span class="info-muted">{{ madeItemLabel(lot.made_item_part_number, lot.made_item_revision) }}</span>
          <span class="info-sep" />
          <span class="info-muted">{{ lot.made_item_article_name }}</span>

          <template v-if="stateSignals.length">
            <span class="info-sep" />
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
          </template>
        </template>
        <template v-else-if="loading">
          <Skeleton width="7rem" height="1.5rem" border-radius="1rem" />
          <Skeleton width="5.5rem" height="1.5rem" border-radius="1rem" />
        </template>
      </InfoBar>
    </template>

    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            icon="mdi mdi-arrow-left"
            :label="t('production.lots.detail.back')"
            severity="contrast"
            text
            @click="router.push('/production/lots')"
          />

          <template v-if="lot">
            <Divider layout="vertical" />

            <SplitButton
              v-if="canPrint"
              :label="t('production.lots.detail.print.docket')"
              icon="mdi mdi-printer-outline"
              severity="contrast"
              text
              :model="printMenuItems"
              :loading="content?.isPrinting('lot_docket') ?? false"
              @click="content?.printLot('lot_docket')"
            />
            <Button
              v-else
              :label="t('production.lots.report.print')"
              icon="mdi mdi-file-certificate-outline"
              severity="contrast"
              text
              data-testid="lot-inspection-report"
              @click="content?.openInspectionReport()"
            />
            <span v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="
                  manageMode
                    ? t('production.lots.detail.manage.exit')
                    : t('production.lots.detail.manage.enter')
                "
                :icon="manageMode ? 'mdi mdi-eye-outline' : 'mdi mdi-cog-outline'"
                severity="contrast"
                :text="!manageMode"
                :disabled="!canWrite"
                data-testid="lot-manage-toggle"
                @click="content?.toggleManage()"
              />
            </span>

            <Divider layout="vertical" />

            <span v-if="hasAction(lot, 'hold')" v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('production.lots.detail.hold')"
                icon="mdi mdi-pause-circle-outline"
                severity="contrast"
                text
                :disabled="!canWrite"
                @click="content?.openHold()"
              />
            </span>
            <span v-if="hasAction(lot, 'resume')" v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('production.lots.detail.resume')"
                icon="mdi mdi-play-circle-outline"
                severity="contrast"
                text
                :disabled="!canWrite"
                @click="content?.resumeLot()"
              />
            </span>
            <span
              v-if="canScrapPosition && hasAction(lot, 'scrap')"
              v-tooltip.bottom="scrapBlocked || undefined"
            >
              <Button
                :label="t('production.lots.detail.scrapPieces')"
                icon="mdi mdi-delete-alert-outline"
                severity="contrast"
                text
                :disabled="!canScrap"
                @click="content?.openScrap()"
              />
            </span>
            <span
              v-if="offersAction(lot, 'force_complete')"
              v-tooltip.bottom="lotWriteBlocked || missingForAction(lot, 'force_complete') || undefined"
            >
              <Button
                :label="t('production.lots.detail.complete')"
                icon="mdi mdi-check-circle-outline"
                severity="contrast"
                text
                :disabled="!hasAction(lot, 'force_complete') || !canWrite"
                @click="content?.openForceStatus('complete')"
              />
            </span>
            <span
              v-if="offersAction(lot, 'cancel')"
              v-tooltip.bottom="lotWriteBlocked || missingForAction(lot, 'cancel') || undefined"
            >
              <Button
                :label="t('production.lots.detail.cancel')"
                icon="mdi mdi-close-circle-outline"
                severity="contrast"
                text
                :disabled="!hasAction(lot, 'cancel') || !canWrite"
                @click="content?.openForceStatus('cancel')"
              />
            </span>
          </template>
        </template>
        <template #handbook>
          <ShareButton :public-id="lot?.public_id" />
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <template #views>
      <ViewsBar
        id-prefix="lot-detail"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="false"
        @sync="content?.reload()"
      />
    </template>

    <LotDetailContent ref="content" :lot-id="lotId" variant="page" />
  </PageLayout>
</template>

<style scoped lang="scss">
.lot-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}
</style>
