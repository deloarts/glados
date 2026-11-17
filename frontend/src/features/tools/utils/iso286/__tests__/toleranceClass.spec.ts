import { describe, it, expect } from 'vitest'

import { DEVIATION_RANGE_UPPER_BOUNDS } from '../sizeRanges'
import {
  availableGrades,
  closestGrade,
  limitDeviations,
  parseClass,
} from '../toleranceClass'
import type { ToleranceClass } from '../toleranceClass'
import { calculateFit } from '../fit'

type Pair = [number, number]

// The limit deviation tables of ISO 286-2 list rows per main range (13 rows),
// with the finer split only where a class changes value. These helpers expand
// such a column to one pair per fine deviation range.
const MAIN_OF_FINE = [0, 1, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 8, 9, 9, 9, 10, 10, 11, 11, 12, 12]
const ROW23_OF_FINE = [0, 1, 2, 3, 3, 4, 4, ...Array.from({ length: 18 }, (_, i) => 5 + i)]
const ROW22_OF_FINE = [0, 1, 2, 3, 3, 4, 4, 5, 5, ...Array.from({ length: 16 }, (_, i) => 6 + i)]

function main(rows: Pair[]): Pair[] {
  expect(rows).toHaveLength(13)
  return MAIN_OF_FINE.map((i) => rows[i] as Pair)
}
function rows23(rows: Pair[]): Pair[] {
  expect(rows).toHaveLength(23)
  return ROW23_OF_FINE.map((i) => rows[i] as Pair)
}
function rows22(rows: Pair[]): Pair[] {
  expect(rows).toHaveLength(22)
  return ROW22_OF_FINE.map((i) => rows[i] as Pair)
}
function hole(uppers: number[]): Pair[] {
  return main(uppers.map((u) => [u, 0]))
}
function shaftH(lowers: number[]): Pair[] {
  return main(lowers.map((l) => [0, l]))
}

