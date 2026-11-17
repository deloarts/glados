<script setup lang="ts">
// The read-only field display of a source item, shared by the detail
// dialog's view mode and the detail page's Item card.
import { computed, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@/core/composables/useClipboard'
import { RouterLink, routerKey } from 'vue-router'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useUsersStore } from '@/core/stores/usersStore'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'

import type { SourceItemResponse } from '../types/sourceItemsResponse'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// The dialog hides the meta block, keeping its own footer copy, and the page
// hides the status, which its info bar already shows.
const props = withDefaults(
  defineProps<{
    item: SourceItemResponse
    showMeta?: boolean
    showStatus?: boolean
  }>(),
  { showMeta: true, showStatus: true },
)

// Injected with a default, since this also mounts without a router; the
// successor link then degrades to plain text.
const router = inject(routerKey, null)

const usersStore = useUsersStore()

// Source items carry only an approver_id.
const approver = computed(() => {
  const id = props.item.approver_id
  return id === null ? null : (usersStore.getById(id) ?? null)
})

const { t } = useI18n()
const { localize } = useLocalizedText()
const { copyIfPresent } = useClipboard()
</script>

<template>
  <div class="detail-top">
    <Tag
      v-if="showStatus"
      :value="t(`sourceItems.catalogue.status.${item.status}`)"
      :severity="catalogueStatusTagSeverity(item.status)"
    />
  </div>

  <Divider />

  <div class="detail-grid">
    <div class="field">
      <span class="field-label">{{ t('sourceItems.catalogue.columns.id') }}</span>
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
    <div v-if="item.successor_item_id" class="field field-wide">
      <span class="field-label">{{ t('sourceItems.catalogue.columns.successorItem') }}</span>
      <div class="field-value-row">
        <RouterLink
          v-if="router"
          :to="`/catalogue/source-items/${item.successor_item_id}`"
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
      <span class="field-label">{{ t('sourceItems.catalogue.columns.dimension') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.dimension ?? getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.dimension"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(item.dimension)"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('sourceItems.catalogue.columns.type') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ localizeLabel(item.type_name) || getEmptyPlaceholder() }}</span>
        <Button
          v-if="localizeLabel(item.type_name)"
          icon="mdi mdi-content-copy"
          text
          rounded
          size="small"
          class="copy-btn"
          v-tooltip.top.focus="t('common.copy')"
          :aria-label="t('common.copy')"
          @click="copyIfPresent(localize(item.type_name))"
        />
      </div>
    </div>
    <div class="field">
      <span class="field-label">{{ t('sourceItems.catalogue.columns.material') }}</span>
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
      <span class="field-label">{{ t('sourceItems.catalogue.columns.mass') }}</span>
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
      <span class="field-label">{{ t('sourceItems.catalogue.columns.manufacturer') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.manufacturer_name || getEmptyPlaceholder() }}</span>
        <Button
          v-if="item.manufacturer_name"
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
      <span class="field-label">{{ t('sourceItems.catalogue.detail.approver') }}</span>
      <UserAvatarPreview :user="approver" />
    </div>

    <div v-if="item.order_code_1" class="field">
      <span class="field-label">{{ t('sourceItems.catalogue.columns.orderCode1') }}</span>
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
    <div v-if="item.order_code_2" class="field">
      <span class="field-label">{{ t('sourceItems.catalogue.columns.orderCode2') }}</span>
      <div class="field-value-row">
        <span class="field-value">{{ item.order_code_2 }}</span>
        <Button
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

    <div v-if="item.note" class="field field-wide">
      <span class="field-label">{{ t('sourceItems.catalogue.columns.note') }}</span>
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
        <span class="field-label">{{ t('sourceItems.catalogue.columns.creator') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.creator?.full_name ?? getEmptyPlaceholder() }}</span>
        </div>
      </div>
      <div class="field">
        <span class="field-label">{{ t('sourceItems.catalogue.columns.created') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.created }}</span>
        </div>
      </div>
      <div class="field">
        <span class="field-label">{{ t('sourceItems.catalogue.columns.changed') }}</span>
        <div class="field-value-row">
          <span class="field-value">{{ item.changed }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.detail-top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
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
</style>
