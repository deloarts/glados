<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate, formatISODateTime } from '@/core/utils/dates'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import type { ChecklistDocument } from '../composables/useChecklistDocument'
import { typeLabel } from '../utils/definitions'
import { ownerLink, ownerOf } from '../utils/owner'
import ChecklistStatusTag from './ChecklistStatusTag.vue'

/**
 * The identity strip of a checklist, laid out like a calculation's: document
 * number, revision, status, its type, the project or product it belongs to
 * and its creator.
 */

const props = defineProps<{ doc: ChecklistDocument }>()

const { t } = useI18n()
const translate = (key: string, params?: Record<string, unknown>) => (params ? t(key, params) : t(key))

const checklist = computed(() => props.doc.checklist.value)

const owner = computed(() => {
  const c = checklist.value
  if (!c) return null
  const o = ownerOf(c)
  if (o.kind === 'personal') {
    return { icon: 'mdi mdi-account-outline', label: t('checklists.owner.personal'), link: null, tooltip: '' }
  }
  return {
    icon: o.kind === 'project' ? 'mdi mdi-folder-outline' : 'mdi mdi-package-variant-closed',
    label: o.label,
    link: ownerLink(o),
    tooltip: t(`checklists.owner.${o.kind}`),
  }
})

const changedTooltip = computed(() => {
  const c = checklist.value
  if (!c?.changed || c.changed === c.created) return ''
  return t('checklists.info.changed', { date: formatISODateTime(c.changed) })
})
</script>

<template>
  <InfoBar>
    <template v-if="checklist">
      <span class="info-title" data-testid="cl-info-number">{{ checklist.document_number }}</span>
      <span class="info-sep" />
      <Tag
        v-tooltip.bottom="checklist.revision_reason ?? ''"
        :value="t('documents.revision.tag', { revision: checklist.revision })"
        severity="secondary"
        data-testid="cl-info-revision"
      />
      <span class="info-sep" />
      <ChecklistStatusTag :checklist="checklist" />
      <Tag
        v-if="checklist.invalid_at"
        :value="t('documents.status.invalid')"
        severity="danger"
        data-testid="cl-info-invalid"
      />
      <Tag
        v-if="doc.lock.editing.value"
        :value="t('documents.status.editing')"
        severity="info"
        data-testid="cl-info-editing"
      />
      <Tag
        v-if="doc.dirty.value"
        :value="t('checklists.status.unsaved')"
        severity="warn"
        data-testid="cl-info-unsaved"
      />
      <span class="info-sep" />
      <span class="info-muted" data-testid="cl-info-title">
        {{ t('checklists.info.typeTitle', { type: typeLabel(checklist.type, translate) }) }}
      </span>
      <span class="info-sep" />
      <span v-if="owner" v-tooltip.bottom="owner.tooltip" class="info-muted" data-testid="cl-info-owner">
        <i :class="owner.icon" aria-hidden="true" />
        <RouterLink v-if="owner.link" :to="owner.link" class="info-link">{{ owner.label }}</RouterLink>
        <template v-else>{{ owner.label }}</template>
      </span>
      <span class="info-sep" />
      <span v-tooltip.bottom="changedTooltip" class="info-muted" data-testid="cl-info-creator">
        {{
          t('checklists.info.created', {
            name: checklist.creator_full_name,
            date: formatISODate(checklist.created),
          })
        }}
      </span>
    </template>
  </InfoBar>
</template>

<style scoped lang="scss">
.info-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.info-link {
  color: inherit;
}
</style>
