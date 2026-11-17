import { ref } from 'vue'

// Module-scope singleton so any component can open the lot detail dialog,
// which the app shell mounts once.
const lotId = ref<number | null>(null)
const visible = ref(false)

export function useLotDetail() {
  function openLotDetail(id: number): void {
    lotId.value = id
    visible.value = true
  }

  return { lotId, visible, openLotDetail }
}
