<!--
  Folder picker for the SolidWorks PDM vault: a lazily loaded Tree that starts
  at the vault root's subfolders and fetches a node's children on first
  expand. With `allowWatched` false (adding a folder), folders already watched
  are muted and cannot be picked. It stays mounted, so `watch(visible)` reloads
  from the root on every opening. `apply` emits the folder's path and vault id.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TreeNode } from 'openvue/treenode'

import { useAdminSettingsStore } from '../../stores/adminSettingsStore'
import { normalizePdmPath } from '../../utils/pdmSync'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import type { PdmFolder } from '../../types/adminSettingsTypes'

const VAULT_ROOT_ID = 1

const { t } = useI18n()
const store = useAdminSettingsStore()

const visible = defineModel<boolean>('visible', { required: true })

const props = withDefaults(
  defineProps<{
    /** Paths already on the watched-folder list, for the "already watched" marker. */
    watchedPaths?: string[]
    /** Whether an already-watched folder can still be picked (the per-row editor's own path is always on the list). */
    allowWatched?: boolean
  }>(),
  { watchedPaths: () => [], allowWatched: false },
)

const emit = defineEmits<{ apply: [path: string, folderId: number] }>()

const watchedPathSet = computed(() => new Set(props.watchedPaths.map(normalizePdmPath)))

function isWatched(folder: PdmFolder): boolean {
  return watchedPathSet.value.has(normalizePdmPath(folder.path))
}

function folderOf(node: TreeNode): PdmFolder {
  return node.data as PdmFolder
}

function toNode(folder: PdmFolder): TreeNode {
  return {
    key: String(folder.id),
    label: folder.name,
    leaf: false,
    selectable: props.allowWatched || !isWatched(folder),
    data: folder,
  }
}

const rootLoading = ref(false)
const rootLoadFailed = ref(false)
const nodes = ref<TreeNode[]>([])
const selectionKeys = ref<Record<string, boolean>>({})
const selectedNode = ref<TreeNode | null>(null)
const expandFailedKey = ref<string | null>(null)

watchLoadingBar(rootLoading)

async function loadRoot(): Promise<void> {
  rootLoading.value = true
  rootLoadFailed.value = false
  try {
    const folders = await store.loadPdmFolders(VAULT_ROOT_ID)
    nodes.value = folders.map(toNode)
  } catch {
    rootLoadFailed.value = true
  } finally {
    rootLoading.value = false
  }
}

watch(visible, (isVisible) => {
  if (!isVisible) return
  nodes.value = []
  selectionKeys.value = {}
  selectedNode.value = null
  expandFailedKey.value = null
  void loadRoot()
})

function findNode(list: TreeNode[], key: string): TreeNode | undefined {
  for (const node of list) {
    if (node.key === key) return node
    if (node.children) {
      const found = findNode(node.children, key)
      if (found) return found
    }
  }
  return undefined
}

// Cached per node (children !== undefined once loaded, even when empty) so
// collapsing and re-expanding the same folder never re-fetches it.
async function onNodeExpand(node: TreeNode): Promise<void> {
  if (node.children !== undefined) return
  const folder = folderOf(node)
  node.loading = true
  expandFailedKey.value = null
  try {
    const children = await store.loadPdmFolders(folder.id)
    node.children = children.map(toNode)
    if (children.length === 0) node.leaf = true
  } catch {
    expandFailedKey.value = node.key
  } finally {
    node.loading = false
  }
}

function retryExpand(): void {
  const key = expandFailedKey.value
  const node = key ? findNode(nodes.value, key) : undefined
  if (node) void onNodeExpand(node)
}

function onNodeSelect(node: TreeNode): void {
  selectedNode.value = node
}

function onNodeUnselect(): void {
  selectedNode.value = null
}

function onApply(): void {
  if (!selectedNode.value) return
  const folder = folderOf(selectedNode.value)
  emit('apply', folder.path, folder.id)
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('adminSettings.solidworksPdm.pdm.sync.folderPicker.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div v-if="rootLoading" class="picker-status" />

    <Message v-else-if="rootLoadFailed" severity="error" :closable="false">
      <div class="picker-error">
        <span>{{ t('adminSettings.solidworksPdm.pdm.sync.folderPicker.loadFailed') }}</span>
        <Button :label="t('common.reload')" size="small" text @click="loadRoot" />
      </div>
    </Message>

    <Message v-else-if="nodes.length === 0" severity="info" :closable="false">
      {{ t('adminSettings.solidworksPdm.pdm.sync.folderPicker.empty') }}
    </Message>

    <template v-else>
      <Tree
        :value="nodes"
        v-model:selection-keys="selectionKeys"
        selection-mode="single"
        loading-mode="icon"
        scroll-height="18rem"
        @node-expand="onNodeExpand"
        @node-select="onNodeSelect"
        @node-unselect="onNodeUnselect"
      >
        <template #default="{ node }">
          <span class="folder-node" :class="{ 'folder-node--watched': isWatched(folderOf(node)) }">
            {{ node.label }}
            <span v-if="isWatched(folderOf(node))" class="watched-suffix">
              {{ t('adminSettings.solidworksPdm.pdm.sync.folderPicker.alreadyWatched') }}
            </span>
          </span>
        </template>
      </Tree>

      <Message v-if="expandFailedKey" severity="error" :closable="false">
        <div class="picker-error">
          <span>{{ t('adminSettings.solidworksPdm.pdm.sync.folderPicker.loadFailed') }}</span>
          <Button :label="t('common.reload')" size="small" text @click="retryExpand" />
        </div>
      </Message>
    </template>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('adminSettings.solidworksPdm.pdm.sync.folderPicker.apply')"
        :disabled="!selectedNode"
        @click="onApply"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.picker-status {
  display: flex;
  justify-content: center;
  padding: var(--space-6) 0;
}

.picker-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.folder-node--watched {
  color: var(--p-text-muted-color);
}

.watched-suffix {
  margin-left: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
