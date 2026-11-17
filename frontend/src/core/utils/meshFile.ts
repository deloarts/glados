/**
 * The single 3D-mesh slot on bought and made items ("mesh" category) holds
 * either an STL or a 3MF, the newest upload replaces whatever was there.
 *
 * Recognising one is filename-first on purpose. The backend pins a canonical
 * mime on upload, but rows predating that carry whatever the browser guessed
 * (frequently application/octet-stream, sometimes nothing), so the extension
 * is the only field that has always been reliable.
 */

/** Extensions the backend's mesh category accepts (upload_*_item_file.py). */
export const MESH_EXTENSIONS = ['.stl', '.3mf'] as const

/**
 * Mime types that identify a mesh. `application/sla` and the long
 * `vnd.ms-package…` form are older spellings of STL and 3MF that some
 * browsers and CAD tools still produce.
 */
export const MESH_MIME_TYPES = [
  'model/stl',
  'application/sla',
  'model/3mf',
  'application/vnd.ms-package.3dmanufacturing-3dmodel+xml',
] as const

/** `accept` attribute for the mesh file input. */
export const MESH_ACCEPT = MESH_EXTENSIONS.join(',')

export function isMeshFile(fileName: string, mimeType: string | null | undefined): boolean {
  const name = fileName.toLowerCase()
  if (MESH_EXTENSIONS.some((ext) => name.endsWith(ext))) return true
  return mimeType != null && (MESH_MIME_TYPES as readonly string[]).includes(mimeType)
}

/** True for a file the preview dialog can show: a PDF, an image or a mesh. */
export function isPreviewableFile(fileName: string, mimeType: string | null | undefined): boolean {
  return mimeType === 'application/pdf' || (mimeType?.startsWith('image/') ?? false) || isMeshFile(fileName, mimeType)
}