// Limit deviations in µm from the ISO 286-2 tables of common classes,
// an independent source for the fundamental deviation and IT tables.
const ISO_286_2_LIMITS: Record<string, () => Pair[]> = {
  H6: () => hole([6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40]),
  H7: () => hole([10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63]),
  H8: () => hole([14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97]),
  H11: () => hole([60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400]),
  h5: () => shaftH([-4, -5, -6, -8, -9, -11, -13, -15, -18, -20, -23, -25, -27]),
  h6: () => shaftH([-6, -8, -9, -11, -13, -16, -19, -22, -25, -29, -32, -36, -40]),
  h9: () => shaftH([-25, -30, -36, -43, -52, -62, -74, -87, -100, -115, -130, -140, -155]),
  h11: () => shaftH([-60, -75, -90, -110, -130, -160, -190, -220, -250, -290, -320, -360, -400]),
  k6: () =>
    main([[6, 0], [9, 1], [10, 1], [12, 1], [15, 2], [18, 2], [21, 2], [25, 3], [28, 3], [33, 4], [36, 4], [40, 4], [45, 5]]),
  m6: () =>
    main([[8, 2], [12, 4], [15, 6], [18, 7], [21, 8], [25, 9], [30, 11], [35, 13], [40, 15], [46, 17], [52, 20], [57, 21], [63, 23]]),
  n5: () =>
    main([[8, 4], [13, 8], [16, 10], [20, 12], [24, 15], [28, 17], [33, 20], [38, 23], [45, 27], [51, 31], [57, 34], [62, 37], [67, 40]]),
  n6: () =>
    main([[10, 4], [16, 8], [19, 10], [23, 12], [28, 15], [33, 17], [39, 20], [45, 23], [52, 27], [60, 31], [66, 34], [73, 37], [80, 40]]),
  f7: () =>
    main([[-6, -16], [-10, -22], [-13, -28], [-16, -34], [-20, -41], [-25, -50], [-30, -60], [-36, -71], [-43, -83], [-50, -96], [-56, -108], [-62, -119], [-68, -131]]),
  g6: () =>
    main([[-2, -8], [-4, -12], [-5, -14], [-6, -17], [-7, -20], [-9, -25], [-10, -29], [-12, -34], [-14, -39], [-15, -44], [-17, -49], [-18, -54], [-20, -60]]),
  d9: () =>
    main([[-20, -45], [-30, -60], [-40, -76], [-50, -93], [-65, -117], [-80, -142], [-100, -174], [-120, -207], [-145, -245], [-170, -285], [-190, -320], [-210, -350], [-230, -385]]),
  d11: () =>
    main([[-20, -80], [-30, -105], [-40, -130], [-50, -160], [-65, -195], [-80, -240], [-100, -290], [-120, -340], [-145, -395], [-170, -460], [-190, -510], [-210, -570], [-230, -630]]),
  e8: () =>
    main([[-14, -28], [-20, -38], [-25, -47], [-32, -59], [-40, -73], [-50, -89], [-60, -106], [-72, -126], [-85, -148], [-100, -172], [-110, -191], [-125, -214], [-135, -232]]),
  r5: () =>
    rows22([[14, 10], [20, 15], [25, 19], [31, 23], [37, 28], [45, 34], [54, 41], [56, 43], [66, 51], [69, 54], [81, 63], [83, 65], [86, 68], [97, 77], [100, 80], [104, 84], [117, 94], [121, 98], [133, 108], [139, 114], [153, 126], [159, 132]]),
  r6: () =>
    rows22([[16, 10], [23, 15], [28, 19], [34, 23], [41, 28], [50, 34], [60, 41], [62, 43], [73, 51], [76, 54], [88, 63], [90, 65], [93, 68], [106, 77], [109, 80], [113, 84], [126, 94], [130, 98], [144, 108], [150, 114], [166, 126], [172, 132]]),
  s6: () =>
    rows22([[20, 14], [27, 19], [32, 23], [39, 28], [48, 35], [59, 43], [72, 53], [78, 59], [93, 71], [101, 79], [117, 92], [125, 100], [133, 108], [151, 122], [159, 130], [169, 140], [190, 158], [202, 170], [226, 190], [244, 208], [272, 232], [292, 252]]),
  a11: () =>
    rows23([[-270, -330], [-270, -345], [-280, -370], [-290, -400], [-300, -430], [-310, -470], [-320, -480], [-340, -530], [-360, -550], [-380, -600], [-410, -630], [-460, -710], [-520, -770], [-580, -830], [-660, -950], [-740, -1030], [-820, -1110], [-920, -1240], [-1050, -1370], [-1200, -1560], [-1350, -1710], [-1500, -1900], [-1650, -2050]]),
  c11: () =>
    rows23([[-60, -120], [-70, -145], [-80, -170], [-95, -205], [-110, -240], [-120, -280], [-130, -290], [-140, -330], [-150, -340], [-170, -390], [-180, -400], [-200, -450], [-210, -460], [-230, -480], [-240, -530], [-260, -550], [-280, -570], [-300, -620], [-330, -650], [-360, -720], [-400, -760], [-440, -840], [-480, -880]]),
  N6: () =>
    main([[-4, -10], [-5, -13], [-7, -16], [-9, -20], [-11, -24], [-12, -28], [-14, -33], [-16, -38], [-20, -45], [-22, -51], [-25, -57], [-26, -62], [-27, -67]]),
  P6: () =>
    main([[-6, -12], [-9, -17], [-12, -21], [-15, -26], [-18, -31], [-21, -37], [-26, -45], [-30, -52], [-36, -61], [-41, -70], [-47, -79], [-51, -87], [-55, -95]]),
  F8: () =>
    main([[20, 6], [28, 10], [35, 13], [43, 16], [53, 20], [64, 25], [76, 30], [90, 36], [106, 43], [122, 50], [137, 56], [151, 62], [165, 68]]),
  G7: () =>
    main([[12, 2], [16, 4], [20, 5], [24, 6], [28, 7], [34, 9], [40, 10], [47, 12], [54, 14], [61, 15], [69, 17], [75, 18], [83, 20]]),
  K7: () =>
    main([[0, -10], [3, -9], [5, -10], [6, -12], [6, -15], [7, -18], [9, -21], [10, -25], [12, -28], [13, -33], [16, -36], [17, -40], [18, -45]]),
  M7: () =>
    main([[-2, -12], [0, -12], [0, -15], [0, -18], [0, -21], [0, -25], [0, -30], [0, -35], [0, -40], [0, -46], [0, -52], [0, -57], [0, -63]]),
  N7: () =>
    main([[-4, -14], [-4, -16], [-4, -19], [-5, -23], [-7, -28], [-8, -33], [-9, -39], [-10, -45], [-12, -52], [-14, -60], [-14, -66], [-16, -73], [-17, -80]]),
  R7: () =>
    rows22([[-10, -20], [-11, -23], [-13, -28], [-16, -34], [-20, -41], [-25, -50], [-30, -60], [-32, -62], [-38, -73], [-41, -76], [-48, -88], [-50, -90], [-53, -93], [-60, -106], [-63, -109], [-67, -113], [-74, -126], [-78, -130], [-87, -144], [-93, -150], [-103, -166], [-109, -172]]),
  S7: () =>
    rows22([[-14, -24], [-15, -27], [-17, -32], [-21, -39], [-27, -48], [-34, -59], [-42, -72], [-48, -78], [-58, -93], [-66, -101], [-77, -117], [-85, -125], [-93, -133], [-105, -151], [-113, -159], [-123, -169], [-138, -190], [-150, -202], [-169, -226], [-187, -244], [-209, -272], [-229, -292]]),
  C11: () =>
    rows23([[120, 60], [145, 70], [170, 80], [205, 95], [240, 110], [280, 120], [290, 130], [330, 140], [340, 150], [390, 170], [400, 180], [450, 200], [460, 210], [480, 230], [530, 240], [550, 260], [570, 280], [620, 300], [650, 330], [720, 360], [760, 400], [840, 440], [880, 480]]),
  D10: () =>
    main([[60, 20], [78, 30], [98, 40], [120, 50], [149, 65], [180, 80], [220, 100], [260, 120], [305, 145], [355, 170], [400, 190], [440, 210], [480, 230]]),
  E9: () =>
    main([[39, 14], [50, 20], [61, 25], [75, 32], [92, 40], [112, 50], [134, 60], [159, 72], [185, 85], [215, 100], [240, 110], [265, 125], [290, 135]]),
  JS9: () =>
    main([12.5, 15, 18, 21.5, 26, 31, 37, 43.5, 50, 57.5, 65, 70, 77.5].map((v) => [v, -v] as Pair)),
  P9: () =>
    main([[-6, -31], [-12, -42], [-15, -51], [-18, -61], [-22, -74], [-26, -88], [-32, -106], [-37, -124], [-43, -143], [-50, -165], [-56, -186], [-62, -202], [-68, -223]]),
  A11: () =>
    rows23([[330, 270], [345, 270], [370, 280], [400, 290], [430, 300], [470, 310], [480, 320], [530, 340], [550, 360], [600, 380], [630, 410], [710, 460], [770, 520], [830, 580], [950, 660], [1030, 740], [1110, 820], [1240, 920], [1370, 1050], [1560, 1200], [1710, 1350], [1900, 1500], [2050, 1650]]),
}

