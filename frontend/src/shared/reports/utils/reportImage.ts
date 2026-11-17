/**
 * Images prepared for a PDF report, such as the company logo or a part
 * photo. pdfmake embeds PNG and JPEG byte for byte, so a large upload would
 * make every report as large as the photo. An image is therefore redrawn on
 * a canvas no taller than it is ever printed at, as a PNG to keep a logo's
 * transparency or as a JPEG for a photo. A WebP or SVG image is converted the
 * same way, because pdfmake cannot read WebP and renders only simple SVGs.
 * An image that cannot be loaded leaves the report without it rather than
 * failing the export.
 */

/** Pixel height of a company logo, about three times its printed size. */
export const LOGO_HEIGHT = 240

const JPEG_QUALITY = 0.85

function readAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error ?? new Error('Could not read the image.'))
    reader.readAsDataURL(blob)
  })
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('Could not decode the image.'))
    image.src = url
  })
}

async function redraw(blob: Blob, maxHeight: number, maxWidth: number): Promise<string> {
  const url = URL.createObjectURL(blob)
  try {
    const image = await loadImage(url)
    const sized = image.naturalWidth > 0 && image.naturalHeight > 0
    // An SVG without its own size reports zero, so it gets a 4:1 box.
    const ratio = sized ? image.naturalWidth / image.naturalHeight : 4
    const fitted = Math.min(sized ? image.naturalHeight : maxHeight, maxHeight, maxWidth / ratio)
    const height = Math.max(1, Math.round(fitted))
    const canvas = document.createElement('canvas')
    canvas.height = height
    canvas.width = Math.max(1, Math.round(height * ratio))
    const context = canvas.getContext('2d')
    if (!context) throw new Error('No canvas available.')
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    return blob.type === 'image/jpeg' ? canvas.toDataURL('image/jpeg', JPEG_QUALITY) : canvas.toDataURL('image/png')
  } finally {
    URL.revokeObjectURL(url)
  }
}

async function needsRedraw(blob: Blob, maxHeight: number, maxWidth: number): Promise<boolean> {
  if (blob.type !== 'image/png' && blob.type !== 'image/jpeg') return true
  const url = URL.createObjectURL(blob)
  try {
    const image = await loadImage(url)
    return image.naturalHeight > maxHeight || image.naturalWidth > maxWidth
  } finally {
    URL.revokeObjectURL(url)
  }
}

/**
 * An image already loaded, such as a file the API returned, ready to embed,
 * at most `maxHeight` pixels tall and `maxWidth` wide; null when it cannot
 * be decoded.
 */
export async function reportImageFromBlob(
  blob: Blob,
  maxHeight: number,
  maxWidth = Number.POSITIVE_INFINITY,
): Promise<string | null> {
  try {
    return (await needsRedraw(blob, maxHeight, maxWidth))
      ? await redraw(blob, maxHeight, maxWidth)
      : await readAsDataUrl(blob)
  } catch {
    return null
  }
}

/** A data URL pdfmake can embed, at most `maxHeight` pixels tall, or null when there is no usable image. */
export async function loadReportImage(url: string | null, maxHeight: number): Promise<string | null> {
  if (!url) return null
  try {
    const response = await fetch(url)
    if (!response.ok) return null
    return await reportImageFromBlob(await response.blob(), maxHeight)
  } catch {
    return null
  }
}

/** The company logo from the general settings. */
export function loadCompanyLogo(url: string | null): Promise<string | null> {
  return loadReportImage(url, LOGO_HEIGHT)
}
