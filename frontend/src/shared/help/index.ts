// Public surface of the in-app help. A page drops a HelpButton into its
// toolbar, or opens a HelpDrawer from its own explain button, and a component
// a help doc embeds reads the page's state through useHelpContext(). The help
// itself comes from the provider the app shell installs (the handbook), so
// nothing here or in a feature imports the handbook directly.
export { default as HelpButton } from './HelpButton.vue'
export { default as HelpDrawer } from './HelpDrawer.vue'
export { helpContextKey, helpProviderKey, useHelp, useHelpContext } from './useHelp'
export type { HelpContext, HelpProvider } from './useHelp'
