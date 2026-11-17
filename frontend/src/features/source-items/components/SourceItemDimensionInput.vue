<script setup lang="ts">
import { reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

type DimensionShape = 'box' | 'hollow-box' | 'rod' | 'hollow-rod' | 'custom'
type DimensionField = 'a' | 'b' | 'c' | 'd'

const props = defineProps<{ id?: string }>()

const dimension = defineModel<string>({ default: '' })

const { t } = useI18n()

const dimensionShapeOptions: { label: string; value: DimensionShape; icon: string }[] = [
  { label: t('sourceItems.dimensionShapes.box'), value: 'box', icon: 'mdi-cube' },
  {
    label: t('sourceItems.dimensionShapes.hollowBox'),
    value: 'hollow-box',
    icon: 'mdi-cube-outline',
  },
  { label: t('sourceItems.dimensionShapes.rod'), value: 'rod', icon: 'mdi-cylinder' },
  { label: t('sourceItems.dimensionShapes.hollowRod'), value: 'hollow-rod', icon: 'mdi-pipe' },
  { label: t('sourceItems.dimensionShapes.custom'), value: 'custom', icon: 'mdi-creation' },
]

function dimensionShapeIcon(shape: DimensionShape): string {
  return dimensionShapeOptions.find((option) => option.value === shape)?.icon ?? 'mdi-cube'
}

const shape = ref<DimensionShape>('box')
const numbers = reactive<{
  a: number | null
  b: number | null
  c: number | null
  d: number | null
}>({
  a: null,
  b: null,
  c: null,
  d: null,
})
const customText = ref('')

// Which fields exist, and their labels, differ by shape.
const FIELD_LABELS: Record<DimensionShape, Partial<Record<DimensionField, string>>> = {
  box: {
    a: t('sourceItems.dimensionFields.width'),
    b: t('sourceItems.dimensionFields.height'),
    c: t('sourceItems.dimensionFields.thickness'),
  },
  'hollow-box': {
    a: t('sourceItems.dimensionFields.width'),
    b: t('sourceItems.dimensionFields.height'),
    c: t('sourceItems.dimensionFields.length'),
    d: t('sourceItems.dimensionFields.wallThickness'),
  },
  rod: {
    a: t('sourceItems.dimensionFields.diameter'),
    b: t('sourceItems.dimensionFields.length'),
  },
  'hollow-rod': {
    a: t('sourceItems.dimensionFields.diameter'),
    b: t('sourceItems.dimensionFields.length'),
    c: t('sourceItems.dimensionFields.wallThickness'),
  },
  custom: {},
}

const baseId = props.id ?? useId()

function fieldId(field: DimensionField): string {
  return `${baseId}-${field}`
}

function fieldLabel(field: DimensionField): string {
  return FIELD_LABELS[shape.value][field] ?? ''
}

// Once every field is filled the biggest value leads, so 400 x 20 x 100
// reads back as 400 x 100 x 20. A diameter is never reordered.
function normalizeBoxOrder(): void {
  const { a, b, c } = numbers
  if (shape.value !== 'box' || a === null || b === null || c === null) return
  const sorted = [a, b, c].sort((x, y) => y - x)
  numbers.a = sorted[0]!
  numbers.b = sorted[1]!
  numbers.c = sorted[2]!
}

function normalizeProfileOrder(): void {
  const { a, b, c, d } = numbers
  if (shape.value !== 'hollow-box' || a === null || b === null || c === null || d === null) return
  const sorted = [a, b].sort((x, y) => y - x)
  numbers.a = sorted[0]!
  numbers.b = sorted[1]!
}

function formatDimension(): string {
  const { a, b, c, d } = numbers

  switch (shape.value) {
    case 'box':
      return a !== null && b !== null && c !== null ? `${a} × ${b} × ${c}` : ''
    case 'hollow-box':
      return a !== null && b !== null && c !== null && d !== null ? `${a} × ${b} × ${c} × ${d}` : ''
    case 'rod':
      return a !== null && b !== null ? `Ø${a} × ${b}` : ''
    case 'hollow-rod':
      return a !== null && b !== null && c !== null ? `Ø${a} × ${b} × ${c}` : ''
    case 'custom':
      return customText.value
    default:
      return ''
  }
}

const NUMBER = String.raw`-?\d+(?:\.\d+)?`
const HOLLOW_ROD_RE = new RegExp(`^Ø(${NUMBER})\\s*×\\s*(${NUMBER})\\s*×\\s*(${NUMBER})$`)
const ROD_RE = new RegExp(`^Ø(${NUMBER})\\s*×\\s*(${NUMBER})$`)
const HOLLOW_BOX_RE = new RegExp(
  `^(${NUMBER})\\s*×\\s*(${NUMBER})\\s*×\\s*(${NUMBER})\\s*×\\s*(${NUMBER})$`,
)
const BOX_RE = new RegExp(`^(${NUMBER})\\s*×\\s*(${NUMBER})\\s*×\\s*(${NUMBER})$`)

function applyParsed(value: string): void {
  const trimmed = value.trim()

  const hollowRod = HOLLOW_ROD_RE.exec(trimmed)
  if (hollowRod) {
    shape.value = 'hollow-rod'
    Object.assign(numbers, {
      a: Number(hollowRod[1]),
      b: Number(hollowRod[2]),
      c: Number(hollowRod[3]),
      d: null,
    })
    return
  }

  const rod = ROD_RE.exec(trimmed)
  if (rod) {
    shape.value = 'rod'
    Object.assign(numbers, { a: Number(rod[1]), b: Number(rod[2]), c: null, d: null })
    return
  }

  const hollowBox = HOLLOW_BOX_RE.exec(trimmed)
  if (hollowBox) {
    shape.value = 'hollow-box'
    Object.assign(numbers, {
      a: Number(hollowBox[1]),
      b: Number(hollowBox[2]),
      c: Number(hollowBox[3]),
      d: Number(hollowBox[4]),
    })
    return
  }

  const box = BOX_RE.exec(trimmed)
  if (box) {
    shape.value = 'box'
    Object.assign(numbers, { a: Number(box[1]), b: Number(box[2]), c: Number(box[3]), d: null })
    return
  }

  shape.value = 'custom'
  Object.assign(numbers, { a: null, b: null, c: null, d: null })
  customText.value = trimmed
}

watch(
  dimension,
  (value) => {
    if (value === formatDimension()) return
    applyParsed(value ?? '')
  },
  { immediate: true },
)

watch(
  [shape, numbers, customText],
  () => {
    dimension.value = formatDimension()
  },
  { deep: true },
)

function reset(): void {
  shape.value = 'box'
  Object.assign(numbers, { a: null, b: null, c: null, d: null })
  customText.value = ''
}

defineExpose({ reset })
</script>

<template>
  <div class="dimension-row">
    <Select
      :id="id"
      v-model="shape"
      :aria-label="t('sourceItems.dimensionFields.shape')"
      :options="dimensionShapeOptions"
      option-label="label"
      option-value="value"
      size="small"
      class="dimension-shape-select"
      :pt="{ label: { class: 'dimension-shape-label' } }"
    >
      <template #value="{ value }">
        <i :class="['mdi', dimensionShapeIcon(value)]" aria-hidden="true" />
      </template>
      <template #option="{ option }">
        <div class="dimension-shape-option">
          <i :class="['mdi', option.icon]" aria-hidden="true" />
          <span>{{ option.label }}</span>
        </div>
      </template>
    </Select>

    <template v-if="shape === 'box'">
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber
class="dimension-number" input-class="dimension-number-input"
          :id="fieldId('a')"
          v-model="numbers.a"
          :min="0"
          :max-fraction-digits="2"
          @blur="normalizeBoxOrder"
        />
        <label :for="fieldId('a')">{{ fieldLabel('a') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber
class="dimension-number" input-class="dimension-number-input"
          :id="fieldId('b')"
          v-model="numbers.b"
          :min="0"
          :max-fraction-digits="2"
          @blur="normalizeBoxOrder"
        />
        <label :for="fieldId('b')">{{ fieldLabel('b') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber
class="dimension-number" input-class="dimension-number-input"
          :id="fieldId('c')"
          v-model="numbers.c"
          :min="0"
          :max-fraction-digits="2"
          @blur="normalizeBoxOrder"
        />
        <label :for="fieldId('c')">{{ fieldLabel('c') }}</label>
      </FloatLabel>
    </template>

    <template v-else-if="shape === 'hollow-box'">
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber
class="dimension-number" input-class="dimension-number-input"
          :id="fieldId('a')"
          v-model="numbers.a"
          :min="0"
          :max-fraction-digits="2"
          @blur="normalizeProfileOrder"
        />
        <label :for="fieldId('a')">{{ fieldLabel('a') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber
class="dimension-number" input-class="dimension-number-input"
          :id="fieldId('b')"
          v-model="numbers.b"
          :min="0"
          :max-fraction-digits="2"
          @blur="normalizeProfileOrder"
        />
        <label :for="fieldId('b')">{{ fieldLabel('b') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber
class="dimension-number" input-class="dimension-number-input"
          :id="fieldId('c')"
          v-model="numbers.c"
          :min="0"
          :max-fraction-digits="2"
          @blur="normalizeProfileOrder"
        />
        <label :for="fieldId('c')">{{ fieldLabel('c') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber
class="dimension-number" input-class="dimension-number-input"
          :id="fieldId('d')"
          v-model="numbers.d"
          :min="0"
          :max-fraction-digits="2"
          @blur="normalizeProfileOrder"
        />
        <label :for="fieldId('d')">{{ fieldLabel('d') }}</label>
      </FloatLabel>
    </template>

    <template v-else-if="shape === 'rod'">
      <span class="dimension-sep">Ø</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber class="dimension-number" input-class="dimension-number-input" :id="fieldId('a')" v-model="numbers.a" :min="0" :max-fraction-digits="2" />
        <label :for="fieldId('a')">{{ fieldLabel('a') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber class="dimension-number" input-class="dimension-number-input" :id="fieldId('b')" v-model="numbers.b" :min="0" :max-fraction-digits="2" />
        <label :for="fieldId('b')">{{ fieldLabel('b') }}</label>
      </FloatLabel>
    </template>

    <template v-else-if="shape === 'hollow-rod'">
      <span class="dimension-sep">Ø</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber class="dimension-number" input-class="dimension-number-input" :id="fieldId('a')" v-model="numbers.a" :min="0" :max-fraction-digits="2" />
        <label :for="fieldId('a')">{{ fieldLabel('a') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber class="dimension-number" input-class="dimension-number-input" :id="fieldId('b')" v-model="numbers.b" :min="0" :max-fraction-digits="2" />
        <label :for="fieldId('b')">{{ fieldLabel('b') }}</label>
      </FloatLabel>
      <span class="dimension-sep">×</span>
      <FloatLabel variant="on" class="dimension-field">
        <InputNumber class="dimension-number" input-class="dimension-number-input" :id="fieldId('c')" v-model="numbers.c" :min="0" :max-fraction-digits="2" />
        <label :for="fieldId('c')">{{ fieldLabel('c') }}</label>
      </FloatLabel>
    </template>

    <InputText v-else v-model="customText" class="dimension-custom-input" fluid />

    <span class="dimension-unit">[mm]</span>
  </div>
</template>

<style scoped lang="scss">
.dimension-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.dimension-field {
  flex: 0 1 7rem;
  min-width: 5.5rem;
}

.dimension-number {
  width: 100%;
}

.dimension-row :deep(.dimension-number-input) {
  width: 100%;
  min-width: 0;
}

.dimension-row :deep(.dimension-custom-input) {
  width: 20rem;
}

.dimension-shape-select {
  width: 5rem;
  flex: 0 0 auto;
  padding-top: var(--space-1);
  padding-bottom: var(--space-1);
  margin-right: var(--space-5);
}

.dimension-shape-select :deep(.dimension-shape-label) {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-right: 0;
}

.dimension-shape-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.dimension-sep {
  flex: 0 0 auto;
  color: var(--p-text-color);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.dimension-unit {
  flex: 0 0 auto;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
