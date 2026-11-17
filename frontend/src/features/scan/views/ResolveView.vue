<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { resolvePublicId } from '../api/resolvePublicId'
import { routeForResolved } from '../resourceRoutes'

/**
 * Where the link in a QR code lands, from a label or a report page: looks
 * the public id up and replaces itself with the record's page, so the back
 * button skips it. The record's page says when a newer revision exists.
 */

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const problem = ref<'notFound' | 'noRoute' | null>(null)

onMounted(async () => {
  try {
    const resolved = await resolvePublicId(String(route.params.publicId))
    const path = routeForResolved(resolved)
    if (path) await router.replace(path)
    else problem.value = 'noRoute'
  } catch {
    problem.value = 'notFound'
  }
})
</script>

<template>
  <div class="resolve-view">
    <Message v-if="problem === 'notFound'" severity="error" data-testid="resolve-not-found">
      {{ t('scan.errors.notFound') }}
    </Message>
    <Message v-else-if="problem === 'noRoute'" severity="info" data-testid="resolve-no-route">
      {{ t('scan.foundNoRoute') }}
    </Message>
    <p v-else class="resolve-pending">{{ t('scan.resolving') }}</p>
  </div>
</template>

<style scoped lang="scss">
.resolve-view {
  padding: var(--space-4);
}

.resolve-pending {
  color: var(--p-text-muted-color);
}
</style>
