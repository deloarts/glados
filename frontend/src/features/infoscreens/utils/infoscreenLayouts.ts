import type {
  ClockStyle,
  InfoscreenBar,
  InfoscreenBarArea,
  InfoscreenBarItem,
  InfoscreenBarState,
  InfoscreenLayout,
  InfoscreenPage,
  InfoscreenThemePreset,
  InfoscreenWidgetConfig,
  InfoscreenWidgetType,
  MessageSeverity,
  MessageTextAlign,
  MessageVerticalAlign,
} from '../types/infoscreenResponse'

/** How many widgets each page layout holds, one slot per position. */
export const LAYOUT_SLOT_COUNTS: Record<InfoscreenLayout, number> = {
  full: 1,
  two_columns: 2,
  main_side: 2,
  grid_2x2: 4,
  two_rows: 2,
  three_rows: 3,
  grid_2x3: 6,
  grid_3x2: 6,
}

export const LAYOUTS = Object.keys(LAYOUT_SLOT_COUNTS) as InfoscreenLayout[]

export const WIDGET_TYPES: InfoscreenWidgetType[] = [
  'machine_board',
  'lots_due',
  'late_lots',
  'qa_queue',
  'deliveries_expected',
  'machine_detail',
  'products',
  'projects',
  'weather',
  'message',
  'clock',
]

/** The theme presets a screen can use; null keeps the tenant's default. */
export const THEME_PRESETS: InfoscreenThemePreset[] = ['Aura', 'Lara', 'Material', 'Nora']

/** The styles of a message widget; none is plain text without colour or icon. */
export const MESSAGE_SEVERITIES: MessageSeverity[] = ['none', 'info', 'success', 'warning', 'danger']

/** Where a message sits in its widget, across and down, today's look as the default. */
export const MESSAGE_TEXT_ALIGNS: MessageTextAlign[] = ['left', 'center', 'right']
export const MESSAGE_VERTICAL_ALIGNS: MessageVerticalAlign[] = ['top', 'middle', 'bottom']
export const DEFAULT_TEXT_ALIGN: MessageTextAlign = 'left'
export const DEFAULT_VERTICAL_ALIGN: MessageVerticalAlign = 'middle'

/** The server keeps a message text to this many characters. */
export const MESSAGE_TEXT_MAX_LENGTH = 2000

/** How a clock widget draws the time; binary is a binary coded decimal clock. */
export const CLOCK_STYLES: ClockStyle[] = ['digital', 'analogue', 'binary']

/** The server keeps a screen to this many pages. */
export const MAX_PAGES = 20

export const ROTATION_SECONDS = { min: 10, max: 600, default: 30 } as const
export const NEXT_COUNT = { min: 1, max: 10, default: 3 } as const
export const LOTS_DUE_HORIZON_DAYS = { min: 1, max: 60, default: 7 } as const
export const DELIVERIES_HORIZON_DAYS = { min: 0, max: 30, default: 0 } as const
export const DETAIL_NEXT_COUNT = { min: 0, max: 5, default: 3 } as const
export const WEATHER_DAYS = { min: 0, max: 7, default: 3 } as const

/** A fresh widget of the given type, with the defaults the server applies too. */
export function defaultWidget(type: InfoscreenWidgetType): InfoscreenWidgetConfig {
  switch (type) {
    case 'machine_board':
      return { type, title: null, machine_ids: [], pool_ids: [], next_count: NEXT_COUNT.default }
    case 'lots_due':
      return {
        type,
        title: null,
        horizon_days: LOTS_DUE_HORIZON_DAYS.default,
        pool_ids: [],
        show_customer: false,
      }
    case 'late_lots':
      return { type, title: null, show_customer: false }
    case 'qa_queue':
      return { type, title: null }
    case 'deliveries_expected':
      return {
        type,
        title: null,
        horizon_days: DELIVERIES_HORIZON_DAYS.default,
        show_overdue: false,
      }
    case 'machine_detail':
      // No machine yet; the widget is incomplete until one is picked.
      return {
        type,
        title: null,
        machine_id: 0,
        next_count: DETAIL_NEXT_COUNT.default,
        show_drawing: true,
        show_customer: false,
      }
    case 'products':
      return { type, title: null, show_projects: false, show_customer: false }
    case 'projects':
      return { type, title: null, show_customer: false }
    case 'weather':
      // No place yet; the widget is incomplete until a town is picked.
      return {
        type,
        title: null,
        location_name: '',
        region: null,
        country_code: '',
        latitude: 0,
        longitude: 0,
        days: WEATHER_DAYS.default,
        show_wind: false,
      }
    case 'message':
      return {
        type,
        title: null,
        text: '',
        severity: 'info',
        text_align: DEFAULT_TEXT_ALIGN,
        vertical_align: DEFAULT_VERTICAL_ALIGN,
      }
    case 'clock':
      return {
        type,
        title: null,
        show_date: true,
        show_next_holiday: false,
        show_seconds: false,
        style: 'digital',
      }
  }
}

