<script setup lang="ts">
/**
 * Where a contact is used, as small tags: the products and projects that
 * link it, the meetings it attends or owns todos in and, for a supplier's
 * contact, the mails it receives. The usage
 * comes from the contact usage route, so a record that starts linking
 * contacts adds its list to that answer and its tags here.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type { ContactUsageResponse } from '../types/contactResponse'

const props = defineProps<{
  contact: { receives_request_mails: boolean; receives_order_mails: boolean }
  usage: ContactUsageResponse | null | undefined
  /** Says so when nothing uses the contact, instead of showing a dash. */
  explainEmpty?: boolean
}>()

const { t } = useI18n()

interface UsageTag {
  key: string
  icon: string
  label: string
  title?: string
  to?: string
}

const tags = computed<UsageTag[]>(() => {
  const shown: UsageTag[] = []
  for (const product of props.usage?.products ?? []) {
    shown.push({
      key: `product-${product.id}`,
      icon: 'mdi mdi-anvil',
      label: product.number,
      to: `/workspace/products/${product.id}`,
    })
  }
  for (const project of props.usage?.projects ?? []) {
    shown.push({
      key: `project-${project.id}`,
      icon: 'mdi mdi-folder-outline',
      label: project.number,
      to: `/workspace/projects/${project.id}`,
    })
  }
  for (const meeting of props.usage?.meetings ?? []) {
    shown.push({
      key: `meeting-${meeting.id}`,
      icon: 'mdi mdi-forum-outline',
      label: meeting.meeting_number,
      title: meeting.name,
      to: `/meetings/${meeting.id}`,
    })
  }
  if (props.contact.receives_request_mails) {
    shown.push({ key: 'request', icon: 'mdi mdi-email-fast-outline', label: t('contacts.usedIn.requestMails') })
  }
  if (props.contact.receives_order_mails) {
    shown.push({ key: 'order', icon: 'mdi mdi-cart-outline', label: t('contacts.usedIn.orderMails') })
  }
  return shown
})
</script>

<template>
  <span v-if="tags.length" class="used-in" data-testid="contact-used-in">
    <template v-for="tag in tags" :key="tag.key">
      <RouterLink v-if="tag.to" :to="tag.to" :title="tag.title" class="used-in-link" @click.stop>
        <Tag :value="tag.label" :icon="tag.icon" severity="secondary" />
      </RouterLink>
      <Tag v-else :value="tag.label" :icon="tag.icon" severity="secondary" />
    </template>
  </span>
  <span v-else-if="explainEmpty" class="empty-note">{{ t('contacts.usedIn.nothing') }}</span>
  <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
</template>

<style scoped lang="scss">
.used-in {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.used-in-link {
  text-decoration: none;
}
</style>
