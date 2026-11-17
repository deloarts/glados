<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@/core/composables/useClipboard'

import { API_KEY_BASE_URL, getApiKeyOpenApiSpec } from '../api/apiKeyDocsApi'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type {
  OpenApiOperation,
  OpenApiParameter,
  OpenApiSchema,
  OpenApiSpec,
} from '../types/openApiTypes'

const { t } = useI18n()
const { copyToClipboard } = useClipboard()

const emit = defineEmits<{ close: [] }>()

/** Everything else in a path item (summary, servers, …) is metadata, not an operation. */
const HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

const METHOD_SEVERITY: Record<string, string> = {
  GET: 'info',
  POST: 'success',
  PUT: 'warn',
  PATCH: 'warn',
  DELETE: 'danger',
}

interface DocResponseEntry {
  code: string
  description: string
  type: string
  /** Set when the response body is a named component schema we can expand. */
  schemaName: string | null
}

interface DocField {
  name: string
  type: string
  required: boolean
  description: string
}

interface DocOperation {
  key: string
  method: string
  path: string
  summary: string
  description: string
  parameters: OpenApiParameter[]
  requestBodyType: string | null
  responses: DocResponseEntry[]
  fields: DocField[]
  curl: string
}

interface DocGroup {
  tag: string
  label: string
  operations: DocOperation[]
}

const spec = ref<OpenApiSpec | null>(null)
const loading = ref(false)
const loadFailed = ref(false)

watchLoadingBar(loading)

/** Header the API key goes in, read off the spec so it tracks the backend. */
const authHeader = computed(() => {
  const schemes = spec.value?.components?.securitySchemes ?? {}
  const apiKeyScheme = Object.values(schemes).find((s) => s.type === 'apiKey')
  return apiKeyScheme?.name ?? 'X-Api-Key'
})

function refName(ref: string): string {
  return ref.split('/').pop() ?? ref
}

function formatSchema(schema?: OpenApiSchema): string {
  if (!schema) return getEmptyPlaceholder()
  if (schema.$ref) return refName(schema.$ref)
  if (schema.anyOf) return schema.anyOf.map(formatSchema).join(' | ')
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(' | ')
  if (schema.type === 'array') return `${formatSchema(schema.items)}[]`
  if (schema.type && schema.format) return `${schema.type} (${schema.format})`
  return schema.type ?? 'any'
}

function schemaNameOf(schema?: OpenApiSchema): string | null {
  if (!schema) return null
  if (schema.$ref) return refName(schema.$ref)
  if (schema.type === 'array' && schema.items?.$ref) return refName(schema.items.$ref)
  return null
}

/** One level deep, nested component schemas stay as their type name. */
function resolveFields(schemaName: string | null): DocField[] {
  if (!schemaName) return []

  const resolved = spec.value?.components?.schemas?.[schemaName]
  if (!resolved?.properties) return []

  const required = new Set(resolved.required ?? [])

  return Object.entries(resolved.properties).map(([name, property]) => ({
    name,
    type: formatSchema(property),
    required: required.has(name),
    description: property.description ?? '',
  }))
}

function buildCurl(method: string, path: string): string {
  const verb = method === 'GET' ? '' : `-X ${method} `
  return `curl ${verb}-H "${authHeader.value}: $GLADOS_API_KEY" \\\n  "${API_KEY_BASE_URL}${path}"`
}

function buildOperation(method: string, path: string, operation: OpenApiOperation): DocOperation {
  const responses: DocResponseEntry[] = Object.entries(operation.responses ?? {}).map(
    ([code, response]) => {
      const schema = response.content?.['application/json']?.schema
      return {
        code,
        description: response.description ?? '',
        type: formatSchema(schema),
        schemaName: schemaNameOf(schema),
      }
    },
  )

  const successSchema = responses.find((response) => response.code.startsWith('2'))?.schemaName
  const requestSchema = operation.requestBody?.content?.['application/json']?.schema

  return {
    key: operation.operationId ?? `${method}-${path}`,
    method,
    path,
    summary: operation.summary ?? '',
    description: operation.description ?? '',
    parameters: operation.parameters ?? [],
    requestBodyType: requestSchema ? formatSchema(requestSchema) : null,
    responses,
    fields: resolveFields(successSchema ?? null),
    curl: buildCurl(method, path),
  }
}

