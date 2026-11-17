/**
 * Shared with settings.users.permissions.*, these are the same global
 * permission constants, rendered in more than one place.
 */

import type { TagSeverity } from '@/core/types/tagSeverity'

export type { TagSeverity }

const VERB_SEVERITY: Record<string, TagSeverity> = {
  read: 'info',
  write: 'success',
  manage: 'warn',
  delete: 'danger',
}

export function permissionSeverity(perm: string): TagSeverity {
  const verb = perm.split(':')[0] ?? ''
  return VERB_SEVERITY[verb] ?? 'secondary'
}

export function permissionLabel(t: (key: string) => string, perm: string): string {
  const key = perm.replace(':', '_').replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
  return t(`settings.users.permissions.${key}`)
}

/** What a permission allows, the same text the account page shows under its label. */
export function permissionDescription(t: (key: string) => string, perm: string): string {
  return t(`accountMe.permissions.desc.${perm.replace(':', '_')}`)
}
