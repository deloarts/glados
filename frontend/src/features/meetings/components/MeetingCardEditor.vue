<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import type { JSONContent } from '@tiptap/core'

import { useUsersStore } from '@/core/stores/usersStore'
import { docToMarkdown, markdownToDoc } from '../utils/cardMarkdown'
import { cardEditorExtensions, LINK_PATTERN } from '../utils/cardEditorExtensions'
import { useMentionSuggestion } from '../composables/useMentionSuggestion'
import { activePeople } from '../utils/todoOwners'

/**
 * The editor of one card: a Visual mode on Tiptap and a Markdown mode over
 * the same text, which is Markdown in the subset of meeting cards either
 * way. Typing `@` suggests Glados users, and an image pasted, dropped or
 * picked is uploaded as a meeting file of the card and shown in the text.
 */
const props = defineProps<{
  imageUrl?: (fileId: number) => string | undefined
  /** Bumped whenever another image finished loading, so the editor shows it. */
  imageVersion?: number
  uploadImage?: (file: File) => Promise<{ id: number; name: string } | null>
}>()

const body = defineModel<string>({ required: true })

const { t } = useI18n()
const uid = useId()
const usersStore = useUsersStore()
void usersStore.ensureLoaded()

const mode = ref<'visual' | 'markdown'>('visual')
const modeOptions = computed(() => [
  { value: 'visual', label: t('meetings.editor.visual') },
  { value: 'markdown', label: t('meetings.editor.markdown') },
])

const userName = (id: number) => usersStore.users.find((user) => user.id === id)?.full_name
const mention = useMentionSuggestion(() => activePeople(usersStore.users))

// The text last written to or read from the editor, so an outside change,
// such as a restored draft or a merge, can be told apart from typing.
let synced = body.value
const uploading = ref(false)

const editor = useEditor({
  extensions: cardEditorExtensions({
    placeholder: t('meetings.editor.placeholder'),
    userName,
    imageUrl: (fileId) => props.imageUrl?.(fileId),
    mentionSuggestion: mention.suggestion,
  }),
  content: markdownToDoc(body.value) as JSONContent,
  editorProps: {
    attributes: { class: 'card-editor-content', 'aria-label': t('meetings.editor.label') },
    handlePaste: (_view, event) => uploadFiles(event.clipboardData?.files),
    handleDrop: (_view, event) => uploadFiles((event as DragEvent).dataTransfer?.files),
  },
  onUpdate: ({ editor: current }) => {
    synced = docToMarkdown(current.getJSON())
    body.value = synced
  },
})

watch(body, (value) => {
  if (value === synced) return
  synced = value
  if (mode.value === 'visual') editor.value?.commands.setContent(markdownToDoc(value) as JSONContent, { emitUpdate: false })
})

watch(mode, (next) => {
  if (next === 'visual') editor.value?.commands.setContent(markdownToDoc(body.value) as JSONContent, { emitUpdate: false })
  synced = body.value
})

watch(
  () => props.imageVersion,
  () => {
    editor.value?.view.dom.querySelectorAll<HTMLImageElement>('img[data-file-id]').forEach((img) => {
      const url = props.imageUrl?.(Number(img.dataset.fileId))
      if (url && img.src !== url) img.src = url
    })
  },
)

onBeforeUnmount(() => editor.value?.destroy())

// ── Images ────────────────────────────────────────────────────────────

const textarea = useTemplateRef<{ $el: HTMLTextAreaElement }>('textarea')
const fileInput = useTemplateRef<HTMLInputElement>('fileInput')

function insertImage(id: number, name: string): void {
  if (mode.value === 'visual') {
    editor.value?.chain().focus().insertContent({ type: 'image', attrs: { fileId: id, alt: name } }).run()
    return
  }
  const element = textarea.value?.$el
  const text = `![${name.replace(/[[\]\n]/g, '')}](file:${id})`
  const at = element?.selectionStart ?? body.value.length
  body.value = body.value.slice(0, at) + text + body.value.slice(element?.selectionEnd ?? at)
}

