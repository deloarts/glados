import { searchProjects } from '@/core/api/projects/searchProjects'

import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'
import type { ProjectRef } from '@/core/types/projectRef'

/** How many projects the demand tables' project filter offers at once. */
const PAGE_SIZE = 20

function toOption(project: ProjectRef): LookupOption {
  const sublabel = [project.customer?.name, project.description].filter(Boolean).join(' · ')
  return { id: project.id, label: project.project_number, ...(sublabel ? { sublabel } : {}) }
}

/**
 * The project filter's page: the newest projects of any status, since a
 * demand of a closed project is still listed, narrowed by project number
 * while the user types.
 */
export async function fetchDemandProjectOptions(query: string): Promise<LookupOption[]> {
  const page = await searchProjects({
    limit: PAGE_SIZE,
    order_by: 'id',
    order_dir: 'desc',
    ...(query ? { project_number: query } : {}),
  })
  return page.items.map(toOption)
}

export async function fetchDemandProjectsByIds(ids: number[]): Promise<LookupOption[]> {
  const page = await searchProjects({ ids })
  return page.items.map(toOption)
}
