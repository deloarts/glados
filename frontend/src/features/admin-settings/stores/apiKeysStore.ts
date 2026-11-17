import { createTokenStore } from '@/shared/stores/createTokenStore'
import { apiKeysApi } from '../api/apiKeysApi'

export const useApiKeysStore = createTokenStore('apiKeys', apiKeysApi)
