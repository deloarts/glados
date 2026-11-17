import { webApi } from '@/core/api/webRequest'

import type { Operator } from '../types/operatorsResponse'

export async function getOperators(): Promise<Operator[]> {
  return webApi.get('/production-operators/')
}
