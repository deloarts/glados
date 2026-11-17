<script setup lang="ts">
/**
 * The phone's main navigation: the few places a phone is used for most, with
 * the scanner one tap away. Everything else sits behind More, which opens the
 * sidebar as an overlay.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { useProductionPlanning } from '@/core/composables/useProductionPlanning'
import { useScan } from '@/features/scan'

const props = defineProps<{ sidebarCollapsed: boolean }>()
const emit = defineEmits<{ (e: 'update:sidebarCollapsed', v: boolean): void }>()

const { t } = useI18n()
const route = useRoute()
const scan = useScan()
const { productionPlanningEnabled } = useProductionPlanning()

const moreOpen = computed(() => !props.sidebarCollapsed)

function isActive(path: string): boolean {
  return !moreOpen.value && route.path.startsWith(path)
}

function toggleMore(): void {
  emit('update:sidebarCollapsed', moreOpen.value)
}
</script>

<template>
  <nav class="bottom-nav" :aria-label="t('main.bottomNav.label')">
    <router-link
      class="bottom-nav-item"
      :class="{ active: isActive('/procurement') }"
      to="/procurement/orders"
      data-testid="bottom-nav-procurement"
    >
      <i class="mdi mdi-cart" aria-hidden="true" />
      <span class="bottom-nav-label">{{ t('main.sidebar.procurement.label') }}</span>
    </router-link>
    <router-link
      v-if="productionPlanningEnabled"
      class="bottom-nav-item"
      :class="{ active: isActive('/production') }"
      to="/production/lots"
      data-testid="bottom-nav-production"
    >
      <i class="mdi mdi-factory" aria-hidden="true" />
      <span class="bottom-nav-label">{{ t('main.sidebar.production.label') }}</span>
    </router-link>
    <button
      type="button"
      class="bottom-nav-item"
      data-testid="bottom-nav-scan"
      @click="scan.openScan()"
    >
      <i class="mdi mdi-qrcode-scan" aria-hidden="true" />
      <span class="bottom-nav-label">{{ t('scan.title') }}</span>
    </button>
    <router-link
      class="bottom-nav-item"
      :class="{ active: isActive('/search') }"
      to="/search"
      data-testid="bottom-nav-search"
    >
      <i class="mdi mdi-magnify" aria-hidden="true" />
      <span class="bottom-nav-label">{{ t('search.title') }}</span>
    </router-link>
    <button
      type="button"
      class="bottom-nav-item"
      :class="{ active: moreOpen }"
      :aria-expanded="moreOpen"
      data-testid="bottom-nav-more"
      @click="toggleMore"
    >
      <i :class="moreOpen ? 'mdi mdi-close' : 'mdi mdi-menu'" aria-hidden="true" />
      <span class="bottom-nav-label">{{ t('main.bottomNav.more') }}</span>
    </button>
  </nav>
</template>

<style scoped lang="scss">
.bottom-nav {
  display: flex;
  height: 100%;
  // Keeps the entries above the home indicator of an installed app.
  padding-bottom: env(safe-area-inset-bottom, 0px);
  user-select: none;

  background-color: var(--p-content-background);
  border-top: 1px solid var(--p-content-border-color);
}

.bottom-nav-item {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  min-width: 0;
  padding: 0;

  cursor: pointer;
  color: var(--p-text-muted-color);
  background: transparent;
  border: none;
  border-top: 0.2rem solid transparent;
  font: inherit;
  text-decoration: none;
}

.bottom-nav-item i {
  font-size: var(--font-size-xl);
  pointer-events: none;
}

.bottom-nav-label {
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: var(--font-size-xs);
}

.bottom-nav-item.active {
  color: var(--p-primary-color);
  border-top-color: var(--p-primary-500);
}

.bottom-nav-item:focus-visible {
  outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
  outline-offset: -2px;
}
</style>
