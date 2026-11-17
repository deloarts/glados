<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { MenuItem } from 'openvue/menuitem'

import { SAVEABLE_TOOLS } from '../registry'

/**
 * "New Calculation" in a controls bar, styled like the catalogue's New
 * button. It opens a menu of the tools whose results can be saved.
 */

const props = defineProps<{
  /** `project:<id>:<label>` or `product:<id>:<label>`, preselected when saving. */
  owner?: string | null
  /** A device of the owner's product, preselected when saving. */
  deviceId?: number | null
  disabled?: boolean
}>()

const { t } = useI18n()
const router = useRouter()

const menu = ref<{ toggle: (event: Event) => void } | null>(null)

const items = computed<MenuItem[]>(() =>
  SAVEABLE_TOOLS.map((tool) => ({
    label: t(tool.labelKey),
    icon: `mdi ${tool.icon}`,
    command: () =>
      router.push({
        name: 'Tools',
        params: { tab: tool.tab },
        query: {
          ...(props.owner ? { for: props.owner } : {}),
          ...(props.deviceId ? { device: String(props.deviceId) } : {}),
        },
      }),
  })),
)
</script>

<template>
  <Button
    :label="t('tools.calculations.actions.new')"
    icon="mdi mdi-plus"
    severity="contrast"
    text
    :disabled="disabled"
    aria-haspopup="menu"
    data-testid="calc-new"
    @click="menu?.toggle($event)"
  />
  <Menu ref="menu" :model="items" popup />
</template>