function cls(code: string): ToleranceClass {
  const parsed = parseClass(code)
  if (!parsed) throw new Error(`Unparseable class ${code}`)
  return parsed
}

// Two sizes per fine range: just above its lower bound and exactly its upper
// bound, so both ends of every "over ... up to" range are exercised.
function sizesOfRange(index: number): number[] {
  const upper = DEVIATION_RANGE_UPPER_BOUNDS[index] as number
  const lower = index === 0 ? 0 : (DEVIATION_RANGE_UPPER_BOUNDS[index - 1] as number)
  return [lower + 0.001, upper]
}

describe('limitDeviations against the ISO 286-2 tables', () => {
  for (const [code, rows] of Object.entries(ISO_286_2_LIMITS)) {
    it(`matches every row of ${code}`, () => {
      const expected = rows()
      expect(expected).toHaveLength(DEVIATION_RANGE_UPPER_BOUNDS.length)
      // Collected rather than asserted one by one, so a failure lists every
      // mismatching size of the class at once.
      const mismatches: string[] = []
      expected.forEach(([upper, lower], index) => {
        for (const size of sizesOfRange(index)) {
          const actual = limitDeviations(size, cls(code))
          if (!actual.ok || actual.upper !== upper || actual.lower !== lower) {
            mismatches.push(`${size} mm: expected ${upper}/${lower}, got ${JSON.stringify(actual)}`)
          }
        }
      })
      expect(mismatches).toEqual([])
    })
  }
})

