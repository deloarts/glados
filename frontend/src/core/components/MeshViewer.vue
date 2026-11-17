<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { WebGLRenderer, PerspectiveCamera, Scene, Object3D, Mesh } from 'three'
import type { OrbitControls as OrbitControlsType } from 'three/examples/jsm/controls/OrbitControls.js'

import { useErrorToast } from '@/core/composables/useErrorToast'

const props = defineProps<{
  blob: Blob
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const initLoading = ref(true)

let renderer: WebGLRenderer | null = null
let controls: OrbitControlsType | null = null
let animationId: number | null = null
let resizeObserver: ResizeObserver | null = null

onMounted(() => render())
onUnmounted(() => dispose())

watch(
  () => props.blob,
  () => {
    dispose()
    initLoading.value = true
    render()
  },
)

// A file that does not parse as a mesh stops the spinner and says so,
// instead of spinning forever.
function render(): void {
  init().catch((e: unknown) => {
    initLoading.value = false
    toastOnError(t('common.filePreview.error'))(e)
  })
}

// A 3MF is a ZIP container, so it always starts with the local-file-header
// magic "PK\x03\x04"; an STL (binary or ASCII) never does. Sniffing the bytes
// rather than trusting the filename or the server's content type means a
// mislabelled upload still renders instead of failing inside the wrong parser.
function isThreeMf(buffer: ArrayBuffer): boolean {
  if (buffer.byteLength < 4) return false
  const head = new Uint8Array(buffer, 0, 4)
  return head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04
}

async function init(): Promise<void> {
  if (!canvasRef.value) return
  const canvas = canvasRef.value

  const arrayBuffer = await props.blob.arrayBuffer()
  const threeMf = isThreeMf(arrayBuffer)

  const [THREE, { OrbitControls }] = await Promise.all([
    import('three'),
    import('three/examples/jsm/controls/OrbitControls.js'),
  ])

  const width = canvas.clientWidth || 800
  const height = canvas.clientHeight || 800

  // Scene
  const scene: Scene = new THREE.Scene()
  scene.background = null

  // Camera: Z is up, the CAD convention both STL and 3MF are exported with
  const camera: PerspectiveCamera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000)
  camera.up.set(0, 0, 1)

  // Renderer
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
  renderer.setSize(width, height, false)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

  // Lights
  const ambient = new THREE.AmbientLight(0xffffff, 1.0)
  scene.add(ambient)
  // Positions are Z-up to match the camera: key from above-front-right.
  const key = new THREE.DirectionalLight(0xffffff, 2.0)
  key.position.set(3, -3, 5)
  scene.add(key)
  const fill = new THREE.DirectionalLight(0xcce8ff, 0.6)
  fill.position.set(-4, -2, 1)
  scene.add(fill)
  const rim = new THREE.DirectionalLight(0xffffff, 0.5)
  rim.position.set(0, 4, -3)
  scene.add(rim)

  // Load the mesh. STL is a bare triangle soup that we skin ourselves; 3MF is
  // a scene graph that carries its own materials and colours, so it is used
  // as loaded. Both end up as one Object3D the framing code below treats alike.
  let model: Object3D
  if (threeMf) {
    const { ThreeMFLoader } = await import('three/examples/jsm/loaders/3MFLoader.js')
    model = new ThreeMFLoader().parse(arrayBuffer)
    // 3MFLoader writes position (and, for colour groups, colour) but never
    // normals, since the format stores none and the loader does not derive them.
    // A lit material with no normals shades every face by the same undefined
    // value, which flattens the model into one dead tone and reads as "the
    // file's colours are missing". STLLoader has no such gap, since an STL
    // carries a normal per facet.
    //
    // flatShading on top of that: a 3MF's mesh is usually indexed, so the
    // computed normals get averaged across every face sharing a vertex, which
    // rounds off the hard edges of a CAD part. 3MF carries no smoothing
    // information to honour, and per-face shading is what the STL path already
    // does, so faceted is both the safer and the consistent default.
    model.traverse((child) => {
      const mesh = child as Mesh
      const geometry = mesh.geometry
      if (!geometry) return
      if (!geometry.getAttribute('normal')) geometry.computeVertexNormals()
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
        if (material && 'flatShading' in material) material.flatShading = true
      }
    })
  } else {
    const { STLLoader } = await import('three/examples/jsm/loaders/STLLoader.js')
    const geometry = new STLLoader().parse(arrayBuffer)
    model = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({ color: 0x8eafc4, roughness: 0.45, metalness: 0.25 }),
    )
  }

  // Center and normalize. The model is offset inside a wrapper rather than
  // having its own geometry translated, because a 3MF is a whole subtree whose
  // children carry their own transforms, so moving the wrapper is the only
  // recentring that is correct for both shapes.
  const box = new THREE.Box3().setFromObject(model)
  const center = new THREE.Vector3()
  box.getCenter(center)
  const size = new THREE.Vector3()
  box.getSize(size)
  const largest = Math.max(size.x, size.y, size.z)
  // An empty or degenerate file would otherwise divide by zero and NaN the
  // camera, leaving a blank canvas with no clue why.
  const scale = largest > 0 ? 2.5 / largest : 1

  model.position.sub(center)
  const root = new THREE.Group()
  root.add(model)
  root.scale.setScalar(scale)
  scene.add(root)

  // Bounding sphere of the scaled model: the camera is fitted against this so
  // the model stays fully inside the frustum at any orbit angle.
  const sphere = box.getBoundingSphere(new THREE.Sphere())
  const radius = (sphere.radius || largest / 2 || 1) * scale

  // Isometric start view (front / right / above), Z-up
  const isoDirection = new THREE.Vector3(1, -1, 1).normalize()

  // Distance that fits the bounding sphere in *both* axes: using the smaller
  // of the vertical and horizontal FOV means a tall or a wide box both frame
  // the whole model instead of cropping it.
  function fitDistance(): number {
    const fovV = THREE.MathUtils.degToRad(camera.fov)
    const fovH = 2 * Math.atan(Math.tan(fovV / 2) * camera.aspect)
    return (radius / Math.sin(Math.min(fovV, fovH) / 2)) * 1.08
  }

  let framed = false

  function frameModel(): void {
    const distance = fitDistance()
    // First fit starts at ISO; later re-fits (box resized) keep whatever angle
    // the auto-rotation has reached and only correct the distance.
    const direction =
      framed && camera.position.lengthSq() > 0 ? camera.position.clone().normalize() : isoDirection
    framed = true
    camera.position.copy(direction).multiplyScalar(distance)
    camera.near = Math.max(distance - radius * 4, 0.01)
    camera.far = distance + radius * 4
    camera.updateProjectionMatrix()
    if (controls) {
      controls.target.set(0, 0, 0)
      controls.minDistance = radius * 0.5
      controls.maxDistance = distance * 4
      controls.update()
    }
  }

  // Controls
  controls = new OrbitControls(camera, canvas)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.8

  // Once the user has orbited/zoomed themselves, resizes must not yank the
  // camera back to the fitted default.
  let userMoved = false
  controls.addEventListener('start', () => {
    userMoved = true
  })

  frameModel()

  // Render loop
  function animate(): void {
    animationId = requestAnimationFrame(animate)
    controls!.update()
    renderer!.render(scene, camera)
  }
  animate()
  initLoading.value = false

  // Handle resize
  resizeObserver = new ResizeObserver(() => {
    if (!canvas || !renderer) return
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    if (w === 0 || h === 0) return
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h, false)
    // The first observation is usually the first time the real box size is
    // known. Re-fit so the model is framed against the actual aspect ratio.
    if (!userMoved) frameModel()
  })
  resizeObserver.observe(canvas)
}

function dispose(): void {
  if (animationId !== null) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
  resizeObserver?.disconnect()
  resizeObserver = null
  controls?.dispose()
  controls = null
  renderer?.dispose()
  renderer = null
}
</script>

<template>
  <div class="mesh-wrap">
    <canvas ref="canvasRef" class="mesh-canvas" />
    <div v-if="initLoading" class="mesh-loading">
      <i class="mdi mdi-loading mdi-spin mesh-loading-icon" aria-hidden="true" />
    </div>
  </div>
</template>

<style scoped>
/* align-self/height keep the wrapper filling its box even when the host is a
   row flex container with align-items other than stretch, since the canvas is
   absolutely positioned and contributes no intrinsic height of its own. */
.mesh-wrap {
  position: relative;
  flex: 1;
  align-self: stretch;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* Absolute fill: the canvas takes the exact box size instead of being sized by
   flex layout, which can leave it taller than the box and crop the render. */
.mesh-canvas {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
}

.mesh-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--p-content-background) 60%, transparent);
}

.mesh-loading-icon {
  font-size: var(--font-size-3xl);
  color: var(--p-text-muted-color);
  opacity: 0.6;
}
</style>
