/**
 * Ergonomic entry point for the generated API schema: re-exports the
 * generated `components["schemas"]` map under a shorter name so hand-written
 * types can alias a named schema instead of writing
 * `components["schemas"]["Foo"]` at every call site.
 *
 * The generated file itself (webSchema.ts) is never imported directly
 * outside this directory: go through here so there is one place that
 * knows the generated file's exact shape.
 */
import type { components } from './webSchema'

export type Schemas = components['schemas']
