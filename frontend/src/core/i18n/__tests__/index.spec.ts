import { describe, it, expect, afterEach } from 'vitest'
import { nextTick } from 'vue'

import { i18n } from '../index'

describe('i18n document.documentElement.lang sync', () => {
  afterEach(async () => {
    i18n.global.locale.value = 'enGB'
    await nextTick()
  })

  it('sets the BCP-47 tag for the current locale', async () => {
    i18n.global.locale.value = 'deAT'
    await nextTick()
    i18n.global.locale.value = 'enGB'
    await nextTick()

    expect(document.documentElement.lang).toBe('en-GB')
  })

  it('updates document.documentElement.lang when the locale switches to German', async () => {
    i18n.global.locale.value = 'deAT'
    await nextTick()

    expect(document.documentElement.lang).toBe('de-AT')
  })

  it('switches back to English when the locale reverts', async () => {
    i18n.global.locale.value = 'deAT'
    await nextTick()
    expect(document.documentElement.lang).toBe('de-AT')

    i18n.global.locale.value = 'enGB'
    await nextTick()
    expect(document.documentElement.lang).toBe('en-GB')
  })
})
