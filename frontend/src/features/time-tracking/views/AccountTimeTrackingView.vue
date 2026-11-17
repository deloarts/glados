<script setup lang="ts">
// The Time Tracking account tab: the signed-in user's own attendance data,
// fetched live from the time tracking system. It is the only place that
// fetches that data, and only on opening the tab, switching the month,
// pressing reload, or opening the year section. Without usable credentials
// it shows an empty state pointing to My Account and fetches nothing; with
// an outdated consent it asks for consent first, confirming it re-saves the
// stored credentials under the new consent and then loads the month.
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { HelpButton } from '@/shared/help'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import AsyncChunkLoading from '@/shared/components/layout/AsyncChunkLoading.vue'
import TimeTrackingConsentDialog from '../components/TimeTrackingConsentDialog.vue'
import TimeTrackingTotalsCard from '../components/TimeTrackingTotalsCard.vue'
import TimeTrackingAccountsCard from '../components/TimeTrackingAccountsCard.vue'
import TimeTrackingMonthTable from '../components/TimeTrackingMonthTable.vue'
import TimeTrackingDailyChart from '../components/TimeTrackingDailyChart.vue'
import TimeTrackingBalanceChart from '../components/TimeTrackingBalanceChart.vue'
import TimeTrackingWeekdayStats from '../components/TimeTrackingWeekdayStats.vue'
import TimeTrackingKpiTiles from '../components/TimeTrackingKpiTiles.vue'
import TimeTrackingYearChart from '../components/TimeTrackingYearChart.vue'
import { saveMyTimeTrackingAccount } from '../api/timeTrackingApi'
import { useTimeTrackingAccountStore } from '../stores/timeTrackingAccountStore'
import { useTimeTrackingAvailability } from '../composables/useTimeTrackingAvailability'
import { useTimeTrackingData } from '../composables/useTimeTrackingData'
import { isCredentialStateError, timeTrackingErrorMessage } from '../utils/timeTrackingErrors'
import { monthLabel, shiftMonth, yearOfMonth } from '../utils/timeTrackingMonth'
import { countedDays } from '../utils/timeTrackingStats'

const { t } = useI18n()
const toast = useAppToast()
const store = useTimeTrackingAccountStore()
const { providerName } = useTimeTrackingAvailability()

const data = useTimeTrackingData({ onCredentialStateError: () => void store.refresh() })
const {
  currentMonth,
  selectedMonth,
  month,
  live,
  monthLoading,
  monthError,
  canReload,
  canGoNext,
  cutoffDate,
  todayDate,
  runningDate,
  year,
  yearLoading,
  yearError,
} = data

const invalidReason = computed(() => store.account?.time_tracking_credentials_invalid_reason ?? null)
const credentialsValid = computed(() => store.credentialsValid)

// ── Consent ─────────────────────────────────────────────────────────────

const consentDeclined = ref(false)
const confirmingConsent = ref(false)
const consentVisible = computed(
  () =>
    store.loaded &&
    invalidReason.value === 'consent_outdated' &&
    !consentDeclined.value &&
    !confirmingConsent.value,
)

async function onConsentConfirm(): Promise<void> {
  const account = store.account
  if (!account?.time_tracking_user) return
  confirmingConsent.value = true
  try {
    const result = await saveMyTimeTrackingAccount({
      time_tracking_user: account.time_tracking_user,
      time_tracking_consent_version: account.time_tracking_consent_version,
    })
    store.setAccount(result)
  } catch (err: unknown) {
    consentDeclined.value = true
    toast.error(
      t('timeTracking.consent.saveFailed'),
      timeTrackingErrorMessage(err, t, t('timeTracking.errors.unknown')),
    )
    if (isCredentialStateError(err)) void store.refresh()
  } finally {
    confirmingConsent.value = false
  }
}

// ── Loading ─────────────────────────────────────────────────────────────

// Loads the month once the account state says the credentials are usable:
// on mount, or later after the consent was confirmed. Both paths can fire
// for the same change, so only the first one that finds nothing loaded or
// loading sends the request.
function loadIfReady(): void {
  if (store.loaded && store.credentialsValid && !month.value && !monthLoading.value) data.load()
}

onMounted(async () => {
  await store.ensureLoaded()
  loadIfReady()
})

watch(credentialsValid, (valid) => {
  if (valid) loadIfReady()
  else data.clearData()
})

const emptyMessage = computed(() => {
  const reason = invalidReason.value
  if (reason && reason !== 'missing') {
    return t(`timeTracking.empty.${reason}`, { provider: providerName.value })
  }
  return t('timeTracking.empty.missing', { provider: providerName.value })
})

const statDays = computed(() =>
  countedDays(
    (live.value?.days ?? []).filter((day) => cutoffDate.value === null || day.date <= cutoffDate.value),
    runningDate.value,
  ),
)

const monthAllowed = computed(() => month.value?.rights.month !== false)

// ── Month switcher ──────────────────────────────────────────────────────

function previousMonth(): void {
  data.goToMonth(shiftMonth(selectedMonth.value, -1))
}

function nextMonth(): void {
  if (canGoNext.value) data.goToMonth(shiftMonth(selectedMonth.value, 1))
}

// ── Year section ────────────────────────────────────────────────────────

const yearPanel = ref<string | null>(null)

function onYearPanelChange(value: unknown): void {
  const open = value === 'year' || (Array.isArray(value) && value.includes('year'))
  yearPanel.value = open ? 'year' : null
  if (open) data.openYear()
}

const yearAllowed = computed(() => year.value?.rights.year !== false)
</script>

