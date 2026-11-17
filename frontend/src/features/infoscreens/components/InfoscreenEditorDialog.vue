<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { fetchAllPages } from '@/core/api/fetchAllPages'
import { useHostStore } from '@/core/host/stores/hostStore'
import { LOCALE_MESSAGES, localeEndonym } from '@/core/i18n/localeMessages'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { extractApiError } from '@/core/utils/errors'
import { HelpButton, HelpDrawer } from '@/shared/help'
import {
  getMachinePools,
  getProductionMachines,
  type MachinePoolResponse,
  type ProductionMachineResponse,
} from '@/features/production-machines'
import InfoscreenBarEditor from './InfoscreenBarEditor.vue'
import InfoscreenPageEditor from './InfoscreenPageEditor.vue'
import InfoscreenScheduleEditor from './InfoscreenScheduleEditor.vue'
import { createInfoscreen, updateInfoscreen } from '../api/infoscreensApi'
import {
  MAX_PAGES,
  ROTATION_SECONDS,
  THEME_PRESETS,
  defaultFooter,
  defaultHeader,
  emptyPage,
  isBarComplete,
  isWidgetComplete,
  normaliseBar,
  normaliseWidget,
  toBarState,
} from '../utils/infoscreenLayouts'
import {
  isGridValid,
  toScheduleGrid,
  toScheduleRequest,
  type ScheduleGrid,
} from '../utils/displaySchedule'

import type {
  DisplayScheduleMode,
  InfoscreenBarState,
  InfoscreenColorMode,
  InfoscreenCreateRequest,
  InfoscreenLanguage,
  InfoscreenThemePreset,
  InfoscreenPage,
  InfoscreenResponse,
} from '../types/infoscreenResponse'

/**
 * Creates or edits an infoscreen: its look and language, how fast it turns
 * its pages, when its displays are on, and the pages with a widget per
 * layout position. Without the permission
 * to write infoscreens the form opens read only and cannot be saved.
 */
