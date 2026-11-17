import type { Schemas } from '@/core/api/generated'

type ProjectResponse = Schemas['ProjectResponse']

// Minimal project shape needed by features that link records to a project
// (e.g. bought-items demands/orders) without depending on the full
// ProjectResponse type or the projects feature's product/customer relations.
// The product and delivery date fields are optional because the slimmer
// project shapes nested in other responses leave them out.
export type ProjectRef = Pick<ProjectResponse, 'id' | 'project_number' | 'description'> &
  Partial<
    Pick<
      ProjectResponse,
      'product_id' | 'required_delivery_date_made' | 'required_delivery_date_bought'
    >
  > & {
    customer: Pick<Schemas['CustomerResponse'], 'name'> | null
  }
