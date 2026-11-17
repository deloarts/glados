/**
 * Holes for screws, all lengths in mm, keyed by nominal thread diameter:
 * clearance holes (ISO 273), counterbores (DIN 974-1 and DIN 974-2) and
 * countersinks (ISO 15065, DIN 74 form F). `null` marks a size the standard
 * leaves out.
 */

/** Clearance holes: fine (H12), medium (H13) and coarse (H14) series. */
export const CLEARANCE_HOLES: Readonly<Record<number, readonly [fine: number, medium: number, coarse: number]>> = {
  1: [1.1, 1.2, 1.3],
  1.2: [1.3, 1.4, 1.5],
  1.6: [1.7, 1.8, 2],
  2: [2.2, 2.4, 2.6],
  2.5: [2.7, 2.9, 3.1],
  3: [3.2, 3.4, 3.6],
  4: [4.3, 4.5, 4.8],
  5: [5.3, 5.5, 5.8],
  6: [6.4, 6.6, 7],
  8: [8.4, 9, 10],
  10: [10.5, 11, 12],
  12: [13, 13.5, 14.5],
  16: [17, 17.5, 18.5],
  20: [21, 22, 24],
  24: [25, 26, 28],
  30: [31, 33, 35],
  36: [37, 39, 42],
  42: [43, 45, 48],
  48: [50, 52, 56],
  56: [58, 62, 66],
  64: [66, 70, 74],
}

export interface CapScrewCounterbore {
  /** Clearance hole diameter dh (H13). */
  dh: number
  /** Counterbore diameter d1 (H13) for series 1 to 6. */
  series: readonly [number | null, number | null, number | null, number | null, number | null, number | null]
  /** Counterbore depth for screws without washers, by screw standard. */
  depth: { iso1207: number | null; iso4762: number | null; din7984: number | null }
}

/**
 * Counterbores for cap screws (DIN 974-1). Series 1 is for screws without
 * washer such as ISO 4762, series 2 for ISO 1580, ISO 7045 and ISO 14583, series
 * 3 to 6 for screws with the various washer components.
 */
export const CAP_SCREW_COUNTERBORES: Readonly<Record<number, CapScrewCounterbore>> = {
  3: { dh: 3.4, series: [6.5, 7, 6.5, 7, 9, 8], depth: { iso1207: 2.4, iso4762: 3.4, din7984: 2.4 } },
  4: { dh: 4.5, series: [8, 9, 8, 9, 10, 10], depth: { iso1207: 3, iso4762: 4.4, din7984: 3.2 } },
  5: { dh: 5.5, series: [10, 11, 10, 11, 13, 13], depth: { iso1207: 3.7, iso4762: 5.4, din7984: 3.9 } },
  6: { dh: 6.6, series: [11, 13, 11, 13, 15, 15], depth: { iso1207: 4.3, iso4762: 6.4, din7984: 4.4 } },
  8: { dh: 9, series: [15, 18, 15, 16, 18, 20], depth: { iso1207: 5.6, iso4762: 8.6, din7984: 5.6 } },
  10: { dh: 11, series: [18, 24, 18, 20, 24, 24], depth: { iso1207: 6.6, iso4762: 10.6, din7984: 6.6 } },
  12: { dh: 13.5, series: [20, null, 20, 24, 26, 33], depth: { iso1207: null, iso4762: 12.6, din7984: 7.6 } },
  16: { dh: 17.5, series: [26, null, 26, 30, 33, 43], depth: { iso1207: null, iso4762: 16.6, din7984: 9.6 } },
  20: { dh: 22, series: [33, null, 33, 36, 40, 48], depth: { iso1207: null, iso4762: 20.6, din7984: 11.6 } },
  24: { dh: 26, series: [40, null, 40, 43, 48, 58], depth: { iso1207: null, iso4762: 24.8, din7984: 13.8 } },
  27: { dh: 30, series: [46, null, 46, 46, 54, 63], depth: { iso1207: null, iso4762: null, din7984: null } },
  30: { dh: 33, series: [50, null, 50, 54, 61, 73], depth: { iso1207: null, iso4762: 31, din7984: null } },
  36: { dh: 39, series: [58, null, 58, 63, 69, null], depth: { iso1207: null, iso4762: 37, din7984: null } },
}

export interface HexCounterbore {
  widthAcrossFlats: number
  dh: number
  /** Counterbore diameter d1 (H13): series 1 for socket wrenches, 2 for box wrenches, 3 for tight spaces. */
  series: readonly [number, number, number]
  /** Counterbore depth for hexagon bolts without washer components. */
  depth: number
}

