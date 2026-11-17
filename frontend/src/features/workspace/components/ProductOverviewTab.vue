<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useUsersStore } from '@/core/stores/usersStore'
import { formatISODate } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { getChecklists } from '@/features/checklists'
import { useHostStore } from '@/core/host/stores/hostStore'
import { projectStatusSeverity } from '@/features/projects'
import { getCalculations } from '@/features/tools'
import type { ProjectResponse } from '@/features/projects'
import OverviewRelatedRow from '@/shared/components/resource-view/OverviewRelatedRow.vue'
import OverviewSection from '@/shared/components/resource-view/OverviewSection.vue'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { legalBasisOutdated, ProductContactsSection, ProductPicture } from '@/features/products'
import type { ProductResponse } from '@/features/products'

type ProjectStatus = ProjectResponse['status']

/**
 * The product at a glance: its details beside the machine data its
 * checklists take, and below them its picture beside what is related to
 * it. The info bar above already names the product and its status, so they
 * are not repeated here. A related row opens the tab that lists it.
 */

const props = defineProps<{
  product: ProductResponse
  projects: ProjectResponse[]
}>()

const emit = defineEmits<{
  openTab: [tab: 'projects' | 'calculations' | 'checklists']
}>()

const { t } = useI18n()
const usersStore = useUsersStore()

// The severity map is keyed by every project status in display order, so it
// doubles as the status list.
const projectStatuses = Object.keys(projectStatusSeverity) as ProjectStatus[]

const projectCounts = computed(() => {
  const counts = Object.fromEntries(projectStatuses.map((status) => [status, 0])) as Record<
    ProjectStatus,
    number
  >
  for (const project of props.projects) counts[project.status] += 1
  return counts
})

// Only the statuses some project has; a row of zeros says nothing.
const shownProjectStatuses = computed(() => projectStatuses.filter((status) => projectCounts.value[status] > 0))

// Totals only: one row per list is enough to read its total. A count that
// fails to load shows as empty rather than blocking the overview.
interface RecordCounts {
  calculations: number | null
  checklists: number | null
  failedChecklists: number | null
}

const hostStore = useHostStore()

const recordCounts = ref<RecordCounts>({ calculations: null, checklists: null, failedChecklists: null })

async function total(request: Promise<{ total: number }>): Promise<number | null> {
  try {
    return (await request).total
  } catch {
    return null
  }
}

watch(
  () => props.product.id,
  async (id) => {
    // A switched-off feature shows no row, so its counts are not fetched.
    const skip = Promise.resolve(null)
    const [calculations, checklists, failedChecklists] = await Promise.all([
      hostStore.calculationsEnabled
        ? total(getCalculations({ related_product_id: id, limit: 1 }))
        : skip,
      hostStore.checklistsEnabled ? total(getChecklists({ related_product_id: id, limit: 1 })) : skip,
      hostStore.checklistsEnabled
        ? total(getChecklists({ related_product_id: id, verdict: 'failed', limit: 1 }))
        : skip,
    ])
    if (props.product.id === id) recordCounts.value = { calculations, checklists, failedChecklists }
  },
  { immediate: true },
)

const machineRows = computed(() => [
  { key: 'designation', label: 'designation', value: props.product.designation },
  { key: 'machine-type', label: 'machineType', value: props.product.machine_type },
  { key: 'installation-site', label: 'installationSite', value: props.product.installation_site },
  { key: 'installation-location', label: 'installationLocation', value: props.product.installation_location },
  {
    key: 'placing',
    label: 'placingOnMarket',
    value: props.product.planned_placing_on_market ? formatISODate(props.product.planned_placing_on_market) : null,
  },
])

const legalBasisLabel = computed(() =>
  props.product.legal_basis ? t(`resources.products.legalBases.${props.product.legal_basis}`) : getEmptyPlaceholder(),
)
const legalBasisWarning = computed(() =>
  legalBasisOutdated(props.product.legal_basis, props.product.planned_placing_on_market),
)

function shownCount(value: number | null): string {
  return value === null ? getEmptyPlaceholder() : String(value)
}
</script>

