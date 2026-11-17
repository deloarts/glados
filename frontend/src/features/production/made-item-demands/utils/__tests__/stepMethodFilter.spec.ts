import { describe, expect, it } from 'vitest'

import { decodeStepMethods, STEP_METHOD_SEPARATOR } from '../stepMethodFilter'

describe('decodeStepMethods', () => {
  it('splits the picked values by kind and drops values without a numeric id', () => {
    const picked = [
      `fabrication${STEP_METHOD_SEPARATOR}3`,
      `inspection${STEP_METHOD_SEPARATOR}7`,
      `fabrication${STEP_METHOD_SEPARATOR}x`,
      `other${STEP_METHOD_SEPARATOR}9`,
    ]

    expect(decodeStepMethods(picked)).toEqual({
      fabricationMethodIds: [3],
      inspectionMethodIds: [7],
    })
  })
})
