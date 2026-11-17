<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { HANDBOOK_SECTIONS } from '../utils/handbookSections'
import { provideHandbookOutline } from '../utils/handbookOutline'
import { loadHandbookTree, type HandbookSectionDocs } from '../utils/handbookContent'
import type { AppLocale } from '@/core/i18n'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()

// The tree is visible on every handbook page, so the layout loads it once
// rather than each page doing it. loadHandbookTree memoises per locale, so
// moving between pages re-imports nothing.
const sections = ref<HandbookSectionDocs[]>([])
const loading = ref(true)

watch(
  locale,
  async (current) => {
    loading.value = true
    sections.value = await loadHandbookTree(current as AppLocale)
    loading.value = false
  },
  { immediate: true },
)

// Filled in by whichever page is rendering markdown below us.
const outline = provideHandbookOutline()

const activeSection = computed(() =>
  typeof route.params.section === 'string' ? route.params.section : undefined,
)

const activePage = computed(() =>
  typeof route.params.page === 'string' ? route.params.page : undefined,
)

const tabs = computed(() => HANDBOOK_SECTIONS.map((meta) => ({ ...meta, label: t(meta.labelKey) })))

const sectionLabel = computed(() => {
  const meta = HANDBOOK_SECTIONS.find((entry) => entry.key === activeSection.value)
  return meta ? t(meta.labelKey) : undefined
})

const pages = computed(
  () => sections.value.find((entry) => entry.section === activeSection.value)?.docs ?? [],
)

function onSelectSection(value: string | number) {
  const section = String(value)
  if (section === activeSection.value) return
  // Land on the section's first page when it has one, so picking a tab shows
  // content rather than an index the reader has to click through.
  const docs = sections.value.find((entry) => entry.section === section)?.docs ?? []
  const first = docs[0]
  void router.push(
    first
      ? { name: 'HandbookPage', params: { section, page: first.page } }
      : { name: 'HandbookSection', params: { section } },
  )
}

function scrollToHeading(id: string) {
  // The centre column scrolls, so scrollIntoView suffices. Smoothness comes
  // from the column's scroll-behavior, which respects reduced motion.
  document.getElementById(id)?.scrollIntoView?.({ block: 'start' })
}
</script>

<template>
  <div class="section-view">
    <!-- Empty on the index, which matches no tab. The rail still shows the
         whole app, just with nothing selected yet. -->
    <Tabs :value="activeSection ?? ''" class="section-tabs" @update:value="onSelectSection">
      <TabList class="section-tablist">
        <Tab v-for="tab in tabs" :key="tab.key" :value="tab.key">
          <i :class="`mdi ${tab.icon} tab-icon`" aria-hidden="true" />
          {{ tab.label }}
        </Tab>
      </TabList>
    </Tabs>

    <div class="handbook-columns">
      <aside class="card handbook-aside">
        <h2 class="handbook-aside-title">{{ sectionLabel ?? t('handbook.title') }}</h2>

        <div class="handbook-aside-body">
          <Skeleton v-if="loading" height="1.5rem" />

          <p v-else-if="!activeSection" class="handbook-aside-hint">
            {{ t('handbook.pickSection') }}
          </p>

          <p v-else-if="pages.length === 0" class="handbook-aside-hint">
            {{ t('handbook.sectionEmpty') }}
          </p>

          <RouterLink
            v-for="doc in pages"
            :key="doc.slug"
            class="handbook-aside-link"
            :class="{ 'handbook-aside-link-current': doc.page === activePage }"
            :to="{ name: 'HandbookPage', params: { section: doc.section, page: doc.page } }"
          >
            {{ doc.frontmatter.title }}
          </RouterLink>
        </div>
      </aside>

      <main class="card handbook-main">
        <!-- One frame for every handbook route. The index, a section and a doc
             page must line up exactly, otherwise the content shifts sideways
             and down as you move between them. -->
        <div class="handbook-page-frame">
          <RouterView />
        </div>
      </main>

      <aside class="card handbook-aside">
        <h2 class="handbook-aside-title">{{ t('handbook.onThisPage') }}</h2>

        <div class="handbook-aside-body">
          <p v-if="outline.length === 0" class="handbook-aside-hint">
            {{ t('handbook.noHeadings') }}
          </p>

          <a
            v-for="heading in outline"
            :key="heading.id"
            class="handbook-aside-link"
            :class="{ 'handbook-aside-link-nested': heading.level > 2 }"
            :href="`#${heading.id}`"
            @click.prevent="scrollToHeading(heading.id)"
          >
            {{ heading.text }}
          </a>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss">
.section-view {
  height: calc(100% + 1rem);
  margin: -0.5rem;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.section-tabs {
  flex-shrink: 0;
}

.section-tablist {
  flex-shrink: 0;
}

.tab-icon {
  margin-right: var(--space-1);
}

// Three full-height columns: section pages, the doc, and the doc's own
// headings. `.card` already carries height:100% + min-height:0, so each one
// scrolls inside itself rather than growing the page.
.handbook-columns {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 19rem minmax(0, 1fr) 19rem;
  gap: var(--space-2);
  padding: var(--space-2);
}

.handbook-aside {
  overflow: hidden;
  gap: var(--space-2);
}

.handbook-aside-title {
  flex-shrink: 0;
  margin: 0;
  padding: var(--space-1) var(--space-1) var(--space-2);
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: var(--font-size-sm);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--p-text-muted-color);
}

.handbook-aside-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  // Same reason as .handbook-main: a long outline must not narrow the rail
  // relative to a short one.
  scrollbar-gutter: stable;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.handbook-aside-link {
  padding: var(--space-2) var(--space-2);
  border-left: 0.2rem solid transparent;
  border-radius: var(--p-content-border-radius);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  line-height: 1.35;
  text-decoration: none;
}

.handbook-aside-link:hover {
  background: var(--p-content-hover-background);
  color: var(--p-text-color);
}

.handbook-aside-link-current {
  border-left-color: var(--p-primary-color);
  background: var(--p-highlight-background);
  color: var(--p-highlight-color);
  font-weight: 600;
}

.handbook-aside-link-nested {
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
}

.handbook-aside-hint {
  margin: 0;
  padding: var(--space-2) var(--space-2);
  font-size: var(--font-size-sm);
  font-style: italic;
  color: var(--p-text-muted-color);
}

.handbook-page-frame {
  max-width: 52rem;
  // `.card` already pads by 0.5rem, so this lands at 1rem from the card edge,
  // the same density the tab panels elsewhere in the app use.
  padding: var(--space-2);
  margin: 0 auto;
}

.handbook-main {
  overflow-y: auto;
  // Reserve the scrollbar track even when the page is short enough not to need
  // one. Without this the index (no scrollbar) and a long doc (scrollbar) get
  // different content widths, so the text shifts as you move between them.
  scrollbar-gutter: stable;
  // Jumping to a heading from the outline animates instead of teleporting, so
  // the reader can see where in the doc they landed.
  scroll-behavior: smooth;
  padding-top: var(--space-6);
}

@media (prefers-reduced-motion: reduce) {
  .handbook-main {
    scroll-behavior: auto;
  }
}

// The two rails are navigation aids, not content. Drop the outline first and
// the section list second rather than squeezing the prose.
@media (max-width: $bp-xl) {
  .handbook-columns {
    grid-template-columns: 19rem minmax(0, 1fr);
  }

  .handbook-aside:last-child {
    display: none;
  }
}

@media (max-width: $bp-md) {
  .handbook-columns {
    grid-template-columns: minmax(0, 1fr);
  }

  .handbook-aside {
    display: none;
  }
}
</style>
