<script setup lang="ts">
// The Data Portal search on top of the bought-item create dialog. Typing an
// order, type or EPLAN part number or a name lists the portal's hits with
// their picture; picking one hands its values to the form. A hit the
// catalogue already has, or whose manufacturer has no supplier with its
// Data Portal code, is pointed out next to the search. A hit whose order
// code 1 is exactly the searched text is tagged and listed first. Without
// use:data_portal the search stays visible but disabled, and its tooltip
// names the missing permission.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'

import { Permission } from '@/core/auth/permissions'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { extractApiError } from '@/core/utils/errors'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { HelpButton } from '@/shared/help'
import EdpPartPicture from './EdpPartPicture.vue'
import { searchEdpParts } from '../api/boughtItemsEdpApi'
import { exactMatchesFirst, isExactOrderCodeMatch } from '../utils/edpSearchHits'

import type { AutoCompleteCompleteEvent } from 'openvue/autocomplete'
import type { EdpSearchHit } from '../types/boughtItemsEdpTypes'

const emit = defineEmits<{
  pick: [hit: EdpSearchHit]
}>()

const { t } = useI18n()
const { missing } = useMissingPermission()
const blockedHint = computed(() => missing(Permission.USE_DATA_PORTAL))

const query = ref<string | EdpSearchHit>('')
const hits = ref<EdpSearchHit[]>([])
// The text the shown hits were found with, which the exact match compares.
const searchedText = ref('')
const picked = ref<EdpSearchHit | null>(null)
const errorMessage = ref<string | null>(null)

const runSearch = useDebounceFn(async (text: string) => {
  errorMessage.value = null
  try {
    hits.value = exactMatchesFirst(await searchEdpParts(text), text)
    searchedText.value = text
  } catch (error) {
    hits.value = []
    searchedText.value = ''
    errorMessage.value = extractApiError(error) ?? t('boughtItems.create.edp.searchFailed')
  }
}, TABLE_DEBOUNCE_MS)

function onComplete(event: AutoCompleteCompleteEvent): void {
  const text = event.query.trim()
  if (text.length < 2) {
    hits.value = []
    searchedText.value = ''
    return
  }
  void runSearch(text)
}

function hitLabel(hit: EdpSearchHit): string {
  return [hit.part.order_number ?? hit.part.part_number, hit.part.designation]
    .filter((v) => !!v)
    .join(' · ')
}

function onSelect(event: { value: EdpSearchHit }): void {
  picked.value = event.value
  emit('pick', event.value)
}

function reset(): void {
  query.value = ''
  hits.value = []
  searchedText.value = ''
  picked.value = null
  errorMessage.value = null
}

defineExpose({ reset })
</script>

<template>
  <div class="edp-search">
    <div class="edp-search-label">
      <label for="bi-edp-search">{{ t('boughtItems.create.edp.label') }}</label>
      <HelpButton slug="catalogue/eplan-data-portal" size="small" rounded />
    </div>
    <span
      v-tooltip.bottom="blockedHint || undefined"
      class="edp-search-field"
      data-testid="bought-item-edp-search-wrap"
    >
      <AutoComplete
        v-model="query"
        input-id="bi-edp-search"
        :suggestions="hits"
        :option-label="hitLabel"
        :delay="0"
        :placeholder="t('boughtItems.create.edp.placeholder')"
        :disabled="!!blockedHint"
        fluid
        data-testid="bought-item-edp-search"
        @complete="onComplete"
        @option-select="onSelect"
      >
        <template #option="{ option }">
          <div class="hit">
            <EdpPartPicture :part-id="(option as EdpSearchHit).part.part_id" size="2.5rem" />
            <div class="hit-text">
              <span>{{ (option as EdpSearchHit).part.designation }}</span>
              <small>
                {{ (option as EdpSearchHit).part.manufacturer_name }} ·
                {{ (option as EdpSearchHit).part.order_number ?? (option as EdpSearchHit).part.part_number }}
              </small>
            </div>
            <Tag
              v-if="isExactOrderCodeMatch(option as EdpSearchHit, searchedText)"
              :value="t('boughtItems.create.edp.exactMatch')"
              severity="success"
              data-testid="bought-item-edp-exact-match"
            />
            <Tag
              v-if="(option as EdpSearchHit).existing_item"
              :value="t('boughtItems.create.edp.inCatalogue')"
              severity="warn"
            />
          </div>
        </template>
      </AutoComplete>
    </span>
    <small class="hint">{{ t('boughtItems.create.edp.hint') }}</small>
    <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>
    <Message
      v-if="picked?.existing_item"
      severity="warn"
      :closable="false"
      data-testid="bought-item-edp-existing"
    >
      {{
        t('boughtItems.create.edp.existing', {
          id: picked.existing_item.id,
          name: picked.existing_item.article_name,
        })
      }}
    </Message>
    <Message
      v-if="picked && picked.draft.manufacturer_id === null"
      severity="warn"
      :closable="false"
      data-testid="bought-item-edp-no-supplier"
    >
      {{
        t('boughtItems.create.edp.noSupplier', {
          code: picked.draft.manufacturer_code ?? '?',
          name: picked.part.manufacturer_name ?? '',
        })
      }}
    </Message>
  </div>
</template>

<style scoped lang="scss">
.edp-search {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.edp-search-field {
  display: block;
}

.edp-search-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.hit {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.hit-text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;

  small {
    color: var(--p-text-muted-color);
  }
}
</style>
