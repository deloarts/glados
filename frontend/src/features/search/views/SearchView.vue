<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

import { useSearchStore } from '../stores/searchStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { isPublicId, resolvePublicId, routeForResolved } from '@/features/scan'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import SearchResultGroup from '../components/SearchResultGroup.vue'

import type { GlobalSearchHit } from '../types/globalSearchResponse'
import { apiErrorStatus } from '@/core/utils/errors'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useAppToast()

const searchStore = useSearchStore()
const hostStore = useHostStore()

const query = computed(() => {
  const q = route.query.q
  return typeof q === 'string' ? q : ''
})

const isUuidQuery = computed(() => isPublicId(query.value))

// The header's search field has no room on a phone, so the page brings its own.
const { isPhone } = usePhoneLayout()
const phoneQuery = ref(query.value)
watch(query, (q) => {
  phoneQuery.value = q
})

function submitPhoneQuery(): void {
  const q = phoneQuery.value.trim()
  if (q) void router.push({ name: 'Search', query: { q } })
}

// ── UUID fast path ─────────────────────────────────────────────────────
// The store never sees a UUID query. It's resolved directly against
// GET /resolve/{public_id} and replaces the page with the record itself.

const resolving = ref(false)
const uuidError = ref(false)
const uuidNotFoundId = ref<string | null>(null)
const uuidNoRoute = ref(false)

async function resolveAndNavigate(id: string): Promise<void> {
  resolving.value = true
  uuidError.value = false
  uuidNotFoundId.value = null
  uuidNoRoute.value = false

  try {
    const resolved = await resolvePublicId(id)
    const path = routeForResolved(resolved)
    if (path === null) {
      uuidNoRoute.value = true
      resolving.value = false
      return
    }
    // Stays in the lookup state until navigation, so the error branch never
    // flashes.
    void router.replace(path)
  } catch (e) {
    resolving.value = false
    if (apiErrorStatus(e) === 404) {
      uuidNotFoundId.value = id
    } else {
      uuidError.value = true
    }
  }
}

// Hides the groups of a switched-off feature, like the router guard.
const filteredVisibleGroups = computed(() =>
  searchStore.visibleGroups.filter((group) => {
    if (hostStore.productionPlanningEnabled === false) {
      if (group.resource === 'production-lots' || group.resource === 'production-orders') {
        return false
      }
    }
    if (group.resource === 'calculations') return hostStore.calculationsEnabled
    if (group.resource === 'checklists') return hostStore.checklistsEnabled
    return true
  }),
)

// Counted over the groups actually shown, so hidden production groups
// never inflate the number above the cards.
const totalHits = computed(() =>
  filteredVisibleGroups.value.reduce((sum, group) => sum + group.total, 0),
)

// The group cards render as siblings of the summary panel.
const showResultGroups = computed(
  () =>
    !isUuidQuery.value &&
    searchStore.query !== '' &&
    !searchStore.loading &&
    !searchStore.error &&
    filteredVisibleGroups.value.length > 0,
)

watch(
  query,
  (q) => {
    const trimmed = q.trim()
    if (isPublicId(trimmed)) {
      void resolveAndNavigate(trimmed)
      return
    }
    uuidError.value = false
    uuidNotFoundId.value = null
    uuidNoRoute.value = false
    void searchStore.search(q)
  },
  { immediate: true },
)

function retry(): void {
  if (isUuidQuery.value) {
    void resolveAndNavigate(query.value.trim())
  } else {
    void searchStore.retry()
  }
}

function onSelect(hit: GlobalSearchHit): void {
  const path = routeForResolved({ resource: hit.resource, id: hit.id, public_id: hit.public_id })
  if (path === null) {
    toast.error(t('search.noRoute'))
    return
  }
  void router.push(path)
}
</script>

