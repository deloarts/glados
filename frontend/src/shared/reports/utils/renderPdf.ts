import type { TDocumentDefinitions } from 'pdfmake/interfaces'

import carlitoBold from '../fonts/Carlito-Bold.ttf?url'
import carlitoItalic from '../fonts/Carlito-Italic.ttf?url'
import carlitoRegular from '../fonts/Carlito-Regular.ttf?url'
import playBold from '../fonts/Play-Bold.ttf?url'
import playRegular from '../fonts/Play-Regular.ttf?url'
import { REPORT_FONTS } from './palette'
import { downloadBlob } from '@/core/utils/downloadBlob'

/**
 * Renders a pdfmake document definition to a PDF in the browser. pdfmake and
 * the fonts load on the first export only, so nothing of either is part of
 * the app's initial download.
 */

type PdfMake = typeof import('pdfmake/build/pdfmake')

// pdfmake downloads a font only from an absolute http(s) URL and treats any
// other string as a file in its in-memory file system.
function absolute(url: string): string {
  return new URL(url, window.location.href).href
}

let loading: Promise<PdfMake> | null = null

function loadPdfMake(): Promise<PdfMake> {
  loading ??= import('pdfmake/build/pdfmake').then((module) => {
    // The browser build is a UMD bundle whose methods live on an instance,
    // which the bundler hands over as the default export.
    const pdfMake = (module as PdfMake & { default?: PdfMake }).default ?? module
    pdfMake.setFonts({
      [REPORT_FONTS.heading]: {
        normal: absolute(playRegular),
        bold: absolute(playBold),
        italics: absolute(playRegular),
        bolditalics: absolute(playBold),
      },
      [REPORT_FONTS.body]: {
        normal: absolute(carlitoRegular),
        bold: absolute(carlitoBold),
        italics: absolute(carlitoItalic),
        // No bold italic is ever set, so its file is not shipped.
        bolditalics: absolute(carlitoBold),
      },
    })
    // Images reach a report as data URLs; the only downloads are the fonts
    // above, so nothing may be fetched from another origin.
    pdfMake.setUrlAccessPolicy((url) => new URL(url).origin === window.location.origin)
    return pdfMake
  })
  loading.catch(() => {
    loading = null
  })
  return loading
}

export async function renderPdf(definition: TDocumentDefinitions): Promise<Blob> {
  const pdfMake = await loadPdfMake()
  return pdfMake.createPdf(definition).getBlob()
}

/** Hands a rendered PDF to the browser as a file download. */
export function downloadPdf(blob: Blob, fileName: string): void {
  downloadBlob(blob, fileName)
}
