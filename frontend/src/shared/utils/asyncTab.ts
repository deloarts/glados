import { defineAsyncComponent } from 'vue'
import type { Component } from 'vue'

import AsyncChunkLoading from '@/shared/components/layout/AsyncChunkLoading.vue'

/**
 * Wraps a dynamic `import()` for use as a hub view's tab panel component.
 *
 * Shows `AsyncChunkLoading` while the chunk is in flight (after a 200ms
 * delay, to avoid a flash for chunks that are already cached) instead of
 * eagerly bundling every tab into the hub's initial chunk.
 */
export function asyncTab(loader: () => Promise<Component>): Component {
  return defineAsyncComponent({ loader, loadingComponent: AsyncChunkLoading, delay: 200 })
}
