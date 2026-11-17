<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { getCalculation } from '../api/getCalculation'
import { toolPath } from '../composables/useSavedCalculation'
import { toolByKey } from '../registry'

/**
 * Where a calculation found by its public id (search, scan) lands: the
 * resolver only knows its internal id, while the tool route needs the tool
 * and the public id, so this page looks it up and moves on.
 */

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const failed = ref(false)

onMounted(async () => {
  try {
    const calculation = await getCalculation(Number(route.params.id))
    const tool = toolByKey(calculation.tool)
    if (!tool) {
      failed.value = true
      return
    }
    await router.replace(toolPath(tool.tab, calculation.public_id))
  } catch {
    failed.value = true
  }
})
</script>

<template>
  <div class="open-calculation">
    <Message v-if="failed" severity="error">{{ t('tools.calculations.errors.notFound') }}</Message>
  </div>
</template>

<style scoped lang="scss">
.open-calculation {
  padding: var(--space-4);
}
</style>