/**
 * Switches a page to another layout. The widgets already placed keep their
 * position as far as the new layout reaches; new positions start empty and
 * the ones beyond its end are dropped.
 */
export function changeLayout(page: InfoscreenPage, layout: InfoscreenLayout): InfoscreenPage {
  const count = LAYOUT_SLOT_COUNTS[layout]
  const slots = Array.from({ length: count }, (_, index) => page.slots[index] ?? null)
  return { layout, slots }
}

export function emptyPage(layout: InfoscreenLayout = 'full'): InfoscreenPage {
  return changeLayout({ layout, slots: [] }, layout)
}

/** A slot as it is sent: a blank title becomes null and the message text is trimmed. */
export function normaliseWidget(slot: InfoscreenWidgetConfig | null): InfoscreenWidgetConfig | null {
  if (!slot) return null
  const title = slot.title?.trim() ? slot.title.trim() : null
  if (slot.type === 'message') return { ...slot, title, text: slot.text.trim() }
  return { ...slot, title }
}

/** What a header or footer bar can show, in the order they are offered. */
export const BAR_ITEMS: InfoscreenBarItem[] = [
  'logo',
  'app_name',
  'company_name',
  'title',
  'clock',
  'date',
  'next_holiday',
  'last_updated',
  'text',
]

/** The areas of a bar, as they sit on the screen. */
export const BAR_AREAS: InfoscreenBarArea[] = ['left', 'center', 'right']

export function defaultHeader(): InfoscreenBarState {
  return { left: ['logo', 'title'], center: [], right: ['clock'], text: null }
}

export function defaultFooter(): InfoscreenBarState {
  return { left: [], center: [], right: ['last_updated'], text: null }
}

/** A bar from the server in the editor's shape, an absent area being empty. */
export function toBarState(bar: InfoscreenBar): InfoscreenBarState {
  return {
    left: [...(bar.left ?? [])],
    center: [...(bar.center ?? [])],
    right: [...(bar.right ?? [])],
    text: bar.text ?? null,
  }
}

/** Every item of a bar, from the left area to the right one. */
export function barItems(bar: InfoscreenBarState): InfoscreenBarItem[] {
  return BAR_AREAS.flatMap((area) => bar[area])
}

/**
 * A bar as it is sent: each item once across all three areas, the first
 * place wins, and a text only while the custom text item is in the bar.
 */
export function normaliseBar(bar: InfoscreenBarState): InfoscreenBarState {
  const seen = new Set<InfoscreenBarItem>()
  function keepNew(items: InfoscreenBarItem[]): InfoscreenBarItem[] {
    return items.filter((item) => {
      if (seen.has(item)) return false
      seen.add(item)
      return true
    })
  }
  const left = keepNew(bar.left)
  const center = keepNew(bar.center)
  const right = keepNew(bar.right)
  const text = seen.has('text') ? bar.text?.trim() || null : null
  return { left, center, right, text }
}

/** A bar that shows the custom text item needs a text for it. */
export function isBarComplete(bar: InfoscreenBarState): boolean {
  return !barItems(bar).includes('text') || (bar.text?.trim() ?? '') !== ''
}

/**
 * Whether a widget can be saved: a message needs its text, the weather a
 * town and the machine detail a machine.
 */
export function isWidgetComplete(slot: InfoscreenWidgetConfig | null): boolean {
  if (!slot) return true
  if (slot.type === 'message') return slot.text.trim() !== ''
  if (slot.type === 'weather') return slot.location_name.trim() !== '' && slot.country_code !== ''
  if (slot.type === 'machine_detail') return slot.machine_id > 0
  return true
}
