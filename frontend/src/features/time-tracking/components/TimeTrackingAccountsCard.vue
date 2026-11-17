<script setup lang="ts">
// Every account the time tracking system returns for the month, whatever
// it is (overtime, vacation, a counter), with its opening value, the
// month's change and its closing value, each written by the account's own
// format code. All accounts are always listed; the card takes the height
// of the overview next to it and the table scrolls inside it.
import { useI18n } from 'vue-i18n'

import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import { formatAccountValue } from '../utils/accountValueFormat'
import type { TimeTrackingAccountValue } from '../types/timeTrackingTypes'

defineProps<{
  accounts: TimeTrackingAccountValue[]
}>()

const { t } = useI18n()
</script>

<template>
  <SectionCard
    :title="t('timeTracking.accounts.title')"
    class="tt-card"
    data-testid="time-tracking-accounts"
  >
    <EmptyState
      v-if="accounts.length === 0"
      :message="t('timeTracking.accounts.empty')"
      icon="mdi mdi-scale-balance"
    />

    <div v-else class="tt-accounts-scroll" data-testid="time-tracking-accounts-scroll">
      <table class="tt-accounts-table">
        <thead>
          <tr>
            <th scope="col">{{ t('timeTracking.accounts.account') }}</th>
            <th scope="col" class="num">{{ t('timeTracking.accounts.opening') }}</th>
            <th scope="col" class="num">{{ t('timeTracking.accounts.change') }}</th>
            <th scope="col" class="num">{{ t('timeTracking.accounts.closing') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="account in accounts" :key="account.account_id" data-testid="time-tracking-account-row">
            <th scope="row" :title="account.short_name">{{ account.name || account.short_name }}</th>
            <td class="num">{{ formatAccountValue(account.pre, account.format) }}</td>
            <td class="num">{{ formatAccountValue(account.sum, account.format) }}</td>
            <td class="num tt-closing">{{ formatAccountValue(account.post, account.format) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </SectionCard>
</template>

<style scoped lang="scss">
// Size containment keeps the account list from adding to the height of the
// grid row, so the row is as tall as the overview card and this card
// stretches to match it. The minimum height keeps a few rows visible when
// the cards stack on a narrow screen.
.tt-card {
  min-height: 14rem;
  contain: size;
}

.tt-accounts-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.tt-accounts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th,
  td {
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--p-content-border-color);
    text-align: left;
  }

  thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background-color: var(--p-content-background);
    font-weight: 500;
    color: var(--p-text-muted-color);
    font-size: var(--font-size-xs);
  }

  tbody th {
    font-weight: 500;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
}

.tt-closing {
  font-weight: 600;
}
</style>
