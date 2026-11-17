/// <reference types="vite/client" />

// Handbook content: unplugin-vue-markdown compiles every .md file into a Vue
// component. Each frontmatter key comes out as its own named export, which
// handbookContent.ts collects back into one object.
declare module '*.md' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Injected at build/dev/test time by vite.config.ts's `define`, from
// package.json's `version` - see useVersionCheck.ts for what reads this.
declare const __APP_VERSION__: string
