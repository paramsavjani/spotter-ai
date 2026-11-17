import { Fragment, memo, useEffect, useMemo } from 'react'
import { CircleMarker, ImageOverlay, MapContainer, Marker, Pane, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import { LEVEL_COLORS, ROUTE_COLORS, causeText, formatDuration, formatTime, heatLevel, routeName } from '../format'

const originIcon = L.divIcon({ className: 'pin origin', iconSize: [22, 22] })
const destinationIcon = L.divIcon({ className: 'pin destination', iconSize: [22, 22] })
const truckIcon = L.divIcon({ className: 'truck-marker', iconSize: [18, 18] })

// thin route lines are hard to hit on the canvas, so accept clicks a few pixels away
const canvasRenderer = L.canvas({ tolerance: 8 })

// Small "A 9 h 0 min" label sitting on the route line. Each route puts it at a different point
// along its path so the labels don't stack on top of each other.
const LABEL_SPOT = [0.5, 0.35, 0.65, 0.45]

function routeLabel(route, selected) {
  const text = route.blocked ? 'Closed' : formatDuration(route.duration_hours)
  return L.divIcon({
    className: '',
    iconSize: null,
    html: `<div class="route-label${selected ? ' selected' : ''}"><b style="background:${ROUTE_COLORS[route.id]}">${routeName(route.id)}</b>${text}</div>`,
  })
}

// Draw every heatmap hour as a tiny image, one pixel per grid cell.
// The browser scales it up smoothly and the slider just switches images.
function makeHeatImages(heatmap) {
  const { points, cell_deg: cell, frames } = heatmap
  const lats = points.map((p) => p[0])
  const lons = points.map((p) => p[1])
  const top = Math.max(...lats)
  const left = Math.min(...lons)
  const cols = Math.round((Math.max(...lons) - left) / cell) + 1
  const rows = Math.round((top - Math.min(...lats)) / cell) + 1

  const canvas = document.createElement('canvas')
  canvas.width = cols
  canvas.height = rows
  const ctx = canvas.getContext('2d')

  const urls = frames.map((values) => {
    ctx.clearRect(0, 0, cols, rows)
    points.forEach(([lat, lon], i) => {
      if (values[i] < 0.15) return
      ctx.globalAlpha = 0.12 + values[i] * 0.6
      ctx.fillStyle = LEVEL_COLORS[heatLevel(values[i])]
      ctx.fillRect(Math.round((lon - left) / cell), Math.round((top - lat) / cell), 1, 1)
    })
    return canvas.toDataURL()
  })

  const half = cell / 2
  const bounds = [
    [top - (rows - 1) * cell - half, left - half],
    [top + half, left + (cols - 1) * cell + half],
  ]
  return { urls, bounds }
}

// Truck position at a given time, between the two checkpoints around it.
function truckPosition(route, time) {
  const cps = route.checkpoints
  const i = cps.findIndex((cp) => new Date(cp.eta) >= time)
  if (i === -1) return [cps[cps.length - 1].lat, cps[cps.length - 1].lon]
  if (i === 0) return [cps[0].lat, cps[0].lon]

  const a = cps[i - 1]
  const b = cps[i]
  const f = (time - new Date(a.eta)) / (new Date(b.eta) - new Date(a.eta))
  return [a.lat + f * (b.lat - a.lat), a.lon + f * (b.lon - a.lon)]
}

function FitToRoutes({ routes }) {
  const map = useMap()
  useEffect(() => {
    // extra bottom padding so the routes are not hidden behind the forecast panel
    if (routes.length) map.fitBounds(routes.flatMap((r) => r.path), { paddingTopLeft: [40, 60], paddingBottomRight: [40, 180] })
  }, [routes, map])
  return null
}

function FlyTo({ point }) {
  const map = useMap()
  useEffect(() => {
    if (point) map.flyTo([point.lat, point.lon], Math.max(map.getZoom(), 8))
  }, [point, map])
  return null
}

function HeatLayer({ heatmap, hour }) {
  const { urls, bounds } = useMemo(() => makeHeatImages(heatmap), [heatmap])
  return (
    <Pane name="heat" style={{ zIndex: 350 }}>
      <ImageOverlay url={urls[hour]} bounds={bounds} className="heat-image" />
    </Pane>
  )
}

// memo so the routes are not redrawn every time the slider moves
const Routes = memo(function Routes({ routes, selectedId, onSelect }) {
  // selected route goes last so it is drawn on top (the key makes it re-mount when selection changes)
  const ordered = [...routes].sort((a, b) => (a.id === selectedId) - (b.id === selectedId))

  return ordered.map((route) => {
    const selected = route.id === selectedId
    return (
      <Fragment key={`${route.id}-${selected}`}>
        <Polyline
          positions={route.path}
          pathOptions={{
            color: ROUTE_COLORS[route.id],
            weight: selected ? 6 : 4,
            opacity: selected ? 0.95 : 0.4,
            dashArray: route.blocked ? '8 10' : null,
          }}
          eventHandlers={{ click: () => onSelect(route.id) }}
        />

        <Marker
          position={route.path[Math.floor(route.path.length * LABEL_SPOT[route.id])]}
          icon={routeLabel(route, selected)}
          zIndexOffset={selected ? 1000 : 0}
          eventHandlers={{ click: () => onSelect(route.id) }}
        />

        {route.checkpoints.map((cp) => (
          <CircleMarker
            key={cp.mile}
            center={[cp.lat, cp.lon]}
            radius={selected ? 6 : 3}
            pathOptions={{ color: '#fff', weight: selected ? 2 : 0.5, fillColor: LEVEL_COLORS[cp.level_name], fillOpacity: selected ? 1 : 0.5 }}
            eventHandlers={{ click: () => onSelect(route.id) }}
          >
            <Popup>
              <b style={{ color: LEVEL_COLORS[cp.level_name] }}>{cp.level_name}</b>
              <br />
              Mile {cp.mile}, ETA {formatTime(cp.eta)}
              {cp.wind_mph !== null && (
                <>
                  <br />
                  Wind {cp.wind_mph} mph, rain {cp.rain_in} in/h, snow {cp.snow_in} in/h
                </>
              )}
              {cp.cause && (
                <>
                  <br />
                  Main factor: {causeText(cp)}
                </>
              )}
            </Popup>
          </CircleMarker>
        ))}
      </Fragment>
    )
  })
})

export default function RouteMap({ result, selectedId, onSelect, focus, heatHour, showHeat }) {
  const routes = result ? result.routes : []
  const selected = routes.find((r) => r.id === selectedId)
  const time = result && new Date(new Date(result.heatmap.start).getTime() + heatHour * 3600 * 1000)

  return (
    <MapContainer center={[39.5, -98.35]} zoom={4} preferCanvas renderer={canvasRenderer} className="map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitToRoutes routes={routes} />
      <FlyTo point={focus} />

      {result && showHeat && <HeatLayer heatmap={result.heatmap} hour={heatHour} />}
      <Routes routes={routes} selectedId={selectedId} onSelect={onSelect} />

      {result && (
        <>
          <Marker position={[result.origin.lat, result.origin.lon]} icon={originIcon} />
          <Marker position={[result.destination.lat, result.destination.lon]} icon={destinationIcon} />
        </>
      )}

      {selected && (
        <Marker position={truckPosition(selected, time)} icon={truckIcon}>
          <Tooltip direction="top">Truck at {formatTime(time)}</Tooltip>
        </Marker>
      )}
    </MapContainer>
  )
}