/** Tags are namespaced per surface ("key/products"), the prefix is noise here. */
function groupLabel(tag: string): string {
  const name = tag.includes('/') ? tag.slice(tag.indexOf('/') + 1) : tag
  return name.charAt(0).toUpperCase() + name.slice(1)
}

const groups = computed<DocGroup[]>(() => {
  if (!spec.value) return []

  const byTag = new Map<string, DocOperation[]>()

  for (const [path, pathItem] of Object.entries(spec.value.paths)) {
    for (const [rawMethod, operation] of Object.entries(pathItem)) {
      if (!HTTP_METHODS.includes(rawMethod)) continue

      const doc = buildOperation(rawMethod.toUpperCase(), path, operation)

      for (const tag of operation.tags ?? ['other']) {
        const bucket = byTag.get(tag)
        if (bucket) bucket.push(doc)
        else byTag.set(tag, [doc])
      }
    }
  }

  return [...byTag.entries()]
    .map(([tag, operations]) => ({
      tag,
      label: groupLabel(tag),
      operations: operations.sort(
        (a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method),
      ),
    }))
    .sort((a, b) => a.label.localeCompare(b.label))
})

const isEmpty = computed(() => !loading.value && !loadFailed.value && groups.value.length === 0)

async function load(): Promise<void> {
  loading.value = true
  loadFailed.value = false

  try {
    spec.value = await getApiKeyOpenApiSpec()
  } catch {
    spec.value = null
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function copy(value: string): Promise<void> {
  await copyToClipboard(value)
}

onMounted(load)
</script>

<template>
  <Panel class="docs-panel fill-panel">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('settings.apiKeys.docs.title') }}</span>
        <div class="panel-header-actions">
          <Tag v-if="spec" severity="secondary" :value="`v${spec.info.version}`" />
          <Button
            icon="mdi mdi-close"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="t('common.close')"
            :aria-label="t('common.close')"
            @click="emit('close')"
          />
        </div>
      </div>
    </template>

    <div class="docs-body">
      <div v-if="loading" class="docs-status" />

      <Message v-else-if="loadFailed" severity="error" :closable="false">
        <div class="docs-error">
          <span>{{ t('settings.apiKeys.docs.loadFailed') }}</span>
          <Button :label="t('common.reload')" size="small" text @click="load" />
        </div>
      </Message>

      <template v-else>
        <div class="docs-meta">
          <div class="meta-row">
            <span class="meta-label">{{ t('settings.apiKeys.docs.baseUrl') }}</span>
            <code class="meta-value">{{ API_KEY_BASE_URL }}</code>
            <Button
              icon="mdi mdi-content-copy"
              size="small"
              severity="secondary"
              text
              v-tooltip.top.focus="t('common.copy')"
              :aria-label="t('common.copy')"
              @click="copy(API_KEY_BASE_URL)"
            />
          </div>
          <div class="meta-row">
            <span class="meta-label">{{ t('settings.apiKeys.docs.auth') }}</span>
            <code class="meta-value">{{ authHeader }}: &lt;key&gt;</code>
            <Button
              icon="mdi mdi-content-copy"
              size="small"
              severity="secondary"
              text
              v-tooltip.top.focus="t('common.copy')"
              :aria-label="t('common.copy')"
              @click="copy(authHeader)"
            />
          </div>
          <p class="meta-hint">{{ t('settings.apiKeys.docs.authHint') }}</p>
        </div>

        <Message v-if="isEmpty" severity="info" :closable="false">
          {{ t('settings.apiKeys.docs.empty') }}
        </Message>

        <div v-for="group in groups" :key="group.tag" class="docs-group">
          <div class="group-title">{{ group.label }}</div>

          <Accordion multiple>
            <AccordionPanel
              v-for="operation in group.operations"
              :key="operation.key"
              :value="operation.key"
            >
              <AccordionHeader>
                <div class="op-header">
                  <Tag
                    class="op-method"
                    :severity="METHOD_SEVERITY[operation.method] ?? 'secondary'"
                    :value="operation.method"
                  />
                  <code class="op-path">{{ operation.path }}</code>
                </div>
              </AccordionHeader>

              <AccordionContent>
                <div class="op-body">
                  <p v-if="operation.summary" class="op-summary">{{ operation.summary }}</p>
                  <p v-if="operation.description" class="op-description">
                    {{ operation.description }}
                  </p>

                  <section v-if="operation.parameters.length > 0" class="op-section">
                    <h4>{{ t('settings.apiKeys.docs.parameters') }}</h4>
                    <ul class="op-list">
                      <li
                        v-for="parameter in operation.parameters"
                        :key="`${parameter.in}-${parameter.name}`"
                      >
                        <code>{{ parameter.name }}</code>
                        <span class="op-type">{{ formatSchema(parameter.schema) }}</span>
                        <Tag severity="secondary" :value="parameter.in" />
                        <Tag
                          v-if="parameter.required"
                          severity="danger"
                          :value="t('settings.apiKeys.docs.required')"
                        />
                        <span v-if="parameter.description" class="op-note">{{
                          parameter.description
                        }}</span>
                      </li>
                    </ul>
                  </section>

                  <section v-if="operation.requestBodyType" class="op-section">
                    <h4>{{ t('settings.apiKeys.docs.requestBody') }}</h4>
                    <code>{{ operation.requestBodyType }}</code>
                  </section>

                  <section v-if="operation.responses.length > 0" class="op-section">
                    <h4>{{ t('settings.apiKeys.docs.responses') }}</h4>
                    <ul class="op-list">
                      <li v-for="response in operation.responses" :key="response.code">
                        <Tag
                          :severity="response.code.startsWith('2') ? 'success' : 'warn'"
                          :value="response.code"
                        />
                        <span class="op-type">{{ response.type }}</span>
                        <span v-if="response.description" class="op-note">{{
                          response.description
                        }}</span>
                      </li>
                    </ul>
                  </section>

                  <section v-if="operation.fields.length > 0" class="op-section">
                    <h4>{{ t('settings.apiKeys.docs.responseFields') }}</h4>
                    <ul class="op-list">
                      <li v-for="field in operation.fields" :key="field.name">
                        <code>{{ field.name }}</code>
                        <span class="op-type">{{ field.type }}</span>
                        <Tag
                          v-if="field.required"
                          severity="danger"
                          :value="t('settings.apiKeys.docs.required')"
                        />
                        <span v-if="field.description" class="op-note">{{
                          field.description
                        }}</span>
                      </li>
                    </ul>
                  </section>

                  <section class="op-section">
                    <div class="op-example-head">
                      <h4>{{ t('settings.apiKeys.docs.example') }}</h4>
                      <Button
                        icon="mdi mdi-content-copy"
                        size="small"
                        severity="secondary"
                        text
                        v-tooltip.top.focus="t('common.copy')"
                        :aria-label="t('common.copy')"
                        @click="copy(operation.curl)"
                      />
                    </div>
                    <pre class="op-curl">{{ operation.curl }}</pre>
                  </section>
                </div>
              </AccordionContent>
            </AccordionPanel>
          </Accordion>
        </div>
      </template>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.docs-panel {
  flex: 0 0 auto;
  width: 34rem;
  max-width: 100%;
  --fill-panel-overflow-y: hidden;
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-2);
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.docs-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.docs-status {
  display: flex;
  justify-content: center;
  padding: var(--space-6) 0;
}

.docs-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.docs-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
}

.meta-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.meta-label {
  flex: 0 0 5.5rem;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.meta-value {
  flex: 1;
  min-width: 0;
  font-family: monospace;
  font-size: var(--font-size-sm);
  overflow-x: auto;
  white-space: nowrap;
}

.meta-hint {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.docs-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.group-title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.op-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.op-method {
  flex: 0 0 auto;
  font-size: var(--font-size-xs);
}

.op-path {
  font-family: monospace;
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
  text-align: left;
}

.op-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.op-summary {
  margin: 0;
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.op-description {
  margin: 0;
  font-size: var(--font-size-sm);
  white-space: pre-line;
  color: var(--p-text-muted-color);
}

.op-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  h4 {
    margin: 0;
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--p-text-muted-color);
  }

  code {
    font-family: monospace;
    font-size: var(--font-size-sm);
  }
}

.op-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  li {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
}

.op-type {
  font-family: monospace;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.op-note {
  flex-basis: 100%;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.op-example-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.op-curl {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--p-content-border-radius);
  background: var(--p-surface-100);
  font-family: monospace;
  font-size: var(--font-size-xs);
  line-height: 1.5;
  overflow-x: auto;
}
</style>
