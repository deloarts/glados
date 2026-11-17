<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  FEATURE_TREE_FIELD,
  MAX_FEATURE_TREE_TEMPLATE_LENGTH,
  propertyLink,
  renderFeatureTreePreview,
  validateFeatureTreeTemplate,
} from '../../utils/featureTreeTemplate'
import type { ItemFieldOwnership } from '../../types/adminSettingsTypes'

// One kind's feature-tree template editor, placed under that kind's
// ItemFieldOwnershipTable on the SolidWorks PDM tab,
// a single-line input bound to AdminPdmSettings.
// made_feature_tree_template/bought_feature_tree_template. The add-in
// writes the text verbatim and SolidWorks resolves each $PRP:"name" link,
// so a chip per mapped custom property inserts such a link at the cursor,
// taking the name from the unsaved field mapping above. The preview shows
// a generic `<Field Label>` per link (never real business data), and the
// inline validation mirrors the backend's own rule
// (domain.services.feature_tree_template.validate_feature_tree_template),
// plus a warning for a link to a property outside the field mapping.
const props = defineProps<{
  fields: ItemFieldOwnership[]
  variableMap: Record<string, string>
  canWrite: boolean
}>()

const template = defineModel<string>({ required: true })

const { t } = useI18n()
const inputRef = ref<HTMLInputElement | null>(null)

function fieldLabel(field: string): string {
  return t(`adminSettings.itemFields.fields.${field}`)
}

function mappedProperty(field: string): string {
  return (props.variableMap[field] ?? '').trim()
}

// Rows whose custom property the add-in or PDM writes into the file. The
// server's write-back variables live only on the datacard, and the
// feature-tree property cannot link to itself.
const linkableFields = computed(() =>
  props.fields.filter(
    (row) =>
      row.mappable &&
      row.owner !== 'server' &&
      row.field !== FEATURE_TREE_FIELD &&
      mappedProperty(row.field) !== '',
  ),
)

const previewLabels = computed<Record<string, string>>(() => {
  const labels: Record<string, string> = {}
  for (const row of props.fields) {
    const property = mappedProperty(row.field)
    if (row.mappable && property) labels[property.toLowerCase()] = `<${fieldLabel(row.field)}>`
  }
  return labels
})

const preview = computed(() => renderFeatureTreePreview(template.value, previewLabels.value))
const validation = computed(() => validateFeatureTreeTemplate(template.value, props.variableMap))

function insertLink(field: string): void {
  if (!props.canWrite) return
  const text = propertyLink(mappedProperty(field))
  const el = inputRef.value
  if (!el) {
    template.value += text
    return
  }
  const start = el.selectionStart ?? template.value.length
  const end = el.selectionEnd ?? template.value.length
  template.value = template.value.slice(0, start) + text + template.value.slice(end)
  void nextTick(() => {
    el.selectionStart = el.selectionEnd = start + text.length
    el.focus()
  })
}
</script>

<template>
  <div class="feature-tree-template">
    <label class="section-label" for="feature-tree-template-input">
      {{ t('adminSettings.itemFields.featureTree.label') }}
    </label>
    <p class="hint">
      {{
        t('adminSettings.itemFields.featureTree.hint', {
          example: propertyLink('Glados.ArticleName'),
        })
      }}
    </p>
    <input
      id="feature-tree-template-input"
      ref="inputRef"
      v-model="template"
      type="text"
      class="feature-tree-input"
      :disabled="!canWrite"
    />
    <div class="chips">
      <Tag
        v-for="row in linkableFields"
        :key="row.field"
        :value="fieldLabel(row.field)"
        severity="secondary"
        class="var-chip"
        role="button"
        tabindex="0"
        v-tooltip.focus="
          t('adminSettings.itemFields.featureTree.insertLinkTooltip', {
            property: mappedProperty(row.field),
          })
        "
        @click="insertLink(row.field)"
        @keydown.enter="insertLink(row.field)"
        @keydown.space.prevent="insertLink(row.field)"
      />
    </div>
    <p class="preview">{{ t('adminSettings.itemFields.featureTree.previewLabel') }}: {{ preview }}</p>
    <Message v-if="validation.controlCharacter" severity="error" :closable="false">
      {{ t('adminSettings.itemFields.featureTree.controlCharacter') }}
    </Message>
    <Message v-if="validation.tooLong" severity="error" :closable="false">
      {{ t('adminSettings.itemFields.featureTree.tooLong', { max: MAX_FEATURE_TREE_TEMPLATE_LENGTH }) }}
    </Message>
    <Message v-if="validation.selfReference" severity="error" :closable="false">
      {{
        t('adminSettings.itemFields.featureTree.selfReference', {
          property: mappedProperty(FEATURE_TREE_FIELD),
        })
      }}
    </Message>
    <Message v-if="validation.unknownProperties.length > 0" severity="warn" :closable="false">
      {{
        t('adminSettings.itemFields.featureTree.unknownProperties', {
          properties: validation.unknownProperties.join(', '),
        })
      }}
    </Message>
  </div>
</template>

<style scoped lang="scss">
.feature-tree-template {
  margin-top: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-label {
  font-weight: 600;
}

.feature-tree-input {
  width: 100%;
  padding: var(--space-2) var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  background: var(--p-content-background);
  color: var(--p-text-color);
  font-family: monospace;
  font-size: var(--font-size-sm);

  &:disabled {
    opacity: 0.6;
  }
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.var-chip {
  cursor: pointer;
  font-family: monospace;
  font-size: var(--font-size-xs);
  user-select: none;

  &:hover {
    opacity: 0.75;
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}

.hint {
  margin: 0;
}

.preview {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  font-family: monospace;
}
</style>
