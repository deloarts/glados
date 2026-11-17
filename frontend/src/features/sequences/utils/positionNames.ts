import type { SequencePositionName } from '../composables/useSequenceNames'

/**
 * How a sequence names a position: the kind's name from the resources,
 * such as "Extended", with the device's own label for it in brackets where
 * it has one, such as "Extended (Clamp and punch)".
 */
export function stateName(position: SequencePositionName): string {
  return position.kindLabel ? `${position.kindLabel} (${position.label})` : position.label
}

/**
 * How an action names the position it drives to: the kind's command, such
 * as "Extend", with the device's own label in brackets, or the position's
 * name where the kind sets no command.
 */
export function commandName(position: SequencePositionName): string {
  if (!position.command) return stateName(position)
  return position.kindLabel ? `${position.command} (${position.label})` : position.command
}
