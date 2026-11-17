import type { Schemas } from '@/core/api/generated'

export type InfoscreenFeedResponse = Schemas['InfoscreenFeedResponse']
export type InfoscreenFeedScreen = InfoscreenFeedResponse['infoscreen']
export type InfoscreenFeedBanner = NonNullable<InfoscreenFeedResponse['banner']>
/** A message to terminals, sent from the terminals page; it carries no author. */
export type TerminalMessage = Schemas['TerminalBroadcastMessage']
export type InfoscreenFeedPage = InfoscreenFeedScreen['pages'][number]
export type InfoscreenLayout = InfoscreenFeedPage['layout']
export type InfoscreenBar = InfoscreenFeedScreen['header']
export type InfoscreenBarItem = NonNullable<InfoscreenBar['left']>[number]
export type InfoscreenBarArea = 'left' | 'center' | 'right'

export type InfoscreenWidgetConfig = NonNullable<InfoscreenFeedPage['slots'][number]>
export type InfoscreenWidgetData = NonNullable<InfoscreenFeedResponse['widgets'][number][number]>
export type InfoscreenWidgetType = InfoscreenWidgetConfig['type']

// Members of the two unions by their `type`, derived from the feed schema
// so they follow whatever the backend names the member schemas.
export type WidgetConfigOf<T extends InfoscreenWidgetType> = Extract<
  InfoscreenWidgetConfig,
  { type: T }
>
export type WidgetDataOf<T extends InfoscreenWidgetType> = Extract<InfoscreenWidgetData, { type: T }>

export type MachineBoardMachine = WidgetDataOf<'machine_board'>['machines'][number]
export type InfoscreenOrderCard = NonNullable<MachineBoardMachine['current']>
export type MachineBoardPool = WidgetDataOf<'machine_board'>['pools'][number]
export type InfoscreenLotRow = WidgetDataOf<'lots_due'>['lots'][number]
export type InfoscreenQaRow = WidgetDataOf<'qa_queue'>['tasks'][number]
export type InfoscreenDeliveryRow = WidgetDataOf<'deliveries_expected'>['deliveries'][number]
export type InfoscreenHoliday = NonNullable<WidgetDataOf<'clock'>['next_holiday']>
export type InfoscreenWeatherDay = WidgetDataOf<'weather'>['days'][number]
export type InfoscreenProductRow = WidgetDataOf<'products'>['products'][number]
export type InfoscreenProjectRow = WidgetDataOf<'projects'>['projects'][number]
export type InfoscreenMachineOrder = NonNullable<WidgetDataOf<'machine_detail'>['order']>
export type InfoscreenRawMaterial = NonNullable<InfoscreenMachineOrder['raw_material']>

/** How many widget slots each layout preset has, in reading order. */
export const LAYOUT_SLOT_COUNT: Record<InfoscreenLayout, number> = {
  full: 1,
  two_columns: 2,
  main_side: 2,
  grid_2x2: 4,
  two_rows: 2,
  three_rows: 3,
  grid_2x3: 6,
  grid_3x2: 6,
}
