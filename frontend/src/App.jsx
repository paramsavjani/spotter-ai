import { useState } from 'react'
import { planTrip } from './api'
import TripForm from './components/TripForm'
import Results from './components/Results'
import RouteMap from './components/RouteMap'
import ForecastSlider from './components/ForecastSlider'

export default function App() {
  const [trip, setTrip] = useState(null)
  const [result, setResult] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [focus, setFocus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [heatHour, setHeatHour] = useState(0)
  const [showHeat, setShowHeat] = useState(true)

  async function plan(newTrip) {
    setTrip(newTrip)
    setLoading(true)
    setError('')
    try {
      const data = await planTrip(newTrip)
      setResult(data)
      setSelectedId(data.recommended_id ?? data.routes[0].id)
      setFocus(null)
      setHeatHour(0)
    } catch (err) {
      setError(err.message)
    }
    setLoading(false)
  }

  // the heatmap only runs until the selected route reaches its destination
  let maxHour = 0
  if (result) {
    const route = result.routes.find((r) => r.id === selectedId)
    const hoursToArrival = (new Date(route.arrival) - new Date(result.heatmap.start)) / 3600000
    maxHour = Math.min(Math.ceil(hoursToArrival), result.heatmap.frames.length - 1)
  }
  const hour = Math.min(heatHour, maxHour)

  return (
    <div className="layout">
      <aside className="sidebar">
        <header className="brand">
          <h1>Truck Weather Routing</h1>
          <p>Checks the forecast for the hour your truck reaches each part of the road.</p>
        </header>

        <TripForm
          onSubmit={plan}
          loading={loading}
          error={error}
          departure={trip?.departure}
          showExamples={!result}
        />

        {result && (
          <Results
            result={result}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onFocus={setFocus}
            onPlanAt={(departure) => plan({ ...trip, departure })}
            loading={loading}
          />
        )}
      </aside>

      <main className="map-area">
        <RouteMap
          result={result}
          selectedId={selectedId}
          onSelect={setSelectedId}
          focus={focus}
          heatHour={hour}
          showHeat={showHeat}
        />

        {!result && !loading && (
          <div className="map-hint">Enter a trip, or pick one of the example trips on the left.</div>
        )}
        {loading && <div className="map-hint dark">Getting routes and forecasts...</div>}

        {result && (
          <ForecastSlider
            start={result.heatmap.start}
            hour={hour}
            maxHour={maxHour}
            onChange={setHeatHour}
            showHeat={showHeat}
            onToggleHeat={setShowHeat}
          />
        )}
      </main>
    </div>
  )
}