<template>
  <PageLayout :card="false">
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('timeTracking.reload')"
            icon="mdi mdi-refresh"
            severity="contrast"
            text
            :loading="monthLoading"
            :disabled="!credentialsValid || !canReload"
            data-testid="time-tracking-reload"
            @click="data.reload()"
          />
          <Divider layout="vertical" />
          <Button
            icon="mdi mdi-chevron-left"
            severity="contrast"
            text
            :aria-label="t('timeTracking.previousMonth')"
            v-tooltip.bottom="t('timeTracking.previousMonth')"
            :disabled="!credentialsValid"
            data-testid="time-tracking-previous-month"
            @click="previousMonth"
          />
          <span class="tt-month-label" data-testid="time-tracking-month-label">
            {{ monthLabel(selectedMonth) }}
          </span>
          <Button
            icon="mdi mdi-chevron-right"
            severity="contrast"
            text
            :aria-label="t('timeTracking.nextMonth')"
            v-tooltip.bottom="t('timeTracking.nextMonth')"
            :disabled="!credentialsValid || !canGoNext"
            data-testid="time-tracking-next-month"
            @click="nextMonth"
          />
          <Button
            :label="t('timeTracking.currentMonth')"
            icon="mdi mdi-calendar-today"
            severity="contrast"
            text
            :disabled="!credentialsValid || selectedMonth === currentMonth"
            data-testid="time-tracking-current-month"
            @click="data.goToMonth(currentMonth)"
          />
        </template>
        <template #end>
          <span v-if="month" class="tt-employee">
            <i class="mdi mdi-account-clock-outline" aria-hidden="true" />
            {{ month.employee_name }}
          </span>
          <HelpButton slug="account/time-tracking" rounded />
        </template>
      </Toolbar>
    </template>

    <div class="tt-page">
      <AsyncChunkLoading v-if="!store.loaded && store.loading" />

      <div v-else-if="!credentialsValid" class="card tt-empty" data-testid="time-tracking-empty">
        <EmptyState :message="emptyMessage" icon="mdi mdi-clock-alert-outline">
          <RouterLink to="/account/me" class="tt-link" data-testid="time-tracking-open-account">
            <i class="mdi mdi-account-cog-outline" aria-hidden="true" />
            {{ t('timeTracking.empty.openAccount') }}
          </RouterLink>
        </EmptyState>
      </div>

      <template v-else>
        <Message v-if="monthError" severity="error" :closable="false" data-testid="time-tracking-error">
          {{ monthError }}
        </Message>

        <AsyncChunkLoading v-if="!month && monthLoading" />

        <div v-else-if="month && !monthAllowed" class="card tt-empty">
          <EmptyState
            :message="t('timeTracking.empty.monthNotAllowed')"
            icon="mdi mdi-lock-outline"
          />
        </div>

        <template v-else-if="month && live">
          <section class="tt-top">
            <TimeTrackingTotalsCard
              v-if="live.totals"
              :totals="live.totals"
              :today="live.today"
              :fetched-at="month.fetched_at"
            />
            <TimeTrackingAccountsCard :accounts="month.accounts" />
          </section>

          <TimeTrackingMonthTable :days="live.days" :today-date="todayDate" />

          <section class="tt-charts">
            <SectionCard :title="t('timeTracking.stats.dailyTitle')">
              <TimeTrackingDailyChart :days="live.days" :today-date="cutoffDate" />
            </SectionCard>
            <SectionCard :title="t('timeTracking.stats.balanceTitle')">
              <TimeTrackingBalanceChart :days="live.days" :today-date="cutoffDate" />
            </SectionCard>
          </section>

          <TimeTrackingKpiTiles :days="statDays" />

          <SectionCard :title="t('timeTracking.stats.weekdayTitle')">
            <TimeTrackingWeekdayStats :days="statDays" />
          </SectionCard>

          <Accordion
            v-if="month.rights.year !== false"
            :value="yearPanel"
            class="card tt-year"
            data-testid="time-tracking-year"
            @update:value="onYearPanelChange"
          >
            <AccordionPanel value="year">
              <AccordionHeader>
                {{ t('timeTracking.stats.yearTitle', { year: yearOfMonth(selectedMonth) }) }}
              </AccordionHeader>
              <AccordionContent>
                <AsyncChunkLoading v-if="yearLoading" />
                <Message v-else-if="yearError" severity="error" :closable="false">
                  {{ yearError }}
                </Message>
                <EmptyState
                  v-else-if="year && !yearAllowed"
                  :message="t('timeTracking.empty.yearNotAllowed')"
                  icon="mdi mdi-lock-outline"
                />
                <TimeTrackingYearChart v-else-if="year" :months="year.months" />
              </AccordionContent>
            </AccordionPanel>
          </Accordion>
        </template>
      </template>
    </div>

    <TimeTrackingConsentDialog
      :visible="consentVisible"
      :provider-name="providerName"
      :privacy-policy-url="store.account?.time_tracking_privacy_policy_url ?? null"
      @confirm="onConsentConfirm"
      @cancel="consentDeclined = true"
    />
  </PageLayout>
</template>

<style scoped lang="scss">
.tt-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-height: 0;
}

.tt-month-label {
  min-width: 9rem;
  text-align: center;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.tt-employee {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.tt-empty {
  height: auto;
  padding: var(--space-4);
}

.tt-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--p-primary-color);
  font-weight: 500;
}

.tt-top {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
  gap: var(--space-1);
}

.tt-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
  gap: var(--space-1);
}

.tt-year {
  height: auto;
  padding: 0;
}
</style>
