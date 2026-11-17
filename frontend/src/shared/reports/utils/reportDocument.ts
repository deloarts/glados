import type { Column, Content, TDocumentDefinitions } from 'pdfmake/interfaces'

import type { AppLocale } from '@/core/i18n'
import { localeTag } from '@/core/utils/dates'
import { keyValueGrid, notice } from './blocks'
import type { KeyValue } from './blocks'
import { REPORT_COLORS } from './palette'
import type { ReportTone } from './palette'
import { CONTENT_WIDTH, DEFAULT_STYLE, REPORT_STYLES } from './styles'

/**
 * The page frame every PDF report shares: A4 portrait, a header on every
 * page naming the kind of document and when it was exported with the company
 * logo on the right, a title block with the record's details, and a footer
 * naming who exported it, the company, the page number and, for a saved
 * record, a QR code with its reference that opens the exact revision in the
 * app. The body comes from the feature.
 *
 * Reports are documentation that may be kept for the life of a machine, so
 * they are written as PDF/A-2b (ISO 19005-2), the archival profile: fonts
 * embedded, colours tied to sRGB, the metadata in XMP. The document carries
 * its language and shows its title in the viewer instead of the file name.
 */

/** Where a printed copy points back to: the record's revision in the app. */
export interface FrameIdentity {
  /** The link the QR code holds. */
  url: string
  /** A readable reference next to it, such as "CAL-0042 rev. B". */
  reference: string
}

export interface ReportFrame {
  locale: AppLocale
  /** The app's name from the branding settings, "Glados" by default, kept as the PDF's creator. */
  appName: string
  companyName: string | null
  /** A PNG or JPEG data URL, see loadCompanyLogo in reportImage.ts. */
  logo: string | null
  /** What kind of document this is, shown in the header, e.g. "Drive sizing". */
  kind: string
  /** "Exported 9 Oct 2026, 14:05", under the kind. */
  exportedAt: string
  title: string
  subtitle?: string
  details: readonly KeyValue[]
  /** A remark shown right under the details, such as a draft warning. */
  notice?: { text: string; tone: ReportTone } | null
  /** "Exported by Jane Doe". */
  exportedBy: string
  identity: FrameIdentity | null
  /** The line that marks a printed page as a copy, shown with the QR code. */
  copyNotice: string
  pageLabel: (page: number, pages: number) => string
}

export const PAGE_MARGINS: [number, number, number, number] = [40, 84, 40, 70]

// The logo box, set level with the middle of the two header lines.
const LOGO_FIT: [number, number] = [74, 20]
const LOGO_IMAGE = 'companyLogo'
// Large enough for a phone to read from a printed page at arm's length.
const QR_SIZE = 42

function rule(): Content {
  return {
    canvas: [{ type: 'line', x1: 0, y1: 0, x2: CONTENT_WIDTH, y2: 0, lineWidth: 0.5, lineColor: REPORT_COLORS.rule }],
  }
}

function header(frame: ReportFrame): Content {
  const columns: Column[] = [
    {
      stack: [
        { text: frame.kind, style: 'headerKind' },
        { text: frame.exportedAt, style: 'headerDate' },
      ],
      width: '*',
    },
  ]
  // The logo is named here and defined once in the document's images, so a
  // report of several pages carries it only once.
  if (frame.logo) {
    columns.push({ width: 'auto', stack: [{ image: LOGO_IMAGE, fit: LOGO_FIT, alignment: 'right' }], margin: [0, 4, 0, 0] })
  }
  return {
    stack: [{ columns }, { ...(rule() as object), margin: [0, 6, 0, 0] } as Content],
    margin: [PAGE_MARGINS[0], 22, PAGE_MARGINS[2], 0],
  }
}

function footer(frame: ReportFrame, page: number, pages: number): Content {
  const left: Content[] = [
    { text: frame.exportedBy },
    ...(frame.companyName ? [{ text: frame.companyName }] : []),
    ...(frame.identity ? [{ text: frame.copyNotice, margin: [0, 4, 0, 0] } as Content] : []),
  ]
  const right: Column[] = [
    {
      stack: [
        ...(frame.identity ? [{ text: frame.identity.reference, style: 'footerReference' }] : []),
        { text: frame.pageLabel(page, pages) },
      ],
      alignment: 'right',
      width: 'auto',
    },
  ]
  if (frame.identity) right.push({ qr: frame.identity.url, fit: QR_SIZE, eccLevel: 'M', margin: [0, 0, 0, 0], width: QR_SIZE })
  return {
    stack: [
      rule(),
      {
        columns: [{ stack: left, width: '*' }, ...right],
        columnGap: 8,
        style: 'footer',
        margin: [0, 5, 0, 0],
      },
    ],
    margin: [PAGE_MARGINS[0], 8, PAGE_MARGINS[2], 0],
  }
}

export function reportDocument(frame: ReportFrame, body: readonly Content[]): TDocumentDefinitions {
  const titleBlock: Content[] = [
    { text: frame.title, style: 'title' },
    ...(frame.subtitle ? [{ text: frame.subtitle, style: 'subtitle' }] : []),
    { ...(keyValueGrid(frame.details) as object), margin: [0, 8, 0, 0] } as Content,
    ...(frame.notice ? [notice(frame.notice.text, frame.notice.tone)] : []),
  ]
  return {
    pageSize: 'A4',
    pageOrientation: 'portrait',
    pageMargins: PAGE_MARGINS,
    version: '1.7',
    subset: 'PDF/A-2b',
    displayTitle: true,
    language: localeTag(frame.locale),
    info: {
      title: frame.title,
      subject: frame.kind,
      author: frame.companyName ?? undefined,
      creator: frame.appName,
    },
    images: frame.logo ? { [LOGO_IMAGE]: frame.logo } : {},
    header: () => header(frame),
    footer: (page, pages) => footer(frame, page, pages),
    content: [...titleBlock, ...body],
    defaultStyle: DEFAULT_STYLE,
    styles: REPORT_STYLES,
  }
}
