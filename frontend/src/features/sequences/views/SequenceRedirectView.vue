<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { getSequence } from '../api/sequencesApi'
import { sequenceLocation } from '../utils/routes'

/**
 * /sequences/:id, for links that know only the sequence, such as a scanned
 * public id: looks up its product and moves on to the sequence's page.
 */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const failed = ref(false)

onMounted(async () => {
  try {
    const sequence = await getSequence(Number(route.params.id))
    await router.replace(sequenceLocation(sequence))
  } catch {
    failed.value = true
  }
})
</script>

<template>
  <div v-if="failed" class="state-message">
    <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
    <span>{{ t('sequences.errors.notFound') }}</span>
  </div>
</template>

<style scoped lang="scss">
.state-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--p-text-muted-color);

  .state-icon {
    font-size: var(--font-size-3xl);
  }
}
</style>
