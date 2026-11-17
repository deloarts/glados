import { describe, expect, it } from 'vitest'

import type { SequencePositionName } from '../../composables/useSequenceNames'
import { commandName, stateName } from '../positionNames'

const base: SequencePositionName = { id: 11, label: 'Extended', unit: null, takesValue: false, archived: false, travelTimeMs: null }
const own: SequencePositionName = { ...base, label: 'Clamp and punch', kindLabel: 'Extended' }

describe('positionNames', () => {
  it("names a position by the kind's name with the device's own label in brackets", () => {
    expect(stateName(base)).toBe('Extended')
    expect(stateName(own)).toBe('Extended (Clamp and punch)')
  })

  it("names an action's position by the kind's command, falling back to the position", () => {
    expect(commandName({ ...own, command: 'Extend' })).toBe('Extend (Clamp and punch)')
    expect(commandName({ ...base, command: 'Extend' })).toBe('Extend')
    expect(commandName(own)).toBe('Extended (Clamp and punch)')
  })
})
