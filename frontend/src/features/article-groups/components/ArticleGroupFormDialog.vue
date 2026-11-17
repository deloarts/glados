<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useArticleGroupsStore } from '../stores/articleGroupsStore'
import SimpleNamedEntityFormDialog from '@/shared/components/management/SimpleNamedEntityFormDialog.vue'
import type { ArticleGroupResponse } from '../types/articleGroupResponse'

interface Props {
  group?: ArticleGroupResponse
  /**
   * Lightweight prefill for the group name when creating from elsewhere
   * (e.g. a batch import row), ignored when editing an existing group.
   */
  prefillName?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [group: ArticleGroupResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useArticleGroupsStore()
</script>

<template>
  <SimpleNamedEntityFormDialog
    localized
    v-model:visible="visible"
    :entity="props.group"
    :prefill-name="props.prefillName"
    id-prefix="ag"
    i18n-prefix="settings.articleGroups"
    :create-title="t('settings.articleGroups.createGroup')"
    :edit-title="t('settings.articleGroups.editGroup')"
    show-contrast-warning
    :store="store"
    @saved="(group) => emit('saved', group)"
  />
</template>
