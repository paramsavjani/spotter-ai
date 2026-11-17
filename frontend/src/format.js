export const LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']

export const LEVEL_COLORS = {
  Low: '#2e9e5b',
  Moderate: '#e0b100',
  High: '#f08a24',
  Severe: '#d7263d',
  'No Travel': '#6a1b9a',
  'No forecast': '#9aa0a6',
}

export const ROUTE_COLORS = ['#1f6feb', '#8250df', '#0a8f8f', '#37474f']

export const routeName = (id) => 'ABCD'[id]

export function formatTime(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: 'short',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatDuration(hours) {
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return h ? `${h} h ${m} min` : `${m} min`
}

export function heatLevel(value) {
  if (value >= 1) return 'No Travel'
  if (value >= 0.8) return 'Severe'
  if (value >= 0.6) return 'High'
  if (value >= 0.4) return 'Moderate'
  return 'Low'
}

// "wind 58 mph" / "rain 1.2 in/h" for the condition that caused a checkpoint's level
export function causeText(cp) {
  if (cp.cause === 'wind') return `wind ${cp.wind_mph} mph`
  if (cp.cause === 'rain') return `rain ${cp.rain_in} in/h`
  if (cp.cause === 'snow') return `snow ${cp.snow_in} in/h`
  return ''
}
