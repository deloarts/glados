<script setup lang="ts">
import { computed } from 'vue'

import type { WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import { renderMessageMarkdown } from '../../utils/messageMarkdown'
import WidgetFrame from './WidgetFrame.vue'

// A message an admin wrote for this screen, in Markdown. The feed repeats
// the text, and the configured one stands in until the feed has it. The
// severity `none` shows the text plainly on the widget background.
const props = defineProps<{
  config: WidgetConfigOf<'message'>
  data: WidgetDataOf<'message'> | null
}>()

const text = computed(() => props.data?.text ?? props.config.text)
const severity = computed(() => props.data?.severity ?? props.config.severity)
// Sanitised by the renderer, see messageMarkdown.
const html = computed(() => renderMessageMarkdown(text.value))

const TEXT_ALIGNS = ['left', 'center', 'right'] as const
const VERTICAL_ALIGNS = ['top', 'middle', 'bottom'] as const

// The backend fills in the defaults for configs stored before the
// alignment existed; anything else it might send one day is the default
// too, text on the left and in the middle.
function known<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  return allowed.find((candidate) => candidate === value) ?? fallback
}

const textAlign = computed(() =>
  known(props.data?.text_align ?? props.config.text_align, TEXT_ALIGNS, 'left'),
)
const verticalAlign = computed(() =>
  known(props.data?.vertical_align ?? props.config.vertical_align, VERTICAL_ALIGNS, 'middle'),
)
</script>

<template>
  <WidgetFrame :title="config.title">
    <div
      class="message-widget"
      :class="[
        `message-widget--${severity}`,
        `message-widget--text-${textAlign}`,
        `message-widget--vertical-${verticalAlign}`,
      ]"
      data-testid="message-widget"
    >
      <div class="message-widget-text" v-html="html" />
    </div>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.message-widget {
  --message-accent: var(--p-blue-500);
  height: 100%;
  display: flex;
  align-items: center;
  padding: 0.5em 0.8em;
  border-left: 0.35em solid var(--message-accent);
  background: color-mix(in srgb, var(--message-accent) 12%, transparent);
  border-radius: var(--p-border-radius-sm);
}

.message-widget--success {
  --message-accent: var(--p-green-500);
}

.message-widget--warning {
  --message-accent: var(--p-orange-500);
}

.message-widget--danger {
  --message-accent: var(--p-red-500);
}

.message-widget--vertical-top {
  align-items: flex-start;
}

.message-widget--vertical-bottom {
  align-items: flex-end;
}

.message-widget--text-center .message-widget-text {
  text-align: center;
}

.message-widget--text-right .message-widget-text {
  text-align: right;
}

.message-widget--none {
  border-left: 0;
  background: transparent;
}

.message-widget-text {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 1.6em;
  font-weight: 600;
  line-height: 1.3;

  :deep(> :first-child) {
    margin-top: 0;
  }

  :deep(> :last-child) {
    margin-bottom: 0;
  }

  :deep(p),
  :deep(ul),
  :deep(ol),
  :deep(blockquote),
  :deep(pre) {
    margin: 0 0 0.5em;
  }

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4),
  :deep(h5),
  :deep(h6) {
    margin: 0 0 0.3em;
    font-family: var(--font-head);
    line-height: 1.15;
  }

  :deep(ul),
  :deep(ol) {
    padding-left: 1.2em;
  }

  :deep(blockquote) {
    padding-left: 0.6em;
    border-left: 0.15em solid var(--p-content-border-color);
    color: var(--p-text-muted-color);
  }

  :deep(code) {
    font-family: 'DejaVu Sans Mono', ui-monospace, monospace;
    font-size: 0.9em;
  }

  :deep(pre) {
    white-space: pre-wrap;
  }
}
</style>
