<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useTerminalMessage } from '../composables/useTerminalMessage'
import type { TerminalMessage } from '../types/infoscreenFeed'
import { renderMessageMarkdown } from '../utils/messageMarkdown'

// Puts a message to terminals around what a display shows: as a banner
// above it or over the whole display, as the sender chose. The text is
// Markdown through the same renderer as the message widget, and the message
// goes away at its end by the device clock. Showing a message never wakes
// a display that is switched off; it is drawn whether or not anyone sees it.
const props = withDefaults(defineProps<{ message?: TerminalMessage | null }>(), { message: null })

const { t } = useI18n()
const visible = useTerminalMessage(() => props.message)

// Sanitised by the renderer, see messageMarkdown.
const html = computed(() => (visible.value ? renderMessageMarkdown(visible.value.text) : ''))

const SEVERITY_ICONS: Record<TerminalMessage['severity'], string> = {
  info: 'mdi-information-outline',
  warning: 'mdi-alert-outline',
  danger: 'mdi-alert-octagon-outline',
}
const icon = computed(() => (visible.value ? SEVERITY_ICONS[visible.value.severity] : ''))
</script>

<template>
  <div class="terminal-message-frame">
    <div
      v-if="visible?.style === 'banner'"
      class="terminal-message terminal-message--banner"
      :class="`terminal-message--${visible.severity}`"
      role="status"
      :aria-label="t('infoscreenRuntime.terminalMessage.label')"
      :data-severity="visible.severity"
      data-testid="terminal-message-banner"
    >
      <i class="mdi terminal-message-icon" :class="icon" aria-hidden="true" />
      <div class="terminal-message-text" v-html="html" />
    </div>

    <div class="terminal-message-content">
      <slot />
    </div>

    <div
      v-if="visible?.style === 'fullscreen'"
      class="terminal-message terminal-message--fullscreen"
      :class="`terminal-message--${visible.severity}`"
      role="status"
      :aria-label="t('infoscreenRuntime.terminalMessage.label')"
      :data-severity="visible.severity"
      data-testid="terminal-message-fullscreen"
    >
      <i class="mdi terminal-message-icon" :class="icon" aria-hidden="true" />
      <div class="terminal-message-text" v-html="html" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.terminal-message-frame {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.terminal-message-content {
  flex: 1 1 auto;
  min-height: 0;
}

.terminal-message {
  --terminal-message-accent: var(--p-blue-600);
  display: flex;
  // White text on the severity colour in every theme, like the screen's own banner.
  background: var(--terminal-message-accent);
  color: var(--on-accent);
}

.terminal-message--warning {
  --terminal-message-accent: var(--p-orange-600);
}

.terminal-message--danger {
  --terminal-message-accent: var(--p-red-600);
}

.terminal-message--banner {
  flex: 0 0 auto;
  align-items: flex-start;
  gap: 0.6em;
  max-height: 35vh;
  overflow: hidden;
  padding: 0.5em 0.9em;
  font-size: clamp(1.1rem, 3.2vmin, 3.5rem);
  font-weight: 700;
  line-height: 1.25;

  .terminal-message-icon {
    line-height: 1.25;
  }
}

// Over everything a display shows except the identify overlay.
.terminal-message--fullscreen {
  position: absolute;
  inset: 0;
  z-index: 5;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4vmin;
  padding: 8vmin;
  font-size: clamp(1.8rem, 6vmin, 7rem);
  font-weight: 700;
  line-height: 1.25;
  text-align: center;

  .terminal-message-icon {
    font-size: clamp(4rem, 16vmin, 16rem);
    line-height: 1;
  }

  .terminal-message-text {
    flex: 0 1 auto;
    max-width: 90%;
    max-height: 70%;
    overflow: hidden;
  }
}

.terminal-message-text {
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;

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
    margin: 0 0 0.4em;
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
    text-align: left;
  }

  :deep(blockquote) {
    padding-left: 0.6em;
    border-left: 0.15em solid currentColor;
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
