<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useProductFamiliesStore } from '../stores/productFamiliesStore'
import SimpleNamedEntityManagementTable from '@/shared/components/management/SimpleNamedEntityManagementTable.vue'
import { Permission } from '@/core/auth/permissions'

const { t } = useI18n()
const store = useProductFamiliesStore()
</script>

<template>
  <SimpleNamedEntityManagementTable
    v-model:filters="store.filters"
    :store="store"
    i18n-prefix="settings.productFamilies"
    id-prefix="pf"
    :create-title="t('settings.productFamilies.createFamily')"
    :edit-title="t('settings.productFamilies.editFamily')"
    :write-permission="Permission.WRITE_ARTICLE_GROUPS"
    :delete-permission="Permission.WRITE_ARTICLE_GROUPS"
    show-contrast-warning
  />
</template>
