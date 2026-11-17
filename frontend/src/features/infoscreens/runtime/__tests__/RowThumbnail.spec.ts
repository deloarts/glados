import { describe, it, expect, vi, afterEach } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

// The API root is read when the module loads, so every test imports a fresh
// copy after setting VITE_API_URL.
async function mountThumbnail(apiUrl: string, url: string | null) {
  vi.stubEnv('VITE_API_URL', apiUrl)
  vi.resetModules()
  const { default: RowThumbnail } = await import('../components/widgets/RowThumbnail.vue')
  return mountWithApp(RowThumbnail, { props: { url } })
}

describe('RowThumbnail', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('puts the API root in front of a root-relative thumbnail path', async () => {
    const wrapper = await mountThumbnail('http://localhost:3000', '/api/v1/web/terminal-device/thumbnails/t')

    expect(wrapper.get('[data-testid="row-thumbnail"]').attributes('src')).toBe(
      'http://localhost:3000/api/v1/web/terminal-device/thumbnails/t',
    )
  })

  it('keeps a root-relative path as it is when the API shares the page origin', async () => {
    const wrapper = await mountThumbnail('', '/api/v1/web/terminal-device/thumbnails/t')

    expect(wrapper.get('[data-testid="row-thumbnail"]').attributes('src')).toBe(
      '/api/v1/web/terminal-device/thumbnails/t',
    )
  })

  it('leaves an absolute URL untouched', async () => {
    const wrapper = await mountThumbnail('http://localhost:3000', 'https://cdn.example.com/t.png')

    expect(wrapper.get('[data-testid="row-thumbnail"]').attributes('src')).toBe(
      'https://cdn.example.com/t.png',
    )
  })

  it('shows the placeholder without a URL', async () => {
    const wrapper = await mountThumbnail('http://localhost:3000', null)

    expect(wrapper.find('[data-testid="row-thumbnail"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="row-thumbnail-placeholder"]').exists()).toBe(true)
  })
})
