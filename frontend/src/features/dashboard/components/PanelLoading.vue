<script setup lang="ts">
/**
 * The dashboard's first-load placeholder, a visible bar so a loading panel
 * never looks like a panel without data. The root carries the caller's
 * panel-loading class, so each panel's own padding and sizing apply.
 */
</script>

<template>
  <div>
    <ProgressBar mode="indeterminate" class="panel-loading-bar" />
  </div>
</template>

<style scoped lang="scss">
.panel-loading-bar {
  width: 100%;
  height: 3px;
}
</style>
