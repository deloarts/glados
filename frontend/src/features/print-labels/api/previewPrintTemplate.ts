import api from '@/core/api'

import { PREVIEW_WARNINGS_HEADER, parsePreviewWarnings } from './previewWarnings'

import type { PreviewResponse } from '../types/printTemplateResponse'

export async function previewPrintTemplate(
  classifier: string,
  rootType: string,
  rootId: number,
): Promise<PreviewResponse> {
  const response = await api.post<PreviewResponse>(
    `/print-templates/${classifier}/preview`,
    undefined,
    { params: { root_type: rootType, root_id: rootId } },
  )

  return response.data
}

/**
 * The preview PNG is rendered on a POST, so it is fetched as a blob and
 * returned as an object URL the caller must revoke.
 */
export async function previewPrintTemplateImageUrl(
  classifier: string,
  rootType: string,
  rootId: number,
): Promise<{ url: string; warnings: string[] }> {
  const response = await api.post<Blob>(
    `/print-templates/${classifier}/preview.png`,
    undefined,
    { params: { root_type: rootType, root_id: rootId }, responseType: 'blob' },
  )

  const warnings = parsePreviewWarnings(response.headers[PREVIEW_WARNINGS_HEADER])

  return { url: URL.createObjectURL(response.data), warnings }
}
