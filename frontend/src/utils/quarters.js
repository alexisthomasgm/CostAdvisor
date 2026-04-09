export function qLabel(y, q) { return `Q${q}-${String(y).slice(-2)}`; }

export function generateQuarterOptions(startYear = 2020, endYear = 2027) {
  const opts = [];
  for (let y = startYear; y <= endYear; y++) {
    for (let q = 1; q <= 4; q++) {
      opts.push({ year: y, quarter: q, label: qLabel(y, q) });
    }
  }
  return opts;
}

export const QUARTER_OPTS = generateQuarterOptions();
