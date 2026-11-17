/**
 * Returns the blob unchanged when it carries a MIME type, and otherwise a
 * copy typed as `mime`. Some presigned file responses drop the type, and the
 * browser's embedded viewers then refuse to render the object URL.
 */
export function withMimeFallback(blob: Blob, mime: string): Blob {
  return blob.type ? blob : new Blob([blob], { type: mime })
}
