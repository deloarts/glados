import { createPinia, setActivePinia } from 'pinia'
import { describe, it, expect, beforeEach } from 'vitest'

import { groupMethodLabel, processGroups, processRoutingLabel } from '../madeItemProcessGroups'

import type { MadeItemProcessResponse } from '../../types/madeItemsResponse'

// The German conjunction comes from Intl for de-AT rather than being written
// out, so this spec holds no German text.
function deAtList(items: string[]): string {
  return new Intl.ListFormat('de-AT', { type: 'conjunction' }).format(items)
}

function makeProcess(
  id: number,
  position: number,
  groupIndex: number,
  fabricationMethodName: string,
): MadeItemProcessResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-${String(id).padStart(12, '0')}`,
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    creator_id: 1,
    fabrication_method_id: id,
    role: 'fabrication' as const,
    inspection_method_id: null,
    inspection_method_name: null,
    fabrication_method_name: { enGB: fabricationMethodName },
    made_item_id: 1,
    position,
    group_index: groupIndex,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('processGroups', () => {
  it('groups contiguous processes sharing a group_index', () => {
    const groups = processGroups([
      makeProcess(1, 0, 0, 'Sawing'),
      makeProcess(2, 1, 1, 'Bluing'),
      makeProcess(3, 2, 1, 'Heat Treating'),
    ])

    expect(groups).toHaveLength(2)
    expect(groups[0]!.processes.map((p) => p.fabrication_method_name.enGB)).toEqual(['Sawing'])
    expect(groups[1]!.processes.map((p) => p.fabrication_method_name.enGB)).toEqual([
      'Bluing',
      'Heat Treating',
    ])
  })

  it('sorts by position first, regardless of input order', () => {
    const groups = processGroups([makeProcess(2, 1, 0, 'Milling'), makeProcess(1, 0, 0, 'Sawing')])

    expect(groups).toHaveLength(1)
    expect(groups[0]!.processes.map((p) => p.fabrication_method_name.enGB)).toEqual([
      'Sawing',
      'Milling',
    ])
  })

  it('handles undefined/empty input', () => {
    expect(processGroups(undefined)).toEqual([])
    expect(processGroups([])).toEqual([])
  })
})

describe('groupMethodLabel', () => {
  it('is just the method name for a single-step group', () => {
    const [group] = processGroups([makeProcess(1, 0, 0, 'Sawing')])
    expect(groupMethodLabel(group!, 'enGB')).toBe('Sawing')
  })

  it('joins multi-step groups with a locale-appropriate conjunction', () => {
    const [group] = processGroups([
      makeProcess(1, 0, 0, 'Bluing'),
      makeProcess(2, 1, 0, 'Heat Treating'),
    ])
    expect(groupMethodLabel(group!, 'enGB')).toBe('Bluing and Heat Treating')
    expect(groupMethodLabel(group!, 'deAT')).toBe(deAtList(['Bluing', 'Heat Treating']))
    expect(groupMethodLabel(group!, 'deAT')).not.toBe('Bluing and Heat Treating')
  })
})

describe('processRoutingLabel', () => {
  it('joins grouped labels with an arrow', () => {
    const label = processRoutingLabel(
      [
        makeProcess(1, 0, 0, 'Sawing'),
        makeProcess(2, 1, 1, 'Bluing'),
        makeProcess(3, 2, 1, 'Heat Treating'),
        makeProcess(4, 3, 2, 'Deburring'),
      ],
      'deAT',
    )
    expect(label).toBe(`Sawing → ${deAtList(['Bluing', 'Heat Treating'])} → Deburring`)
  })
})
