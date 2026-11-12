export const METRIC_LABELS: Record<string, string> = {
  revenue: "Revenue",
  ebit: "EBIT",
  pretax_income: "Pretax income",
  tax_expense: "Income tax expense",
  depreciation_amortization: "Depreciation & amortization",
  capital_expenditures: "Capital expenditures",
  current_assets: "Current assets",
  current_liabilities: "Current liabilities",
  interest_expense: "Interest expense",
  cash: "Cash & equivalents",
  total_debt: "Total debt",
  shares_outstanding: "Shares outstanding",
}

export function metricLabel(metric: string): string {
  return METRIC_LABELS[metric] ?? metric
}