/** Counterbores for hexagon bolts, screws and nuts (DIN 974-2). */
export const HEX_COUNTERBORES: Readonly<Record<number, HexCounterbore>> = {
  4: { widthAcrossFlats: 7, dh: 4.5, series: [13, 15, 10], depth: 3.3 },
  5: { widthAcrossFlats: 8, dh: 5.5, series: [15, 18, 11], depth: 4.1 },
  6: { widthAcrossFlats: 10, dh: 6.6, series: [18, 20, 13], depth: 4.6 },
  8: { widthAcrossFlats: 13, dh: 9, series: [24, 26, 18], depth: 6.1 },
  10: { widthAcrossFlats: 16, dh: 11, series: [28, 33, 22], depth: 7.2 },
  12: { widthAcrossFlats: 18, dh: 13.5, series: [33, 36, 26], depth: 8.3 },
  14: { widthAcrossFlats: 21, dh: 15.5, series: [36, 43, 30], depth: 9.6 },
  16: { widthAcrossFlats: 24, dh: 17.5, series: [40, 46, 33], depth: 10.8 },
  20: { widthAcrossFlats: 30, dh: 22, series: [46, 54, 40], depth: 13.3 },
  24: { widthAcrossFlats: 36, dh: 26, series: [58, 73, 48], depth: 16 },
  27: { widthAcrossFlats: 41, dh: 30, series: [61, 76, 54], depth: 18.2 },
  30: { widthAcrossFlats: 46, dh: 33, series: [73, 82, 61], depth: 20.1 },
  33: { widthAcrossFlats: 50, dh: 36, series: [76, 89, 69], depth: 22.4 },
  36: { widthAcrossFlats: 55, dh: 39, series: [82, 93, 73], depth: 23.9 },
  42: { widthAcrossFlats: 65, dh: 45, series: [98, 107, 82], depth: 27.4 },
}

export interface Countersink {
  d1: number
  d2Min: number
  d2Max: number
  /** Approximate countersink depth. */
  depth: number
}

/**
 * 90° countersinks for countersunk head screws with heads per ISO 7721, such as
 * ISO 2009, ISO 2010, ISO 7046 and ISO 7047 (ISO 15065), by metric thread size.
 */
export const COUNTERSINKS_ISO_15065: Readonly<Record<number, Countersink>> = {
  1.6: { d1: 1.8, d2Min: 3.6, d2Max: 3.7, depth: 1 },
  2: { d1: 2.4, d2Min: 4.4, d2Max: 4.5, depth: 1.1 },
  2.5: { d1: 2.9, d2Min: 5.5, d2Max: 5.6, depth: 1.4 },
  3: { d1: 3.4, d2Min: 6.3, d2Max: 6.5, depth: 1.6 },
  4: { d1: 4.5, d2Min: 9.4, d2Max: 9.6, depth: 2.6 },
  5: { d1: 5.5, d2Min: 10.4, d2Max: 10.7, depth: 2.6 },
  6: { d1: 6.6, d2Min: 12.6, d2Max: 12.9, depth: 3.1 },
  8: { d1: 9, d2Min: 17.3, d2Max: 17.6, depth: 4.3 },
  10: { d1: 11, d2Min: 20, d2Max: 20.3, depth: 4.7 },
}

export interface SocketCountersink {
  d1: number
  d2: number
  /** Approximate countersink depth. */
  depth: number
}

/** 90° countersinks for hexagon socket countersunk head screws ISO 10642 (DIN 74 form F). */
export const COUNTERSINKS_ISO_10642: Readonly<Record<number, SocketCountersink>> = {
  3: { d1: 3.4, d2: 6.9, depth: 1.8 },
  4: { d1: 4.5, d2: 9.2, depth: 2.3 },
  5: { d1: 5.5, d2: 11.5, depth: 3 },
  6: { d1: 6.6, d2: 13.7, depth: 3.6 },
  8: { d1: 9, d2: 18.3, depth: 4.6 },
  10: { d1: 11, d2: 22.7, depth: 5.9 },
  12: { d1: 13.5, d2: 27.2, depth: 6.9 },
  14: { d1: 15.5, d2: 31.2, depth: 7.8 },
  16: { d1: 17.5, d2: 34, depth: 8.2 },
  20: { d1: 22, d2: 40.7, depth: 9.4 },
}
