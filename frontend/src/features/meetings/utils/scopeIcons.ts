import type { MeetingScopeIcon } from '../types/meetingResponse'

/**
 * The glyph of each scope icon, in the order the icon grid shows them. The
 * label of an icon is `meetings.scopeIcons.<value>`.
 */
export const SCOPE_ICONS: Record<MeetingScopeIcon, string> = {
  topic: 'mdi-tag-outline',
  schedule: 'mdi-calendar-clock',
  decision: 'mdi-gavel',
  mechanics: 'mdi-cog-outline',
  electrical: 'mdi-flash-outline',
  software: 'mdi-code-tags',
  commercial: 'mdi-currency-eur',
  logistics: 'mdi-truck-outline',
  quality: 'mdi-check-decagram-outline',
  safety: 'mdi-shield-check-outline',
  site: 'mdi-hard-hat',
  risk: 'mdi-alert-outline',
}

export const SCOPE_ICON_VALUES = Object.keys(SCOPE_ICONS) as MeetingScopeIcon[]

export function scopeIconClass(icon: MeetingScopeIcon | null | undefined): string | null {
  return icon ? `mdi ${SCOPE_ICONS[icon]}` : null
}
