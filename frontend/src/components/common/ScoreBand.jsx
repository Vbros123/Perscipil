// Horizontal 0-1000 scale showing the six rating bands with a marker at the
// company's score. Band boundaries mirror RATING_BANDS in the scoring engine.
const BANDS = [
  { from: 0, to: 250, label: 'Critical' },
  { from: 250, to: 400, label: 'Distressed' },
  { from: 400, to: 550, label: 'Weak' },
  { from: 550, to: 700, label: 'Adequate' },
  { from: 700, to: 850, label: 'Strong' },
  { from: 850, to: 1000, label: 'Exceptional' },
]

export default function ScoreBand({ score, rated = true }) {
  const value = Number(score)
  const showMarker = rated && Number.isFinite(value)
  const position = showMarker ? Math.max(0, Math.min(1000, value)) / 10 : null

  return (
    <div className="score-band" aria-hidden={!showMarker}>
      <div className="score-band-track">
        {BANDS.map((band) => (
          <i
            key={band.label}
            title={`${band.label} ${band.from}\u2013${band.to}`}
            className={showMarker && value >= band.from && (value < band.to || band.to === 1000) ? 'band-active' : ''}
            style={{ flexGrow: band.to - band.from }}
          />
        ))}
        {showMarker && <span className="score-band-marker" style={{ left: `${position}%` }} />}
      </div>
      <div className="score-band-scale">
        <span>0</span>
        <span>1000</span>
      </div>
    </div>
  )
}
