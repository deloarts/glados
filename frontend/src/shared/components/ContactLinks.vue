<script setup lang="ts">
/**
 * A contact's e-mail address as a link that opens the mail app. In phone
 * mode the phone number joins it below, as a link that starts a call, since
 * a phone is where a tap can do that. A tap on either link never opens the
 * table row it sits in.
 */
import { computed } from 'vue'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

const props = defineProps<{
  email: string | null
  phone?: string | null
}>()

const { phoneMode } = usePhoneLayout()

const shownPhone = computed(() => (phoneMode.value ? (props.phone ?? null) : null))
// A dial string keeps only the digits and a leading plus.
const telHref = computed(() => `tel:${(shownPhone.value ?? '').replace(/[^\d+]/g, '')}`)
</script>

<template>
  <span class="contact-links">
    <a v-if="email" :href="`mailto:${email}`" class="contact-link" @click.stop>{{ email }}</a>
    <a v-if="shownPhone" :href="telHref" class="contact-link" @click.stop>{{ shownPhone }}</a>
    <span v-if="!email && !shownPhone" class="text-muted">{{ getEmptyPlaceholder() }}</span>
  </span>
</template>

<style scoped lang="scss">
.contact-links {
  display: inline-flex;
  flex-direction: column;
  min-width: 0;
}

.contact-link {
  color: var(--p-primary-color);
  overflow-wrap: anywhere;
}
</style>
