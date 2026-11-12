export function compact(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? "-" : ""
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toFixed(0)}`
}

export function perShare(value: number): string {
  const sign = value < 0 ? "-" : ""
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

export function shareCount(value: number): string {
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toLocaleString()
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`
}
