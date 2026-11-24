<script setup lang="ts">
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ExternalWorkTable from '../components/ExternalWorkTable.vue'
import ExternalWorkViews from '../components/ExternalWorkViews.vue'
</script>

<template>
  <!-- A list without actions has no controls bar; its handbook button
       closes the views bar. -->
  <PageLayout>
    <template #views>
      <ExternalWorkViews />
    </template>
    <ExternalWorkTable />
  </PageLayout>
</template>
