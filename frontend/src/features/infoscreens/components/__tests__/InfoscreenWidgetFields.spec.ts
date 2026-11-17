import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import InfoscreenWeatherPlacePicker from '../InfoscreenWeatherPlacePicker.vue'
import InfoscreenWidgetFields from '../InfoscreenWidgetFields.vue'
import { defaultWidget } from '../../utils/infoscreenLayouts'
import type { InfoscreenWidgetConfig, WeatherPlace } from '../../types/infoscreenResponse'

const searchWeatherPlaces = vi.hoisted(() =>
  vi.fn<(query: string, country: string, language: string) => Promise<WeatherPlace[]>>(),
)

vi.mock('../../api/infoscreensApi', () => ({ searchWeatherPlaces }))

const ZELL_AM_SEE: WeatherPlace = {
  name: 'Zell am See',
  region: 'Salzburg',
  country_code: 'AT',
  latitude: 47.32,
  longitude: 12.8,
}

function mountFields(widget: InfoscreenWidgetConfig, submitted = false) {
  return mountWithApp(InfoscreenWidgetFields, {
    props: {
      widget,
      machines: [{ id: 4, internal_name: 'Lathe' }] as never,
      pools: [],
      submitted,
      idPrefix: 'slot',
      'onUpdate:widget': vi.fn<(widget: InfoscreenWidgetConfig) => void>(),
    },
  })
}

beforeEach(() => {
  searchWeatherPlaces.mockReset()
})

describe('weather fields', () => {
  it('searches towns in the country on request and keeps the picked one', async () => {
    searchWeatherPlaces.mockResolvedValue([ZELL_AM_SEE])
    const w = mountFields(defaultWidget('weather'))

    // Typing alone asks nothing, as the place search allows no search as you type.
    await w.get('[data-testid="widget-weather-query"]').setValue('Lilien')
    expect(searchWeatherPlaces).not.toHaveBeenCalled()

    await w.get('[data-testid="widget-weather-search"]').trigger('click')
    await flushPromises()
    expect(searchWeatherPlaces).toHaveBeenCalledWith('Lilien', 'GB', 'enGB')

    const [result] = w.findAll('[data-testid="widget-weather-result"]')
    expect(result!.text()).toBe('Zell am See, Salzburg')
    await result!.trigger('click')
    await flushPromises()
    const updates = w.emitted('update:widget') as [InfoscreenWidgetConfig][]
    expect(updates.at(-1)![0]).toMatchObject({
      type: 'weather',
      location_name: 'Zell am See',
      region: 'Salzburg',
      country_code: 'AT',
      latitude: 47.32,
      longitude: 12.8,
    })
  })

  it('forgets the town when another country is picked', async () => {
    const w = mountFields({
      ...defaultWidget('weather'),
      location_name: 'Zell am See',
      country_code: 'AT',
      latitude: 47.32,
      longitude: 12.8,
    } as InfoscreenWidgetConfig)
    w.getComponent(InfoscreenWeatherPlacePicker).vm.$emit('country', 'DE')
    await flushPromises()
    const updates = w.emitted('update:widget') as [InfoscreenWidgetConfig][]
    expect(updates.at(-1)![0]).toMatchObject({ country_code: 'DE', location_name: '' })
  })

  it('asks for a place once the form was submitted', () => {
    const w = mountFields(defaultWidget('weather'), true)
    expect(w.text()).toContain('Pick a place.')
  })
})

describe('machine view fields', () => {
  it('asks for a machine once the form was submitted', () => {
    const w = mountFields(defaultWidget('machine_detail'), true)
    expect(w.text()).toContain('Pick a machine.')
    expect(w.find('[data-testid="widget-machine-drawing"]').exists()).toBe(true)
  })
})
