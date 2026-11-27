<script setup lang="ts">
// The read-only field display of a made item, shared by the detail dialog's
// view mode and the detail page's Item card.
import { computed, inject, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@/core/composables/useClipboard'
import { RouterLink, routerKey } from 'vue-router'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatDateTimeOrDash } from '@/core/utils/dates'
import { safeHref } from '@/shared/utils/isSafeHttpUrl'
import { getMadeItems } from '../api/getMadeItems'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { sourceItemDisplayLabel, useMadeItemLabel } from '../utils/madeItemLabel'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import PdmPreviewBadge from '@/shared/pdm-preview/PdmPreviewBadge.vue'

import type { MadeItemResponse } from '../types/madeItemsResponse'
import { catalogueStatusTagSeverity, pdmSyncStateSeverity } from '@/shared/utils/catalogueStatus'
import { useSuccessorItem } from '@/shared/composables/useSuccessorItem'
import LabelTag from '@/shared/components/labels/LabelTag.vue'

// The dialog hides the meta block, keeping its own footer copy, and the page
// hides the status, which its info bar already shows.
const props = withDefaults(
  defineProps<{
    item: MadeItemResponse
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
const madeItemsStore = useMadeItemsStore()
const pdmPreviewStore = usePdmPreviewStore()
const { format: madeItemLabel } = useMadeItemLabel()

const pdmPreviewNewer = computed(() => pdmPreviewStore.isNewer('made', props.item.public_id))

const sourceItemLabel = computed(() => sourceItemDisplayLabel(props.item))

const hasCustomerData = computed(
  () =>
    props.item.customer_id !== null ||
    Boolean(props.item.customer_part_number) ||
    Boolean(props.item.customer_revision),
)

// A weblink becomes a link only when it is an absolute http(s) URL; any other stored value shows as text.
const weblinkHref = computed(() => safeHref(props.item.weblink))

// Store cache first, else a fetch by id, re-run whenever the successor
// changes.
const { successorItem, resolveSuccessorItem } = useSuccessorItem<MadeItemResponse>({
  getById: (id) => madeItemsStore.getById(id),
  list: (params) => getMadeItems(params),
})

watch(
  () => props.item.successor_item_id,
  (id) => resolveSuccessorItem(id),
  { immediate: true },
)
</script>

<template>
  <div class="item-fields">
    <div class="detail-top">
      <Tag
        v-if="showStatus"
        :value="t(`madeItems.catalogue.status.${item.status}`)"
        :severity="catalogueStatusTagSeverity(item.status)"
      />
      <div v-if="item.article_groups?.length" class="groups">
        <LabelTag
          v-for="group in item.article_groups"
          :key="group.id"
          :label="group"
        />
      </div>
    </div>

    <div class="detail-grid">
      <div class="field">
        <span class="field-label">{{ t('madeItems.catalogue.columns.id') }}</span>
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
        <span class="field-label">{{ t('madeItems.catalogue.columns.dataSource') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ t(`madeItems.catalogue.dataSources.${item.data_source}`) }}</span>
          <Tag
            v-if="item.pdm_sync_state"
            :value="t(`madeItems.catalogue.pdmSyncStates.${item.pdm_sync_state}`)"
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
            @click="copyIfPresent(t(`madeItems.catalogue.dataSources.${item.data_source}`))"
          />
        </div>
      </div>
      <div v-if="item.pdm_file_id !== null" class="field">
        <span class="field-label">{{ t('madeItems.catalogue.columns.pdmFileVersion') }}</span>
        <span class="field-value">{{ item.pdm_file_version ?? getEmptyPlaceholder() }}</span>
      </div>
      <div v-if="item.pdm_file_id !== null" class="field">
        <span class="field-label">{{ t('madeItems.catalogue.columns.pdmSyncedAt') }}</span>
        <span class="field-value">{{ formatDateTimeOrDash(item.pdm_synced_at) }}</span>
      </div>
      <div class="field field-wide">
        <span class="field-label">{{ t('madeItems.catalogue.columns.articleName') }}</span>
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
      <div class="field">
        <span class="field-label">{{ t('madeItems.catalogue.columns.partNumber') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ madeItemLabel(item.part_number, item.revision) }}</span>
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
        <span class="field-label">{{ t('madeItems.catalogue.columns.revision') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.revision }}</span>
          <Button
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
        <span class="field-label">{{ t('madeItems.catalogue.columns.revisionDate') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.revision_date ?? getEmptyPlaceholder() }}</span>
          <Button
            v-if="item.revision_date"
            icon="mdi mdi-content-copy"
            text
            rounded
            size="small"
            class="copy-btn"
            v-tooltip.top.focus="t('common.copy')"
            :aria-label="t('common.copy')"
            @click="copyIfPresent(item.revision_date)"
          />
        </div>
      </div>
      <div v-if="item.revision_note" class="field field-wide">
        <span class="field-label">{{ t('madeItems.catalogue.columns.revisionNote') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.revision_note }}</span>
          <Button
            icon="mdi mdi-content-copy"
            text
            rounded
            size="small"
            class="copy-btn"
            v-tooltip.top.focus="t('common.copy')"
            :aria-label="t('common.copy')"
            @click="copyIfPresent(item.revision_note)"
          />
        </div>
      </div>
      <div class="field">
        <span class="field-label">{{ t('madeItems.catalogue.columns.material') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.material ?? getEmptyPlaceholder() }}</span>
          <Button
            v-if="item.material"
            icon="mdi mdi-content-copy"
            text
            rounded
            size="small"
            class="copy-btn"
            v-tooltip.top.focus="t('common.copy')"
            :aria-label="t('common.copy')"
            @click="copyIfPresent(item.material)"
          />
        </div>
      </div>
      <div class="field">
        <span class="field-label">{{ t('madeItems.catalogue.columns.mass') }}</span>
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
      <div class="field">
        <span class="field-label">{{ t('madeItems.catalogue.detail.baseSize') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.base_size ?? getEmptyPlaceholder() }}</span>
          <Button
            v-if="item.base_size"
            icon="mdi mdi-content-copy"
            text
            rounded
            size="small"
            class="copy-btn"
            v-tooltip.top.focus="t('common.copy')"
            :aria-label="t('common.copy')"
            @click="copyIfPresent(item.base_size)"
          />
        </div>
      </div>
      <div class="field">
        <span class="field-label">{{ t('madeItems.catalogue.detail.sourceItem') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ sourceItemLabel }}</span>
        </div>
      </div>
      <!-- Only a customer item, or one PDM filled in partly, carries customer data. -->
      <template v-if="hasCustomerData">
        <div class="field">
          <span class="field-label">{{ t('madeItems.catalogue.detail.customer') }}</span>
          <div class="field-value-row">
            <span class="field-value">{{ item.customer_name ?? getEmptyPlaceholder() }}</span>
          </div>
        </div>
        <div class="field">
          <span class="field-label">{{ t('madeItems.catalogue.detail.customerPartNumber') }}</span>
          <div class="field-value-row">
            <span class="field-value">{{ item.customer_part_number ?? getEmptyPlaceholder() }}</span>
            <Button
              v-if="item.customer_part_number"
              icon="mdi mdi-content-copy"
              text
              rounded
              size="small"
              class="copy-btn"
              v-tooltip.top.focus="t('common.copy')"
              :aria-label="t('common.copy')"
              @click="copyIfPresent(item.customer_part_number)"
            />
          </div>
        </div>
        <div class="field">
          <span class="field-label">{{ t('madeItems.catalogue.detail.customerRevision') }}</span>
          <div class="field-value-row">
            <span class="field-value">{{ item.customer_revision ?? getEmptyPlaceholder() }}</span>
          </div>
        </div>
      </template>
      <div v-if="item.successor_item_id" class="field field-wide">
        <span class="field-label">{{ t('madeItems.catalogue.columns.successorItem') }}</span>
        <div class="field-value-row">
          <RouterLink
            v-if="router"
            :to="`/catalogue/made-items/${item.successor_item_id}`"
            class="field-link"
            >{{
              successorItem
                ? `#${successorItem.id}: ${successorItem.article_name}`
                : `#${item.successor_item_id}`
            }}</RouterLink
          >
          <span v-else class="field-value">{{
            successorItem
              ? `#${successorItem.id}: ${successorItem.article_name}`
              : `#${item.successor_item_id}`
          }}</span>
        </div>
      </div>
      <div v-if="item.weblink" class="field field-wide">
        <span class="field-label">{{ t('madeItems.catalogue.columns.weblink') }}</span>
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
        <span class="field-label">{{ t('madeItems.catalogue.columns.note') }}</span>
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

      <template v-if="showMeta">
        <div class="field">
          <span class="field-label">{{ t('madeItems.catalogue.columns.creator') }}</span>
          <div class="field-value-row">
            <span class="field-value">{{ item.creator?.full_name ?? getEmptyPlaceholder() }}</span>
          </div>
        </div>
        <div class="field">
          <span class="field-label">{{ t('madeItems.catalogue.columns.created') }}</span>
          <div class="field-value-row">
            <span class="field-value">{{ formatDateTimeOrDash(item.created) }}</span>
          </div>
        </div>
        <div v-if="item.changed" class="field">
          <span class="field-label">{{ t('madeItems.catalogue.columns.changed') }}</span>
          <div class="field-value-row">
            <span class="field-value">{{ formatDateTimeOrDash(item.changed) }}</span>
          </div>
        </div>
        <div v-if="item.changed_by" class="field">
          <span class="field-label">{{ t('madeItems.catalogue.columns.changedBy') }}</span>
          <div class="field-value-row">
            <span class="field-value">{{ item.changed_by.full_name }}</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped lang="scss">
.item-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

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
</style>
