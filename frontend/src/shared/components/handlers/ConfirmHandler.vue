<script setup lang="ts">
// The confirmation dialogs of the whole app, mounted once in App.vue. The
// ungrouped one answers every useConfirm().require and useConfirmAsync().ask
// without a group, so no view mounts a ConfirmDialog of its own, which left
// an action dead on a view without one and showed two dialogs where a nested
// view had one too. The second is useConfirmDelete()'s.
import { CONFIRM_DELETE_GROUP } from '@/shared/composables/useConfirmDelete'
</script>

<template>
  <ConfirmDialog />
  <ConfirmDialog :group="CONFIRM_DELETE_GROUP" />
</template>