describe('limitDeviations', () => {
  it('works through the Δ examples (40 g5 and 100 K6)', () => {
    expect(limitDeviations(40, cls('g5'))).toEqual({ ok: true, upper: -9, lower: -20 })
    expect(limitDeviations(100, cls('K6'))).toEqual({ ok: true, upper: 4, lower: -18 })
  })

  it('covers h, H, js and JS up to 3150 mm from the IT table alone', () => {
    expect(limitDeviations(3150, cls('h7'))).toEqual({ ok: true, upper: 0, lower: -210 })
    expect(limitDeviations(600, cls('H11'))).toEqual({ ok: true, upper: 440, lower: 0 })
    expect(limitDeviations(1000, cls('js6'))).toEqual({ ok: true, upper: 28, lower: -28 })
    expect(limitDeviations(2600, cls('JS18'))).toEqual({ ok: true, upper: 16500, lower: -16500 })
  })

  it('refuses every other letter above 500 mm', () => {
    expect(limitDeviations(500, cls('g6')).ok).toBe(true)
    expect(limitDeviations(500.1, cls('g6'))).toEqual({ ok: false, reason: 'sizeAboveRange' })
    expect(limitDeviations(600, cls('u8'))).toEqual({ ok: false, reason: 'sizeAboveRange' })
    expect(limitDeviations(3150.1, cls('h7'))).toEqual({ ok: false, reason: 'sizeAboveRange' })
  })

  it('refuses grades outside the letter span', () => {
    expect(limitDeviations(25, cls('a8'))).toEqual({ ok: false, reason: 'gradeNotAvailable' })
    expect(limitDeviations(25, cls('K9'))).toEqual({ ok: false, reason: 'gradeNotAvailable' })
    expect(limitDeviations(25, cls('j8'))).toEqual({ ok: false, reason: 'gradeNotAvailable' })
    expect(limitDeviations(25, cls('u7'))).toEqual({ ok: false, reason: 'gradeNotAvailable' })
  })

  it('applies k = 0 outside IT4 to IT7', () => {
    expect(limitDeviations(25, cls('k8'))).toEqual({ ok: true, upper: 33, lower: 0 })
    expect(limitDeviations(25, cls('k7'))).toEqual({ ok: true, upper: 23, lower: 2 })
  })

  it('takes R and S above IT7 without Δ', () => {
    expect(limitDeviations(25, cls('R8'))).toEqual({ ok: true, upper: -28, lower: -61 })
  })

  it('keeps N9 out of sizes up to 1 mm', () => {
    expect(limitDeviations(1, cls('N9'))).toEqual({ ok: false, reason: 'notForSmallSizes' })
    expect(limitDeviations(1.5, cls('N9'))).toEqual({ ok: true, upper: -4, lower: -29 })
  })

  it('rejects a non-positive or non-numeric size', () => {
    expect(limitDeviations(0, cls('H7'))).toEqual({ ok: false, reason: 'invalidSize' })
    expect(limitDeviations(Number.NaN, cls('H7'))).toEqual({ ok: false, reason: 'invalidSize' })
  })
})

describe('parseClass', () => {
  it('tells holes from shafts by case', () => {
    expect(parseClass('H7')).toEqual({ part: 'hole', letter: 'H', grade: 7 })
    expect(parseClass('js6')).toEqual({ part: 'shaft', letter: 'js', grade: 6 })
  })

  it('rejects unknown letters and grades', () => {
    expect(parseClass('B7')).toBeNull()
    expect(parseClass('H19')).toBeNull()
    expect(parseClass('H0')).toBeNull()
    expect(parseClass('7H')).toBeNull()
  })
})

describe('availableGrades and closestGrade', () => {
  it('lists the grades of a letter at a size', () => {
    expect(availableGrades('shaft', 'j', 25)).toEqual([5, 6, 7])
    expect(availableGrades('hole', 'N', 25)).toEqual([3, 4, 5, 6, 7, 8, 9])
    expect(availableGrades('shaft', 'g', 600)).toEqual([])
  })

  it('keeps the current grade or moves to the nearest one', () => {
    expect(closestGrade([5, 6, 7], 6)).toBe(6)
    expect(closestGrade([9, 10, 11, 12, 13], 6)).toBe(9)
    expect(closestGrade([7, 9], 8)).toBe(7)
    expect(closestGrade([], 6)).toBeNull()
  })
})

describe('calculateFit', () => {
  it('reproduces the 30 H8/f7 example', () => {
    const fit = calculateFit(
      { upper: 33, lower: 0 },
      { upper: -20, lower: -41 },
    )
    expect(fit).toEqual({ maxClearance: 74, minClearance: 20, type: 'clearance' })
  })

  it('classifies transition and interference fits', () => {
    expect(calculateFit({ upper: 21, lower: 0 }, { upper: 15, lower: 2 }).type).toBe('transition')
    expect(calculateFit({ upper: 21, lower: 0 }, { upper: 48, lower: 35 }).type).toBe('interference')
    expect(calculateFit({ upper: 21, lower: 0 }, { upper: 0, lower: -13 }).type).toBe('clearance')
  })
})
