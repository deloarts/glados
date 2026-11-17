import type { Component } from 'vue'

/**
 * Wraps a component as the module a `vi.mock` factory returns for a tab that
 * `asyncTab()` loads lazily.
 *
 * `asyncTab()` loads its target through a real dynamic `import()`, and Vue's
 * `defineAsyncComponent` only unwraps a resolved module's `default` when the
 * module reports itself as ESM (`__esModule` or a `Symbol.toStringTag` of
 * `'Module'`). A compiled `.vue` file always does, but a plain `{ default }`
 * object from a mock factory does not, so without the flag Vue takes the
 * wrapper itself for the component and @vue/test-utils fails with an opaque
 * "No __isTeleport export is defined" error.
 *
 * Mock factories are hoisted above the spec's imports but run only when the
 * tab is first loaded, after those imports have been evaluated, so a factory
 * may call this helper.
 */
export function asyncTabModule(component: Component) {
  return { __esModule: true, default: component }
}

/**
 * A lazily loaded tab replaced by a named stub that renders `template`, so a
 * spec can check which tab is shown without mounting the real view.
 */
export function asyncTabStub(name: string, template = `<div>${name}-stub</div>`) {
  return asyncTabModule({ name, template })
}
