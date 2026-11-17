import { ROUTE_COLORS, routeName } from '../format'

// Small interstate-style shield with the route letter
export default function RouteShield({ id, size = 26 }) {
  return (
    <svg className="shield" width={size} height={size} viewBox="0 0 24 24" aria-label={`Route ${routeName(id)}`}>
      <path d="M2.5 2.5h19v8c0 5.8-4 9.6-9.5 11.5C6.5 20.1 2.5 16.3 2.5 10.5z" fill={ROUTE_COLORS[id]} stroke="#fff" strokeWidth="1.4" />
      <text x="12" y="15.5" textAnchor="middle" fill="#fff" fontSize="10" fontWeight="800">
        {routeName(id)}
      </text>
    </svg>
  )
}
