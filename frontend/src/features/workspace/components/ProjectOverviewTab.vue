<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useUsersStore } from '@/core/stores/usersStore'
import { formatISODate } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { getChecklists } from '@/features/checklists'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useOrderFormatters } from '@/features/orders'
import { ProductPicture } from '@/features/products'
import { getCalculations } from '@/features/tools'
import OverviewRelatedRow from '@/shared/components/resource-view/OverviewRelatedRow.vue'
import OverviewSection from '@/shared/components/resource-view/OverviewSection.vue'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { ProjectContactsSection, projectStatusSeverity } from '@/features/projects'
import type { ProjectResponse, ProjectSummaryResponse } from '@/features/projects'
import { DEMAND_STATUSES, DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'

/**
 * The project at a glance: its details beside its procurement and
 * production figures, and below them the picture of its product beside
 * what is related to it. The info bar above already names the project, so
 * its number is not repeated here. A related row opens the tab that lists
 * it.
 */

const props = defineProps<{
  project: ProjectResponse
  summary: ProjectSummaryResponse | null
  /** Lines of the bill of material, bought, made and source items together. */
  bomCount: number
}>()

const emit = defineEmits<{
  openTab: [tab: 'bom' | 'orders' | 'calculations' | 'checklists']
}>()

const { t } = useI18n()
const usersStore = useUsersStore()
const { formatPrice } = useOrderFormatters()

// Only the statuses some demand has; a row of zeros says nothing.
const shownDemandStatuses = computed(() =>
  DEMAND_STATUSES.filter((status) => (props.summary?.demand_counts[status] ?? 0) > 0),
)

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
  () => props.project.id,
  async (id) => {
    // A switched-off feature shows no row, so its counts are not fetched.
    const skip = Promise.resolve(null)
    const [calculations, checklists, failedChecklists] = await Promise.all([
      hostStore.calculationsEnabled
        ? total(getCalculations({ project_id: id, limit: 1 }))
        : skip,
      hostStore.checklistsEnabled ? total(getChecklists({ project_id: id, limit: 1 })) : skip,
      hostStore.checklistsEnabled
        ? total(getChecklists({ project_id: id, verdict: 'failed', limit: 1 }))
        : skip,
    ])
    if (props.project.id === id) recordCounts.value = { calculations, checklists, failedChecklists }
  },
  { immediate: true },
)

function shownCount(value: number | null | undefined): string {
  return value === null || value === undefined ? getEmptyPlaceholder() : String(value)
}
</script>

