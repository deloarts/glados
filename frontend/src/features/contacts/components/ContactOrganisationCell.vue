<script setup lang="ts">
/**
 * The organisation a contact belongs to: an icon and a tag for its kind,
 * then its name, muted when it is archived. A contact of neither shows a
 * muted note.
 */
import { useI18n } from 'vue-i18n'

import { ORGANISATION_ICONS } from '../utils/contactLabels'
import type { ContactOrganisationResponse } from '../types/contactResponse'

defineProps<{
  organisation: ContactOrganisationResponse | null
}>()

const { t } = useI18n()
</script>

<template>
  <span v-if="organisation" class="organisation" :class="{ archived: organisation.archived }">
    <i :class="`mdi ${ORGANISATION_ICONS[organisation.kind]}`" aria-hidden="true" />
    <Tag
      :value="t(`contacts.organisationKinds.${organisation.kind}`)"
      :severity="organisation.kind === 'customer' ? 'info' : 'secondary'"
    />
    <span class="organisation-name">{{ organisation.name }}</span>
  </span>
  <span v-else class="text-muted">{{ t('contacts.noOrganisation') }}</span>
</template>

<style scoped lang="scss">
.organisation {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;

  &.archived .organisation-name {
    color: var(--p-text-muted-color);
  }
}
</style>
