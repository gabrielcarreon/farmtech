export type LocationOption = {
  id: number;
  region: string;
  province: string;
  latitude: number;
  longitude: number;
};

export type CropSummary = {
  id: number;
  name: string;
  scientific_name: string | null;
  category: string | null;
};

export type Evidence = {
  document_id: number;
  title: string;
  section?: string | null;
  excerpt: string;
  source?: string | null;
};

export type CropAnalysis = {
  crop: string;
  crop_id: number;
  scientific_name: string | null;
  growing_period_days: number;
  capital_constrained: boolean;
  confidence: number;
  weather: {
    temperature_score: number;
    rainfall_score: number;
    season_score: number;
    extreme_weather_risk: number;
    overall_score: number;
    forecast_days: number;
    climatology_days: number;
  };
  market: {
    price_range: { min: number; median: number; max: number };
    unit: string;
    sentiment: number | null;
    sentiment_status: string;
    sentiment_as_of: string | null;
    volatility: number | null;
    favorability: number | null;
  };
  profit: { conservative: number; expected: number; optimistic: number; currency: string };
  revenue: { conservative: number; expected: number; optimistic: number };
  cost: { expected: number; conservative: number; per_hectare: number };
  yield: { min: number; mid: number; max: number; unit: string };
  risk: {
    weather: number;
    market: number;
    production: number;
    data: number;
    overall: number;
    overall_label: string;
    weather_label: string;
    market_label: string;
    production_label: string;
    data_label: string;
  };
  sentiment: {
    status: string;
    source: string;
    index: number | null;
    as_of: string | null;
    confidence: number | null;
    article_count: number;
  };
  timeline: {
    date: string;
    temp_min: number;
    temp_max: number;
    rainfall: number;
    source: string;
    extreme: boolean;
    stage: string;
  }[];
  assumptions: string[];
  evidence: Evidence[];
  explanation: string;
  freshness: {
    forecast_days: number;
    climatology_days: number;
    prices_as_of: string | null;
    costs_as_of: string | null;
    sentiment_as_of: string | null;
    sentiment_status: string;
  };
};

export type AnalysisResponse = {
  id: number;
  disclaimer: string;
  location: { region: string; province: string; latitude: number; longitude: number };
  planting_date: string;
  horizon_months: number;
  farm_size_hectares: number;
  available_capital: number;
  scoring_version: string;
  model_versions: Record<string, string | null>;
  ai: { status: string };
  crops: CropAnalysis[];
};

export function pesos(value: number) {
  return new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: "PHP",
    maximumFractionDigits: 0,
  }).format(value);
}

export function percent(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}
