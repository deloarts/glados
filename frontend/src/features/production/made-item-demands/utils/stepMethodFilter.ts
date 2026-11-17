/**
 * The step method filter of the made item demands offers fabrication and
 * inspection methods in one grouped picker. Each value carries its kind, so
 * the two id spaces cannot collide.
 */
export const STEP_METHOD_SEPARATOR = ':'

/** Splits the picked values back into fabrication and inspection method ids. */
export function decodeStepMethods(encoded: string[]): {
  fabricationMethodIds: number[]
  inspectionMethodIds: number[]
} {
  const fabricationMethodIds: number[] = []
  const inspectionMethodIds: number[] = []
  for (const entry of encoded) {
    const [kind, rawId] = entry.split(STEP_METHOD_SEPARATOR)
    const id = Number(rawId)
    if (!Number.isInteger(id)) continue
    if (kind === 'fabrication') fabricationMethodIds.push(id)
    else if (kind === 'inspection') inspectionMethodIds.push(id)
  }
  return { fabricationMethodIds, inspectionMethodIds }
}
