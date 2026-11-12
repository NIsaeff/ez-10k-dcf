export const SUPPORTED_TICKERS = [
  "AAPL",
  "MSFT",
  "GOOGL",
  "AMZN",
  "NVDA",
  "META",
  "TSLA",
  "KO",
  "PWR",
] as const

export type Ticker = (typeof SUPPORTED_TICKERS)[number]
