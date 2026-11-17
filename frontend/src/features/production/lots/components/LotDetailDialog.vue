<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { HelpDrawer } from '@/shared/help'

import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useMadeItemLabel } from '@/features/made-items'
import LotDetailContent from './LotDetailContent.vue'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  lotId: number | null
}>()

const { t } = useI18n()
const detailStore = useProductionLotDetailStore()
const { format: madeItemLabel } = useMadeItemLabel()
const explainVisible = ref(false)

// Same stale-lot guard as LotDetailContent: the store is a shared singleton,
// so on a lot-to-lot switch it still holds the previous lot until the new
// fetch lands, and the header would otherwise name the wrong lot meanwhile.
const lot = computed(() => (detailStore.lot?.id === props.lotId ? detailStore.lot : null))

// The page variant fetches into this same store singleton on mount. clear()
// here only stays safe because it runs on the watcher's flush (nextTick),
// well before the page's own fetch() round-trip resolves, so it can never
// wipe data the page just loaded.
watch(visible, (isVisible) => {
  if (!isVisible) detailStore.clear()
})

function closeAndNavigate(navigate: (event: MouseEvent) => void, event: MouseEvent): void {
  visible.value = false
  navigate(event)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-full)', height: '88vh' }"
    :content-style="{
      display: 'flex',
      flexDirection: 'column',
      minHeight: '0',
    }"
  >
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">
          {{ lot?.lot_number ?? t('production.lots.detail.dialogTitle') }}
        </span>
        <template v-if="lot">
          <span class="info-sep" />
          <span class="header-field">{{ madeItemLabel(lot.made_item_part_number, lot.made_item_revision) }}</span>
          <span class="info-sep" />
          <span class="header-field">{{ lot.made_item_article_name }}</span>
        </template>
      </div>
    </template>

    <!-- Replaces the native close button rather than adding a sibling to it:
         OpenVue has no slot for an extra header icon, only maximizebutton
         and closebutton, and repurposing maximizebutton would carry its own
         (wrong) semantics. Same pattern as OrderDetailDialog. -->
    <template #closebutton="{ closeCallback }">
      <Button
        icon="mdi mdi-help"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.bottom="t('production.lots.detail.explain')"
        :aria-label="t('production.lots.detail.explain')"
        data-testid="lot-dialog-help"
        @click="explainVisible = true"
      />
      <RouterLink
        v-if="lotId !== null"
        v-slot="{ navigate }"
        :to="`/production/lots/${lotId}`"
        custom
      >
        <Button
          icon="mdi mdi-open-in-new"
          size="small"
          severity="secondary"
          text
          rounded
          v-tooltip.bottom.focus="t('production.lots.detail.open')"
          :aria-label="t('production.lots.detail.open')"
          @click="closeAndNavigate(navigate, $event)"
        />
      </RouterLink>
      <Button
        icon="mdi mdi-close"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.bottom.focus="t('common.close')"
        :aria-label="t('common.close')"
        @click="closeCallback"
      />
    </template>

    <LotDetailContent v-if="visible && lotId !== null" :lot-id="lotId" />
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/lots" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  align-items: center;
  min-width: 0;
}

// Same divider the detail page's InfoBar draws between these fields, so the
// dialog header and the page read as the same record.
.info-sep {
  display: inline-block;
  width: 1px;
  height: 1.1rem;
  background: var(--p-surface-300);
  margin: 0 var(--space-3);
  flex-shrink: 0;
}

.header-field {
  font-weight: 400;
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
