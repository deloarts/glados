<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

defineProps<{
  item: BoughtItemResponse
}>()

const { t } = useI18n()
</script>

<template>
  <!-- CAD marks a row PDM owns and writes and shows as PDM, WEB one that
       was entered here. The column's filter offers the same labels. -->
  <Tag
    :value="t(`boughtItems.catalogue.dataSources.${item.data_source}`)"
    :severity="item.data_source === 'CAD' ? 'info' : 'secondary'"
  />
</template>
