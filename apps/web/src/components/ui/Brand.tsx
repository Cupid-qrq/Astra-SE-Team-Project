export function BrandMark() {
  return (
    <svg className="brand-symbol" viewBox="0 0 48 36" fill="none" aria-hidden="true">
      <path d="M3 30 22 3h8l15 27H32l-5-10H17l5-7h2l-1-2-13 19H3Z" fill="currentColor" />
    </svg>
  )
}

export function OrbitGraphic() {
  return (
    <div className="orbit-graphic" aria-hidden="true">
      <svg viewBox="0 0 520 240" fill="none">
        <path
          d="M34 123h450M280 16v204M62 117v12m57-12v12m57-12v12m57-12v12m95-12v12m57-12v12m57-12v12M274 45h12m-12 40h12m-12 78h12m-12 40h12"
          stroke="currentColor"
          strokeWidth=".8"
        />
        <circle
          cx="280"
          cy="123"
          r="87"
          stroke="currentColor"
          strokeWidth=".8"
          strokeDasharray="420 127"
        />
        <ellipse
          className="orbit-ring"
          cx="280"
          cy="123"
          rx="205"
          ry="43"
          transform="rotate(-20 280 123)"
          stroke="currentColor"
          strokeWidth=".8"
        />
        <path d="M191 50v-13h13M366 198h13v-13" stroke="currentColor" />
        <path d="M273 116h14v14h-14z" fill="var(--accent)" />
        <path d="M278 121h4v4h-4z" fill="#171b19" />
        <circle className="orbit-point" cx="471" cy="54" r="3" fill="currentColor" />
      </svg>
      <span className="orbit-word">ASTRA</span>
    </div>
  )
}
