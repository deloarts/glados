// The lifecycle actions a backend response offers in its `actions` field:
// the actions its aggregate's intent table allows the reading user right
// now. The backend computes them from the same table its use cases check,
// so a button gated on hasAction is offered exactly when the backend would
// accept it on state grounds. Orders, order lines and lots also carry
// `blocked_actions`: the actions their state allows but the reading user
// lacks an extra permission for, such as manage:lots, each with that
// permission. A control shows when offersAction holds and is disabled
// unless hasAction holds, naming the missing permission. The base
// permission of an action stays the caller's own usePermissions check. The
// action names come from the generated schema, so a new backend action
// reaches the type with the next type generation.

import type { Schemas } from '@/core/api/generated'

export type LifecycleAction = Schemas['LifecycleAction']

export interface HasActions {
  actions?: readonly string[] | null
  blocked_actions?: Readonly<Record<string, string>> | null
}

/** Whether the response offers the action now. */
export function hasAction(
  subject: HasActions | null | undefined,
  action: LifecycleAction,
): boolean {
  return subject?.actions?.includes(action) ?? false
}

/** Whether every response offers the action now; false for an empty list. */
export function allHaveAction(subjects: readonly HasActions[], action: LifecycleAction): boolean {
  return subjects.length > 0 && subjects.every((subject) => hasAction(subject, action))
}

/** Whether any response offers the action now. */
export function anyHasAction(subjects: readonly HasActions[], action: LifecycleAction): boolean {
  return subjects.some((subject) => hasAction(subject, action))
}

/**
 * The permission the reading user lacks for an action the response's state
 * allows, or null when the action is allowed or not possible now.
 */
export function blockingPermission(
  subject: HasActions | null | undefined,
  action: LifecycleAction,
): string | null {
  return subject?.blocked_actions?.[action] ?? null
}

/**
 * Whether the response's state allows the action now, whether or not the
 * reading user may take it: the action is allowed or blocked by a missing
 * permission. A control shows when this holds and is enabled by hasAction.
 */
export function offersAction(
  subject: HasActions | null | undefined,
  action: LifecycleAction,
): boolean {
  return hasAction(subject, action) || blockingPermission(subject, action) !== null
}

/** Whether any response's state allows the action now, for any user. */
export function anyOffersAction(subjects: readonly HasActions[], action: LifecycleAction): boolean {
  return subjects.some((subject) => offersAction(subject, action))
}
