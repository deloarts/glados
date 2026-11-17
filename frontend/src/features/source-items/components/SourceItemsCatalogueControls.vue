<script setup lang="ts">
import { ref, computed } from 'vue'

import SourceItemCreateForm from './SourceItemCreateForm.vue'
import { useSourceItemsStore } from '../stores/sourceItemsStore'
import { useSourceItemsCatalogueEditStore } from '../stores/sourceItemsCatalogueEditStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import CatalogueControlsBar from '@/shared/components/resource-view/CatalogueControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

const showCreateForm = ref(false)

const sourceItemsStore = useSourceItemsStore()
const editStore = useSourceItemsCatalogueEditStore()
const { hasPermission } = usePermissions()

const canWrite = computed(() => hasPermission(Permission.WRITE_SOURCE_ITEMS))
const { missing } = useMissingPermission()

function onItemCreated(): void {
  void sourceItemsStore.refresh()
}
</script>

<template>
  <CatalogueControlsBar
    i18n-prefix="sourceItems.catalogue.controls"
    :can-write="canWrite"
    :write-blocked="missing(Permission.WRITE_SOURCE_ITEMS)"
    :edit-mode="editStore.editMode"
    @create="showCreateForm = true"
    @toggle-edit="editStore.toggleEditMode()"
  >
    <template #handbook>
      <HelpButton slug="catalogue/source-items" rounded />
    </template>
  </CatalogueControlsBar>

  <SourceItemCreateForm v-model:visible="showCreateForm" @created="onItemCreated" />
</template>
