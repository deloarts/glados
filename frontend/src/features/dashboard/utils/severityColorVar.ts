// Maps a Tag severity to a CSS color for SVG or backgrounds, where a Tag
// does not fit.
const SEVERITY_COLOR_VARS: Record<string, string> = {
  secondary: 'var(--p-surface-500)',
  info: 'var(--p-blue-500)',
  warn: 'var(--p-orange-500)',
  help: 'var(--p-purple-500)',
  success: 'var(--p-green-500)',
  danger: 'var(--p-red-500)',
  contrast: 'var(--p-surface-900)',
}

const FALLBACK_COLOR_VAR = 'var(--p-surface-500)'

export function severityColorVar(severity: string): string {
  return SEVERITY_COLOR_VARS[severity] ?? FALLBACK_COLOR_VAR
}
