import type {
  ProductDevice,
  ProductDeviceKind,
  ProductDeviceSaveRequest,
  ProductDeviceSignalType,
} from '../types/productDevice'

/**
 * The editable state of the device dialog and its conversion from a stored
 * device and into a save request. Kept apart from the component so the
 * rules (what a kind change clears, which values are sent) are testable.
 */

export interface ProductDeviceComponentForm {
  key: number
  id: number | null
  role_id: number | null
  bought_item_id: number | null
  eplan_tag: string
  b10d_cycles: number | null
  mttfd_years: number | null
  note: string
  signals: SignalForm[]
}

/**
 * A signal as the form edits it. One position field serves both
 * directions: an input confirms the position, an output drives to it. A
 * signal without a position may pick one of its kind's signals instead.
 */
export interface SignalForm {
  signal_type: ProductDeviceSignalType
  meaning: string
  position_id: number | null
  kind_signal_id: number | null
  safety: boolean
  address: string
  tag_suffix: string
  // Kept as loaded; the tag list edits it.
  tag_name: string | null
}

/** The signal types that report to the PLC and so may confirm a position. */
export const INPUT_SIGNAL_TYPES: ProductDeviceSignalType[] = ['di', 'ai']
/** The signal types the PLC sets and so may drive a position. */
export const OUTPUT_SIGNAL_TYPES: ProductDeviceSignalType[] = ['do', 'ao']

/** A new, empty signal; a safety-relevant device starts its signals as safety signals. */
export function newSignal(safety: boolean): SignalForm {
  return {
    signal_type: 'di',
    meaning: '',
    position_id: null,
    kind_signal_id: null,
    safety,
    address: '',
    tag_suffix: '',
    tag_name: null,
  }
}

export interface ProductDeviceForm {
  location: string
  name: string
  driving_medium_id: number | null
  // Null lets the backend pick the next free number.
  number: number | null
  kind_id: number | null
  description: string
  initial_position_id: number | null
  initial_position_value: number | null
  energy_loss_behaviour_id: number | null
  energy_restoration_behaviour_id: number | null
  monitoring_time_ms: number | null
  safety_relevant: boolean
  driven_by_id: number | null
  // Driver position id to own position id, for a driver of another kind.
  driven_position_map: Record<string, number | null>
  // Keyed by parameter id, as the backend stores them.
  parameters: Record<string, number | string | boolean | null>
  // Keyed by position id.
  position_labels: Record<string, string>
  // Keyed by position id: the time in ms to reach the position.
  travel_times_ms: Record<string, number | null>
  marker_x: number | null
  marker_y: number | null
  components: ProductDeviceComponentForm[]
}

let nextComponentKey = 0

export function newComponentForm(): ProductDeviceComponentForm {
  return {
    key: nextComponentKey++,
    id: null,
    role_id: null,
    bought_item_id: null,
    eplan_tag: '',
    b10d_cycles: null,
    mttfd_years: null,
    note: '',
    signals: [],
  }
}

export function emptyDeviceForm(): ProductDeviceForm {
  return {
    location: '',
    name: '',
    driving_medium_id: null,
    number: null,
    kind_id: null,
    description: '',
    initial_position_id: null,
    initial_position_value: null,
    energy_loss_behaviour_id: null,
    energy_restoration_behaviour_id: null,
    monitoring_time_ms: null,
    safety_relevant: false,
    driven_by_id: null,
    driven_position_map: {},
    parameters: {},
    position_labels: {},
    travel_times_ms: {},
    marker_x: null,
    marker_y: null,
    components: [],
  }
}

export function deviceFormFromDevice(device: ProductDevice): ProductDeviceForm {
  return {
    location: device.location,
    name: device.name,
    driving_medium_id: device.driving_medium_id,
    number: device.number,
    kind_id: device.kind_id,
    description: device.description ?? '',
    initial_position_id: device.initial_position_id,
    initial_position_value: device.initial_position_value,
    energy_loss_behaviour_id: device.energy_loss_behaviour_id,
    energy_restoration_behaviour_id: device.energy_restoration_behaviour_id,
    monitoring_time_ms: device.monitoring_time_ms,
    safety_relevant: device.safety_relevant,
    driven_by_id: device.driven_by_id,
    driven_position_map: Object.fromEntries(
      Object.entries(device.driven_position_map).map(([driver, own]) => [driver, Number(own)]),
    ),
    parameters: { ...(device.parameters as Record<string, number | string | boolean | null>) },
    position_labels: { ...device.position_labels },
    travel_times_ms: { ...device.travel_times_ms },
    marker_x: device.marker_x,
    marker_y: device.marker_y,
    components: device.components.map((component) => ({
      key: nextComponentKey++,
      id: component.id,
      role_id: component.role_id,
      bought_item_id: component.bought_item_id,
      eplan_tag: component.eplan_tag ?? '',
      b10d_cycles: component.b10d_cycles,
      mttfd_years: component.mttfd_years,
      note: component.note ?? '',
      signals: component.signals.map((signal) => ({
        signal_type: signal.signal_type,
        meaning: signal.meaning,
        position_id: signal.confirms_position_id ?? signal.drives_position_id,
        kind_signal_id: signal.kind_signal_id ?? null,
        safety: signal.safety,
        address: signal.address ?? '',
        tag_suffix: signal.tag_suffix ?? '',
        tag_name: signal.tag_name,
      })),
    })),
  }
}

