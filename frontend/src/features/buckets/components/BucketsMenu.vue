<script setup lang="ts">
/**
 * The Buckets ViewsBar control: a membership filter (buckets plus
 * "Unbucketed") and lightweight bucket CRUD in one Popover. It depends only
 * on resourceType and its v-models, so every demand kind reuses it.
 * bucketsStore.createRequestTrigger lets the table's context menu open it.
 */
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useBucketsStore } from '../stores/bucketsStore'
import { pickNextColor } from '../utils/bucketColors'

import type { BucketResourceType, BucketResponse } from '../types/bucketResponse'

const props = defineProps<{
  resourceType: BucketResourceType
  bucketIds: number[]
  includeUnbucketed: boolean
}>()

const emit = defineEmits<{
  'update:bucketIds': [value: number[]]
  'update:includeUnbucketed': [value: boolean]
  /** A bucket was deleted; the caller's rows may hold its stale id. */
  deleted: [bucketId: number]
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()
const bucketsStore = useBucketsStore()

const canWrite = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))

const buckets = computed(() => bucketsStore.items[props.resourceType])
const loading = computed(() => bucketsStore.loading[props.resourceType])

const bucketIdsModel = computed({
  get: () => props.bucketIds,
  set: (value: number[]) => emit('update:bucketIds', value),
})
const includeUnbucketedModel = computed({
  get: () => props.includeUnbucketed,
  set: (value: boolean) => emit('update:includeUnbucketed', value),
})

const activeCount = computed(() => props.bucketIds.length + (props.includeUnbucketed ? 1 : 0))

function clearChecked(): void {
  emit('update:bucketIds', [])
  emit('update:includeUnbucketed', false)
}

// ── Popover + fetch-on-first-open ───────────────────────────────────────
// The table fetches on mount too, so this guard avoids a second request.

const popover = ref()
const menuButton = ref()
let fetched = false

function ensureFetched(): void {
  if (fetched) return
  fetched = true
  void bucketsStore.fetch(props.resourceType)
}

function toggleMenu(event: Event): void {
  ensureFetched()
  popover.value?.toggle(event)
}

// ── Inline rename/recolor ────────────────────────────────────────────────

const editingId = ref<number | null>(null)
const editName = ref('')
const editColor = ref('')
const { submitting: editSaving, errorMessage: editError, run: runEdit } = useSubmitAction()

function startEdit(bucket: BucketResponse): void {
  editingId.value = bucket.id
  editName.value = bucket.name
  editColor.value = bucket.color
  editError.value = null
}

function cancelEdit(): void {
  editingId.value = null
  editError.value = null
}

async function saveEdit(): Promise<void> {
  const id = editingId.value
  const name = editName.value.trim()
  if (id === null || !name) return

  await runEdit(async () => {
    await bucketsStore.update(props.resourceType, id, { name, color: editColor.value })
    editingId.value = null
  }, t('buckets.duplicateError'))
}

function confirmDelete(bucket: BucketResponse): void {
  async function onAccept(): Promise<void> {
    await bucketsStore.remove(props.resourceType, bucket.id)
    if (props.bucketIds.includes(bucket.id)) {
      emit(
        'update:bucketIds',
        props.bucketIds.filter((id) => id !== bucket.id),
      )
    }
    emit('deleted', bucket.id)
  }

  confirm.require({
    message: t('buckets.deleteConfirm', { name: bucket.name }),
    header: t('buckets.delete'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('buckets.delete'), severity: 'danger' },
    accept: () => void onAccept().catch(toastOnError(t('buckets.delete'))),
  })
}

// ── New bucket ─────────────────────────────────────────────────────────

const showCreateRow = ref(false)
const createName = ref('')
const createColor = ref('')
const { submitting: createSaving, errorMessage: createError, run: runCreate } = useSubmitAction()
const createInput = ref()

function startCreate(): void {
  if (!canWrite.value) return
  showCreateRow.value = true
  createName.value = ''
  createColor.value = pickNextColor(buckets.value.map((b) => b.color))
  createError.value = null
  void nextTick(() => (createInput.value?.$el as HTMLElement | undefined)?.focus())
}

function cancelCreate(): void {
  showCreateRow.value = false
  createError.value = null
}

async function saveCreate(): Promise<void> {
  const name = createName.value.trim()
  if (!name) return

  await runCreate(async () => {
    await bucketsStore.create(props.resourceType, {
      name,
      color: createColor.value,
    })
    showCreateRow.value = false
  }, t('buckets.duplicateError'))
}

watch(
  () => bucketsStore.createRequestTrigger,
  () => {
    ensureFetched()
    popover.value?.show({ currentTarget: menuButton.value?.$el })
    startCreate()
  },
)
</script>

