import type { Schemas } from '@/core/api/generated'

export type InfoscreenResponse = Schemas['InfoscreenResponse']
export type InfoscreenTerminalRef = Schemas['InfoscreenTerminalRef']
export type InfoscreenPage = Schemas['InfoscreenPage']
export type InfoscreenLayout = InfoscreenPage['layout']
export type InfoscreenColorMode = InfoscreenResponse['color_mode']
export type InfoscreenThemePreset = NonNullable<InfoscreenResponse['theme_preset']>

/**
 * A header or footer bar: three areas, each with its items from left to
 * right, and the text of the custom text item.
 */
export type InfoscreenBar = Schemas['InfoscreenBar']
export type InfoscreenBarItem = Schemas['InfoscreenBarItem']
export type InfoscreenBarArea = 'left' | 'center' | 'right'

/**
 * A bar as the editor holds it, with every area present. The schema leaves
 * the areas optional because the server fills in the defaults.
 */
export type InfoscreenBarState = Record<InfoscreenBarArea, InfoscreenBarItem[]> & {
  text: string | null
}

/** One widget in a slot; a slot without a widget is null. */
export type InfoscreenWidgetConfig = NonNullable<InfoscreenPage['slots'][number]>
export type InfoscreenWidgetType = InfoscreenWidgetConfig['type']

export type MachineBoardWidgetConfig = Schemas['MachineBoardWidgetConfig']
export type LotsDueWidgetConfig = Schemas['LotsDueWidgetConfig']
export type LateLotsWidgetConfig = Schemas['LateLotsWidgetConfig']
export type QaQueueWidgetConfig = Schemas['QaQueueWidgetConfig']
export type DeliveriesExpectedWidgetConfig = Schemas['DeliveriesExpectedWidgetConfig']
export type MessageWidgetConfig = Schemas['MessageWidgetConfig']
export type ClockWidgetConfig = Schemas['ClockWidgetConfig']
export type WeatherWidgetConfig = Schemas['WeatherWidgetConfig']
export type MachineDetailWidgetConfig = Schemas['MachineDetailWidgetConfig']
/** A town the weather widget may show, found by the place search. */
export type WeatherPlace = Schemas['WeatherPlaceResponse']
export type MessageSeverity = MessageWidgetConfig['severity']
export type ClockStyle = ClockWidgetConfig['style']

/** The weekday on-windows of a screen's displays; null keeps them on all the time. */
export type InfoscreenDisplaySchedule = Schemas['InfoscreenDisplaySchedule']
/** Which schedule a screen's displays follow: the default, its own or none. */
export type DisplayScheduleMode = InfoscreenResponse['display_schedule_mode']
/** The schedule every screen in the default mode follows; null is always on. */
export type DisplayScheduleDefault = Schemas['DisplayScheduleDefaultResponse']
export type DisplayScheduleDefaultRequest = Schemas['DisplayScheduleDefaultRequest']

/** The language a screen shows its built-in words in; null follows the installation's default. */
export type InfoscreenLanguage = Schemas['Language']

export type MessageTextAlign = MessageWidgetConfig['text_align']
export type MessageVerticalAlign = MessageWidgetConfig['vertical_align']

export type InfoscreenCreateRequest = Schemas['InfoscreenCreateRequest']
export type InfoscreenUpdateRequest = Schemas['InfoscreenUpdateRequest']
