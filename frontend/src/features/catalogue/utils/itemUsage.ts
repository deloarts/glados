import type { ItemOrderRow, ItemUsageDemand, ItemUsageRow } from '../types/itemDetail'
import type { ProjectResponse } from '@/features/projects'

/**
 * The rows of the "Used in" card, one per project the item's demands or
 * delivered order items touch. There is no where-used endpoint, so this is
 * computed from what the page already fetched. Fulfilled orders are those
 * whose order item, not the order, is delivered for that project. A project
 * missing from projectsById renders without product fields.
 */
export function aggregateItemUsage(
  demands: ItemUsageDemand[],
  orderRows: ItemOrderRow[],
  projectsById: Map<number, ProjectResponse>,
): ItemUsageRow[] {
  const rows = new Map<number, ItemUsageRow>()
  // Lists an order once per project, even with several delivered lines.
  const seenOrderIdsByProject = new Map<number, Set<number>>()

  function rowFor(
    projectId: number,
    projectNumber: string,
    projectCustomer: string | null,
    projectDescription: string | null,
    projectStatus: string | null,
  ): ItemUsageRow {
    const existing = rows.get(projectId)
    if (existing) return existing

    const project = projectsById.get(projectId) ?? null
    const row: ItemUsageRow = {
      projectId,
      projectNumber,
      projectCustomer,
      projectDescription,
      projectStatus,
      productNumber: project?.product?.product_number ?? null,
      productDescription: project?.product?.description ?? null,
      qtyDemanded: 0,
      qtyFulfilled: 0,
      demandCount: 0,
      fulfilledOrders: [],
    }
    rows.set(projectId, row)
    return row
  }

  for (const demand of demands) {
    const row = rowFor(
      demand.projectId,
      demand.projectNumber,
      demand.projectCustomer,
      demand.projectDescription,
      demand.projectStatus,
    )
    row.qtyDemanded += demand.quantity
    row.demandCount += 1
    if (demand.status === 'fulfilled') row.qtyFulfilled += demand.quantity
  }

  for (const { order, orderItem } of orderRows) {
    if (orderItem.status !== 'delivered') continue

    const row = rowFor(
      orderItem.project_id,
      orderItem.project_number,
      orderItem.project_customer,
      orderItem.project_description,
      orderItem.project_status,
    )

    let seenOrderIds = seenOrderIdsByProject.get(orderItem.project_id)
    if (!seenOrderIds) {
      seenOrderIds = new Set()
      seenOrderIdsByProject.set(orderItem.project_id, seenOrderIds)
    }
    if (!seenOrderIds.has(order.id)) {
      seenOrderIds.add(order.id)
      row.fulfilledOrders.push({ orderId: order.id, orderNumber: order.order_number })
    }
  }

  return [...rows.values()].sort((a, b) =>
    b.projectNumber.localeCompare(a.projectNumber, undefined, { numeric: true }),
  )
}
