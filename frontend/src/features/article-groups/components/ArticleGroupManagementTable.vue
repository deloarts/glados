<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useArticleGroupsStore } from '../stores/articleGroupsStore'
import SimpleNamedEntityManagementTable from '@/shared/components/management/SimpleNamedEntityManagementTable.vue'
import { Permission } from '@/core/auth/permissions'

const { t } = useI18n()
const store = useArticleGroupsStore()
</script>

<template>
  <SimpleNamedEntityManagementTable
    localized
    v-model:filters="store.filters"
    :store="store"
    i18n-prefix="settings.articleGroups"
    id-prefix="ag"
    :create-title="t('settings.articleGroups.createGroup')"
    :edit-title="t('settings.articleGroups.editGroup')"
    :write-permission="Permission.WRITE_ARTICLE_GROUPS"
    :delete-permission="Permission.WRITE_ARTICLE_GROUPS"
    show-contrast-warning
  />
</template>
