import { createItemChangelogStore } from '@/shared/stores/createItemChangelogStore'
import { getMadeItemChangelog } from '../api/getMadeItemChangelog'

import type { MadeItemResponse } from '../types/madeItemsResponse'

export const useMadeItemsChangelogStore = createItemChangelogStore<MadeItemResponse>(
  'madeItemsChangelog',
  getMadeItemChangelog,
)