<template>
  <div class="overview-layout">
    <div class="overview-column">
      <OverviewSection :title="t('resources.projects.detail.overview.details')">
        <dl>
          <dt>{{ t('resources.projects.columns.description') }}</dt>
          <dd :class="{ empty: !project.description }" class="description">
            {{ project.description ?? getEmptyPlaceholder() }}
          </dd>
          <dt>{{ t('resources.projects.columns.status') }}</dt>
          <dd>
            <Tag
              :value="t(`resources.projects.status.${project.status}`)"
              :severity="projectStatusSeverity[project.status]"
            />
          </dd>
          <dt>{{ t('resources.projects.columns.customer') }}</dt>
          <dd :class="{ empty: !project.customer }">{{ project.customer?.name ?? getEmptyPlaceholder() }}</dd>
          <dt>{{ t('resources.projects.columns.product') }}</dt>
          <dd :class="{ empty: !project.product }">
            <RouterLink
              v-if="project.product"
              :to="{ name: 'ProductDetail', params: { id: project.product.id } }"
              class="product-link"
              data-testid="project-product-link"
            >
              {{ project.product.product_number }}
            </RouterLink>
            <template v-else>{{ getEmptyPlaceholder() }}</template>
          </dd>
          <dt>{{ t('resources.projects.columns.designatedUser') }}</dt>
          <dd><UserAvatarPreview :user="usersStore.getById(project.designated_user_id) ?? null" /></dd>
          <dt>{{ t('resources.projects.columns.creator') }}</dt>
          <dd><UserAvatarPreview :user="project.creator ?? null" /></dd>
          <dt>{{ t('resources.projects.columns.created') }}</dt>
          <dd>{{ formatISODate(project.created) }}</dd>
        </dl>
      </OverviewSection>

      <ProductPicture
        v-if="project.product"
        :product-id="project.product.id"
        :product-number="project.product.product_number"
      />
    </div>

    <div class="overview-column">
      <OverviewSection
        :title="t('resources.projects.detail.overview.procurement')"
        label-width="16rem"
        data-testid="project-procurement"
      >
        <dl>
          <dt>{{ t('resources.projects.detail.overview.boughtDemands') }}</dt>
          <dd :class="{ empty: !shownDemandStatuses.length }" class="tag-list" data-testid="project-demand-statuses">
            <Tag
              v-for="status in shownDemandStatuses"
              :key="status"
              :value="`${summary?.demand_counts[status]} ${t(`resources.projects.detail.bom.status.${status}`)}`"
              :severity="DEMAND_STATUS_SEVERITY[status]"
              :data-testid="`project-demands-${status}`"
            />
            <template v-if="!shownDemandStatuses.length">{{ getEmptyPlaceholder() }}</template>
          </dd>
          <dt>{{ t('resources.projects.detail.overview.totalOrdered') }}</dt>
          <dd :class="{ empty: !summary }" data-testid="project-total-ordered">
            {{ summary ? formatPrice(summary.total_ordered_cost) : getEmptyPlaceholder() }}
          </dd>
          <dt>{{ t('resources.projects.detail.overview.totalDelivered') }}</dt>
          <dd :class="{ empty: !summary }" data-testid="project-total-delivered">
            {{ summary ? formatPrice(summary.total_delivered_cost) : getEmptyPlaceholder() }}
          </dd>
          <dt>{{ t('resources.projects.fields.requiredDeliveryDateBought') }}</dt>
          <dd :class="{ empty: !project.required_delivery_date_bought }">
            {{ project.required_delivery_date_bought ? formatISODate(project.required_delivery_date_bought) : getEmptyPlaceholder() }}
          </dd>
          <dt>{{ t('resources.projects.fields.requiredDeliveryDateMade') }}</dt>
          <dd :class="{ empty: !project.required_delivery_date_made }">
            {{ project.required_delivery_date_made ? formatISODate(project.required_delivery_date_made) : getEmptyPlaceholder() }}
          </dd>
          <dt>{{ t('resources.projects.fields.productionTimeBudget') }}</dt>
          <dd :class="{ empty: project.production_time_budget === null }">
            {{
              project.production_time_budget === null
                ? getEmptyPlaceholder()
                : t('resources.projects.detail.overview.minutes', { count: project.production_time_budget })
            }}
          </dd>
        </dl>
      </OverviewSection>

      <OverviewSection :title="t('resources.projects.detail.overview.related')" flush>
        <OverviewRelatedRow
          :label="t('resources.projects.detail.tabs.bom')"
          :count="bomCount"
          data-testid="project-related-bom"
          @click="emit('openTab', 'bom')"
        />
        <OverviewRelatedRow
          :label="t('resources.projects.detail.tabs.orders')"
          :count="shownCount(summary?.order_count)"
          data-testid="project-related-orders"
          @click="emit('openTab', 'orders')"
        />
        <OverviewRelatedRow
          v-if="hostStore.calculationsEnabled"
          :label="t('resources.projects.detail.tabs.calculations')"
          :count="shownCount(recordCounts.calculations)"
          data-testid="project-related-calculations"
          @click="emit('openTab', 'calculations')"
        />
        <OverviewRelatedRow
          v-if="hostStore.checklistsEnabled"
          :label="t('resources.projects.detail.tabs.checklists')"
          :count="shownCount(recordCounts.checklists)"
          data-testid="project-related-checklists"
          @click="emit('openTab', 'checklists')"
        >
          <Tag
            v-if="recordCounts.failedChecklists"
            :value="t('resources.projects.detail.overview.withFindings', { count: recordCounts.failedChecklists })"
            severity="danger"
            data-testid="project-checklists-failed"
          />
        </OverviewRelatedRow>
      </OverviewSection>

      <ProjectContactsSection :project="project" />
    </div>
  </div>
</template>

<style scoped lang="scss">
// Two independent columns, so a short card does not wait for its taller
// neighbour: the details over the picture, the procurement figures over the
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

.tag-list {
  flex-wrap: wrap;
  gap: var(--space-1);
}

.product-link {
  color: var(--p-primary-color);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}
</style>
