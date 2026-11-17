import { createRouter, createWebHistory } from 'vue-router'
import type { RouteLocationNormalized } from 'vue-router'

// Eager (not lazy like every other route below): it's the first screen an
// unauthenticated visitor sees, so there is no logged-in app shell already
// on screen to cover a chunk-fetch delay; it must be ready immediately.
import { LoginView, resolveStartPageRoute } from '@/features/auth'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { MODULE_FLAGS, type ModuleFeature } from '@/core/host/moduleFeatures'
import { useLoadingBarStore } from '@/core/stores/loadingBarStore'

// A public id (UUID) as a route parameter pattern.
const UUID_PATTERN = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'

// `meta.phone` marks a page, or some of its tabs, as built for a phone. A page
// without it shows a notice on a phone instead, see `usePhoneLayout`.
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: LoginView,
      meta: { requiresAuth: false, layout: 'auth', titleKey: 'login.title' },
    },
    {
      // Every wall display's KIOSK_URL. The device signs in with its own
      // terminal token from the glados-terminal bridge, never a web session,
      // so the guard below lets these routes through untouched.
      path: '/infoscreen',
      name: 'Infoscreen',
      component: () => import('@/features/infoscreens/runtime/views/InfoscreenEntryView.vue'),
      meta: { requiresAuth: false, layout: 'kiosk', titleKey: 'infoscreenRuntime.title' },
    },
    {
      // Where a display waiting for approval shows its pairing code.
      path: '/infoscreen/register',
      name: 'InfoscreenRegister',
      component: () => import('@/features/infoscreens/runtime/views/InfoscreenRegisterView.vue'),
      meta: { requiresAuth: false, layout: 'kiosk', titleKey: 'infoscreenRuntime.registerTitle' },
    },
    {
      // The builder's preview: the same screen in the same bare layout, read
      // with the viewer's own web session and permissions.
      path: '/infoscreen/preview/:id(\\d+)',
      name: 'InfoscreenPreview',
      component: () => import('@/features/infoscreens/runtime/views/InfoscreenPreviewView.vue'),
      meta: { layout: 'kiosk', titleKey: 'infoscreenRuntime.previewTitle' },
    },
    {
      // Deliberately not a `redirect` config: vue-router resolves a
      // route-level redirect (static or function) before `beforeEach` runs,
      // which would see this path resolved to a fixed target before
      // `userStore.refresh()` below has even run, stranding a user whose
      // start page is e.g. "production" on the dashboard on every cold
      // load. The guard below handles the redirect instead, once
      // `isAuthenticated` reflects the freshly-loaded user. This route's own
      // component is never actually shown; the guard always redirects it
      // away. It exists only so `to.path === '/'` is a real, matched
      // navigation the guard gets to see.
      path: '/',
      name: 'Root',
      component: () => import('@/features/dashboard/views/DashboardView.vue'),
      meta: { phone: true, titleKey: 'main.sidebar.dashboard.label' },
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/features/dashboard/views/DashboardView.vue'),
      meta: { phone: true, titleKey: 'main.sidebar.dashboard.label' },
    },
    {
      path: '/todo',
      name: 'Todo',
      component: () => import('@/features/todo/views/TodoView.vue'),
      meta: { phone: true, requiresFeature: 'todos', titleKey: 'todo.title' },
    },
    {
      path: '/search',
      name: 'Search',
      component: () => import('@/features/search/views/SearchView.vue'),
      meta: { phone: true, titleKey: 'search.title' },
    },
    {
      // Where a scanned label or report page lands: the QR code holds this
      // link with the record's public id, and the page moves on to the
      // record. Signing in first keeps the link through the redirect query.
      path: `/resolve/:publicId(${UUID_PATTERN})`,
      name: 'Resolve',
      component: () => import('@/features/scan/views/ResolveView.vue'),
      meta: { phone: true, titleKey: 'scan.title' },
    },
    {
      path: '/calculations',
      name: 'Calculations',
      component: () => import('@/features/tools/views/CalculationsView.vue'),
      meta: { requiresFeature: 'calculations', titleKey: 'tools.calculations.title' },
    },
    {
      // Where a resolved public id (search, scan) lands: looks the
      // calculation up and moves on to its tool.
      path: '/calculations/:id(\\d+)',
      name: 'CalculationOpen',
      component: () => import('@/features/tools/views/CalculationOpenView.vue'),
      meta: { requiresFeature: 'calculations', titleKey: 'tools.calculations.title' },
    },
    {
      path: '/checklists',
      name: 'Checklists',
      component: () => import('@/features/checklists/views/ChecklistsView.vue'),
      meta: { requiresFeature: 'checklists', titleKey: 'checklists.title' },
    },
    {
      path: '/checklists/:id(\\d+)',
      name: 'ChecklistDetail',
      component: () => import('@/features/checklists/views/ChecklistDetailView.vue'),
      meta: { requiresFeature: 'checklists', titleKey: 'checklists.title' },
    },
    {
      path: '/checklists/:id(\\d+)/compare',
      name: 'ChecklistCompare',
      component: () => import('@/features/checklists/views/ChecklistCompareView.vue'),
      meta: { requiresFeature: 'checklists', titleKey: 'checklists.compare.title' },
    },
    // The reference tables' /tools paths redirect to /tables so old links still work.
    // Remove them once the web server's access log shows no request for these
    // paths over a full release cycle.
    {
      path: '/tools/general-tolerances',
      redirect: '/tables/general-tolerances',
      meta: { titleKey: 'main.sidebar.tables.label' },
    },
    {
      path: '/tools/threads',
      redirect: '/tables/threads',
      meta: { titleKey: 'main.sidebar.tables.label' },
    },
    {
      path: `/tools/:tab?/:calc(${UUID_PATTERN})?`,
      name: 'Tools',
      component: () => import('@/features/tools/views/ToolsView.vue'),
      meta: { titleKey: 'tools.title' },
    },
    {
      path: '/tables/:tab?',
      name: 'Tables',
      component: () => import('@/features/tools/views/TablesView.vue'),
      meta: { phone: true, titleKey: 'main.sidebar.tables.label' },
    },
    {
      // A meeting's page below its project or product, without the tab
      // strip. Its own chunk, and the only one that loads the card editor.
      path: '/workspace/projects/:id(\\d+)/meeting-notes/:meetingId(\\d+)',
      name: 'ProjectMeeting',
      component: () => import('@/features/meetings/views/MeetingDetailView.vue'),
      meta: { titleKey: 'meetings.title' },
    },
    {
      path: '/workspace/products/:id(\\d+)/meeting-notes/:meetingId(\\d+)',
      name: 'ProductMeeting',
      component: () => import('@/features/meetings/views/MeetingDetailView.vue'),
      meta: { titleKey: 'meetings.title' },
    },
    {
      // The review of a draft of meeting notes an AI agent prepared, which
      // only its creator sees.
      path: '/meeting-notes-drafts/:id(\\d+)',
      name: 'MeetingNotesDraft',
      component: () => import('@/features/meetings/views/MeetingNotesDraftView.vue'),
      meta: { titleKey: 'meetings.drafts.title' },
    },
    {
      // Where a resolved public id, a search hit or a notification lands:
      // looks up the meeting's owner and moves on to its page.
      path: '/meetings/:id(\\d+)',
      name: 'MeetingRedirect',
      component: () => import('@/features/meetings/views/MeetingRedirectView.vue'),
      meta: { titleKey: 'meetings.title' },
    },
    {
      path: '/workspace/projects/:id/:tab?',
      name: 'ProjectDetail',
      component: () => import('@/features/workspace/views/ProjectDetailView.vue'),
      meta: { phone: { param: 'tab', tabs: ['overview'] }, titleKey: 'pageTitles.projectDetail' },
    },
    {
      path: '/workspace/products/:id(\\d+)/sequences/:sequenceId(\\d+)/:view(initial|diagram|grafcet)?',
      name: 'SequenceDetail',
      component: () => import('@/features/sequences/views/SequenceDetailView.vue'),
      meta: { requiresFeature: 'sequences', titleKey: 'sequences.title' },
    },
    {
      path: '/sequences/:id(\\d+)',
      name: 'SequenceRedirect',
      component: () => import('@/features/sequences/views/SequenceRedirectView.vue'),
      meta: { requiresFeature: 'sequences', titleKey: 'sequences.title' },
    },
    {
      path: '/workspace/products/:id(\\d+)/:tab?',
      name: 'ProductDetail',
      component: () => import('@/features/workspace/views/ProductDetailView.vue'),
      meta: { titleKey: 'pageTitles.productDetail' },
    },
    {
      path: '/workspace/:tab?',
      name: 'Workspace',
      component: () => import('@/features/workspace/views/WorkspaceView.vue'),
      meta: {
        phone: { param: 'tab', tabs: ['projects'] },
        titleKey: 'main.sidebar.workspace.label',
      },
    },
    {
      path: '/resources/:tab?',
      name: 'Resources',
      component: () => import('@/features/resources/views/ResourcesView.vue'),
      meta: {
        phone: { param: 'tab', tabs: ['customers', 'suppliers'] },
        titleKey: 'main.sidebar.resources.label',
      },
    },
    {
      // `(\d+)`-constrained for the same reason as OrderDetail below: an
      // unconstrained `:id` would out-rank the `/catalogue/:tab?` catch-all
      // for every non-numeric tab segment those items' own list tabs use.
      path: '/catalogue/bought-items/:id(\\d+)',
      name: 'BoughtItemDetail',
      component: () => import('@/features/catalogue/views/BoughtItemDetailView.vue'),
      meta: { phone: true, titleKey: 'pageTitles.boughtItemDetail' },
    },
    {
      path: '/catalogue/made-items/:id(\\d+)',
      name: 'MadeItemDetail',
      component: () => import('@/features/catalogue/views/MadeItemDetailView.vue'),
      meta: { phone: true, titleKey: 'pageTitles.madeItemDetail' },
    },
    {
      path: '/catalogue/source-items/:id(\\d+)',
      name: 'SourceItemDetail',
      component: () => import('@/features/catalogue/views/SourceItemDetailView.vue'),
      meta: { phone: true, titleKey: 'pageTitles.sourceItemDetail' },
    },
    {
      path: '/catalogue/:tab?',
      name: 'Catalogue',
      component: () => import('@/features/catalogue-section/views/CatalogueView.vue'),
      meta: { phone: true, titleKey: 'main.sidebar.catalogue.label' },
    },
    {
      // The `(\d+)` constraint is load-bearing: `/procurement/orders/timeline`
      // is a real route served by the catch-all below (OrdersView reads it off
      // `params.tab`), and an unconstrained `:id` out-ranks that catch-all,
      // because vue-router scores the static `orders` segment above a param
      // one, so the timeline would silently render this page with id="timeline".
      path: '/procurement/orders/:id(\\d+)',
      name: 'OrderDetail',
      component: () => import('@/features/orders/views/OrderDetailView.vue'),
      meta: { phone: true, titleKey: 'pageTitles.orderDetail' },
    },
    {
      // Registered before the catch-all below for the same reason as the
      // order detail route.
      path: '/procurement/quotes/:id(\\d+)',
      name: 'QuoteRequestDetail',
      component: () => import('@/features/quote-requests/views/QuoteRequestDetailView.vue'),
      meta: { phone: true, titleKey: 'pageTitles.quoteRequestDetail' },
    },
    {
      path: '/procurement/:section?/:tab?',
      name: 'Procurement',
      component: () => import('@/features/procurement/views/ProcurementView.vue'),
      meta: { phone: true, titleKey: 'main.sidebar.procurement.label' },
    },
    {
      path: '/production/lots/timeline',
      name: 'ProductionLotsTimeline',
      component: () => import('@/features/production-section/views/ProductionView.vue'),
      meta: { requiresProductionPlanning: true, titleKey: 'production.lots.tabLabel' },
    },
    {
      path: '/production/lots',
      name: 'ProductionLots',
      component: () => import('@/features/production-section/views/ProductionView.vue'),
      // The same tab scope as the Production route below: the lots tab has a
      // route of its own, and its tab strip lists the other phone tabs.
      meta: {
        phone: { param: 'tab', tabs: ['lots', 'queue', 'qa'] },
        requiresProductionPlanning: true,
        titleKey: 'production.lots.tabLabel',
      },
    },
    {
      // `(\d+)`-constrained for the same reason as OrderDetail above:
      // /production/lots/timeline is a real static route and an unconstrained
      // :id would out-rank it.
      path: '/production/lots/:id(\\d+)',
      name: 'LotDetail',
      component: () => import('@/features/production/lots/views/LotDetailView.vue'),
      meta: { phone: true, requiresProductionPlanning: true, titleKey: 'pageTitles.lotDetail' },
    },
    {
      path: '/production/orders/:id(\\d+)',
      name: 'ProductionOrderDetail',
      component: () => import('@/features/production/orders/views/ProductionOrderDetailView.vue'),
      meta: { requiresProductionPlanning: true, titleKey: 'pageTitles.productionOrderDetail' },
    },
    {
      // `(\d+)`-constrained for the same reason as LotDetail/OrderDetail
      // above. `machines/` is its own module inside `production` (not
      // `production-machines`, the /resources management feature); this is
      // the shop-floor work view for one machine.
      path: '/production/machines/:id(\\d+)',
      name: 'MachineDetail',
      component: () => import('@/features/production/machines/views/MachineDetailView.vue'),
      meta: { requiresProductionPlanning: true, titleKey: 'main.sidebar.resources.machines' },
    },
    {
      // Declared before the /production/:tab? catch-all, which only matches
      // a single segment and would otherwise 404 on a task id.
      path: '/production/qa/:orderId',
      name: 'ProductionQaTask',
      component: () => import('@/features/production-qa/views/ProductionQaTaskView.vue'),
      meta: {
        phone: true,
        requiresProductionPlanning: true,
        titleKey: 'productionQa.detail.title',
      },
    },
    {
      path: '/production/:tab?',
      name: 'Production',
      component: () => import('@/features/production-section/views/ProductionView.vue'),
      meta: {
        phone: { param: 'tab', tabs: ['lots', 'queue', 'qa'] },
        requiresProductionPlanning: true,
        titleKey: 'main.sidebar.production.label',
      },
    },
    {
      // The section tree stays visible across the whole handbook, so the pages
      // are children of a layout that owns it rather than siblings.
      path: '/handbook',
      component: () => import('@/features/handbook/views/HandbookLayout.vue'),
      meta: { phone: true, titleKey: 'handbook.title' },
      children: [
        {
          path: '',
          name: 'Handbook',
          component: () => import('@/features/handbook/views/HandbookIndexView.vue'),
          meta: { titleKey: 'handbook.title' },
        },
        {
          path: ':section',
          name: 'HandbookSection',
          component: () => import('@/features/handbook/views/HandbookSectionView.vue'),
          meta: { titleKey: 'handbook.title' },
        },
        {
          path: ':section/:page',
          name: 'HandbookPage',
          component: () => import('@/features/handbook/views/HandbookPageView.vue'),
          meta: { titleKey: 'handbook.title' },
        },
      ],
    },
    {
      path: '/account/:tab?',
      name: 'Account',
      component: () => import('@/features/account/views/AccountView.vue'),
      meta: {
        phone: { param: 'tab', tabs: ['me', 'time-tracking'] },
        titleKey: 'main.sidebar.account.label',
      },
    },
    {
      path: '/settings/:tab?',
      name: 'Settings',
      component: () => import('@/features/admin-settings/views/AdminSettingsView.vue'),
      meta: { requiresAdmin: true, titleKey: 'main.sidebar.settings.label' },
    },
  ],
})

