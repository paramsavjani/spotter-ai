const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options) {
  const res = await fetch(BASE + path, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`)
  }
  return data
}

export function searchPlaces(query, signal) {
  return request(`/api/geocode/?q=${encodeURIComponent(query)}`, { signal }).then((d) => d.results)
}

export function planTrip(trip) {
  return request('/api/plan/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(trip),
  })
}