/**
 * Clears everything that belongs to the previous kind: positions,
 * position labels, parameter values and the positions signals confirm
 * or drive.
 */
export function resetKindSpecificFields(form: ProductDeviceForm): void {
  form.initial_position_id = null
  form.initial_position_value = null
  form.parameters = {}
  form.position_labels = {}
  form.travel_times_ms = {}
  for (const component of form.components) {
    for (const signal of component.signals) signal.position_id = null
  }
}

/**
 * Whether a signal says what it is: by its meaning, or by the position or
 * kind signal it names, whose label stands in for a meaning.
 */
export function signalNamed(signal: SignalForm): boolean {
  return signal.meaning.trim() !== '' || signal.position_id !== null || signal.kind_signal_id !== null
}

/** Whether a signal says nothing about what it is, which the save request would leave out. */
export function lacksSignalMeaning(form: ProductDeviceForm): boolean {
  return form.components.some((component) => component.signals.some((signal) => !signalNamed(signal)))
}

/**
 * The save request, with empty texts sent as null and only the values
 * that belong to the chosen kind. Returns null while a required choice is
 * missing.
 */
export function deviceSaveRequest(
  form: ProductDeviceForm,
  kind: ProductDeviceKind | undefined,
): ProductDeviceSaveRequest | null {
  if (form.kind_id === null || !kind) return null
  if (!kind.without_driving_medium && form.driving_medium_id === null) return null
  if (form.components.some((component) => component.role_id === null)) return null

  const parameterIds = new Set(kind.parameters.map((p) => String(p.id)))
  const positionIds = new Set(kind.positions.map((p) => String(p.id)))
  const parameters: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(form.parameters)) {
    if (parameterIds.has(key) && value !== null && value !== '') parameters[key] = value
  }
  const positionLabels: Record<string, string> = {}
  for (const [key, value] of Object.entries(form.position_labels)) {
    if (positionIds.has(key) && value.trim()) positionLabels[key] = value.trim()
  }
  const travelTimes: Record<string, number> = {}
  for (const [key, value] of Object.entries(form.travel_times_ms)) {
    if (positionIds.has(key) && value !== null) travelTimes[key] = value
  }

  return {
    location: form.location,
    name: form.name,
    driving_medium_id: kind.without_driving_medium ? null : form.driving_medium_id,
    number: form.number,
    kind_id: form.kind_id,
    description: form.description.trim() || null,
    initial_position_id: form.initial_position_id,
    initial_position_value: form.initial_position_value,
    energy_loss_behaviour_id: form.energy_loss_behaviour_id,
    energy_restoration_behaviour_id: form.energy_restoration_behaviour_id,
    monitoring_time_ms: form.monitoring_time_ms,
    safety_relevant: form.safety_relevant,
    driven_by_id: form.driven_by_id,
    driven_position_map: Object.fromEntries(
      Object.entries(form.driven_position_map)
        .filter(([, own]) => own !== null)
        .map(([driver, own]) => [driver, String(own)]),
    ),
    parameters,
    position_labels: positionLabels,
    travel_times_ms: travelTimes,
    marker_x: form.marker_x,
    marker_y: form.marker_y,
    components: form.components.map((component) => ({
      id: component.id,
      role_id: component.role_id as number,
      bought_item_id: component.bought_item_id,
      eplan_tag: component.eplan_tag.trim() || null,
      b10d_cycles: component.b10d_cycles,
      mttfd_years: component.mttfd_years,
      note: component.note.trim() || null,
      signals: component.signals
        .filter(signalNamed)
        .map((signal) => ({
          signal_type: signal.signal_type,
          meaning: signal.meaning.trim(),
          // An input confirms its position, an output drives to it, a bus signal has none.
          confirms_position_id: INPUT_SIGNAL_TYPES.includes(signal.signal_type) ? signal.position_id : null,
          drives_position_id: OUTPUT_SIGNAL_TYPES.includes(signal.signal_type) ? signal.position_id : null,
          safety: signal.signal_type === 'bus' ? false : signal.safety,
          address: signal.address.trim() || null,
          tag_suffix: signal.tag_suffix.trim() || null,
          tag_name: signal.tag_name,
          kind_signal_id: signal.kind_signal_id,
        })),
    })),
  }
}