<template>
  <Button
    ref="menuButton"
    :label="t('buckets.menuTitle')"
    icon="mdi mdi-bucket-outline"
    severity="contrast"
    :text="activeCount === 0"
    :badge="activeCount > 0 ? String(activeCount) : undefined"
    @click="toggleMenu"
  />

  <Popover ref="popover">
    <div class="buckets-menu">
      <div class="buckets-header">
        <span class="buckets-title">{{ t('buckets.menuTitle') }}</span>
        <Button
          v-if="activeCount > 0"
          :label="t('common.clear')"
          text
          size="small"
          severity="secondary"
          @click="clearChecked"
        />
      </div>

      <div class="bucket-row bucket-row--pinned">
        <Checkbox v-model="includeUnbucketedModel" binary input-id="buckets-menu-unbucketed" />
        <label for="buckets-menu-unbucketed">{{ t('buckets.unbucketed') }}</label>
      </div>

      <Divider />

      <i v-if="loading" class="mdi mdi-loading mdi-spin buckets-loading" aria-hidden="true" />

      <span v-else-if="buckets.length === 0" class="buckets-empty">
        {{ t('buckets.noBucketsYet') }}
      </span>

      <div v-else class="bucket-list">
        <div v-for="bucket in buckets" :key="bucket.id" class="bucket-row">
          <template v-if="editingId === bucket.id">
            <div class="bucket-edit">
              <input v-model="editColor" :aria-label="t('buckets.color')" type="color" class="color-input" />
              <InputText
                v-model="editName"
                size="small"
                :placeholder="t('buckets.namePlaceholder')"
                @keydown.enter="saveEdit"
                @keydown.esc="cancelEdit"
              />
              <Button
                icon="mdi mdi-check"
                text
                rounded
                size="small"
                :loading="editSaving"
                :aria-label="t('common.save')"
                @click="saveEdit"
              />
              <Button
                icon="mdi mdi-close"
                text
                rounded
                size="small"
                :aria-label="t('common.cancel')"
                @click="cancelEdit"
              />
            </div>
            <Message v-if="editError" severity="error" :closable="false" size="small">{{
              editError
            }}</Message>
          </template>
          <template v-else>
            <Checkbox
              v-model="bucketIdsModel"
              :value="bucket.id"
              :input-id="`buckets-menu-${bucket.id}`"
            />
            <span class="color-dot" :style="{ background: bucket.color }" />
            <label :for="`buckets-menu-${bucket.id}`" class="bucket-name">{{ bucket.name }}</label>
            <div class="row-actions">
              <Button
                icon="mdi mdi-pencil"
                text
                rounded
                size="small"
                :disabled="!canWrite"
                :aria-label="t('buckets.rename')"
                @click="startEdit(bucket)"
              />
              <Button
                icon="mdi mdi-delete-outline"
                text
                rounded
                size="small"
                severity="danger"
                :disabled="!canWrite"
                :aria-label="t('buckets.delete')"
                @click="confirmDelete(bucket)"
              />
            </div>
          </template>
        </div>
      </div>

      <Divider />

      <div v-if="showCreateRow" class="bucket-create">
        <div class="bucket-create-row">
          <input v-model="createColor" :aria-label="t('buckets.color')" type="color" class="color-input" />
          <InputText
            ref="createInput"
            class="bucket-name-input"
            v-model="createName"
            size="small"
            :placeholder="t('buckets.namePlaceholder')"
            @keydown.enter="saveCreate"
            @keydown.esc="cancelCreate"
          />
          <Button
            icon="mdi mdi-check"
            text
            rounded
            size="small"
            :loading="createSaving"
            :aria-label="t('buckets.create')"
            @click="saveCreate"
          />
          <Button
            icon="mdi mdi-close"
            text
            rounded
            size="small"
            :aria-label="t('common.cancel')"
            @click="cancelCreate"
          />
        </div>
        <Message v-if="createError" severity="error" :closable="false" size="small">{{
          createError
        }}</Message>
      </div>
      <Button
        v-else
        :label="t('buckets.newBucket')"
        icon="mdi mdi-plus"
        text
        size="small"
        :disabled="!canWrite"
        @click="startCreate"
      />
    </div>
  </Popover>
</template>

<style scoped lang="scss">
.buckets-menu {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 16rem;
}

.buckets-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.buckets-title {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.bucket-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2rem;

  .row-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
    opacity: 0;
  }

  &:hover .row-actions,
  &:focus-within .row-actions {
    opacity: 1;
  }
}

.bucket-row--pinned {
  font-weight: 500;
}

.bucket-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 16rem;
  overflow-y: auto;
}

.bucket-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.color-dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.color-input {
  width: 1.8rem;
  height: 1.8rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  cursor: pointer;
  padding: var(--space-1);
  flex-shrink: 0;
}

.bucket-edit,
.bucket-create-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  width: 100%;
}

.bucket-name-input {
  flex: 1;
  min-width: 0;
}

.buckets-loading {
  align-self: center;
  color: var(--p-text-muted-color);
}

.buckets-empty {
  align-self: center;
  padding: var(--space-1) 0;
  color: var(--p-text-muted-color);
  font-style: italic;
}
</style>
