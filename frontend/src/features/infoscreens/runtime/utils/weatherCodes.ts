/**
 * The weather a symbol code of MET Norway stands for, such as
 * `lightrainshowers_day` or `heavysnowandthunder`: a kind with its words in
 * the locale files and an icon, with a night variant where the sky shows.
 * The suffix `_day`, `_night` or `_polartwilight` says which light it is.
 */
export type WeatherKind =
  | 'clear'
  | 'partlyCloudy'
  | 'cloudy'
  | 'fog'
  | 'drizzle'
  | 'rain'
  | 'sleet'
  | 'snow'
  | 'showers'
  | 'snowShowers'
  | 'thunderstorm'
  | 'unknown'

/** The symbol without its light suffix. */
function baseSymbol(symbol: string): string {
  return symbol.replace(/_(day|night|polartwilight)$/, '')
}

export function weatherKind(symbol: string | null | undefined): WeatherKind {
  if (!symbol) return 'unknown'
  const base = baseSymbol(symbol)
  if (base.includes('thunder')) return 'thunderstorm'
  if (base === 'clearsky') return 'clear'
  if (base === 'fair' || base === 'partlycloudy') return 'partlyCloudy'
  if (base === 'cloudy') return 'cloudy'
  if (base === 'fog') return 'fog'
  if (base.includes('sleet')) return 'sleet'
  if (base.includes('snowshowers')) return 'snowShowers'
  if (base.includes('snow')) return 'snow'
  if (base.includes('rainshowers')) return 'showers'
  if (base === 'lightrain') return 'drizzle'
  if (base.includes('rain')) return 'rain'
  return 'unknown'
}

/** Whether a symbol is for the night sky. */
export function isNightSymbol(symbol: string | null | undefined): boolean {
  return !!symbol && symbol.endsWith('_night')
}

const ICONS: Record<WeatherKind, string> = {
  clear: 'mdi-weather-sunny',
  partlyCloudy: 'mdi-weather-partly-cloudy',
  cloudy: 'mdi-weather-cloudy',
  fog: 'mdi-weather-fog',
  drizzle: 'mdi-weather-partly-rainy',
  rain: 'mdi-weather-rainy',
  sleet: 'mdi-weather-snowy-rainy',
  snow: 'mdi-weather-snowy',
  showers: 'mdi-weather-pouring',
  snowShowers: 'mdi-weather-snowy-heavy',
  thunderstorm: 'mdi-weather-lightning-rainy',
  unknown: 'mdi-weather-cloudy-alert',
}

const NIGHT_ICONS: Partial<Record<WeatherKind, string>> = {
  clear: 'mdi-weather-night',
  partlyCloudy: 'mdi-weather-night-partly-cloudy',
}

/** The icon class of a symbol, the night sky for a night symbol. */
export function weatherIcon(symbol: string | null | undefined): string {
  const kind = weatherKind(symbol)
  return (isNightSymbol(symbol) && NIGHT_ICONS[kind]) || ICONS[kind]
}
