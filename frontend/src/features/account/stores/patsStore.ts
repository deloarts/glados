import { createTokenStore } from '@/shared/stores/createTokenStore'
import { patsApi } from '../api/patsApi'

export const usePatsStore = createTokenStore('pats', patsApi)
