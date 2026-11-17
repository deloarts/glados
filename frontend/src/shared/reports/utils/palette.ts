/**
 * The colours of every PDF report. Fixed on purpose: a report looks the same
 * whoever exports it, whatever theme, primary colour or dark mode they use in
 * the app. Status colours stay readable on a black and white printer because
 * every status is also written out as text.
 */
export const REPORT_COLORS = {
  ink: '#1d2430',
  muted: '#5b6573',
  faint: '#8a94a3',
  rule: '#d6dce4',
  band: '#f3f5f8',
  accent: '#0f4c81',
  accentSoft: '#e7eff7',
  pass: '#1f7a4d',
  passSoft: '#e4f4ec',
  warn: '#9a5b00',
  warnSoft: '#fcf1de',
  fail: '#b3261e',
  failSoft: '#fbe7e5',
  info: '#35618f',
  infoSoft: '#e8eff7',
} as const

export type ReportTone = 'pass' | 'warn' | 'fail' | 'info'

export function toneColors(tone: ReportTone): { text: string; fill: string } {
  switch (tone) {
    case 'pass':
      return { text: REPORT_COLORS.pass, fill: REPORT_COLORS.passSoft }
    case 'warn':
      return { text: REPORT_COLORS.warn, fill: REPORT_COLORS.warnSoft }
    case 'fail':
      return { text: REPORT_COLORS.fail, fill: REPORT_COLORS.failSoft }
    case 'info':
      return { text: REPORT_COLORS.info, fill: REPORT_COLORS.infoSoft }
  }
}

/** Font families registered with pdfmake, see utils/renderPdf.ts. */
export const REPORT_FONTS = {
  heading: 'Play',
  body: 'Carlito',
} as const
