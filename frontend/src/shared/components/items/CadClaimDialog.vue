<script setup lang="ts">
// The warning before a PDM-claimed catalogue item is edited in the web,
// driven by useCadClaimGuard.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ConfirmActionDialog from '@/shared/components/dialogs/ConfirmActionDialog.vue'
import type { CadClaimGuard } from '@/shared/composables/useCadClaimGuard'

const props = defineProps<{ guard: CadClaimGuard }>()

const { t } = useI18n()

const message = computed(() => {
  const { reason, count } = props.guard.dialog
  return count > 1
    ? t(`catalogue.cadClaim.${reason}Many`, { count })
    : t(`catalogue.cadClaim.${reason}`)
})
</script>

<template>
  <ConfirmActionDialog
    :visible="guard.dialog.visible"
    :header="t('catalogue.cadClaim.header')"
    :message="message"
    :confirm-label="t('catalogue.cadClaim.continue')"
    confirm-severity="warn"
    data-testid="cad-claim-dialog"
    @update:visible="guard.onVisibleChange"
    @confirm="guard.confirm"
  />
</template>
