/**
 * The optional modules an admin can switch off in the Features settings tab.
 * Each maps to the host store flag that carries it, so a gate can name the
 * module (a route's `requiresFeature` meta, for one) without spelling out
 * the store field.
 */
export type ModuleFeature = 'calculations' | 'checklists' | 'devices' | 'sequences' | 'todos'

export const MODULE_FLAGS = {
  calculations: 'calculationsEnabled',
  checklists: 'checklistsEnabled',
  devices: 'devicesEnabled',
  sequences: 'sequencesEnabled',
  todos: 'todosEnabled',
} as const satisfies Record<ModuleFeature, string>
