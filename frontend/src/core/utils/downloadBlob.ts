/**
 * Triggers a browser download for an already-fetched blob, via a throwaway
 * object URL and a synthetic anchor click. The one implementation every
 * download action in the app uses.
 *
 * The anchor is attached to the document for the click, since some browsers
 * ignore a click on a detached anchor, and the URL is revoked a moment later
 * rather than right away, so a browser that starts the download
 * asynchronously still finds it.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
