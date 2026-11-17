import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { useOrderFilesStore } from '../stores/orderFilesStore'
import type { OrderFileCategory, OrderResponse } from '../types/ordersResponse'

const DOCUMENT_CATEGORIES: OrderFileCategory[] = [
  'proposal',
  'order_confirmation',
  'delivery_note',
  'invoice',
  'general',
]

/**
 * Opens a file picker and resolves with the chosen file, or null when
 * dismissed. The input is attached to the document before clicking, since
 * some browsers ignore click() on a detached file input.
 */
function pickFile(options: { accept?: string; capture?: boolean } = {}): Promise<File | null> {
  const input = document.createElement('input')
  input.type = 'file'
  input.style.display = 'none'
  if (options.accept) input.accept = options.accept
  if (options.capture) input.capture = 'environment'
  document.body.appendChild(input)

  return new Promise((resolve) => {
    function finish(file: File | null): void {
      input.remove()
      resolve(file)
    }
    input.addEventListener('change', () => finish(input.files?.[0] ?? null), { once: true })
    // Not universally supported; without it a dismissed picker leaves the
    // promise pending, which is harmless.
    input.addEventListener('cancel', () => finish(null), { once: true })
    input.click()
  })
}

/**
 * The "add file" menu and its uploads, shared by every surface that offers
 * them for an order (the list's row menu, the detail page's action bar).
 */
export function useOrderFileUpload() {
  const { t } = useI18n()
  const { toastOnError } = useErrorToast()
  const filesStore = useOrderFilesStore()

  async function browseAndUpload(order: OrderResponse, category: OrderFileCategory): Promise<void> {
    const file = await pickFile({ accept: category === 'picture' ? 'image/*' : undefined })
    if (file) await filesStore.upload(order.id, file, category)
  }

  async function captureAndUpload(order: OrderResponse): Promise<void> {
    const file = await pickFile({ accept: 'image/*', capture: true })
    if (file) await filesStore.upload(order.id, file, 'picture')
  }

  function reportUploadError(e: unknown): void {
    toastOnError(t('common.files.errors.upload'))(e)
  }

  function fileMenuItems(order: OrderResponse): MenuItem[] {
    return [
      ...DOCUMENT_CATEGORIES.map((category) => ({
        label: t(`orders.files.categories.${category}`),
        icon: 'mdi mdi-file-outline',
        command: () => void browseAndUpload(order, category).catch(reportUploadError),
      })),
      { separator: true },
      {
        label: t('orders.files.categories.picture'),
        icon: 'mdi mdi-image-outline',
        command: () => void browseAndUpload(order, 'picture').catch(reportUploadError),
      },
      {
        label: t('orders.files.takePicture'),
        icon: 'mdi mdi-camera-outline',
        command: () => void captureAndUpload(order).catch(reportUploadError),
      },
    ]
  }

  return { browseAndUpload, captureAndUpload, fileMenuItems }
}
