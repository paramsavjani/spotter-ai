import { useEffect, useState } from 'react'
import { searchPlaces } from '../api'

export default function PlaceInput({ label, value, onChange, className }) {
  const [text, setText] = useState('')
  const [options, setOptions] = useState([])

  // value can change from outside (swap button)
  useEffect(() => {
    if (value) setText(value.label)
  }, [value])

  useEffect(() => {
    if (text.length < 3 || text === value?.label) {
      setOptions([])
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchPlaces(text, controller.signal)
        .then(setOptions)
        .catch(() => {})
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [text, value])

  function pick(place) {
    onChange(place)
    setText(place.label)
    setOptions([])
  }

  return (
    <label className="field place-input">
      <span>{label}</span>
      <input
        className={className}
        value={text}
        placeholder="City or address"
        onChange={(e) => {
          setText(e.target.value)
          onChange(null)
        }}
        onBlur={() => setTimeout(() => setOptions([]), 150)}
      />
      {options.length > 0 && (
        <ul className="suggestions">
          {options.map((place) => (
            <li key={`${place.lat},${place.lon}`} onMouseDown={() => pick(place)}>
              {place.label}
            </li>
          ))}
        </ul>
      )}
    </label>
  )
}