<template>
  <div class="overview-layout">
    <div class="overview-column">
      <OverviewSection :title="t('resources.products.detail.overview.details')">
        <dl>
          <dt>{{ t('resources.products.columns.description') }}</dt>
          <dd :class="{ empty: !product.description }" class="description">
            {{ product.description ?? getEmptyPlaceholder() }}
          </dd>
          <dt>{{ t('resources.products.columns.customer') }}</dt>
          <dd :class="{ empty: !product.customer }">{{ product.customer?.name ?? getEmptyPlaceholder() }}</dd>
          <dt>{{ t('resources.products.columns.designatedUser') }}</dt>
          <dd><UserAvatarPreview :user="usersStore.getById(product.designated_user_id) ?? null" /></dd>
          <dt>{{ t('resources.products.columns.creator') }}</dt>
          <dd><UserAvatarPreview :user="product.creator ?? null" /></dd>
          <dt>{{ t('resources.products.columns.created') }}</dt>
          <dd>{{ formatISODate(product.created) }}</dd>
        </dl>
      </OverviewSection>

      <ProductPicture :product-id="product.id" :product-number="product.product_number" />
    </div>

    <div class="overview-column">
      <OverviewSection
        :title="t('resources.products.machineData.title')"
        :hint="t('resources.products.machineData.hint')"
        label-width="16rem"
        data-testid="product-machine-data"
      >
        <dl>
          <template v-for="row in machineRows" :key="row.key">
            <dt>{{ t(`resources.products.fields.${row.label}`) }}</dt>
            <dd :class="{ empty: !row.value }" :data-testid="`product-machine-${row.key}`">
              {{ row.value || getEmptyPlaceholder() }}
            </dd>
          </template>
          <dt>{{ t('resources.products.fields.legalBasis') }}</dt>
          <dd :class="{ empty: !product.legal_basis }" class="legal-basis" data-testid="product-machine-legal-basis">
            <span>{{ legalBasisLabel }}</span>
            <Message v-if="legalBasisWarning" severity="warn" size="small" data-testid="product-legal-basis-warning">
              {{ t('resources.products.machineData.legalBasisOutdated') }}
            </Message>
          </dd>
        </dl>
      </OverviewSection>

      <OverviewSection :title="t('resources.products.detail.overview.related')" flush>
        <OverviewRelatedRow
          :label="t('resources.products.detail.overview.projects')"
          :count="projects.length"
          data-testid="product-related-projects"
          @click="emit('openTab', 'projects')"
        >
          <Tag
            v-for="status in shownProjectStatuses"
            :key="status"
            :value="`${projectCounts[status]} ${t(`resources.projects.status.${status}`)}`"
            :severity="projectStatusSeverity[status]"
            :data-testid="`product-projects-${status}`"
          />
        </OverviewRelatedRow>
        <OverviewRelatedRow
          v-if="hostStore.calculationsEnabled"
          :label="t('resources.products.detail.overview.calculations')"
          :count="shownCount(recordCounts.calculations)"
          data-testid="product-related-calculations"
          @click="emit('openTab', 'calculations')"
        />
        <OverviewRelatedRow
          v-if="hostStore.checklistsEnabled"
          :label="t('resources.products.detail.overview.checklists')"
          :count="shownCount(recordCounts.checklists)"
          data-testid="product-related-checklists"
          @click="emit('openTab', 'checklists')"
        >
          <Tag
            v-if="recordCounts.failedChecklists"
            :value="t('resources.products.detail.overview.withFindings', { count: recordCounts.failedChecklists })"
            severity="danger"
            data-testid="product-checklists-failed"
          />
        </OverviewRelatedRow>
      </OverviewSection>

      <ProductContactsSection :product="product" />
    </div>
  </div>
</template>

<style scoped lang="scss">
// Two independent columns, so a short card does not wait for its taller
// neighbour: the details over the picture, the machine data over the
// related records. They stack when the panel is too narrow for both.
.overview-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: var(--space-4);
  align-items: start;
  height: 100%;
  overflow-y: auto;
  padding: var(--space-1) 0;

  @media (max-width: $bp-lg) {
    grid-template-columns: minmax(0, 1fr);
  }
}

.overview-column {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.description {
  white-space: pre-line;
}

// The warning goes below the legal basis, not beside it.
.legal-basis {
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
}
</style>
