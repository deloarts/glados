<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import LotAuditEventList from './LotAuditEventList.vue'

import type { LotEventResponse } from '../../../types/productionLotsResponse'
import type { LotChangelogEntry } from '../../types/lotChangelogResponse'

defineProps<{
  events: LotEventResponse[]
  changelog: LotChangelogEntry[]
  loading: boolean
  requiredDeliveryDate: string | null
}>()

const { t } = useI18n()

// Two genuinely different records, so they get their own tabs rather than
// one concatenated list: `events` is the structured ISO 9001 trail (actor,
// entity, type), `changelog` is the lot's own free-text `changes` column.
// They overlap for lot_updated but diverge everywhere else.
const activeTab = ref('events')
</script>

<template>
  <Panel
    :header="t('production.lots.detail.audit.title')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <Tabs v-model:value="activeTab" class="audit-tabs">
      <TabList class="audit-tablist">
        <Tab value="events">{{ t('production.lots.detail.audit.tabs.events') }}</Tab>
        <Tab value="changelog">
          {{ t('production.lots.detail.audit.tabs.changelog') }}
        </Tab>
      </TabList>
      <!-- card-scroll-body is the class .record-card--scroll scrolls (see
           LotDetailContent.vue); putting it on the panels rather than the
           whole Tabs keeps the tab strip pinned, the same way the other
           cards pin their meta footer. -->
      <TabPanels class="card-scroll-body audit-panels">
        <TabPanel value="events">
          <LotAuditEventList
            :events="events"
            :loading="loading"
            :required-delivery-date="requiredDeliveryDate"
          />
        </TabPanel>
        <TabPanel value="changelog">
          <ul v-if="loading && changelog.length === 0" class="changelog-list">
            <li v-for="n in 4" :key="n" class="changelog-item">
              <Skeleton width="10rem" height="0.78rem" />
              <Skeleton width="14rem" height="0.83rem" />
            </li>
          </ul>
          <div v-else-if="changelog.length === 0" class="empty-note">
            {{ t('production.lots.detail.audit.changelogEmpty') }}
          </div>
          <ul v-else class="changelog-list">
            <li v-for="(entry, index) in changelog" :key="index" class="changelog-item">
              <div class="changelog-meta">
                <span>{{ entry.timestamp }}</span>
                <span>{{ entry.username }}</span>
              </div>
              <div class="changelog-message">{{ entry.message }}</div>
            </li>
          </ul>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </Panel>
</template>

<style scoped lang="scss">
// .record-card--scroll puts the Panel content out of flow at overflow:
// hidden and scrolls .card-scroll-body instead, so this shell has to thread
// the card's height down to the panels, otherwise the trail is simply
// clipped with nothing scrollable.
.audit-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.audit-tablist {
  flex-shrink: 0;
}

// flex/overflow come from .record-card--scroll's .card-scroll-body rule.
.audit-panels {
  padding: var(--space-3) 0 0;
}

.changelog-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.changelog-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-1);
  border-bottom: 1px solid var(--p-content-border-color);

  &:last-child {
    border-bottom: none;
  }
}

.changelog-meta {
  display: flex;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.changelog-message {
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
  // Entries from diff_changes() are multi-line bullet lists.
  white-space: pre-line;
}
</style>