const props = defineProps<{
  infoscreen: InfoscreenResponse | null
  canWrite: boolean
  /** The tooltip of the disabled Save button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  saved: [infoscreen: InfoscreenResponse]
  preview: [infoscreen: InfoscreenResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const hostStore = useHostStore()
const { primaryColors } = storeToRefs(useLayoutStore())

interface EditorPageState {
  key: number
  page: InfoscreenPage
}

interface InfoscreenEditorForm {
  name: string
  description: string
  color_mode: InfoscreenColorMode
  theme_preset: InfoscreenThemePreset | null
  primary_color: string | null
  language: InfoscreenLanguage | null
  rotation_seconds: number
  show_banner: boolean
  show_header: boolean
  header: InfoscreenBarState
  show_footer: boolean
  footer: InfoscreenBarState
  display_schedule_mode: DisplayScheduleMode
  display_schedule: ScheduleGrid | null
  off_on_holidays: boolean
  pages: EditorPageState[]
}

let nextKey = 0

function emptyForm(): InfoscreenEditorForm {
  return {
    name: '',
    description: '',
    color_mode: 'dark',
    theme_preset: null,
    primary_color: null,
    language: null,
    rotation_seconds: ROTATION_SECONDS.default,
    show_banner: true,
    show_header: true,
    header: defaultHeader(),
    show_footer: false,
    footer: defaultFooter(),
    display_schedule_mode: 'default',
    display_schedule: null,
    off_on_holidays: false,
    pages: [{ key: nextKey++, page: emptyPage() }],
  }
}

function formFrom(screen: InfoscreenResponse): InfoscreenEditorForm {
  return {
    name: screen.name,
    description: screen.description ?? '',
    color_mode: screen.color_mode,
    theme_preset: screen.theme_preset,
    primary_color: screen.primary_color,
    language: screen.language,
    rotation_seconds: screen.rotation_seconds,
    show_banner: screen.show_banner,
    show_header: screen.show_header,
    header: toBarState(screen.header),
    show_footer: screen.show_footer,
    footer: toBarState(screen.footer),
    display_schedule_mode: screen.display_schedule_mode,
    display_schedule: toScheduleGrid(screen.display_schedule).grid,
    off_on_holidays: screen.off_on_holidays,
    pages: screen.pages.map((page) => ({
      key: nextKey++,
      page: { layout: page.layout, slots: page.slots.map((slot) => (slot ? { ...slot } : null)) },
    })),
  }
}

const form = reactive<InfoscreenEditorForm>(emptyForm())
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const explainVisible = ref(false)
// A stored window off the half hours shows widened, with a note, until the screen is saved.
const scheduleRounded = ref(false)

const machines = ref<ProductionMachineResponse[]>([])
const pools = ref<MachinePoolResponse[]>([])
let optionsLoaded = false

async function loadOptions(): Promise<void> {
  if (optionsLoaded) return
  optionsLoaded = true
  try {
    const [machineRows, poolRows] = await Promise.all([
      fetchAllPages((window) =>
        getProductionMachines({ ...window, order_by: 'internal_name', order_dir: 'asc' }),
      ),
      fetchAllPages((window) => getMachinePools({ ...window, order_by: 'name', order_dir: 'asc' })),
    ])
    machines.value = machineRows
    pools.value = poolRows
  } catch {
    // The pickers stay empty and the next opening tries again.
    optionsLoaded = false
  }
}

watch(visible, (open) => {
  if (!open) return
  Object.assign(form, props.infoscreen ? formFrom(props.infoscreen) : emptyForm())
  scheduleRounded.value = toScheduleGrid(props.infoscreen?.display_schedule).rounded
  submitted.value = false
  errorMessage.value = null
  void loadOptions()
})

const isEdit = computed(() => props.infoscreen != null)

const colorModeOptions = computed(() => [
  { value: 'dark', label: t('infoscreens.colorModes.dark') },
  { value: 'light', label: t('infoscreens.colorModes.light') },
])

const presetOptions = computed(() => [
  { value: null, label: t('infoscreens.editor.tenantDefault') },
  ...THEME_PRESETS.map((value) => ({ value, label: value })),
])

// Each language the app speaks, by its own name, after the default of this installation.
const languageOptions = computed(() => [
  { value: null, label: t('infoscreens.editor.tenantDefault') },
  ...(Object.keys(LOCALE_MESSAGES) as InfoscreenLanguage[]).map((value) => ({
    value,
    label: localeEndonym(value),
  })),
])

// The palettes this installation offers, the same list the account page picks from.
const primaryOptions = computed(() =>
  primaryColors.value.filter((color) => hostStore.themePrimaries.includes(color.name)),
)

const nameError = computed(() =>
  submitted.value && form.name.trim() === '' ? t('infoscreens.errors.nameRequired') : null,
)

function validate(): string | null {
  if (form.name.trim() === '') return t('infoscreens.errors.nameRequired')
  if (form.pages.length === 0) return t('infoscreens.errors.pagesRequired')
  const incomplete = form.pages.some(({ page }) => page.slots.some((slot) => !isWidgetComplete(slot)))
  if (incomplete) return t('infoscreens.errors.widgetIncomplete')
  const barIncomplete =
    (form.show_header && !isBarComplete(form.header)) ||
    (form.show_footer && !isBarComplete(form.footer))
  if (barIncomplete) return t('infoscreens.errors.barText')
  if (form.display_schedule_mode === 'own' && !isGridValid(form.display_schedule)) return t('infoscreens.errors.schedule')
  return null
}

function addPage(): void {
  if (form.pages.length >= MAX_PAGES) return
  form.pages.push({ key: nextKey++, page: emptyPage() })
}

function movePage(index: number, delta: number): void {
  const target = index + delta
  if (target < 0 || target >= form.pages.length) return
  const [row] = form.pages.splice(index, 1)
  if (row) form.pages.splice(target, 0, row)
}

function removePage(index: number): void {
  if (form.pages.length > 1) form.pages.splice(index, 1)
}

async function onSave(): Promise<void> {
  submitted.value = true
  errorMessage.value = validate()
  if (errorMessage.value || !props.canWrite) return
  saving.value = true
  // The create body is a complete update body as well.
  const body: InfoscreenCreateRequest = {
    name: form.name.trim(),
    description: form.description.trim() || null,
    color_mode: form.color_mode,
    theme_preset: form.theme_preset,
    primary_color: form.primary_color,
    language: form.language,
    rotation_seconds: form.rotation_seconds,
    show_banner: form.show_banner,
    show_header: form.show_header,
    header: normaliseBar(form.header),
    show_footer: form.show_footer,
    footer: normaliseBar(form.footer),
    display_schedule_mode: form.display_schedule_mode,
    // Its own schedule goes along unchanged while the screen follows another,
    // so switching back to it finds it as it was.
    display_schedule: form.display_schedule ? toScheduleRequest(form.display_schedule) : null,
    off_on_holidays: form.off_on_holidays,
    pages: form.pages.map(({ page }) => ({
      layout: page.layout,
      slots: page.slots.map(normaliseWidget),
    })),
  }
  try {
    const saved = props.infoscreen
      ? await updateInfoscreen(props.infoscreen.id, body)
      : await createInfoscreen(body)
    visible.value = false
    emit('saved', saved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('infoscreens.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-lg)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">
          {{ isEdit ? t('infoscreens.editor.editTitle') : t('infoscreens.editor.createTitle') }}
        </span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('infoscreens.editor.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('infoscreens.editor.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <form class="editor" @submit.prevent="onSave">
      <fieldset class="dialog-section" :disabled="!canWrite">
        <legend>{{ t('infoscreens.editor.screenSection') }}</legend>
        <div class="grid">
          <div class="field field-wide">
            <label for="infoscreen-name">{{ t('infoscreens.fields.name') }} *</label>
            <InputText
              id="infoscreen-name"
              v-model="form.name"
              :maxlength="100"
              :invalid="!!nameError"
              autocomplete="off"
              fluid
              autofocus
              data-testid="infoscreen-name"
            />
            <small v-if="nameError" class="field-error">{{ nameError }}</small>
          </div>
          <div class="field field-wide">
            <label for="infoscreen-description">{{ t('infoscreens.fields.description') }}</label>
            <Textarea
              id="infoscreen-description"
              v-model="form.description"
              rows="2"
              auto-resize
              :maxlength="500"
              fluid
            />
          </div>
          <div class="field">
            <label id="infoscreen-color-mode-label" for="infoscreen-color-mode">{{ t('infoscreens.fields.colorMode') }}</label>
            <Select
              v-model="form.color_mode"
              input-id="infoscreen-color-mode"
              aria-labelledby="infoscreen-color-mode-label"
              :options="colorModeOptions"
              option-label="label"
              option-value="value"
              fluid
            />
          </div>
          <div class="field">
            <label id="infoscreen-preset-label" for="infoscreen-preset">{{ t('infoscreens.fields.themePreset') }}</label>
            <Select
              v-model="form.theme_preset"
              input-id="infoscreen-preset"
              aria-labelledby="infoscreen-preset-label"
              :options="presetOptions"
              option-label="label"
              option-value="value"
              fluid
            />
          </div>
          <div class="field">
            <label id="infoscreen-primary-label" for="infoscreen-primary">{{ t('infoscreens.fields.primaryColor') }}</label>
            <Select
              v-model="form.primary_color"
              input-id="infoscreen-primary"
              aria-labelledby="infoscreen-primary-label"
              :options="primaryOptions"
              option-label="name"
              option-value="name"
              :placeholder="t('infoscreens.editor.tenantDefault')"
              show-clear
              fluid
            >
              <template #option="{ option }">
                <span class="color-option">
                  <span class="color-swatch" :style="{ background: option.palette[500] }" />
                  {{ option.name }}
                </span>
              </template>
            </Select>
            <small class="hint">{{ t('infoscreens.fields.primaryColorHint') }}</small>
          </div>
          <div class="field">
            <label id="infoscreen-language-label" for="infoscreen-language">{{ t('infoscreens.fields.language') }}</label>
            <Select
              v-model="form.language"
              input-id="infoscreen-language"
              aria-labelledby="infoscreen-language-label"
              :options="languageOptions"
              option-label="label"
              option-value="value"
              fluid
              data-testid="infoscreen-language"
            />
            <small class="hint">{{ t('infoscreens.fields.languageHint') }}</small>
          </div>
          <div class="field">
            <label for="infoscreen-rotation">{{ t('infoscreens.fields.rotationSeconds') }}</label>
            <InputNumber
              v-model="form.rotation_seconds"
              input-id="infoscreen-rotation"
              :min="ROTATION_SECONDS.min"
              :max="ROTATION_SECONDS.max"
              :allow-empty="false"
              show-buttons
              fluid
              data-testid="infoscreen-rotation"
            />
            <small class="hint">
              {{ t('infoscreens.fields.rotationSecondsHint', ROTATION_SECONDS) }}
            </small>
          </div>
          <label class="check-row field-wide">
            <Checkbox v-model="form.show_banner" binary input-id="infoscreen-banner" />
            {{ t('infoscreens.fields.showBanner') }}
          </label>
        </div>
      </fieldset>

      <fieldset class="dialog-section" :disabled="!canWrite">
        <legend class="section-legend">
          {{ t('infoscreens.editor.scheduleSection') }}
          <HelpButton slug="resources/display-schedule" anchor="schedule" size="small" rounded />
        </legend>
        <InfoscreenScheduleEditor
          v-model:mode="form.display_schedule_mode"
          v-model:schedule="form.display_schedule"
          v-model:off-on-holidays="form.off_on_holidays"
          id-prefix="infoscreen"
          :disabled="!canWrite"
          :rounded="scheduleRounded"
        />
      </fieldset>

      <fieldset class="dialog-section" :disabled="!canWrite">
        <legend class="section-legend">
          {{ t('infoscreens.editor.barsSection') }}
          <HelpButton slug="resources/infoscreen-pages" anchor="bars" size="small" rounded />
        </legend>
        <p class="hint">{{ t('infoscreens.editor.barsHint') }}</p>
        <div class="bars">
          <InfoscreenBarEditor
            v-model:show="form.show_header"
            v-model:bar="form.header"
            :label="t('infoscreens.fields.showHeader')"
            id-prefix="infoscreen-header"
            :submitted="submitted"
          />
          <InfoscreenBarEditor
            v-model:show="form.show_footer"
            v-model:bar="form.footer"
            :label="t('infoscreens.fields.showFooter')"
            id-prefix="infoscreen-footer"
            :submitted="submitted"
          />
        </div>
      </fieldset>

      <fieldset class="dialog-section" :disabled="!canWrite">
        <legend class="section-legend">
          {{ t('infoscreens.editor.pagesSection') }}
          <HelpButton slug="resources/infoscreen-pages" anchor="pages" size="small" rounded />
        </legend>
        <p class="hint">{{ t('infoscreens.editor.pagesHint') }}</p>
        <template v-for="(row, index) in form.pages" :key="row.key">
          <Divider v-if="index > 0" />
          <InfoscreenPageEditor
            v-model:page="row.page"
            :index="index"
            :count="form.pages.length"
            :machines="machines"
            :pools="pools"
            :submitted="submitted"
            @move-up="movePage(index, -1)"
            @move-down="movePage(index, 1)"
            @remove="removePage(index)"
          />
        </template>
        <Button
          type="button"
          icon="mdi mdi-plus"
          :label="t('infoscreens.editor.addPage')"
          size="small"
          text
          class="add-page"
          :disabled="form.pages.length >= MAX_PAGES"
          data-testid="infoscreen-add-page"
          @click="addPage"
        />
      </fieldset>
    </form>

    <template #footer>
      <Button
        v-if="infoscreen"
        type="button"
        :label="t('infoscreens.actions.preview')"
        icon="mdi mdi-open-in-new"
        severity="secondary"
        text
        class="footer-start"
        v-tooltip.top="t('infoscreens.editor.previewHint')"
        @click="emit('preview', infoscreen)"
      />
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <span v-tooltip.top="canWrite ? undefined : missingHint">
        <Button
          :label="t('common.save')"
          icon="mdi mdi-content-save-outline"
          :loading="saving"
          :disabled="!canWrite"
          data-testid="infoscreen-save"
          @click="onSave"
        />
      </span>
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/infoscreens" />
</template>

<style scoped lang="scss">
.section-legend {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3) var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.bars {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field-wide {
  grid-column: 1 / -1;
}

.check-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.color-option {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.color-swatch {
  width: 0.9rem;
  height: 0.9rem;
  border-radius: 50%;
}

.add-page {
  align-self: flex-start;
}

.hint {
  margin: 0;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}

.footer-start {
  margin-right: auto;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
