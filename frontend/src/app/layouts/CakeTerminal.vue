<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'

import { CAKE_PHRASE, CAKE_RESET_LINE, useCakeProtocol } from '@/core/composables/useCakeProtocol'
import { useTypewriter } from '@/core/composables/useTypewriter'

/** Matches the line-height below; used to work out how many rows fit. */
const ROW_HEIGHT_PX = 30

// Capacity is settled before the writer exists so `keepRows` can trim as it
// goes: the phrase types for as long as the stage lasts, and an untrimmed array
// would grow the whole time. Two rows short of the screen leaves the reset line
// somewhere to land.
const rowCapacity =
  typeof window === 'undefined'
    ? 20
    : Math.max(4, Math.floor(window.innerHeight / ROW_HEIGHT_PX) - 4)

const { terminalStage } = useCakeProtocol()

// No maxRows: it types until the protocol moves the stage on.
const { rows, current, start, stop } = useTypewriter({
  phrase: CAKE_PHRASE,
  keepRows: rowCapacity,
})

const resetWriter = useTypewriter({
  phrase: CAKE_RESET_LINE,
  maxRows: 1,
  charDelayMs: 55,
})

// While it types the partial line lives in `current`; once complete it moves to
// `rows[0]` and `current` clears. Either way this is the line to show.
const resetText = computed(() => resetWriter.rows.value[0] ?? resetWriter.current.value)

watch(terminalStage, (stage) => {
  if (stage === 'hold') stop()
  if (stage === 'resetting') resetWriter.start()
})

onMounted(start)
onUnmounted(() => {
  stop()
  resetWriter.stop()
})
</script>

<template>
  <!-- data-cake-exempt: the sweep must not rewrite the terminal's own text,
       which is already the phrase. -->
  <div class="cake-terminal" data-cake-exempt aria-hidden="true">
    <div class="cake-terminal-rows">
      <p v-for="(row, index) in rows" :key="index" class="cake-terminal-row">{{ row }}</p>
      <p v-if="current" class="cake-terminal-row">
        {{ current }}<span v-if="terminalStage === 'typing'" class="cake-terminal-cursor" />
      </p>
      <p v-if="terminalStage === 'resetting'" class="cake-terminal-row is-reset">
        <span class="cake-terminal-spacer" />{{ resetText }}<span class="cake-terminal-cursor" />
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
// The easter egg terminal draws its own fixed palette, whatever the theme.
/* stylelint-disable scale-unlimited/declaration-strict-value, declaration-property-value-disallowed-list */
.cake-terminal {
  position: fixed;
  inset: 0;
  // Above OpenVue's overlay layer (~1100) but below the confetti canvas.
  z-index: 9999;
  background: #000;
  color: #fff;
  font-family: 'Doto', 'Courier New', monospace;
  font-weight: 600;
  font-size: var(--font-size-lg);
  line-height: 30px;
  letter-spacing: 0.08em;
  padding: var(--space-5) var(--space-6);
  overflow: hidden;
  cursor: default;
  user-select: none;
  animation: cake-terminal-in 220ms ease-out;
}

// Scanlines only, in black rather than red: a red wash or vignette here
// would tint the whole screen maroon instead of leaving it black. The red in
// this view belongs to the text and the cursor, not the background.
.cake-terminal::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.5) 0,
    rgba(0, 0, 0, 0.5) 1px,
    transparent 1px,
    transparent 3px
  );
}

.cake-terminal-rows {
  display: flex;
  flex-direction: column;
}

.cake-terminal-row {
  margin: 0;
  white-space: nowrap;
  text-shadow:
    0 0 4px rgba(255, 60, 60, 0.9),
    0 0 14px rgba(255, 0, 0, 0.65);
}

// A blank line between the wall of phrases and the reset, so the last line
// reads as a separate statement rather than one more repetition.
.cake-terminal-spacer {
  display: block;
  height: 30px;
}

.cake-terminal-row.is-reset {
  color: #ff4d4d;
  text-shadow:
    0 0 6px rgba(255, 40, 40, 0.95),
    0 0 18px rgba(255, 0, 0, 0.7);
}

.cake-terminal-cursor {
  display: inline-block;
  width: 0.6em;
  height: 1em;
  margin-left: 0.1em;
  background: #ff2020;
  box-shadow: 0 0 10px rgba(255, 0, 0, 0.9);
  vertical-align: text-bottom;
  animation: cake-cursor 900ms steps(2, end) infinite;
}

@keyframes cake-terminal-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes cake-cursor {
  0%,
  50% {
    opacity: 1;
  }
  50.01%,
  100% {
    opacity: 0;
  }
}

// No blinking cursor, no fade-in.
@media (prefers-reduced-motion: reduce) {
  .cake-terminal {
    animation: none;
  }

  .cake-terminal-cursor {
    animation: none;
  }
}
</style>
