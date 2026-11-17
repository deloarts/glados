<script setup lang="ts">
// The read-only field display of a bought item, shared by the detail
// dialog's view mode and the detail page's Item card.
import { computed, inject } from 'vue'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@/core/composables/useClipboard'
import { RouterLink, routerKey } from 'vue-router'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatDateTimeOrDash } from '@/core/utils/dates'
import { safeHref } from '@/shared/utils/isSafeHttpUrl'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import PdmPreviewBadge from '@/shared/pdm-preview/PdmPreviewBadge.vue'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'
import { catalogueStatusTagSeverity, pdmSyncStateSeverity } from '@/shared/utils/catalogueStatus'

// The dialog hides the meta block, keeping its own footer copy, and the page
// hides the status, which its info bar already shows.
const props = withDefaults(
  defineProps<{
    item: BoughtItemResponse
    showMeta?: boolean
    showStatus?: boolean
  }>(),
  { showMeta: true, showStatus: true },
)

// Injected with a default, since this also mounts without a router; the
// successor link then degrades to plain text.
const router = inject(routerKey, null)

const { t } = useI18n()
const { copyIfPresent } = useClipboard()
const pdmPreviewStore = usePdmPreviewStore()

const pdmPreviewNewer = computed(() => pdmPreviewStore.isNewer('bought', props.item.public_id))

// A weblink becomes a link only when it is an absolute http(s) URL; any other stored value shows as text.
const weblinkHref = computed(() => safeHref(props.item.weblink))
</script>

<template>
  <div class="detail-top">
    <Tag
      v-if="showStatus"
      :value="t(`boughtItems.catalogue.status.${item.status}`)"
      :severity="catalogueStatusTagSeverity(item.status)"
    />
    <div v-if="item.article_groups?.length" class="groups">
      <LabelTag
        v-for="group in item.article_groups"
        :key="group.id"
        :label="group"
      />
    </div>
    <LabelTag :label="item.product_family" />
    <Tag
      v-if="item.edp_part_id"
      :value="t('boughtItems.catalogue.edpLinked', { id: item.edp_part_id })"
      icon="mdi mdi-database-check-outline"
      severity="secondary"
      data-testid="bought-item-edp-linked"
    />
  </div>

  <Divider />

  <div class="detail-grid">
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.id') }}</span>
      <div class="field-value-row">
        <span class="field-value">#{{ item.id }}</span>
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.id)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.dataSource') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ t(`boughtItems.catalogue.dataSources.${item.data_source}`) }}</span>
        <Tag
          v-if="item.pdm_sync_state"
          :value="t(`boughtItems.catalogue.pdmSyncStates.${item.pdm_sync_state}`)"
          :severity="pdmSyncStateSeverity(item.pdm_sync_state)"
        />
        <PdmPreviewBadge v-if="pdmPreviewNewer" :preview="pdmPreviewNewer" />
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(t(`boughtItems.catalogue.dataSources.${item.data_source}`))"
        />
      </div>
    </div>
    <div v-if="item.pdm_file_id !== null" class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.pdmFileVersion') }}</span>
      <span class="field-value">{{ item.pdm_file_version ?? getEmptyPlaceholder() }}</span>
    </div>
    <div v-if="item.pdm_file_id !== null" class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.pdmSyncedAt') }}</span>
      <span class="field-value">{{ formatDateTimeOrDash(item.pdm_synced_at) }}</span>
    </div>
    <div class="field field-wide">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.articleName') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.article_name }}</span>
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.article_name)"
        />
      </div>
    </div>
    <div v-if="item.successor_item_id" class="field field-wide">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.successorItem') }}</span>
      <div class="field-value-row">
        <RouterLink
          v-if="router"
          :to="`/catalogue/bought-items/${item.successor_item_id}`"
          class="field-link"
          >#{{ item.successor_item_id }}</RouterLink
        >
        <span v-else class="field-value">#{{ item.successor_item_id }}</span>
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.successor_item_id)"
        />
      </div>
    </div>

    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.orderCode1') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.order_code_1 }}</span>
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.order_code_1)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.orderCode2') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.order_code_2 ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.order_code_2"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.order_code_2)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.manufacturer') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.manufacturer_name }}</span>
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.manufacturer_name)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.partNumber') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.part_number ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.part_number"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.part_number)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.revision') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.revision ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.revision"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.revision)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.gtin') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.gtin ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.gtin"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.gtin)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.ean') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.ean ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.ean"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.ean)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.tariffNumber') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.tariff_number ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.tariff_number"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.tariff_number)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.mass') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.mass ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.mass !== null && item.mass !== undefined"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.mass)"
        />
      </div>
    </div>
    <div v-if="item.weblink" class="field field-wide">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.weblink') }}</span>
      <div class="field-value-row">
        <a
          v-if="weblinkHref"
          :href="weblinkHref"
          target="_blank"
          rel="noopener noreferrer"
          class="field-link"
          >{{ item.weblink }}</a
        >
        <span v-else class="field-value">{{ item.weblink }}</span>
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.weblink)"
        />
      </div>
    </div>
    <div v-if="item.note" class="field field-wide">
      <span class="field-label">{{ t('boughtItems.catalogue.columns.note') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.note }}</span>
        <Button
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.note)"
        />
      </div>
    </div>
  </div>

  <template v-if="showMeta">
    <Divider />

    <div class="detail-footer-meta">
      <div class="meta-item">
        <UserAvatarPreview :user="item.creator" />
      </div>
      <div class="meta-item">
        <span class="field-label">{{ t('boughtItems.catalogue.columns.created') }}</span>
        <span class="field-value">{{ item.created }}</span>
      </div>
      <div v-if="item.changed" class="meta-item">
        <span class="field-label">{{ t('boughtItems.catalogue.columns.changed') }}</span>
        <span class="field-value">{{ item.changed }}</span>
      </div>
    </div>
  </template>
</template>

<style scoped lang="scss">
.detail-top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.groups {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3) var(--space-5);
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-value-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.copy-btn {
  width: 1.6rem;
  height: 1.6rem;
  padding: 0;
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.copy-btn :deep(.p-button-icon) {
  font-size: var(--font-size-sm);
}

.field-link {
  font-size: var(--font-size-sm);
  color: var(--p-primary-color);
  word-break: break-all;
  min-width: 0;
}

.detail-footer-meta {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