/** Uploads the images among `files`; true when there was one to handle. */
function uploadFiles(files: FileList | null | undefined): boolean {
  const images = [...(files ?? [])].filter((file) => file.type.startsWith('image/'))
  if (!images.length || !props.uploadImage) return false
  void (async () => {
    uploading.value = true
    try {
      for (const file of images) {
        const uploaded = await props.uploadImage?.(file)
        if (uploaded) insertImage(uploaded.id, uploaded.name)
      }
    } finally {
      uploading.value = false
    }
  })()
  return true
}

function onFilePicked(event: Event): void {
  const input = event.target as HTMLInputElement
  uploadFiles(input.files)
  input.value = ''
}

// ── Links ─────────────────────────────────────────────────────────────

const linkPopover = ref<{ toggle: (event: Event) => void; hide: () => void } | null>(null)
const linkUrl = ref('')
const linkValid = computed(() => LINK_PATTERN.test(linkUrl.value.trim()))

function openLink(event: Event): void {
  linkUrl.value = String(editor.value?.getAttributes('link').href ?? '')
  linkPopover.value?.toggle(event)
}

function applyLink(): void {
  if (!linkValid.value) return
  editor.value?.chain().focus().extendMarkRange('link').setLink({ href: linkUrl.value.trim() }).run()
  linkPopover.value?.hide()
}

function removeLink(): void {
  editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
  linkPopover.value?.hide()
}

// ── Toolbar ───────────────────────────────────────────────────────────

interface Tool {
  key: string
  icon: string
  active: () => boolean
  run: () => void
}

const tools: Tool[] = [
  { key: 'bold', icon: 'mdi-format-bold', active: () => !!editor.value?.isActive('bold'), run: () => editor.value?.chain().focus().toggleBold().run() },
  { key: 'italic', icon: 'mdi-format-italic', active: () => !!editor.value?.isActive('italic'), run: () => editor.value?.chain().focus().toggleItalic().run() },
  {
    key: 'heading',
    icon: 'mdi-format-header-3',
    active: () => !!editor.value?.isActive('heading'),
    run: () => editor.value?.chain().focus().toggleHeading({ level: 3 }).run(),
  },
  {
    key: 'bulletList',
    icon: 'mdi-format-list-bulleted',
    active: () => !!editor.value?.isActive('bulletList'),
    run: () => editor.value?.chain().focus().toggleBulletList().run(),
  },
  {
    key: 'orderedList',
    icon: 'mdi-format-list-numbered',
    active: () => !!editor.value?.isActive('orderedList'),
    run: () => editor.value?.chain().focus().toggleOrderedList().run(),
  },
  { key: 'code', icon: 'mdi-code-tags', active: () => !!editor.value?.isActive('code'), run: () => editor.value?.chain().focus().toggleCode().run() },
  { key: 'mention', icon: 'mdi-at', active: () => false, run: () => editor.value?.chain().focus().insertContent('@').run() },
]

