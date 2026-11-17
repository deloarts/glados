import { computed } from 'vue'

import { useProductDeviceResourcesStore } from '@/features/product-devices'
import type { ProductDevice } from '@/features/product-devices'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { commandName, stateName } from '../utils/positionNames'
import type { SequenceDocument } from './useSequenceDocument'

/** A position of a device as a sequence shows it. */
export interface SequencePositionName {
  id: number
  label: string
  /** The kind's name for the position, set only when the device labels it its own way. */
  kindLabel?: string
  unit: string | null
  takesValue: boolean
  archived: boolean
  /** The device's nominal time in ms to reach the position, null when not known. */
  travelTimeMs: number | null
  /**
   * Whether an input signal of the device, or of a device moving with it,
   * confirms the position; left out where not known, as in a released
   * revision.
   */
  confirmed?: boolean
  /**
   * The kind's PLC command that drives to the position, such as "Extend",
   * which an action shows; left out where none is set or not known, as in
   * a released revision.
   */
  command?: string
}

/** A device as a sequence shows it, with its positions and its start state. */
export interface SequenceDeviceName {
  id: number
  name: string
  nameAscii: string
  kind: string
  archived: boolean
  initialPositionId: number | null
  initialPositionValue: number | null
  positions: SequencePositionName[]
  /** The device this one moves with; a step moves the driver instead. */
  drivenById: number | null
  /** Driver position id to own position id, for a driver of another kind. */
  positionMap: Record<string, string>
}

export interface SequenceVariantName {
  id: number
  name: string
  archived: boolean
}

/**
 * The names a sequence shows for the devices, positions and variants its
 * steps refer to by id. A released revision shows the names frozen at its
 * release; a draft shows the current ones, archived ones included so a
 * step that still names one reads right. A device's own label for a
 * position, such as "Robot pickup", follows the kind's in brackets. An action
 * reads as the command that drives to the position, such as "Extend",
 * where the kind sets one, and a condition as the position itself.
 */
export function useSequenceNames(doc: SequenceDocument) {
  const resources = useProductDeviceResourcesStore()
  const { localize } = useLocalizedText()
  void resources.load()

  const frozen = computed(() => doc.sequence.value?.frozen ?? null)

  function confirmedIds(device: ProductDevice): Set<number> {
    const ids = device.components.flatMap((component) => component.signals).map((s) => s.confirms_position_id)
    return new Set(ids.filter((id): id is number => id != null))
  }

  // A driver's position counts as confirmed when a device moving with it
  // confirms the matching position of its own, which is the same position
  // for a device of the same kind.
  function confirmedThroughDriven(driver: ProductDevice, positionId: number): boolean {
    return doc.devices.value.some((driven) => {
      if (driven.driven_by_id !== driver.id) return false
      const own = driven.kind_id === driver.kind_id ? positionId : Number(driven.driven_position_map[String(positionId)])
      return confirmedIds(driven).has(own)
    })
  }

  function liveDevice(device: ProductDevice): SequenceDeviceName {
    const kind = resources.kindById.get(device.kind_id)
    const confirmed = confirmedIds(device)
    return {
      id: device.id,
      name: device.name_utf8,
      nameAscii: device.name_ascii,
      kind: kind ? localize(kind.label) : '',
      archived: device.archived,
      initialPositionId: device.initial_position_id,
      initialPositionValue: device.initial_position_value,
      drivenById: device.driven_by_id,
      positionMap: { ...device.driven_position_map },
      positions: (kind?.positions ?? []).map((position) => ({
        id: position.id,
        label: device.position_labels[String(position.id)] ?? localize(position.label),
        kindLabel: device.position_labels[String(position.id)] ? localize(position.label) : undefined,
        unit: position.unit,
        takesValue: position.takes_value,
        archived: position.archived,
        travelTimeMs: device.travel_times_ms[String(position.id)] ?? null,
        confirmed: confirmed.has(position.id) || confirmedThroughDriven(device, position.id),
        command: position.plc_command_name || undefined,
      })),
    }
  }

  const devices = computed<SequenceDeviceName[]>(() => {
    const names = frozen.value
    if (names) {
      return Object.entries(names.devices).map(([id, device]) => ({
        id: Number(id),
        name: device.name,
        nameAscii: device.name_ascii,
        kind: localize(device.kind),
        archived: false,
        initialPositionId: device.initial_position_id,
        initialPositionValue: device.initial_position_value,
        drivenById: device.driven_by_id ?? null,
        positionMap: { ...device.driven_position_map },
        positions: Object.entries(device.positions).map(([positionId, position]) => ({
          id: Number(positionId),
          label: position.device_label ?? localize(position.label),
          kindLabel: position.device_label ? localize(position.label) : undefined,
          unit: position.unit,
          takesValue: position.takes_value,
          archived: false,
          travelTimeMs: position.travel_time_ms ?? null,
        })),
      }))
    }
    return doc.devices.value.map(liveDevice)
  })

  const variants = computed<SequenceVariantName[]>(() => {
    const names = frozen.value
    if (names) return Object.entries(names.variants).map(([id, name]) => ({ id: Number(id), name, archived: false }))
    return doc.variants.value.map((v) => ({ id: v.id, name: v.name, archived: v.archived }))
  })

  const deviceById = computed(() => new Map(devices.value.map((device) => [device.id, device])))
  const liveVariants = computed(() => variants.value.filter((variant) => !variant.archived))

  function deviceName(id: number | null | undefined): string {
    if (id == null) return ''
    return deviceById.value.get(id)?.name ?? `#${id}`
  }

  function position(deviceId: number | null | undefined, positionId: number | null | undefined) {
    if (deviceId == null || positionId == null) return null
    return deviceById.value.get(deviceId)?.positions.find((p) => p.id === positionId) ?? null
  }

  function positionName(deviceId: number | null | undefined, positionId: number | null | undefined): string {
    if (positionId == null) return ''
    const found = position(deviceId, positionId)
    return found ? stateName(found) : `#${positionId}`
  }

  function actionName(deviceId: number | null | undefined, positionId: number | null | undefined): string {
    const found = position(deviceId, positionId)
    return found ? commandName(found) : positionName(deviceId, positionId)
  }

  function variantName(id: number): string {
    return variants.value.find((variant) => variant.id === id)?.name ?? `#${id}`
  }

  return {
    devices,
    variants,
    liveVariants,
    deviceById,
    deviceName,
    position,
    positionName,
    actionName,
    variantName,
  }
}

export type SequenceNames = ReturnType<typeof useSequenceNames>
