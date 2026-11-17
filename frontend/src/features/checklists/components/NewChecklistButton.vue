<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { useChecklistCreation } from '../composables/useChecklistCreation'
import type { ChecklistOwner } from '../types/checklist'
import type { ChecklistType } from '../utils/types'
import ChecklistOwnerDialog from './ChecklistOwnerDialog.vue'

/**
 * "New Checklist" in a controls bar, styled like the catalogue's New
 * button. It asks for the type and owner, with the project or product of
 * the page preset, creates the checklist and opens it.
 */

const props = defineProps<{
  projectId?: number
  productId?: number
  /** Shown as the preset owner when a checklist is started here. */
  ownerLabel?: string
  disabled?: boolean
}>()

const { t } = useI18n()
const router = useRouter()
const toast = useAppToast()
const creation = useChecklistCreation()

const dialogVisible = ref(false)

const presetOwner = computed<ChecklistOwner>(() => {
  if (props.projectId !== undefined) return { kind: 'project', id: props.projectId, label: props.ownerLabel ?? '' }
  if (props.productId !== undefined) return { kind: 'product', id: props.productId, label: props.ownerLabel ?? '' }
  return { kind: 'personal' }
})

async function start(type: ChecklistType, chosen: ChecklistOwner): Promise<void> {
  try {
    const created = await creation.create(type, chosen)
    dialogVisible.value = false
    void router.push({ name: 'ChecklistDetail', params: { id: created.id } })
  } catch (e) {
    toast.error(t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
  }
}
</script>

<template>
  <Button
    :label="t('checklists.actions.new')"
    icon="mdi mdi-plus"
    severity="contrast"
    text
    :disabled="disabled"
    data-testid="cl-new"
    @click="dialogVisible = true"
  />

  <ChecklistOwnerDialog
    v-model:visible="dialogVisible"
    mode="create"
    :initial-owner="presetOwner"
    :busy="creation.creating.value"
    @save="start"
  />
</template>
