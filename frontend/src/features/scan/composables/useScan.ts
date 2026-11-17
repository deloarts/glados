import { readonly, ref } from 'vue'

// Module-scope singleton so any component can open the scan dialog, which
// the app shell mounts once.
const visible = ref(false)

// Whether the device has any camera to scan with. It starts false so a
// desktop without a webcam never flashes the scan button, and it follows
// devicechange so plugging a webcam in shows the button without a reload.
// Without mediaDevices (an insecure origin or an old browser) the camera
// cannot be used at all, so it stays false.
const cameraAvailable = ref(false)
let cameraWatchStarted = false

async function detectCamera(): Promise<void> {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    cameraAvailable.value = devices.some((device) => device.kind === 'videoinput')
  } catch {
    cameraAvailable.value = false
  }
}

function watchCamera(): void {
  if (cameraWatchStarted) return
  cameraWatchStarted = true
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.enumerateDevices) return
  navigator.mediaDevices.addEventListener?.('devicechange', () => void detectCamera())
  void detectCamera()
}

export function useScan() {
  watchCamera()

  function openScan(): void {
    visible.value = true
  }

  function closeScan(): void {
    visible.value = false
  }

  return { visible, cameraAvailable: readonly(cameraAvailable), openScan, closeScan }
}
