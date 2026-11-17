import { reactive } from 'vue'
import type { SuggestionKeyDownProps, SuggestionOptions, SuggestionProps } from '@tiptap/suggestion'

import type { UserSummary } from '@/core/types/userResponse'

export interface MentionItem {
  id: string
  label: string
}

export interface MentionPopupState {
  open: boolean
  items: MentionItem[]
  index: number
  left: number
  top: number
}

const MAX_ITEMS = 8

/**
 * The `@` suggestion of the card editor: Glados users whose name contains
 * what follows the `@`, in a popup the editor component renders from
 * `state`. The arrow keys move through it, Enter or Tab picks and Escape
 * closes it.
 */
export function useMentionSuggestion(users: () => UserSummary[]) {
  const state = reactive<MentionPopupState>({ open: false, items: [], index: 0, left: 0, top: 0 })
  let command: ((item: MentionItem) => void) | null = null

  function place(props: SuggestionProps<MentionItem>): void {
    const rect = props.clientRect?.()
    if (!rect) return
    state.left = rect.left
    state.top = rect.bottom + 4
  }

  function update(props: SuggestionProps<MentionItem>): void {
    state.items = props.items
    state.index = Math.min(state.index, Math.max(0, props.items.length - 1))
    command = props.command
    place(props)
  }

  function pick(index: number): void {
    const item = state.items[index]
    if (item && command) command(item)
  }

  function onKeyDown({ event }: SuggestionKeyDownProps): boolean {
    if (!state.open || state.items.length === 0) return false
    if (event.key === 'ArrowDown') {
      state.index = (state.index + 1) % state.items.length
      return true
    }
    if (event.key === 'ArrowUp') {
      state.index = (state.index - 1 + state.items.length) % state.items.length
      return true
    }
    if (event.key === 'Enter' || event.key === 'Tab') {
      pick(state.index)
      return true
    }
    if (event.key === 'Escape') {
      state.open = false
      return true
    }
    return false
  }

  const suggestion: Omit<SuggestionOptions<MentionItem>, 'editor'> = {
    char: '@',
    items: ({ query }) => {
      const lower = query.toLowerCase()
      return users()
        .filter((user) => user.full_name.toLowerCase().includes(lower))
        .slice(0, MAX_ITEMS)
        .map((user) => ({ id: String(user.id), label: user.full_name }))
    },
    render: () => ({
      onStart: (props) => {
        state.open = true
        state.index = 0
        update(props)
      },
      onUpdate: update,
      onKeyDown,
      onExit: () => {
        state.open = false
        command = null
      },
    }),
  }

  return { state, suggestion, pick }
}