// The router's hold on the loading bar has to be idempotent: a guard that
// redirects makes vue-router restart the navigation (running `beforeEach`
// again) without ever firing `afterEach` for the aborted one, and a duplicated
// navigation fires `afterEach` without running the guards at all. Counting
// every hook call would leak a `start()` on the first redirect and leave the
// bar spinning for the rest of the session.
let routerHoldsLoadingBar = false

function startRouterLoading() {
  if (routerHoldsLoadingBar) return
  routerHoldsLoadingBar = true
  useLoadingBarStore().start()
}

function stopRouterLoading() {
  if (!routerHoldsLoadingBar) return
  routerHoldsLoadingBar = false
  useLoadingBarStore().stop()
}

/** A kiosk route that a device opens without a web session. */
function isDeviceRoute(to: RouteLocationNormalized): boolean {
  return to.meta.layout === 'kiosk' && to.meta.requiresAuth === false
}

router.beforeEach(async (to) => {
  startRouterLoading()

  // A wall display has no web session and never gets one: it signs in with
  // its own terminal token. So no session probe, no host bootstrap and none
  // of the sign-in, admin or feature gates below, any of which would send
  // an unattended display to the login page.
  if (isDeviceRoute(to)) return true

  const userStore = useCurrentUserStore()

  // The session lives in an httponly cookie invisible to this script, so
  // instead of checking for a client-side token, ask the backend once per
  // app load who (if anyone) the cookie belongs to; sessionChecked is
  // what makes this "once", see its own comment in currentUserStore.
  // Host-config bootstrap below is a separate concern and must never be
  // able to tear down a valid session over a transient failure.
  if (!userStore.sessionChecked && !userStore.user && !userStore.loading) {
    try {
      await userStore.refresh()
    } catch {
      // No live session, or a transient failure: isAuthenticated below
      // already reflects that (user stays null), nothing else needs
      // cleaning up client-side.
    }
  }

  const isAuthenticated = !!userStore.user

  // Bootstrap data (dropdown values, part-number policy, capability flags):
  // fire-and-forget on every authenticated navigation. hostStore.fetch()
  // no-ops once loaded, so this is also what retries a transient failure
  // without needing its own polling.
  if (isAuthenticated) {
    useHostStore()
      .fetch()
      .catch(() => {})
  }

  // The signed-in landing page: an explicit redirect query never reaches
  // here (that is LoginView's postLoginTarget, resolved before the app even
  // has a route to push to), so this only ever resolves the user's own
  // start-page preference (falling back to the dashboard); see
  // resolveStartPageRoute's shared guard against a disabled feature flag.
  if (isAuthenticated && to.path === '/') {
    return { path: resolveStartPageRoute() }
  }

  if (to.meta.requiresAuth !== false && !isAuthenticated) {
    return {
      name: 'Login',
      query: to.path !== '/' ? { redirect: to.fullPath } : undefined,
    }
  }

  if (to.name === 'Login' && isAuthenticated) {
    return { path: '/' }
  }

  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    return { path: '/dashboard' }
  }

  // Production Planning gate. `/resources/machines` is matched by path because
  // every resources tab shares one route, so it has no meta of its own.
  const needsProductionPlanning =
    to.meta.requiresProductionPlanning === true || to.path.startsWith('/resources/machines')
  if (isAuthenticated && needsProductionPlanning) {
    const hostStore = useHostStore()
    // The bootstrap above is fire-and-forget, so on a cold deep-link the flag
    // may not have arrived yet. Await it here rather than letting the default
    // decide, and swallow a failure, which leaves the permissive default and
    // lets the user through instead of stranding them on a network blip.
    await hostStore.fetch().catch(() => {})
    if (!hostStore.productionPlanningEnabled) {
      return { path: '/dashboard' }
    }
  }

  // Module gates, presentational like the one above. The devices lists are a
  // resources tab, matched by path for the same reason as the machines tab,
  // and a saved calculation opened in a tool keeps the tool but drops the
  // calculation when calculations are off.
  const feature: ModuleFeature | undefined =
    (to.meta.requiresFeature as ModuleFeature | undefined) ??
    (to.path.startsWith('/resources/product-devices') ? 'devices' : undefined) ??
    (to.name === 'Tools' && to.params.calc ? 'calculations' : undefined)
  if (isAuthenticated && feature) {
    const hostStore = useHostStore()
    await hostStore.fetch().catch(() => {})
    if (hostStore[MODULE_FLAGS[feature]] === false) {
      if (to.name === 'Tools') return { name: 'Tools', params: { tab: to.params.tab } }
      if (to.path.startsWith('/resources/')) return { path: '/resources' }
      return { path: '/dashboard' }
    }
  }

  return true
})

router.afterEach(() => {
  stopRouterLoading()
})

router.onError(() => {
  stopRouterLoading()
})

export default router
