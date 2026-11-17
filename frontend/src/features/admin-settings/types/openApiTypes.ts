/**
 * Minimal OpenAPI 3.1 shapes, only the parts the API docs panel renders.
 *
 * The backend serves a per-surface, tag-filtered schema (see the backend's
 * `api/docs.py`), so these describe that subset rather than the full spec.
 */

export interface OpenApiSchema {
  $ref?: string
  type?: string
  format?: string
  title?: string
  description?: string
  enum?: unknown[]
  items?: OpenApiSchema
  anyOf?: OpenApiSchema[]
  properties?: Record<string, OpenApiSchema>
  required?: string[]
}

export interface OpenApiParameter {
  name: string
  in: 'path' | 'query' | 'header' | 'cookie'
  required?: boolean
  description?: string
  schema?: OpenApiSchema
}

export interface OpenApiMediaType {
  schema?: OpenApiSchema
}

export interface OpenApiRequestBody {
  required?: boolean
  content?: Record<string, OpenApiMediaType>
}

export interface OpenApiResponse {
  description?: string
  content?: Record<string, OpenApiMediaType>
}

export interface OpenApiOperation {
  tags?: string[]
  summary?: string
  description?: string
  operationId?: string
  parameters?: OpenApiParameter[]
  requestBody?: OpenApiRequestBody
  responses?: Record<string, OpenApiResponse>
  security?: Record<string, string[]>[]
}

export interface OpenApiSecurityScheme {
  type: string
  in?: string
  name?: string
}

export interface OpenApiSpec {
  openapi: string
  info: { title: string; version: string }
  paths: Record<string, Record<string, OpenApiOperation>>
  components?: {
    schemas?: Record<string, OpenApiSchema>
    securitySchemes?: Record<string, OpenApiSecurityScheme>
  }
}
