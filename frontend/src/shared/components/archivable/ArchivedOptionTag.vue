<script setup lang="ts">
// The same "Archived" tag every management table already shows on an
// archived row, reused inside a picker's #option/#value template so an
// archived entry stays visibly distinct in the list and once selected;
// see useArchivableOptions.ts for the composable this pairs with.
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

withDefaults(defineProps<{ tooltip?: string }>(), { tooltip: undefined })
</script>

<template>
  <Tag
    :value="t('common.archivedTag')"
    severity="warn"
    icon="mdi mdi-archive-outline"
    v-tooltip.top="tooltip ?? t('common.archivedTagTooltip')"
  />
</template>
