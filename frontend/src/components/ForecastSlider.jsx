import { useEffect, useState } from 'react'
import { Pause, Play } from 'lucide-react'
import { LEVELS, LEVEL_COLORS, formatTime } from '../format'

export default function ForecastSlider({ start, hour, maxHour, onChange, showHeat, onToggleHeat }) {
  const [playing, setPlaying] = useState(false)

  // play once until the truck arrives, then stop
  useEffect(() => {
    if (!playing) return
    if (hour >= maxHour) {
      setPlaying(false)
      return
    }
    const timer = setTimeout(() => onChange(hour + 1), 400)
    return () => clearTimeout(timer)
  }, [playing, hour, maxHour, onChange])

  function togglePlay() {
    if (!playing && hour >= maxHour) onChange(0)
    setPlaying(!playing)
  }

  const time = new Date(new Date(start).getTime() + hour * 3600 * 1000)

  return (
    <div className="forecast-panel">
      <div className="panel-head">
        <button type="button" className="play" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <div className="panel-time">
          <b>{formatTime(time)}</b>
          <span>
            {hour} of {maxHour} h, {hour === maxHour ? 'truck arrives' : 'on the road'}
          </span>
        </div>
        <label>
          <input type="checkbox" checked={showHeat} onChange={(e) => onToggleHeat(e.target.checked)} /> Heatmap
        </label>
      </div>

      <input
        type="range"
        min="0"
        max={maxHour}
        value={hour}
        onChange={(e) => {
          setPlaying(false)
          onChange(Number(e.target.value))
        }}
      />

      <div className="legend">
        {LEVELS.map((level) => (
          <span key={level}>
            <i style={{ background: LEVEL_COLORS[level] }} />
            {level}
          </span>
        ))}
      </div>
    </div>
  )
}
