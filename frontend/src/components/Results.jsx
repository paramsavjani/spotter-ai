import { LEVELS, LEVEL_COLORS, causeText, formatDuration, formatTime, routeName } from '../format'
import RouteShield from './RouteShield'

function RiskBar({ route }) {
  return (
    <div className="risk-bar">
      {LEVELS.map((level) => {
        const miles = route.miles_by_level[level]
        if (!miles) return null
        return (
          <div
            key={level}
            title={`${level}: ${miles} mi`}
            style={{ width: `${(miles / route.distance_miles) * 100}%`, background: LEVEL_COLORS[level] }}
          />
        )
      })}
    </div>
  )
}

function RouteRow({ route, selected, onSelect, reason }) {
  let className = 'route-row'
  if (selected) className += ' selected'
  if (route.blocked) className += ' blocked'

  return (
    <button type="button" className={className} onClick={() => onSelect(route.id)}>
      <RouteShield id={route.id} />
      <div className="route-body">
        <div className="route-title">
          <h3>Route {routeName(route.id)}</h3>
          {route.recommended && <span className="tag good">Best</span>}
          {route.blocked && <span className="tag bad">Closed</span>}
        </div>

        <div className="route-numbers">
          <span>
            <b>{Math.round(route.distance_miles)}</b> mi
          </span>
          <span>
            <b>{formatDuration(route.duration_hours)}</b>
          </span>
          <span>arrive {formatTime(route.arrival)}</span>
        </div>

        <RiskBar route={route} />
        {route.recommended && <p className="why">{reason}</p>}

        {route.blocked ? (
          <p className="closed">
            No Travel at mile {route.blocked_at.mile}, {formatTime(route.blocked_at.eta)}: {causeText(route.blocked_at)}
          </p>
        ) : (
          <p className="risk-text">
            Severe {route.severe_miles} mi, High {route.high_miles} mi, average risk {route.avg_risk ?? '-'}
          </p>
        )}
        {route.missing_forecast && <p className="risk-text">Part of this trip is past the forecast range.</p>}
      </div>
    </button>
  )
}

export default function Results({ result, selectedId, onSelect, onFocus, onPlanAt, loading }) {
  const best = result.routes.find((r) => r.recommended)
  const selected = result.routes.find((r) => r.id === selectedId)
  const wait = result.earliest_departure

  return (
    <section className="results">
      {!best && (
        <div className="sign stop">
          <div className="sign-inner">
            <h2>No safe route right now</h2>
            <p>{result.recommendation_reason}</p>
          </div>
        </div>
      )}

      {result.all_blocked && (
        <div className="sign wait">
          <div className="sign-inner">
            {wait ? (
              <>
                <h2>Wait {wait.wait_hours} h</h2>
                <p>
                  Leave at {formatTime(wait.departure)}. Route {routeName(wait.route_id)} is clear then, arriving{' '}
                  {formatTime(wait.arrival)}.
                </p>
                <button type="button" onClick={() => onPlanAt(wait.departure)} disabled={loading}>
                  Plan for this time
                </button>
              </>
            ) : (
              <>
                <h2>No clear departure in the next 72 h</h2>
                <p>Every route keeps a No Travel stretch for the whole forecast.</p>
              </>
            )}
          </div>
        </div>
      )}

      <div className="route-list">
        {result.routes.map((route) => (
          <RouteRow
            key={route.id}
            route={route}
            selected={route.id === selectedId}
            onSelect={onSelect}
            reason={result.recommendation_reason}
          />
        ))}
      </div>

      {selected && (
        <div className="timeline">
          <h3>Checkpoints on Route {routeName(selected.id)}</h3>
          <ol>
            {selected.checkpoints.map((cp) => (
              <li key={cp.mile} onClick={() => onFocus(cp)}>
                <i style={{ background: LEVEL_COLORS[cp.level_name] }} />
                <span className="cp-mile">Mile {cp.mile}</span>
                <span className="cp-time">{formatTime(cp.eta)}</span>
                <span className="cp-level" style={{ color: LEVEL_COLORS[cp.level_name] }}>
                  {cp.level_name}
                </span>
                {cp.cause && <span className="cp-cause">{causeText(cp)}</span>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}