function focus(): void {
  if (mode.value === 'visual') editor.value?.commands.focus('end')
  else textarea.value?.$el.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="card-editor" data-testid="meeting-card-editor">
    <div class="editor-bar" role="toolbar" :aria-label="t('meetings.editor.toolbar')">
      <SelectButton
        v-model="mode"
        :options="modeOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        :aria-label="t('meetings.editor.mode')"
        data-testid="meeting-editor-mode"
      />
      <Button
        v-for="tool in tools"
        :key="tool.key"
        :icon="`mdi ${tool.icon}`"
        size="small"
        severity="secondary"
        :text="!(mode === 'visual' && tool.active())"
        :disabled="mode !== 'visual'"
        v-tooltip.top="t(`meetings.editor.tools.${tool.key}`)"
        :aria-label="t(`meetings.editor.tools.${tool.key}`)"
        @click="tool.run"
      />
      <Button
        icon="mdi mdi-link-variant"
        size="small"
        severity="secondary"
        text
        :disabled="mode !== 'visual'"
        v-tooltip.top="t('meetings.editor.tools.link')"
        :aria-label="t('meetings.editor.tools.link')"
        @click="openLink"
      />
      <Button
        v-if="uploadImage"
        icon="mdi mdi-image-plus-outline"
        size="small"
        severity="secondary"
        text
        :loading="uploading"
        v-tooltip.top="t('meetings.editor.tools.image')"
        :aria-label="t('meetings.editor.tools.image')"
        @click="fileInput?.click()"
      />
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        multiple
        hidden
        :aria-label="t('meetings.editor.tools.image')"
        @change="onFilePicked"
      />
    </div>

    <EditorContent v-show="mode === 'visual'" :editor="editor" class="card-editor-visual" />
    <template v-if="mode === 'markdown'">
      <Textarea
        :id="`${uid}-markdown`"
        ref="textarea"
        v-model="body"
        rows="8"
        auto-resize
        spellcheck="true"
        :aria-label="t('meetings.editor.markdownLabel')"
        class="card-editor-markdown"
        fluid
        data-testid="meeting-editor-markdown"
      />
      <small class="hint">{{ t('meetings.editor.markdownHint') }}</small>
    </template>

    <Popover ref="linkPopover">
      <div class="link-form">
        <label :for="`${uid}-link`">{{ t('meetings.editor.linkUrl') }}</label>
        <InputText
          :id="`${uid}-link`"
          v-model="linkUrl"
          placeholder="https://"
          :invalid="!!linkUrl && !linkValid"
          fluid
          @keydown.enter.prevent="applyLink"
        />
        <small class="hint">{{ t('meetings.editor.linkHint') }}</small>
        <div class="link-actions">
          <Button :label="t('meetings.editor.removeLink')" severity="secondary" text size="small" @click="removeLink" />
          <Button :label="t('meetings.editor.applyLink')" size="small" :disabled="!linkValid" @click="applyLink" />
        </div>
      </div>
    </Popover>

    <Teleport to="body">
      <ul
        v-if="mention.state.open && mention.state.items.length"
        class="mention-popup"
        role="listbox"
        :aria-label="t('meetings.editor.mentionList')"
        :style="{ left: `${mention.state.left}px`, top: `${mention.state.top}px` }"
        data-testid="meeting-mention-popup"
      >
        <!-- The editor keeps the focus while the popup is open; the arrow keys move through it. -->
        <!-- eslint-disable-next-line vuejs-accessibility/interactive-supports-focus -->
        <li
          v-for="(item, index) in mention.state.items"
          :key="item.id"
          role="option"
          :aria-selected="index === mention.state.index"
          :class="{ active: index === mention.state.index }"
          @mousedown.prevent="mention.pick(index)"
        >
          <i class="mdi mdi-account-outline" aria-hidden="true" />
          {{ item.label }}
        </li>
      </ul>
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
.card-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.editor-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

.card-editor-visual :deep(.card-editor-content) {
  min-height: 6rem;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  outline: none;

  &:focus {
    border-color: var(--p-primary-color);
  }

  p {
    margin: 0 0 var(--space-2);
  }

  h3 {
    margin: var(--space-2) 0;
    font-size: var(--font-size-md);
  }

  ul,
  ol {
    margin: 0 0 var(--space-2);
    padding-left: var(--space-5);
  }

  p.is-editor-empty:first-child::before {
    content: attr(data-placeholder);
    float: left;
    height: 0;
    color: var(--p-text-muted-color);
    pointer-events: none;
  }

  .card-image {
    max-width: 100%;
    max-height: 16rem;
  }

  .card-mention {
    padding: 0 var(--space-1);
    border-radius: var(--p-border-radius-sm);
    background: var(--p-highlight-background);
    color: var(--p-highlight-color);
  }
}

.card-editor-markdown {
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
}

.link-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 20rem;
}

.link-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-1);
}

.mention-popup {
  position: fixed;
  z-index: 1200;
  margin: 0;
  padding: var(--space-1);
  list-style: none;
  min-width: 12rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  box-shadow: var(--shadow-md);

  li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--p-border-radius-sm);
    cursor: pointer;

    &.active {
      background: var(--p-content-hover-background);
    }
  }
}
</style>
