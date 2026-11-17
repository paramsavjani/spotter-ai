import { useEffect, useState } from 'react'
import { ArrowUpDown } from 'lucide-react'
import PlaceInput from './PlaceInput'

// value for <input type="datetime-local"> in the user's own timezone
function toInputValue(date) {
  const d = new Date(date)
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

function loadNote(load) {
  if (load > 40000) return 'Over 40,000 lb: wind 35-44 mph is Severe, 45+ mph is No Travel.'
  if (load > 30000) return 'Over 30,000 lb: wind 45+ mph is No Travel.'
  return 'Wind 55+ mph is No Travel.'
}

// Long trips across mountains and plains, handy for trying the app quickly
const EXAMPLES = [
  {
    origin: { label: 'Denver, Colorado, United States', lat: 39.7392, lon: -104.9903 },
    destination: { label: 'Salt Lake City, Utah, United States', lat: 40.7608, lon: -111.891 },
    note: 'Rocky Mountains, about 520 mi',
  },
  {
    origin: { label: 'Chicago, Illinois, United States', lat: 41.8781, lon: -87.6298 },
    destination: { label: 'Denver, Colorado, United States', lat: 39.7392, lon: -104.9903 },
    note: 'Across the Great Plains, about 1,000 mi',
  },
  {
    origin: { label: 'Seattle, Washington, United States', lat: 47.6062, lon: -122.3321 },
    destination: { label: 'Boise, Idaho, United States', lat: 43.615, lon: -116.2023 },
    note: 'Cascade passes, about 500 mi',
  },
  {
    origin: { label: 'Dallas, Texas, United States', lat: 32.7767, lon: -96.797 },
    destination: { label: 'Atlanta, Georgia, United States', lat: 33.749, lon: -84.388 },
    note: 'Southern storms, about 780 mi',
  },
  {
    origin: { label: 'Minneapolis, Minnesota, United States', lat: 44.9778, lon: -93.265 },
    destination: { label: 'Chicago, Illinois, United States', lat: 41.8781, lon: -87.6298 },
    note: 'Upper Midwest, about 410 mi',
  },
]

const shortName = (place) => place.label.split(',')[0]

export default function TripForm({ onSubmit, loading, error, departure: newDeparture, showExamples }) {
  const [origin, setOrigin] = useState(null)
  const [destination, setDestination] = useState(null)
  const [departure, setDeparture] = useState(toInputValue(new Date()))
  const [load, setLoad] = useState(35000)
  const [interval, setIntervalMiles] = useState(25)
  const [formError, setFormError] = useState('')

  // "Plan for this time" sets a new departure from the results
  useEffect(() => {
    if (newDeparture) setDeparture(toInputValue(newDeparture))
  }, [newDeparture])

  function plan(from, to) {
    // the page may have been open a while, so never send a departure in the past
    const when = new Date(Math.max(new Date(departure), Date.now()))
    setFormError('')
    onSubmit({
      origin: from,
      destination: to,
      departure: when.toISOString(),
      load_lbs: Number(load),
      interval_miles: interval,
    })
  }

  function submit(e) {
    e.preventDefault()
    if (!origin || !destination) {
      setFormError('Pick the origin and destination from the list.')
      return
    }
    plan(origin, destination)
  }

  function tryExample(example) {
    setOrigin(example.origin)
    setDestination(example.destination)
    plan(example.origin, example.destination)
  }

  return (
    <form className="card trip-form" onSubmit={submit}>
      <div className="places">
        <PlaceInput label="From" value={origin} onChange={setOrigin} className="from" />
        <PlaceInput label="To" value={destination} onChange={setDestination} className="to" />
        <button
          type="button"
          className="swap"
          title="Swap"
          onClick={() => {
            setOrigin(destination)
            setDestination(origin)
          }}
        >
          <ArrowUpDown size={15} />
        </button>
      </div>

      <div className="row">
        <label className="field">
          <span>Departure</span>
          <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        </label>
        <label className="field load">
          <span>Load (lb)</span>
          <input type="number" min="100" max="80000" step="100" value={load} onChange={(e) => setLoad(e.target.value)} required />
        </label>
      </div>
      <p className="hint">{loadNote(Number(load))}</p>

      <div className="field">
        <span>Weather check every</span>
        <div className="segmented">
          {[10, 25, 50].map((miles) => (
            <button
              type="button"
              key={miles}
              className={miles === interval ? 'active' : ''}
              onClick={() => setIntervalMiles(miles)}
            >
              {miles} mi
            </button>
          ))}
        </div>
      </div>

      {(formError || error) && <p className="error">{formError || error}</p>}

      <button type="submit" className="primary" disabled={loading}>
        {loading ? 'Checking routes and weather...' : 'Find the safest route'}
      </button>

      {showExamples && (
        <div className="examples">
          <span>Or try one of these trips</span>
          {EXAMPLES.map((example) => (
            <button type="button" key={example.note} onClick={() => tryExample(example)} disabled={loading}>
              <b>
                {shortName(example.origin)} to {shortName(example.destination)}
              </b>
              <small>{example.note}</small>
            </button>
          ))}
        </div>
      )}
    </form>
  )
}
