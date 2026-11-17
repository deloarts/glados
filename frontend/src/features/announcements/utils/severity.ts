import type { AnnouncementSeverity } from '../types/announcementsTypes'

/**
 * Maps the wire severities to OpenVue's Message and Dialog names. Tag uses
 * a different mapping.
 */
export function toMessageSeverity(severity: AnnouncementSeverity): 'info' | 'warn' | 'error' {
  switch (severity) {
    case 'warning':
      return 'warn'
    case 'danger':
      return 'error'
    default:
      return 'info'
  }
}

/** The icon for a severity, so colour is not the only cue. */
export function toSeverityIcon(severity: AnnouncementSeverity): string {
  switch (severity) {
    case 'warning':
      return 'mdi mdi-alert-outline'
    case 'danger':
      return 'mdi mdi-alert-octagon-outline'
    default:
      return 'mdi mdi-information-outline'
  }
}