<template>
  <PageLayout>
    <template #info>
      <InfoBar>
        <template v-if="isUuidQuery">
          <span v-if="resolving">{{ t('search.resolving') }}</span>
        </template>

        <template v-else-if="searchStore.query === ''">
          <span>{{ t('search.title') }}</span>
        </template>

        <template v-else-if="searchStore.loading">
          <Skeleton width="7rem" height="1.5rem" border-radius="1rem" />
          <Skeleton width="5.5rem" height="1.5rem" border-radius="1rem" />
        </template>

        <template v-else>
          <span class="info-query">{{ t('search.resultsFor', { query: searchStore.query }) }}</span>
          <span class="info-sep" />
          <span>{{ t('search.totalHits', { count: totalHits }) }}</span>
          <template v-if="searchStore.durationMs !== null">
            <span class="info-sep" />
            <span class="info-muted">
              {{ t('search.duration', { ms: Math.round(searchStore.durationMs) }) }}
            </span>
          </template>
        </template>
      </InfoBar>
    </template>

    <div class="search-content">
      <IconField v-if="isPhone" class="phone-search">
        <InputIcon class="mdi mdi-magnify" />
        <InputText
          v-model="phoneQuery"
          class="phone-search-input"
          type="search"
          enterkeyhint="search"
          :placeholder="t('common.search')"
          :aria-label="t('common.search')"
          data-testid="phone-search-input"
          @keyup.enter="submitPhoneQuery"
        />
      </IconField>
      <Panel v-if="!showResultGroups" :header="t('search.title')" class="search-summary">
        <template v-if="isUuidQuery">
          <div v-if="resolving" class="state-center">
            <ProgressSpinner style="width: 2rem; height: 2rem" />
            <span>{{ t('search.resolving') }}</span>
          </div>
          <div v-else-if="uuidNotFoundId !== null" class="state-center state-message">
            <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
            <span>{{ t('search.publicIdNotFound', { id: uuidNotFoundId }) }}</span>
          </div>
          <div v-else-if="uuidNoRoute" class="state-center state-message">
            <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
            <span>{{ t('search.noRoute') }}</span>
          </div>
          <div v-else-if="uuidError" class="state-center">
            <Message severity="error" :closable="false">{{ t('search.error') }}</Message>
            <Button :label="t('search.retry')" @click="retry" />
          </div>
        </template>

        <template v-else-if="searchStore.query === ''">
          <div class="state-center state-message">
            <i class="mdi mdi-magnify state-icon" aria-hidden="true" />
            <span>{{ t('search.emptyQuery') }}</span>
          </div>
        </template>

        <template v-else>
          <div v-if="searchStore.loading" class="state-center">
            <ProgressSpinner style="width: 2rem; height: 2rem" />
          </div>
          <div v-else-if="searchStore.error" class="state-center">
            <Message severity="error" :closable="false">{{ t('search.error') }}</Message>
            <Button :label="t('search.retry')" @click="retry" />
          </div>
          <div v-else-if="filteredVisibleGroups.length === 0" class="state-center state-message">
            <span>{{ t('search.noResults', { query: searchStore.query }) }}</span>
          </div>
        </template>
      </Panel>

      <div v-if="showResultGroups" class="search-groups">
        <SearchResultGroup
          v-for="group in filteredVisibleGroups"
          :key="group.resource"
          :group="group"
          @select="onSelect"
        />
      </div>
    </div>
  </PageLayout>
</template>

<style scoped lang="scss">
// The same 0.5rem rhythm between the summary and the groups.
.search-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  // The content card is height:100% (global .card). The list scrolls inside
  // it instead of overflowing the card's bottom edge.
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.phone-search {
  flex-shrink: 0;
}

.phone-search-input {
  width: 100%;
}

.info-query {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.search-groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.state-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6) var(--space-4);
  text-align: center;
}

.state-message {
  color: var(--p-text-muted-color);

  .state-icon {
    font-size: var(--font-size-3xl);
  }
}
</style>
