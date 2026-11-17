import { describe, expect, it } from 'vitest'

import type { ProductDevice, ProductDeviceKind } from '../../types/productDevice'
import {
  deviceFormFromDevice,
  deviceSaveRequest,
  emptyDeviceForm,
  newComponentForm,
  newSignal,
  resetKindSpecificFields,
} from '../deviceForm'

function makeKind(): ProductDeviceKind {
  return {
    id: 1,
    public_id: 'k',
    created: '2026-10-22T00:00:00Z',
    changed: '2026-10-22T00:00:00Z',
    changed_by: null,
    changed_by_id: null,
    label: { enGB: 'Linear drive' },
    sort_order: 0,
    archived: false,
    creator_id: 1,
    creator: null,
    without_driving_medium: false,
    positions: [
      { id: 10, public_id: 'p', label: { enGB: 'Retracted' }, takes_value: false, unit: null, sort_order: 0, archived: false, plc_state_name: null, plc_command_name: null },
    ],
    parameters: [
      { id: 20, public_id: 'q', label: { enGB: 'Bore' }, unit: 'mm', value_type: 'number', sort_order: 0, archived: false },
    ],
    signals: [],
  }
}

function makeDevice(): ProductDevice {
  return {
    edit_version: 0,
    id: 5,
    public_id: 'd',
    created: '2026-10-22T00:00:00Z',
    changed: '2026-10-22T00:00:00Z',
    changed_by: null,
    changed_by_id: null,
    archived: false,
    product_id: 3,
    product_number: 'M26001',
    location: 'B01',
    name: 'Hubzylinder',
    driving_medium_id: 7,
    driving_medium_letter: 'P',
    number: 1,
    name_utf8: 'B01 Hubzylinder P1',
    name_ascii: 'B01_Hubzylinder_P1',
    full_name_utf8: 'M26001 B01 Hubzylinder P1',
    full_name_ascii: 'M26001_B01_Hubzylinder_P1',
    kind_id: 1,
    description: null,
    initial_position_id: 10,
    initial_position_value: null,
    energy_loss_behaviour_id: null,
    energy_restoration_behaviour_id: null,
    monitoring_time_ms: 1500,
    driven_by_id: null,
    driven_position_map: {},
    safety_relevant: false,
    parameters: { '20': 32 },
    position_labels: { '10': 'up' },
    travel_times_ms: { '10': 300 },
    rendering_file_id: null,
    assembly_file_id: null,
    marker_x: null,
    marker_y: null,
    creator_id: 1,
    creator: null,
    components: [
      {
        id: 9,
        public_id: 'c',
        role_id: 4,
        sort_order: 0,
        bought_item_id: 11,
        bought_item_part_number: 'BI-1',
        bought_item_article_name: 'Sensor SMT',
        eplan_tag: '-BG1',
        b10d_cycles: null,
        mttfd_years: null,
        note: null,
        signals: [{ signal_type: 'di', meaning: 'retracted', confirms_position_id: 10, drives_position_id: null, safety: false, address: null, tag_suffix: null, tag_name: null, kind_signal_id: null }],
      },
    ],
  }
}

describe('deviceForm', () => {
  it('round-trips a stored device into the same save request', () => {
    const body = deviceSaveRequest(deviceFormFromDevice(makeDevice()), makeKind())
    expect(body).toMatchObject({
      location: 'B01',
      name: 'Hubzylinder',
      driving_medium_id: 7,
      number: 1,
      kind_id: 1,
      initial_position_id: 10,
      monitoring_time_ms: 1500,
      driven_by_id: null,
      driven_position_map: {},
      parameters: { '20': 32 },
      position_labels: { '10': 'up' },
      description: null,
    })
    expect(body?.components).toEqual([
      {
        id: 9,
        role_id: 4,
        bought_item_id: 11,
        eplan_tag: '-BG1',
        b10d_cycles: null,
        mttfd_years: null,
        note: null,
        signals: [{ signal_type: 'di', meaning: 'retracted', confirms_position_id: 10, drives_position_id: null, safety: false, address: null, tag_suffix: null, tag_name: null, kind_signal_id: null }],
      },
    ])
  })

  it('returns null while medium, kind or a component role is missing', () => {
    const form = emptyDeviceForm()
    form.name = 'Greifer'
    expect(deviceSaveRequest(form, makeKind())).toBeNull()
    form.driving_medium_id = 7
    form.kind_id = 1
    expect(deviceSaveRequest(form, makeKind())).not.toBeNull()
    form.components.push(newComponentForm())
    expect(deviceSaveRequest(form, makeKind())).toBeNull()
  })

  it('drops values that do not belong to the kind and empty signals', () => {
    const form = deviceFormFromDevice(makeDevice())
    form.parameters['99'] = 5
    form.position_labels['10'] = '  '
    form.components[0]!.signals.push({ ...newSignal(false), signal_type: 'do', meaning: ' ' })
    form.components[0]!.signals.push({
      ...newSignal(true),
      signal_type: 'do',
      meaning: 'extend',
      position_id: 10,
      address: ' Q500.0 ',
      tag_suffix: 'Ausfahren',
    })
    form.components[0]!.signals.push({ ...newSignal(true), signal_type: 'bus', meaning: 'status', position_id: 10 })
    const body = deviceSaveRequest(form, makeKind())
    expect(body?.parameters).toEqual({ '20': 32 })
    expect(body?.position_labels).toEqual({})
    expect(body?.components?.[0]?.signals).toEqual([
      { signal_type: 'di', meaning: 'retracted', confirms_position_id: 10, drives_position_id: null, safety: false, address: null, tag_suffix: null, tag_name: null, kind_signal_id: null },
      // An output drives to its position instead of confirming it.
      {
        signal_type: 'do',
        meaning: 'extend',
        confirms_position_id: null,
        drives_position_id: 10,
        safety: true,
        address: 'Q500.0',
        tag_suffix: 'Ausfahren',
        tag_name: null,
        kind_signal_id: null,
      },
      // A bus signal has no position and is never a safety signal.
      { signal_type: 'bus', meaning: 'status', confirms_position_id: null, drives_position_id: null, safety: false, address: null, tag_suffix: null, tag_name: null, kind_signal_id: null },
    ])
  })

  it('sends the travel times of the kind\'s positions that have one', () => {
    const form = deviceFormFromDevice(makeDevice())
    expect(form.travel_times_ms).toEqual({ '10': 300 })
    form.travel_times_ms['11'] = null
    form.travel_times_ms['99'] = 400
    expect(deviceSaveRequest(form, makeKind())?.travel_times_ms).toEqual({ '10': 300 })
    resetKindSpecificFields(form)
    expect(form.travel_times_ms).toEqual({})
  })

  it('clears kind specific values when the kind changes', () => {
    const form = deviceFormFromDevice(makeDevice())
    resetKindSpecificFields(form)
    expect(form.initial_position_id).toBeNull()
    expect(form.parameters).toEqual({})
    expect(form.position_labels).toEqual({})
    expect(form.components[0]!.signals[0]!.position_id).toBeNull()
    expect(form.components[0]!.eplan_tag).toBe('-BG1')
  })
})
