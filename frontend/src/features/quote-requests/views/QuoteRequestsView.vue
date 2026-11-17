<script setup lang="ts">
// The Quotes tab of procurement: every quote request, the open ones unless
// closed ones are shown too. A row expands into its lines; the number opens
// the request. A new one can be started here, though most come from Manage
// Quotes on a demand or lot list.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { Permission } from '@/core/auth/permissions'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useQuoteRequestsStore } from '../stores/quoteRequestsStore'
import QuoteRequestCreateDialog from '../components/QuoteRequestCreateDialog.vue'
import QuoteRequestsTable from '../components/QuoteRequestsTable.vue'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

const { t } = useI18n()
const router = useRouter()
const store = useQuoteRequestsStore()
const { missing } = useMissingPermission()

const showClosed = ref(false)
const showCreate = ref(false)
const table = ref<InstanceType<typeof QuoteRequestsTable> | null>(null)
const createBlocked = computed(() => missing(Permission.WRITE_ORDERS))

function clearViews(): void {
  showClosed.value = false
  table.value?.clearFilters()
}

function openRequest(request: QuoteRequestResponse): void {
  void router.push(`/procurement/quotes/${request.id}`)
}
</script>

<template>
  <PageLayout data-class="quotes-table-data">
    <template #controls>
      <ControlsBar>
        <template #start>
          <span v-tooltip.bottom="createBlocked || undefined">
            <Button
              icon="mdi mdi-plus"
              :label="t('quoteRequests.list.new')"
              severity="contrast"
              text
              :disabled="createBlocked !== ''"
              data-testid="new-quote-request"
              @click="showCreate = true"
            />
          </span>
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="quote-requests"
        :syncing="store.loading"
        :has-active-filters="showClosed || (table?.hasActiveFilters ?? false)"
        hide-views-toggle
        @sync="table?.fetchItems()"
        @clear="clearViews"
      >
        <template #extra>
          <Divider layout="vertical" />
          <Button
            :label="t('quoteRequests.list.showClosed')"
            icon="mdi mdi-archive-eye-outline"
            severity="contrast"
            :text="!showClosed"
            @click="showClosed = !showClosed"
          />
        </template>
      </ViewsBar>
    </template>

    <QuoteRequestsTable ref="table" :show-closed="showClosed" />
  </PageLayout>

  <QuoteRequestCreateDialog v-model:visible="showCreate" @created="openRequest" />
</template>

<style scoped lang="scss">
:deep(.quotes-table-data) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
</style>
