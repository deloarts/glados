<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { getMeeting } from '../api/meetingsApi'
import { meetingPath } from '../utils/meetingRoutes'

/**
 * /meetings/:id, for links that know only the meeting, such as a scanned
 * public id, a search hit or a notification: looks up its project or
 * product and replaces the route with the meeting's page there. A hash such
 * as a card anchor goes along.
 */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const failed = ref(false)

onMounted(async () => {
  try {
    const meeting = await getMeeting(Number(route.params.id))
    await router.replace({ path: meetingPath(meeting), hash: route.hash })
  } catch {
    failed.value = true
  }
})
</script>

<template>
  <div v-if="failed" class="state-message" data-testid="meeting-redirect-failed">
    <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
    <span>{{ t('meetings.errors.notFound') }}</span>
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
