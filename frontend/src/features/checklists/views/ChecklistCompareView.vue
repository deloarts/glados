<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { getChecklist } from '../api/getChecklist'
import { getChecklistRevisions } from '../api/getChecklistRevisions'
import ChecklistDiffView from '../components/ChecklistDiffView.vue'
import type { ChecklistResponse, ChecklistSummaryResponse } from '../types/checklist'
import { CHECKLISTS } from '../utils/definitions'
import { diffChecklists } from '../utils/diff'
import { completionOf, VERDICT_SEVERITY } from '../utils/owner'
import { isChecklistType } from '../utils/types'

/**
 * /checklists/:id/compare?base=<id>: what changed between two revisions of
 * one checklist. The revision in the route is compared with `base`, by
 * default the revision right before it.
 */

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const targetId = computed(() => Number(route.params.id))
const baseParam = computed(() => {
  const raw = Number(route.query.base)
  return Number.isInteger(raw) && raw > 0 ? raw : null
})

const revisions = ref<ChecklistSummaryResponse[]>([])
const base = ref<ChecklistResponse | null>(null)
const target = ref<ChecklistResponse | null>(null)
const loading = ref(false)
const failed = ref(false)
watchLoadingBar(loading)

const defaultBaseId = computed(() => {
  const index = revisions.value.findIndex((row) => row.id === targetId.value)
  return index >= 0 ? (revisions.value[index + 1]?.id ?? null) : null
})
const baseId = computed(() => baseParam.value ?? defaultBaseId.value)

async function load(): Promise<void> {
  const id = targetId.value
  if (!Number.isInteger(id)) return
  loading.value = true
  failed.value = false
  try {
    revisions.value = await getChecklistRevisions(id)
    const otherId = baseId.value
    const [loadedTarget, loadedBase] = await Promise.all([
      getChecklist(id),
      otherId !== null ? getChecklist(otherId) : Promise.resolve(null),
    ])
    target.value = loadedTarget
    base.value = loadedBase
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

watch([targetId, baseParam], load, { immediate: true })

const definition = computed(() => {
  const type = target.value?.type
  return type && isChecklistType(type) ? CHECKLISTS[type] : null
})

const diff = computed(() =>
  definition.value && base.value && target.value ? diffChecklists(definition.value, base.value, target.value) : null,
)

const revisionOptions = computed(() =>
  revisions.value.map((row) => ({ value: row.id, label: t('checklists.revisionLabel', { revision: row.revision }) })),
)

function label(checklist: ChecklistResponse | null): string {
  return checklist ? t('checklists.revisionLabel', { revision: checklist.revision }) : ''
}

function choose(nextTarget: number | null, nextBase: number | null): void {
  if (nextTarget === null) return
  void router.replace({
    name: 'ChecklistCompare',
    params: { id: nextTarget },
    query: nextBase !== null ? { base: String(nextBase) } : {},
  })
}
</script>

<template>
  <PageLayout :card="false">
    <template #info>
      <InfoBar>
        <span class="page-title">{{ target?.title ?? t('checklists.compare.title') }}</span>
        <span class="page-hint">{{ t('checklists.compare.title') }}</span>
      </InfoBar>
    </template>
    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            icon="mdi mdi-arrow-left"
            :label="t('checklists.compare.back')"
            severity="contrast"
            outlined
            data-testid="cl-compare-back"
            @click="router.push({ name: 'ChecklistDetail', params: { id: targetId } })"
          />
          <div class="pickers">
            <Select
              :model-value="baseId"
              :options="revisionOptions"
              option-label="label"
              option-value="value"
              size="small"
              :aria-label="t('checklists.compare.from')"
              data-testid="cl-compare-base"
              @update:model-value="(value: number | null) => choose(targetId, value)"
            />
            <i class="mdi mdi-arrow-right" aria-hidden="true" />
            <Select
              :model-value="targetId"
              :options="revisionOptions"
              option-label="label"
              option-value="value"
              size="small"
              :aria-label="t('checklists.compare.to')"
              data-testid="cl-compare-target"
              @update:model-value="(value: number | null) => choose(value, baseId)"
            />
          </div>
        </template>
      </ControlsBar>
    </template>

    <Message v-if="failed" severity="error">{{ t('checklists.errors.notFound') }}</Message>
    <Message v-else-if="!loading && target && !base" severity="info">{{ t('checklists.compare.nothing') }}</Message>

    <div v-if="diff && definition && base && target" class="compare">
      <section class="summary" data-testid="cl-compare-summary">
        <div v-for="side in [base, target]" :key="side.id" class="summary-side">
          <span class="summary-label">{{ label(side) }}</span>
          <Tag :value="t(`checklists.verdicts.${side.verdict}`)" :severity="VERDICT_SEVERITY[side.verdict]" />
          <span class="summary-completion">{{ t('checklists.list.completion', { percent: completionOf(side) }) }}</span>
          <span class="summary-findings">{{ t('checklists.compare.findings', { count: side.finding_count }) }}</span>
        </div>
      </section>
      <ChecklistDiffView :definition="definition" :diff="diff" :before-label="label(base)" :after-label="label(target)" />
    </div>
  </PageLayout>
</template>

<style scoped lang="scss">
.page-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.page-hint {
  color: var(--p-text-muted-color);
}

.pickers {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: var(--space-2);
}

.compare {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.summary-side {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.summary-label {
  font-weight: 600;
}

.summary-completion,
.summary-findings {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
