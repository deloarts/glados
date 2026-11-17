<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const router = useRouter()

const links = [
  { icon: 'mdi mdi-folder', label: 'main.sidebar.workspace.label', to: '/workspace' },
  { icon: 'mdi mdi-bookshelf', label: 'main.sidebar.resources.label', to: '/resources' },
  {
    icon: 'mdi mdi-book-open-page-variant',
    label: 'main.sidebar.catalogue.label',
    to: '/catalogue',
  },
  { icon: 'mdi mdi-cart', label: 'main.sidebar.procurement.label', to: '/procurement' },
  { icon: 'mdi mdi-factory', label: 'main.sidebar.production.label', to: '/production' },
] as const
</script>

<template>
  <div class="card quick-links-panel">
    <div class="panel-title">
      <i class="mdi mdi-lightning-bolt-outline" aria-hidden="true" />
      <span>{{ t('dashboard.quickLinks.title') }}</span>
    </div>
    <div class="quick-links-row">
      <button
        v-for="link in links"
        :key="link.to"
        type="button"
        class="quick-link"
        @click="router.push(link.to)"
      >
        <i :class="link.icon" aria-hidden="true" />
        <span>{{ t(link.label) }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.quick-links-panel {
  gap: var(--space-3);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.quick-links-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.quick-link {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--p-content-border-radius);
  border: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
  color: var(--p-text-color);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition:
    background-color 0.15s,
    transform 0.15s;

  i {
    font-size: var(--font-size-lg);
    color: var(--p-primary-500);
  }

  &:hover {
    background-color: var(--p-content-hover-background);
    transform: translateY(-1px);
  }
}
</style>
