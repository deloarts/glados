import api from '@/core/api'
import { downloadBlob } from '@/core/utils/downloadBlob'
import { PREVIEW_WARNINGS_HEADER, parsePreviewWarnings } from './previewWarnings'

/**
 * Renders what a print would send and saves it as a file, a .pdf for a
 * docket or a .zpl for a label. Needs no printer.
 */
export async function downloadPrintTemplate(
  classifier: string,
  rootType: string,
  rootId: number,
): Promise<{ warnings: string[] }> {
  const response = await api.post<Blob>(`/print-templates/${classifier}/download`, undefined, {
    params: { root_type: rootType, root_id: rootId },
    responseType: 'blob',
  })

  const disposition = response.headers['content-disposition'] as string | undefined
  const match = disposition?.match(/filename="([^"]+)"/)
  const filename = match?.[1] ?? `${classifier}.pdf`

  downloadBlob(response.data, filename)

  const warnings = parsePreviewWarnings(response.headers[PREVIEW_WARNINGS_HEADER])

  return { warnings }
}
