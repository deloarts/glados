<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { localeEndonym } from '@/core/i18n/localeMessages'
import type { PdmAddinLanguage } from '../../types/adminSettingsTypes'

// The head of the SolidWorks PDM tab's datacard section: its title and
// hint, the mapping problems that block a save, and the add-in language.
// That is the language the pat API gives catalogue labels (article groups,
// fabrication methods and so on) in, and with that the language the
// SolidWorks add-in writes them into the datacards in. An empty value
// follows the instance's default language.
defineProps<{ canWrite: boolean; kindMismatch: boolean; writebackMismatch: boolean }>()

const addinLanguage = defineModel<PdmAddinLanguage>({ required: true })

const { t } = useI18n()
const host = useHostStore()
const id = useId()

const options = computed(() => [
  { label: t('adminSettings.solidworksPdm.pdm.addinLanguage.defaultLanguage'), value: '' },
  ...host.languages.map((code) => ({ label: localeEndonym(code), value: code })),
])
</script>

<template>
  <p class="section-label">{{ t('adminSettings.solidworksPdm.pdm.datacardSection') }}</p>
  <p class="hint">{{ t('adminSettings.solidworksPdm.pdmHint') }}</p>
  <div class="field-row">
    <label :id="`${id}-label`" :for="id">
      {{ t('adminSettings.solidworksPdm.pdm.addinLanguage.label') }}
      <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.addinLanguage.hint') }}</span>
    </label>
    <Select
      :id="id"
      :aria-labelledby="`${id}-label`"
      v-model="addinLanguage"
      :options="options"
      option-label="label"
      option-value="value"
      :disabled="!canWrite"
      fluid
    />
  </div>
  <Message v-if="kindMismatch" severity="error" :closable="false">
    {{ t('adminSettings.itemFields.validation.kindMismatch') }}
  </Message>
  <Message v-if="writebackMismatch" severity="error" :closable="false">
    {{ t('adminSettings.itemFields.validation.writebackMismatch') }}
  </Message>
</template>
