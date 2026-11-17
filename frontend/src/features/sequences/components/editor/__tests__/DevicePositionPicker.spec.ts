import { describe, expect, it } from 'vitest'
import { computed, defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { provideSequenceEditor } from '../../../composables/sequenceEditorContext'
import type { SequenceEditorContext } from '../../../composables/sequenceEditorContext'
import type { SequenceDeviceName } from '../../../composables/useSequenceNames'
import type { SequenceNames } from '../../../composables/useSequenceNames'
import { commandName } from '../../../utils/positionNames'
import DevicePositionPicker from '../DevicePositionPicker.vue'

const DEVICE: SequenceDeviceName = {
  id: 1,
  name: 'B01 Punch cylinder',
  nameAscii: 'B01_Punch_cylinder',
  kind: 'Cylinder',
  archived: false,
  initialPositionId: null,
  initialPositionValue: null,
  drivenById: null,
  positionMap: {},
  positions: [
    { id: 10, label: 'Retracted', unit: null, takesValue: false, archived: false, travelTimeMs: null },
    {
      id: 11,
      label: 'Clamp and punch',
      kindLabel: 'Extended',
      unit: null,
      takesValue: false,
      archived: false,
      travelTimeMs: null,
    },
    { id: 12, label: 'Stroke', unit: 'mm', takesValue: true, archived: false, travelTimeMs: null },
  ],
}

function mountPicker(device: SequenceDeviceName = DEVICE, forAction = false) {
  const names = {
    devices: computed(() => [device]),
    deviceById: computed(() => new Map([[device.id, device]])),
    deviceName: () => device.name,
    actionName: (_deviceId: number, positionId: number) => commandName(device.positions.find((p) => p.id === positionId)!),
  } as unknown as SequenceNames
  const Host = defineComponent({
    setup() {
      provideSequenceEditor({ names, readonly: computed(() => false) } as unknown as SequenceEditorContext)
      return () => h(DevicePositionPicker, { deviceId: device.id, positionId: null, forAction })
    },
  })
  return mountWithApp(Host)
}

describe('DevicePositionPicker', () => {
  it("offers the kind's name for a position with the device's own label in brackets", () => {
    const wrapper = mountPicker()
    const positions = wrapper.findAllComponents({ name: 'Select' })[1]!
    expect(positions.props('options')).toEqual([
      { value: 10, label: 'Retracted' },
      { value: 11, label: 'Extended (Clamp and punch)' },
      { value: 12, label: 'Stroke (mm)' },
    ])
  })

  it('offers an action the command that drives to each position, where the kind sets one', () => {
    const [retracted, extended, stroke] = DEVICE.positions
    const device = {
      ...DEVICE,
      positions: [{ ...retracted!, command: 'Retract' }, { ...extended!, command: 'Extend' }, stroke!],
    }
    const wrapper = mountPicker(device, true)
    const positions = wrapper.findAllComponents({ name: 'Select' })[1]!
    expect(positions.props('options')).toEqual([
      { value: 10, label: 'Retract' },
      { value: 11, label: 'Extend (Clamp and punch)' },
      { value: 12, label: 'Stroke (mm)' },
    ])
  })
})
