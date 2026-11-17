/**
 * Scales an image File down to fit within `maxDimension × maxDimension`,
 * preserving the full frame and aspect ratio (no cropping). Images already
 * smaller than `maxDimension` on both sides are returned unchanged.
 *
 * This only exists to keep the upload small, the backend performs the
 * actual background removal and square-canvas (transparent) padding, so
 * this must never crop or otherwise discard part of the source image.
 */
export function scaleDownForUpload(file: File, maxDimension = 256): Promise<File> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()

    img.onload = () => {
      URL.revokeObjectURL(url)

      const scale = Math.min(1, maxDimension / img.naturalWidth, maxDimension / img.naturalHeight)
      if (scale === 1) {
        resolve(file)
        return
      }

      const canvas = document.createElement('canvas')
      canvas.width = Math.round(img.naturalWidth * scale)
      canvas.height = Math.round(img.naturalHeight * scale)
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new Error('Canvas 2D context unavailable'))
        return
      }

      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error('Canvas toBlob returned null'))
            return
          }
          const name = file.name.replace(/\.[^.]+$/, '.jpg')
          resolve(new File([blob], name, { type: 'image/jpeg' }))
        },
        'image/jpeg',
        0.88,
      )
    }

    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Image failed to load'))
    }

    img.src = url
  })
}
