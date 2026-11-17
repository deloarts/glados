<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useSourceItemTypesStore } from '../stores/sourceItemTypesStore'
import SimpleNamedEntityManagementTable from '@/shared/components/management/SimpleNamedEntityManagementTable.vue'
import { Permission } from '@/core/auth/permissions'

const { t } = useI18n()
const store = useSourceItemTypesStore()
</script>

<template>
  <SimpleNamedEntityManagementTable
    localized
    v-model:filters="store.filters"
    :store="store"
    i18n-prefix="settings.sourceItemTypes"
    id-prefix="bit"
    :create-title="t('settings.sourceItemTypes.createType')"
    :edit-title="t('settings.sourceItemTypes.editType')"
    :write-permission="Permission.WRITE_SOURCE_ITEM_TYPES"
    :delete-permission="Permission.WRITE_SOURCE_ITEM_TYPES"
  />
</template>
