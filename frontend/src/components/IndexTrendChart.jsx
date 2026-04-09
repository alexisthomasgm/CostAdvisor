/**
 * Simple SVG line chart for displaying index value trends over time.
 * Follows the same SVG pattern as EvoChart.jsx.
 */
export default function IndexTrendChart({ periods, values, unit }) {
  const W = 660, H = 180;
  const PAD = { l: 55, r: 14, t: 14, b: 30 };

  const validPts = values.map((v, i) => v != null ? { x: i, y: v } : null).filter(Boolean);
  if (validPts.length < 2) {
    return <div style={{ color: 'var(--muted)', fontSize: 11, padding: 16 }}>Not enough data to display trend.</div>;
  }

  const allVals = validPts.map(p => p.y);
  const minV = Math.min(...allVals) * 0.97;
  const maxV = Math.max(...allVals) * 1.03;
  const N = periods.length;

  const plotW = W - PAD.l - PAD.r;
  const plotH = H - PAD.t - PAD.b;
  const xScale = i => PAD.l + plotW * i / (N - 1);
  const yScale = v => PAD.t + plotH * (1 - (v - minV) / (maxV - minV || 1));

  // Grid lines
  const gridLines = [];
  const range = maxV - minV;
  let step = Math.pow(10, Math.floor(Math.log10(range || 1)));
  if (range / step < 3) step /= 2;
  if (range / step > 8) step *= 2;
  for (let v = Math.ceil(minV / step) * step; v <= maxV; v += step) {
    gridLines.push(v);
  }

  // Line path
  const linePath = validPts
    .map((p, j) => `${j === 0 ? 'M' : 'L'}${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`)
    .join(' ');

  // Fill area under the line
  const first = validPts[0], last = validPts[validPts.length - 1];
  const fillPath = `${linePath} L${xScale(last.x).toFixed(1)},${(H - PAD.b).toFixed(1)} L${xScale(first.x).toFixed(1)},${(H - PAD.b).toFixed(1)} Z`;

  // Show every Nth label
  const labelStep = N > 16 ? 3 : N > 8 ? 2 : 1;

  return (
    <svg width={W} height={H} style={{ display: 'block', width: '100%', height: 'auto' }} viewBox={`0 0 ${W} ${H}`}>
      {/* Grid */}
      {gridLines.map((v, i) => (
        <g key={i}>
          <line x1={PAD.l} y1={yScale(v)} x2={W - PAD.r} y2={yScale(v)}
            stroke="var(--border)" strokeWidth={0.5} />
          <text x={PAD.l - 6} y={yScale(v) + 3} textAnchor="end"
            fill="var(--muted)" fontSize={9} fontFamily="'JetBrains Mono', monospace">
            {v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(range < 1 ? 4 : range < 10 ? 2 : 0)}
          </text>
        </g>
      ))}

      {/* Unit label */}
      {unit && (
        <text x={4} y={PAD.t + 4} fill="var(--muted)" fontSize={8}
          fontFamily="'JetBrains Mono', monospace">
          {unit}
        </text>
      )}

      {/* Fill area */}
      <path d={fillPath} fill="var(--accent)" opacity={0.07} />

      {/* Line */}
      <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth={1.5} />

      {/* Dots */}
      {validPts.map((p, j) => (
        <circle key={j} cx={xScale(p.x)} cy={yScale(p.y)} r={3}
          fill="var(--accent)" stroke="var(--bg)" strokeWidth={1.5} />
      ))}

      {/* X-axis labels */}
      {periods.map((p, i) => (
        i % labelStep === 0 && (
          <text key={i} x={xScale(i)} y={H - 6} textAnchor="middle"
            fill="var(--muted)" fontSize={9} fontFamily="'JetBrains Mono', monospace">
            {p.label}
          </text>
        )
      ))}
    </svg>
  );
}
