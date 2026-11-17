<script setup lang="ts">
// The theme part of the user dialog: preset, dark mode, primary colour and
// surface, under their own section header. Spans the dialog's field grid
// and lays its fields out in the same two columns.
import { useI18n } from 'vue-i18n'

import { useThemeOptions } from '../composables/useThemeOptions'

const preset = defineModel<string | null>('preset', { required: true })
const darkMode = defineModel<boolean>('darkMode', { required: true })
const primary = defineModel<string | null>('primary', { required: true })
const surface = defineModel<string | null>('surface', { required: true })

const { t } = useI18n()
const { presetOptions, filteredPrimaryColors, filteredSurfaces } = useThemeOptions()
</script>

<template>
  <div class="theme-fields">
    <div class="field field-wide section-header">
      <span>{{ t('settings.users.fields.theme') }}</span>
    </div>

    <div class="field">
      <label id="u-theme-preset-label" for="u-theme-preset">{{ t('settings.users.fields.themePreset') }}</label>
      <Select id="u-theme-preset" aria-labelledby="u-theme-preset-label" v-model="preset" :options="presetOptions" fluid />
    </div>

    <div class="field">
      <label for="u-dark-mode">{{ t('settings.users.fields.themeDarkMode') }}</label>
      <ToggleSwitch v-model="darkMode" input-id="u-dark-mode" />
    </div>

    <div class="field">
      <label id="u-theme-primary-label" for="u-theme-primary">{{ t('settings.users.fields.themePrimary') }}</label>
      <Select
        id="u-theme-primary"
        aria-labelledby="u-theme-primary-label"
        v-model="primary"
        :options="filteredPrimaryColors"
        option-label="name"
        option-value="name"
        fluid
      >
        <template #option="{ option }">
          <div class="color-option">
            <span class="color-swatch" :style="{ background: option.palette[500] }" />
            {{ option.name }}
          </div>
        </template>
      </Select>
    </div>

    <div class="field">
      <label id="u-theme-surface-label" for="u-theme-surface">{{ t('settings.users.fields.themeSurface') }}</label>
      <Select
        id="u-theme-surface"
        aria-labelledby="u-theme-surface-label"
        v-model="surface"
        :options="filteredSurfaces"
        option-label="name"
        option-value="name"
        fluid
      >
        <template #option="{ option }">
          <div class="color-option">
            <span class="color-swatch" :style="{ background: option.palette[500] }" />
            {{ option.name }}
          </div>
        </template>
      </Select>
    </div>
  </div>
</template>

<style scoped lang="scss">
// Takes the full width of the dialog's field grid and repeats its columns.
.theme-fields {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-wide {
  grid-column: 1 / -1;
}

.section-header {
  span {
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--p-text-muted-color);
    border-bottom: 1px solid var(--p-content-border-color);
    padding-bottom: var(--space-1);
  }
}

.color-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.color-swatch {
  width: 0.9rem;
  height: 0.9rem;
  border-radius: 50%;
  flex-shrink: 0;
  border: 1px solid var(--p-content-border-color);
}
</style>
