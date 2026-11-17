/**
 * The mocked API for the README pictures: the screenshot tests' base answers
 * plus the made-up shop in ./fixtures.
 */
import type { components } from '../../src/core/api/generated/webSchema'
import { articleGroups, baseHandlers, madeItems, page, user } from '../visual/fixtures'
import type { MockHandler } from '../visual/mockApi'
import {
  boughtItems,
  dashboardSummary,
  lotDetail,
  lots,
  machinePools,
  machines,
  notifications,
  productionOperators,
  productionOrders,
  scheduleBoard,
  todoSources,
  userDirectory,
  wipLots,
} from './fixtures'

type Schemas = components['schemas']

function ordersFor(url: URL): Schemas['ProductionOrderResponse'][] {
  const machine = url.searchParams.get('machine_id')
  const lot = url.searchParams.get('lot_id')
  const statuses = [...url.searchParams.getAll('statuses'), ...url.searchParams.getAll('status')]
  return productionOrders.filter(
    (order) =>
      (!machine || order.machine_id === Number(machine)) &&
      (!lot || order.lot_id === Number(lot)) &&
      (statuses.length === 0 || statuses.includes(order.status)),
  )
}

export function readmeHandlers(dark: boolean): MockHandler[] {
  return [
    ...baseHandlers(user({ theme_dark_mode: dark })),
    { path: '/web/dashboard/summary', body: dashboardSummary },
    { path: '/web/notifications/', body: notifications },
    { path: '/web/production-machines/', body: () => page(machines()) },
    { path: '/web/production-machine-pools/', body: () => page(machinePools()) },
    { path: '/web/production-orders/', body: (url: URL) => page(ordersFor(url)) },
    {
      path: /^\/web\/production-orders\/\d+$/,
      body: (url: URL) => productionOrders.find((order) => order.id === Number(url.pathname.split('/').pop())),
    },
    { path: '/web/production-operators/', body: productionOperators },
    { path: '/web/production-wip/', body: wipLots },
    { path: '/web/production-lots/', body: page(lots) },
    { path: /^\/web\/production-lots\/\d+$/, body: (url: URL) => lotDetail(Number(url.pathname.split('/').pop())) },
    { path: '/web/quote-requests/open-links', body: { bought_demands: {}, source_demands: {}, lot_positions: {} } },
    { method: 'POST', path: '/web/agent-calls/created-records', body: [] },
    { path: '/web/production-schedule/', body: scheduleBoard },
    { path: '/web/todo/sources', body: todoSources },
    { path: '/web/users/directory', body: page(userDirectory) },
    { path: '/web/made-items/', body: page(madeItems) },
    { path: '/web/bought-items/', body: page(boughtItems) },
    { path: '/web/product-families/', body: page([]) },
    { path: '/web/article-groups/', body: page(articleGroups) },
    { path: '/web/pdm/preview', body: { enabled: false, kind: 'made', newer: [], unlinked: [] } },
    { path: /^\/web\/(made|bought)-items-pictures\/$/, body: [] },
    { path: /^\/web\/made-items-files\/?$/, body: [] },
  ]
}
