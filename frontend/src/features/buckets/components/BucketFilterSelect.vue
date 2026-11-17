<script setup lang="ts">
/**
 * The bucket column filter of a demands table: a MultiSelect over the
 * buckets with a leading "Unbucketed" option whose value is null. It binds
 * the same pair as BucketsMenu, so the two never disagree. Filtering is
 * client-side, since buckets load fully.
 */
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useBucketsStore } from '../stores/bucketsStore'

import type { BucketResourceType } from '../types/bucketResponse'

type BucketFilterValue = number | null

interface BucketFilterOption {
  value: BucketFilterValue
  label: string
  color: string | null
}

const props = defineProps<{
  resourceType: BucketResourceType
  bucketIds: number[]
  includeUnbucketed: boolean
}>()

const emit = defineEmits<{
  'update:bucketIds': [value: number[]]
  'update:includeUnbucketed': [value: boolean]
}>()

const { t } = useI18n()
const bucketsStore = useBucketsStore()

const NO_BUCKET_VALUE: BucketFilterValue = null

const options = computed<BucketFilterOption[]>(() => [
  { value: NO_BUCKET_VALUE, label: t('buckets.unbucketed'), color: null },
  ...bucketsStore.items[props.resourceType].map((bucket) => ({
    value: bucket.id,
    label: bucket.name,
    color: bucket.color,
  })),
])

const loading = computed(() => bucketsStore.loading[props.resourceType])

const model = computed<BucketFilterValue[]>(() =>
  props.includeUnbucketed ? [NO_BUCKET_VALUE, ...props.bucketIds] : [...props.bucketIds],
)

function sameIds(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((id, index) => id === b[index])
}

// Emits only the changed part, so a table watching both fields refetches
// once.
function onUpdate(value: BucketFilterValue[] | null): void {
  const next = value ?? []
  const includeUnbucketed = next.includes(NO_BUCKET_VALUE)
  const bucketIds = next.filter((entry): entry is number => entry !== null)
  if (includeUnbucketed !== props.includeUnbucketed) {
    emit('update:includeUnbucketed', includeUnbucketed)
  }
  if (!sameIds(bucketIds, props.bucketIds)) {
    emit('update:bucketIds', bucketIds)
  }
}

// The table fetches on mount too, so only fetch when nothing is loaded yet.
onMounted(() => {
  if (bucketsStore.items[props.resourceType].length === 0 && !loading.value) {
    void bucketsStore.fetch(props.resourceType)
  }
})
</script>

<template>
  <MultiSelect
    :model-value="model"
    :options="options"
    option-label="label"
    option-value="value"
    :loading="loading"
    filter
    reset-filter-on-hide
    display="chip"
    show-clear
    size="small"
    fluid
    :placeholder="t('buckets.filters.any')"
    @update:model-value="onUpdate"
  >
    <template #option="{ option }">
      <div class="bucket-option">
        <span
          v-if="option.color"
          class="color-dot"
          :style="{ background: option.color }"
          aria-hidden="true"
        />
        <span :class="{ 'bucket-option--pinned': option.value === null }">{{ option.label }}</span>
      </div>
    </template>
  </MultiSelect>
</template>

<style scoped lang="scss">
.bucket-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.bucket-option--pinned {
  font-weight: 500;
}

.color-dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
