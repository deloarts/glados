import { type Ref, ref, watch } from 'vue'

// Animates a number from its previous displayed value to a new target
// whenever `target` changes, via requestAnimationFrame, no library needed
// for a simple ease-out count-up on the dashboard's stat tiles.
export function useCountUp(target: Ref<number>, durationMs = 600): Ref<number> {
  const displayed = ref(target.value)
  let frame: number | null = null

  watch(target, (next, previous) => {
    if (frame !== null) cancelAnimationFrame(frame)
    const start = previous ?? 0
    const delta = next - start
    const startTime = performance.now()

    function step(now: number): void {
      const elapsed = now - startTime
      const progress = Math.min(1, elapsed / durationMs)
      const eased = 1 - (1 - progress) * (1 - progress)
      displayed.value = Math.round(start + delta * eased)
      if (progress < 1) {
        frame = requestAnimationFrame(step)
      } else {
        frame = null
      }
    }

    frame = requestAnimationFrame(step)
  })

  return displayed
}
