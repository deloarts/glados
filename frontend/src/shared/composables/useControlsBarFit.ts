import { computed, nextTick, readonly, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { unrefElement, useResizeObserver } from '@vueuse/core'
import type { MaybeComputedElementRef } from '@vueuse/core'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

/**
 * Keeps the actions of a controls bar on one row by collapsing groups of
 * them into one menu button each. The page names the groups it can collapse,
 * in the order they collapse, and shows a group as one menu button while its
 * flag in `collapsed` is set. A group collapses while the
 * buttons of the bar's start group wrap onto a second row, and spreads out
 * again once the width it needed when it was last shown spread out is free.
 *
 * The bar's own width counts rather than the screen's, so an open side menu
 * and the longer labels of one language are taken into account. A phone
 * shows every group collapsed, since its controls bar puts all actions into
 * one menu anyway. Before the bar has a width, as in a spec or a hidden tab,
 * nothing collapses.
 */
export function useControlsBarFit<Group extends string>(
  bar: MaybeComputedElementRef,
  groups: readonly Group[],
) {
  const groupCount = groups.length
  const { isPhone } = usePhoneLayout()
  const { locale } = useI18n()

  const collapsedGroups = ref(0)
  // The width the start group's buttons took at each number of collapsed
  // groups, as last measured. Spreading a group out again needs this width
  // free, which keeps the bar from swinging between two states.
  let neededWidth: number[] = []
  let fitting = false
  let fitAgain = false

  function startGroup(): HTMLElement | null {
    if (isPhone.value) return null
    return unrefElement(bar)?.querySelector<HTMLElement>('.controls-bar-start') ?? null
  }

  async function fit(): Promise<void> {
    if (fitting) {
      fitAgain = true
      return
    }
    fitting = true
    try {
      do {
        fitAgain = false
        await fitOnce()
      } while (fitAgain)
    } finally {
      fitting = false
    }
  }

  // Collapses or spreads out one group per pass and lets the page render it
  // before it measures again, so a full swing takes groupCount passes.
  async function fitOnce(): Promise<void> {
    for (let pass = 0; pass <= groupCount; pass++) {
      const group = startGroup()
      if (!group) return
      const available = innerWidth(group)
      if (available <= 0) return
      const level = collapsedGroups.value
      const items = visibleItems(group)
      neededWidth[level] = contentWidth(group, items)
      const wider = neededWidth[level - 1]
      if (wraps(items) && level < groupCount) {
        collapsedGroups.value = level + 1
      } else if (level > 0 && wider !== undefined && wider <= available) {
        collapsedGroups.value = level - 1
      } else {
        return
      }
      await nextTick()
    }
  }

  // Watching the start group covers both causes of a change: its width
  // follows the bar, and its height grows when its buttons wrap.
  useResizeObserver(startGroup, () => {
    void fit()
  })

  watch(
    isPhone,
    (phone) => {
      collapsedGroups.value = phone ? groupCount : 0
    },
    { immediate: true },
  )

  // Another language changes every label width, so the measured widths no
  // longer hold. The bar starts spread out again and collapses what it must.
  watch(locale, async () => {
    neededWidth = []
    if (isPhone.value) return
    collapsedGroups.value = 0
    await nextTick()
    await fit()
  })

  const collapsed = computed(
    () =>
      Object.fromEntries(
        groups.map((group, index) => [group, index < collapsedGroups.value]),
      ) as Record<Group, boolean>,
  )

  return { collapsed, collapsedGroups: readonly(collapsedGroups) }
}

function visibleItems(group: HTMLElement): HTMLElement[] {
  return Array.from(group.children).filter(
    (item): item is HTMLElement => item instanceof HTMLElement && item.getClientRects().length > 0,
  )
}

function innerWidth(element: HTMLElement): number {
  const style = getComputedStyle(element)
  return (
    element.getBoundingClientRect().width -
    (parseFloat(style.paddingLeft) || 0) -
    (parseFloat(style.paddingRight) || 0)
  )
}

/** The width the items take side by side on one row, gaps and margins included. */
function contentWidth(group: HTMLElement, items: HTMLElement[]): number {
  const gap = parseFloat(getComputedStyle(group).columnGap) || 0
  let width = gap * Math.max(items.length - 1, 0)
  for (const item of items) {
    const style = getComputedStyle(item)
    width +=
      item.getBoundingClientRect().width +
      (parseFloat(style.marginLeft) || 0) +
      (parseFloat(style.marginRight) || 0)
  }
  return width
}

/**
 * Whether an item starts below the first one. The items of a row are
 * centred and differ in height, so only an item that starts below the first
 * item's bottom edge sits on a row of its own.
 */
function wraps(items: HTMLElement[]): boolean {
  const first = items[0]
  if (!first) return false
  const firstBottom = first.getBoundingClientRect().bottom
  return items.slice(1).some((item) => item.getBoundingClientRect().top >= firstBottom - 1)
}
