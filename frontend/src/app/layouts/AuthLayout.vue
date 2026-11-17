<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''
const LOGIN_VIDEO_URL = `${API_ROOT}/api/v1/public/branding/login-video`

const videoLoaded = ref(false)
const videoAvailable = ref(true)

function onVideoLoaded() {
  videoLoaded.value = true
}

function onVideoError() {
  videoAvailable.value = false
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
let animId = 0
let removeResize: (() => void) | null = null

interface WaveDef {
  yFactor: number
  amp: number
  period: number
  speed: number
  phase: number
  c0: string
  c1: string
  alpha: number
}

const WAVES: WaveDef[] = [
  {
    yFactor: 0.52,
    amp: 100,
    period: 1800,
    speed: 0.00045,
    phase: 0.0,
    c0: '#0070cc',
    c1: '#5010e0',
    alpha: 0.5,
  },
  {
    yFactor: 0.6,
    amp: 85,
    period: 1400,
    speed: 0.00065,
    phase: 1.3,
    c0: '#5010e0',
    c1: '#00b8a0',
    alpha: 0.42,
  },
  {
    yFactor: 0.68,
    amp: 70,
    period: 2000,
    speed: 0.00035,
    phase: 2.7,
    c0: '#00b8a0',
    c1: '#0070cc',
    alpha: 0.34,
  },
  {
    yFactor: 0.76,
    amp: 55,
    period: 1600,
    speed: 0.00055,
    phase: 0.6,
    c0: '#2840ff',
    c1: '#9020e0',
    alpha: 0.26,
  },
]

function toHex8(hex: string, alpha: number) {
  const a = Math.min(255, Math.max(0, Math.round(alpha * 255)))
  return hex + a.toString(16).padStart(2, '0')
}

function initWaves(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d')!

  function resize() {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  let startTime: number | null = null

  function draw(ts: number) {
    if (startTime === null) startTime = ts
    const t = ts - startTime

    const W = canvas.width
    const H = canvas.height

    ctx.clearRect(0, 0, W, H)
    ctx.fillStyle = '#07090f'
    ctx.fillRect(0, 0, W, H)

    for (const wave of WAVES) {
      const baseY = H * wave.yFactor

      const grad = ctx.createLinearGradient(0, 0, W, 0)
      grad.addColorStop(0, toHex8(wave.c0, wave.alpha * 0.6))
      grad.addColorStop(0.5, toHex8(wave.c1, wave.alpha))
      grad.addColorStop(1, toHex8(wave.c0, wave.alpha * 0.6))

      ctx.beginPath()
      ctx.moveTo(0, H)

      for (let x = 0; x <= W; x += 4) {
        const angle = (x / wave.period) * Math.PI * 2 + t * wave.speed + wave.phase
        const y = baseY + Math.sin(angle) * wave.amp
        ctx.lineTo(x, y)
      }

      ctx.lineTo(W, H)
      ctx.closePath()
      ctx.fillStyle = grad
      ctx.fill()
    }

    animId = requestAnimationFrame(draw)
  }

  animId = requestAnimationFrame(draw)
  return () => window.removeEventListener('resize', resize)
}

onMounted(() => {
  if (canvasRef.value) {
    removeResize = initWaves(canvasRef.value)
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animId)
  removeResize?.()
})
</script>

<template>
  <div class="auth-layout">
    <canvas v-if="!videoAvailable" ref="canvasRef" class="wave-canvas" />
    <video
      v-if="videoAvailable"
      class="bg-video"
      :class="{ 'is-loaded': videoLoaded }"
      :src="LOGIN_VIDEO_URL"
      autoplay
      muted
      loop
      playsinline
      @loadeddata="onVideoLoaded"
      @error="onVideoError"
    />
    <div class="video-overlay" />
    <RouterView />
  </div>
</template>

<style scoped lang="scss">
// The sign-in screens are dark in every theme, so they carry their own
// palette. The views and steps rendered inside the layout inherit it.
.auth-layout {
  --auth-backdrop: #07090f;
  --auth-veil: rgb(7 9 15 / 45%);
  --auth-card: rgb(6 8 14 / 88%);
  --auth-ink: #fff;
  --auth-text-strong: rgb(255 255 255 / 90%);
  --auth-text: rgb(255 255 255 / 65%);
  --auth-text-muted: rgb(255 255 255 / 48%);
  --auth-text-faint: rgb(255 255 255 / 35%);
  --auth-field: rgb(255 255 255 / 4%);
  --auth-field-hover: rgb(255 255 255 / 6%);
  --auth-line: rgb(255 255 255 / 8%);
  --auth-sheen: rgb(255 255 255 / 13%);
  --auth-accent: #007acc;
  --auth-accent-hover: #0590e8;
  --auth-accent-active: #006aad;
  --auth-accent-text: rgb(0 160 255 / 85%);
  --auth-accent-fill: rgb(0 122 204 / 18%);
  --auth-focus-fill: rgb(0 122 204 / 7%);
  --auth-hover-border: rgb(0 140 255 / 30%);
  --auth-focus-border: rgb(0 160 255 / 70%);
  --auth-focus-glow: 0 0 0 3px rgb(0 122 204 / 12%), 0 0 18px rgb(0 122 204 / 16%);
  --auth-avatar-ring: 0 0 0 2px rgb(0 122 204 / 35%);
  --auth-card-shadow:
    0 0 0 1px rgb(0 122 204 / 12%), inset 0 1px 0 rgb(255 255 255 / 6%), 0 12px 80px rgb(0 0 0 / 80%),
    0 0 100px rgb(0 122 204 / 8%);
  --auth-submit-shadow: 0 2px 18px rgb(0 122 204 / 30%);
  --auth-submit-shadow-hover: 0 4px 28px rgb(0 140 255 / 45%);
  --auth-submit-shadow-active: 0 1px 10px rgb(0 122 204 / 25%);

  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--auth-backdrop);
  overflow: hidden;
}

.wave-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.bg-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 2.6s ease;

  &.is-loaded {
    opacity: 1;
  }
}

.video-overlay {
  position: absolute;
  inset: 0;
  background: var(--auth-veil);
  pointer-events: none;
}
</style>
