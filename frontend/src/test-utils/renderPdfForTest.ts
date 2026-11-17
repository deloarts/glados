import { join } from 'node:path'
import * as pdfmakeModule from 'pdfmake'
import type { TDocumentDefinitions } from 'pdfmake/interfaces'

/**
 * Renders a report's document definition to PDF bytes inside a spec, with
 * the report fonts read from disk, so a spec can prove that a report really
 * lays out: pdfmake rejects an invalid definition only while rendering it.
 *
 * jsdom puts its own typed array classes on the global object, and pdfkit
 * checks the font files read from disk against them with instanceof. Node's
 * own classes are put back so that check holds; import this module only in
 * specs that render PDFs.
 */
;(globalThis as { Uint8Array: unknown }).Uint8Array = Object.getPrototypeOf(Buffer.prototype).constructor
;(globalThis as { ArrayBuffer: unknown }).ArrayBuffer = Buffer.alloc(1).buffer.constructor

const pdfmake = ((pdfmakeModule as { default?: typeof pdfmakeModule }).default ?? pdfmakeModule) as typeof pdfmakeModule

// Specs run from the frontend folder, as the npm scripts start them.
const FONTS = join(process.cwd(), 'src/shared/reports/fonts/')

pdfmake.setFonts({
  Play: {
    normal: `${FONTS}Play-Regular.ttf`,
    bold: `${FONTS}Play-Bold.ttf`,
    italics: `${FONTS}Play-Regular.ttf`,
    bolditalics: `${FONTS}Play-Bold.ttf`,
  },
  Carlito: {
    normal: `${FONTS}Carlito-Regular.ttf`,
    bold: `${FONTS}Carlito-Bold.ttf`,
    italics: `${FONTS}Carlito-Italic.ttf`,
    bolditalics: `${FONTS}Carlito-Bold.ttf`,
  },
})
pdfmake.setUrlAccessPolicy(() => false)
pdfmake.setLocalAccessPolicy((path) => path.startsWith(FONTS))

export async function renderPdfForTest(definition: TDocumentDefinitions): Promise<Buffer> {
  return pdfmake.createPdf(definition).getBuffer()
}

/** Whether the bytes are a PDF/A-2b file: version 1.7 with the PDF/A identification in its metadata. */
export function isPdfA2b(pdf: Buffer): boolean {
  const text = pdf.toString('latin1')
  return text.startsWith('%PDF-1.7') && text.includes('<pdfaid:part>2</pdfaid:part>') && text.includes('<pdfaid:conformance>B</pdfaid:conformance>')
}
