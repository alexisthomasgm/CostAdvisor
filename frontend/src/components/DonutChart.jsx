export default function DonutChart({ segments, size = 150 }) {
  const r = size * 0.375;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  let offset = 0;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface2)" strokeWidth={size * 0.17} />
      {segments.map((seg, i) => {
        const len = circ * seg.pct;
        const el = (
          <circle key={i} cx={cx} cy={cy} r={r} fill="none"
            stroke={seg.color} strokeWidth={size * 0.17}
            strokeDasharray={`${len} ${circ - len}`}
            strokeDashoffset={-offset}
          />
        );
        offset += len;
        return el;
      })}
    </svg>
  );
}