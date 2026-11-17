import { fileURLToPath, URL } from 'node:url'

import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import Components from 'unplugin-vue-components/vite'
import Markdown from 'unplugin-vue-markdown/vite'
import anchor from 'markdown-it-anchor'
import attrs from 'markdown-it-attrs'
import { PrimeVueResolver } from '@openvue/auto-import-resolver'

// The handbook's content lives in .md files that are compiled to Vue
// components at build time, so no markdown parser ships to the browser and
// every doc becomes its own lazily-loaded chunk. `vue()` and `Components()`
// both have to be told to look at .md as well, otherwise the generated SFC
// never gets compiled or its components resolved.
const MARKDOWN_INCLUDE = /\.md$/

// @svar-ui ships pre-compiled scoped CSS (the `data-v-` hashes are already
// baked in) that still contains literal `:deep(...)` wherever it sits inside
// `:not()` or `:has()` - their build resolves the wrapper everywhere else but
// not there. Vue's compiler never sees a vendor .css file, so nothing downstream
// unwraps it either, and `:deep` is not a real pseudo-class: `:not()` is
// non-forgiving, so every browser discards those rules outright and the gantt's
// pressed/hover button states silently never apply. lightningcss flags each one,
// which is the 15 warnings a build prints. Inside `:not()`/`:has()` the wrapper
// carries no meaning of its own, so dropping it restores the selector the
// library's author wrote. @svar-ui/vue-gantt 2.8.1 and the vue-core, grid,
// toolbar, menu and editor packages it pulls in still ship these selectors,
// so check their CSS for `:deep(` after an upgrade and remove this once none
// is left.
const VENDOR_DEEP_SELECTOR = /:deep\(([^()]*)\)/g

function stripVendorDeepSelectors(): Plugin {
  return {
    name: 'strip-svar-deep-selectors',
    enforce: 'pre',
    transform(code, id) {
      const path = id.split('?')[0] ?? ''
      if (!path.includes('@svar-ui') || !path.endsWith('.css')) return null
      if (!code.includes(':deep(')) return null
      return { code: code.replace(VENDOR_DEEP_SELECTOR, '$1'), map: null }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    stripVendorDeepSelectors(),
    vue({ include: [/\.vue$/, MARKDOWN_INCLUDE] }),
    Markdown({
      // `vue()` splits the generated SFC back into `foo.md?vue&type=script`
      // sub-requests, and those ids still end in .md as far as a naive filter
      // is concerned. Without this they get fed through markdown a second
      // time and the compiled script comes back wrapped in a <template>.
      exclude: [/\?vue/],
      headEnabled: false,
      markdownItSetup(md) {
        // `attrs` first so a heading written as `## Title {#scope}` keeps that
        // exact id, and `anchor` only slugifies the headings that lack one.
        // Handbook docs rely on this: the drawer deep-links to `#scope`, and a
        // text-derived id would differ between the English and German copy.
        md.use(attrs)
        md.use(anchor, { tabIndex: false })
      },
    }),
    vueDevTools(),
    Components({
      include: [/\.vue$/, /\.vue\?vue/, MARKDOWN_INCLUDE],
      // `<Button>` resolves to the app's wrapper, which keeps a loading
      // button disabled (src/core/components/GladosButton.ts).
      resolvers: [
        PrimeVueResolver({
          resolve: (meta, type) =>
            type === 'component' && meta.name === 'Button'
              ? { from: '@/core/components/GladosButton' }
              : undefined,
        }),
      ],
      dts: 'src/components.d.ts',
    }),
  ],
  css: {
    preprocessorOptions: {
      // Every SCSS block, global or scoped, sees the breakpoint scale without
      // its own @use. The partial holds variables only, so it adds no CSS.
      scss: { additionalData: `@use '@/assets/styles/breakpoints' as *;\n` },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  // npm sets `npm_package_version` from package.json for every `npm run`
  // script (dev, build, and vitest via `npm run test:unit`/`test:unit:run`),
  // so this is the single source of truth for the running app's version -
  // nothing here reads a separate VERSION file or env var. Falls back to
  // '0.0.0' for anything that invokes vite directly (bypassing npm), which
  // useVersionCheck treats as "unbuilt dev copy" and never flags as a
  // mismatch. vitest.config.ts merges this in via `mergeConfig(viteConfig,
  // ...)`, so __APP_VERSION__ is available in tests without its own define.
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? '0.0.0'),
  },
  build: {
    // `three` (~724 kB) and `xlsx` (~493 kB) are the only chunks over the 500 kB
    // default, and both sit behind `await import()` (MeshViewer.vue,
    // parseExcelDemandsFile.ts) so neither reaches the initial page load.
    // Raised so the warning stays meaningful instead of firing on every build.
    chunkSizeWarningLimit: 800,
  },
})
