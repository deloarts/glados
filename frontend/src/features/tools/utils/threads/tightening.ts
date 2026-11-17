/**
 * Guide values for tightening torques and preload forces of coarse thread
 * fastening screws in the property classes 8.8, 10.9 and 12.9. The friction
 * coefficient behind them is not recorded, so the UI states that next to the
 * values.
 */

export type PropertyClass = '8.8' | '10.9' | '12.9'

export const PROPERTY_CLASSES: readonly PropertyClass[] = ['8.8', '10.9', '12.9']

export interface TighteningRow {
  d: number
  pitch: number
  /** Tensile stress area in mm² the values are based on. */
  stressArea: number
  /** Tightening torque MA in Nm for 8.8, 10.9 and 12.9. */
  torque: readonly [number, number, number]
  /** Preload force FV in kN for 8.8, 10.9 and 12.9. */
  preload: readonly [number, number, number]
}

export const TIGHTENING: readonly TighteningRow[] = [
  { d: 1.6, pitch: 0.35, stressArea: 1.27, torque: [0.19, 0.26, 0.31], preload: [0.59, 0.83, 0.99] },
  { d: 2, pitch: 0.4, stressArea: 2.07, torque: [0.39, 0.55, 0.66], preload: [0.98, 1.37, 1.65] },
  { d: 2.5, pitch: 0.45, stressArea: 3.39, torque: [0.81, 1.13, 1.36], preload: [1.62, 2.29, 2.74] },
  { d: 3, pitch: 0.5, stressArea: 5.03, torque: [1.51, 1.98, 2.37], preload: [2.62, 3.43, 4.11] },
  { d: 4, pitch: 0.7, stressArea: 8.78, torque: [3.3, 4.8, 5.6], preload: [4.3, 6.3, 7.4] },
  { d: 5, pitch: 0.8, stressArea: 14.2, torque: [6.5, 9.5, 11.2], preload: [7, 10.3, 12] },
  { d: 6, pitch: 1, stressArea: 20.1, torque: [11.3, 16.5, 19.3], preload: [9.9, 14.5, 17] },
  { d: 7, pitch: 1, stressArea: 28.9, torque: [18.7, 27.5, 32.2], preload: [14.4, 21.1, 24.7] },
  { d: 8, pitch: 1.25, stressArea: 36.6, torque: [27.3, 40.1, 46.9], preload: [18.1, 26.6, 31.1] },
  { d: 10, pitch: 1.5, stressArea: 58, torque: [54, 79, 93], preload: [28.8, 42.2, 49.4] },
  { d: 12, pitch: 1.75, stressArea: 84.3, torque: [93, 137, 160], preload: [41.9, 61.5, 72] },
  { d: 14, pitch: 2, stressArea: 115, torque: [148, 218, 255], preload: [57.5, 84.4, 98.8] },
  { d: 16, pitch: 2, stressArea: 157, torque: [230, 338, 395], preload: [78.8, 115.7, 135.4] },
  { d: 18, pitch: 2.5, stressArea: 193, torque: [329, 469, 549], preload: [99, 141, 165] },
  { d: 20, pitch: 2.5, stressArea: 245, torque: [464, 661, 773], preload: [127, 181, 212] },
  { d: 22, pitch: 2.5, stressArea: 303, torque: [634, 904, 1057], preload: [158, 225, 264] },
  { d: 24, pitch: 3, stressArea: 353, torque: [798, 1136, 1329], preload: [183, 260, 305] },
  { d: 27, pitch: 3, stressArea: 459, torque: [1176, 1674, 1959], preload: [240, 342, 400] },
  { d: 30, pitch: 3.5, stressArea: 561, torque: [1597, 2274, 2662], preload: [292, 416, 487] },
  { d: 33, pitch: 3.5, stressArea: 694, torque: [2161, 3078, 3601], preload: [363, 517, 605] },
  { d: 36, pitch: 4, stressArea: 817, torque: [2778, 3957, 4631], preload: [427, 608, 711] },
  { d: 39, pitch: 4, stressArea: 976, torque: [3597, 5123, 5994], preload: [512, 729, 853] },
  { d: 42, pitch: 4.5, stressArea: 1117, torque: [4413, 6285, 7354], preload: [584, 832, 974] },
  { d: 45, pitch: 4.5, stressArea: 1302, torque: [5512, 7851, 9187], preload: [684, 975, 1140] },
  { d: 48, pitch: 5, stressArea: 1468, torque: [6667, 9495, 11112], preload: [770, 1096, 1283] },
  { d: 52, pitch: 5, stressArea: 1753, torque: [8570, 12206, 14284], preload: [922, 1314, 1537] },
  { d: 56, pitch: 5.5, stressArea: 2024, torque: [10678, 15208, 17797], preload: [1064, 1516, 1774] },
  { d: 60, pitch: 5.5, stressArea: 2356, torque: [13249, 18870, 22082], preload: [1242, 1770, 2071] },
  { d: 64, pitch: 6, stressArea: 2669, torque: [15955, 22724, 26592], preload: [1406, 2003, 2344] },
  { d: 68, pitch: 6, stressArea: 3047, torque: [19282, 27462, 32137], preload: [1610, 2293, 2683] },
  { d: 72, pitch: 6, stressArea: 3451, torque: [23043, 32819, 38405], preload: [1828, 2603, 3046] },
  { d: 76, pitch: 6, stressArea: 3881, torque: [27232, 38785, 45387], preload: [2059, 2933, 3432] },
  { d: 80, pitch: 6, stressArea: 4335, torque: [31930, 45476, 53216], preload: [2304, 3282, 3840] },
  { d: 90, pitch: 6, stressArea: 5580, torque: [46188, 65783, 76980], preload: [2977, 4240, 4962] },
  { d: 100, pitch: 6, stressArea: 6983, torque: [64297, 91574, 107161], preload: [3736, 5322, 6227] },
]

/** The row for a coarse thread, or undefined for sizes the table does not list. */
export function tighteningFor(d: number, pitch: number): TighteningRow | undefined {
  return TIGHTENING.find((row) => row.d === d && row.pitch === pitch)
}
