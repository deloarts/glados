/**
 * Contrast helpers for the user-chosen label colours.
 *
 * Article groups let a user pick a background and a font colour independently,
 * which makes it easy to save a combination nobody can read: a real group in
 * this database is white text on yellow. Nothing in the app can override those
 * colours (they are the user's data, and shown wherever the tag appears), so
 * the guard belongs at the point of choice.
 *
 * Contrast is measured with APCA (the Accessible Perceptual Contrast
 * Algorithm, version 0.0.98G-4g) rather than the WCAG 2 ratio. The WCAG 2
 * ratio overrates dark text on saturated mid tones: it scores white on a
 * medium blue, green or orange as unreadable and recommends black, which most
 * people find harder to read. APCA follows perception and prefers white there.
 */

/**
 * The lowest APCA lightness contrast (Lc) we accept before warning. Lc 45 is
 * APCA's floor for large or bold text. Tags are small but only a word or two
 * long, and the warning exists to catch pairs that are hard to read, not to
 * hold tags to body text guidance.
 */
export const MIN_TEXT_CONTRAST = 45

/** Parses `#rgb` / `#rrggbb` into 0-255 channels. Null if unparseable. */
function parseHex(hex: string): [number, number, number] | null {
  const value = hex.trim().replace(/^#/, '')
  const full =
    value.length === 3
      ? value
          .split('')
          .map((c) => c + c)
          .join('')
      : value
  if (!/^[0-9a-f]{6}$/i.test(full)) return null
  return [
    parseInt(full.slice(0, 2), 16),
    parseInt(full.slice(2, 4), 16),
    parseInt(full.slice(4, 6), 16),
  ]
}

/** APCA screen luminance, with the soft clamp APCA applies near black. */
function screenLuminance([r, g, b]: [number, number, number]): number {
  const y =
    0.2126729 * Math.pow(r / 255, 2.4) +
    0.7151522 * Math.pow(g / 255, 2.4) +
    0.072175 * Math.pow(b / 255, 2.4)
  return y > 0.022 ? y : y + Math.pow(0.022 - y, 1.414)
}

/**
 * APCA lightness contrast of `foreground` text on `background`, from about
 * -108 (white on black) to 106 (black on white). Positive means dark text on
 * a light background, negative light text on a dark one, and values near 0
 * mean no readable contrast. Returns null when either colour cannot be
 * parsed, so callers can stay quiet rather than warn about a half-typed hex
 * code.
 */
export function apcaContrast(foreground: string, background: string): number | null {
  const fg = parseHex(foreground)
  const bg = parseHex(background)
  if (!fg || !bg) return null

  const text = screenLuminance(fg)
  const back = screenLuminance(bg)
  if (Math.abs(back - text) < 0.0005) return 0

  if (back > text) {
    const contrast = (Math.pow(back, 0.56) - Math.pow(text, 0.57)) * 1.14
    return contrast < 0.1 ? 0 : (contrast - 0.027) * 100
  }
  const contrast = (Math.pow(back, 0.65) - Math.pow(text, 0.62)) * 1.14
  return contrast > -0.1 ? 0 : (contrast + 0.027) * 100
}

/** How readable `foreground` is on `background`, the APCA Lc without its sign. */
export function textContrast(foreground: string, background: string): number | null {
  const lc = apcaContrast(foreground, background)
  return lc === null ? null : Math.abs(lc)
}

/** Whichever of black or white reads better on `background`. */
export function readableTextColor(background: string): string {
  const black = textContrast('#000000', background)
  const white = textContrast('#ffffff', background)
  if (black === null || white === null) return '#ffffff'
  return black > white ? '#000000' : '#ffffff'
}
