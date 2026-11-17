import { inject, provide, ref, type InjectionKey, type Ref } from 'vue'

/** One heading of the doc currently being read, for the "on this page" rail. */
export interface HandbookHeading {
  id: string
  text: string
  level: number
}

const handbookOutlineKey: InjectionKey<Ref<HandbookHeading[]>> = Symbol('handbookOutline')

/**
 * The outline is produced by the component that renders the markdown and read
 * by the layout's right-hand column, which sits above it, on the other side
 * of a <RouterView>. Passing it through provide/inject keeps the rendering
 * component from having to know a layout exists at all: in the drawer, where
 * nothing provides a sink, collection is simply skipped.
 */
export function provideHandbookOutline(): Ref<HandbookHeading[]> {
  const outline = ref<HandbookHeading[]>([])
  provide(handbookOutlineKey, outline)
  return outline
}

/** The sink to write into, or null when nothing is collecting headings. */
export function useHandbookOutlineSink(): Ref<HandbookHeading[]> | null {
  return inject(handbookOutlineKey, null)
}
