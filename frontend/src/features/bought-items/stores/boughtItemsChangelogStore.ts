import { createItemChangelogStore } from '@/shared/stores/createItemChangelogStore'
import { getBoughtItemChangelog } from '../api/getBoughtItemChangelog'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export const useBoughtItemsChangelogStore = createItemChangelogStore<BoughtItemResponse>(
  'boughtItemsChangelog',
  getBoughtItemChangelog,
)
