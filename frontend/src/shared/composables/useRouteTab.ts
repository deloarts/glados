import { ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * The tab of a hub view kept in step with one route param: the tab starts
 * from the param, a tab change replaces the URL with `<basePath>/<tab>`, and
 * a route change (back, forward, a sidebar link) moves the tab.
 *
 * A param that names no valid tab, or one `isAllowed` rejects, resolves to
 * the default tab. `isAllowed` is checked only when the param is resolved,
 * so a view whose gate can change later watches the gate itself.
 *
 * A detail page passes `basePath` as a getter, since it holds the record's
 * id, and sets `defaultOnBase` so its default tab lives on the bare record
 * URL instead of `<basePath>/<defaultTab>`.
 */
export function useRouteTab(options: {
  param: string
  validTabs: ReadonlySet<string>
  defaultTab: string
  basePath: string | (() => string)
  isAllowed?: (tab: string) => boolean
  defaultOnBase?: boolean
}): Ref<string> {
  const route = useRoute()
  const router = useRouter()

  function resolveTab(param: unknown): string {
    if (typeof param !== 'string' || !options.validTabs.has(param)) return options.defaultTab
    if (options.isAllowed && !options.isAllowed(param)) return options.defaultTab
    return param
  }

  const activeTab = ref(resolveTab(route.params[options.param]))
  // Leaving the view changes the route before the view unmounts; neither
  // watcher may act on a route that is no longer this view's.
  const ownRoute = route.name
  const onOwnRoute = () => route.name === ownRoute

  function pathFor(tab: string): string {
    const base = typeof options.basePath === 'function' ? options.basePath() : options.basePath
    return options.defaultOnBase && tab === options.defaultTab ? base : `${base}/${tab}`
  }

  watch(activeTab, (tab) => {
    if (onOwnRoute()) void router.replace(pathFor(tab))
  })

  watch(
    () => route.params[options.param],
    (param) => {
      if (!onOwnRoute()) return
      const tab = resolveTab(param)
      if (tab !== activeTab.value) activeTab.value = tab
    },
  )

  return activeTab
}
