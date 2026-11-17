import { createMasterDataStore } from '@/shared/stores/createMasterDataStore'
import { archiveArticleGroup } from '../api/archiveArticleGroup'
import { createArticleGroup } from '../api/createArticleGroup'
import { getArticleGroups } from '../api/getArticleGroups'
import { placeArticleGroup } from '../api/placeArticleGroup'
import { restoreArticleGroup } from '../api/restoreArticleGroup'
import { updateArticleGroup } from '../api/updateArticleGroup'

// items is the complete article group list other features pick from.
export const useArticleGroupsStore = createMasterDataStore('articleGroups', {
  api: {
    list: getArticleGroups,
    create: createArticleGroup,
    update: updateArticleGroup,
    archive: archiveArticleGroup,
    restore: restoreArticleGroup,
    place: placeArticleGroup,
  },
  filters: {
    name: 'contains',
  },
})
