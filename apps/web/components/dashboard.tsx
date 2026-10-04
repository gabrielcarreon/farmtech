"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { AnalysisResponse, CropAnalysis, Evidence, LocationOption, percent, pesos } from "@/lib/types";

const fieldClass = "w-full rounded-xl border border-line bg-white/80 px-3 py-2 text-ink outline-none focus:border-canopy";

export function Dashboard() {
  const locations = useQuery({
    queryKey: ["locations"],
    queryFn: () => api<LocationOption[]>("/api/locations"),
  });
  const [province, setProvince] = useState("Nueva Ecija");
  const [hectares, setHectares] = useState("1");
  const [plantingDate, setPlantingDate] = useState("2026-10-15");
  const [horizon, setHorizon] = useState("6");
  const [capital, setCapital] = useState("200000");
  const [selected, setSelected] = useState(0);
  const [question, setQuestion] = useState("Why is tomato suitable for this planting period?");
  const [answer, setAnswer] = useState<{ answer: string; evidence: Evidence[]; llm: string } | null>(null);

  const analysis = useMutation({
    mutationFn: () => {
      const place = locations.data?.find((item) => item.province === province);
      return api<AnalysisResponse>("/api/analysis/crops", {
        method: "POST",
        body: JSON.stringify({
          location: {
            province,
            region: place?.region,
            latitude: place?.latitude,
            longitude: place?.longitude,
          },
          farm_size_hectares: Number(hectares),
          planting_date: plantingDate,
          horizon_months: Number(horizon),
          available_capital: Number(capital),
        }),
      });
    },
    onSuccess: (data) => {
      const tomato = data.crops.findIndex((item) => item.crop === "Tomato");
      setSelected(tomato >= 0 ? tomato : 0);
    },
  });

  const result = analysis.data;
  const crop = result?.crops[selected];

  const explore = useMutation({
    mutationFn: () =>
      api<{ answer: string; evidence: Evidence[]; llm: string }>("/api/rag/analyze", {
        method: "POST",
        body: JSON.stringify({
          query: question,
          crop: crop?.crop,
          region: result?.location.region,
        }),
      }),
    onSuccess: setAnswer,
  });

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <form
        className="h-fit rounded-[28px] border border-line bg-paper p-5 shadow-ledger"
        onSubmit={(event) => {
          event.preventDefault();
          analysis.mutate();
        }}
      >
        <p className="text-xs uppercase tracking-[0.18em] text-leaf">Farm sheet</p>
        <h1 className="mt-1 text-3xl text-ink">What does the data indicate?</h1>
        <p className="mt-2 text-sm leading-6 text-ink/70">
          Scenarios from weather, stored crop records, and cited documents. Not a guarantee of profit.
        </p>
        <label className="mt-5 block text-sm font-semibold">
          Province
          <select className={`${fieldClass} mt-1`} value={province} onChange={(event) => setProvince(event.target.value)}>
            {(locations.data ?? [{ id: 0, province: "Nueva Ecija", region: "Central Luzon", latitude: 15.48, longitude: 120.59 }]).map(
              (item) => (
                <option key={item.province} value={item.province}>
                  {item.region} · {item.province}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="mt-3 block text-sm font-semibold">
          Farm size (hectares)
          <input className={`${fieldClass} mt-1`} min="0.01" step="0.01" type="number" value={hectares} onChange={(event) => setHectares(event.target.value)} required />
        </label>
        <label className="mt-3 block text-sm font-semibold">
          Planting date
          <input className={`${fieldClass} mt-1`} type="date" value={plantingDate} onChange={(event) => setPlantingDate(event.target.value)} required />
        </label>
        <label className="mt-3 block text-sm font-semibold">
          Planning horizon (months)
          <input className={`${fieldClass} mt-1`} min="1" max="18" type="number" value={horizon} onChange={(event) => setHorizon(event.target.value)} required />
        </label>
        <label className="mt-3 block text-sm font-semibold">
          Available capital (PHP)
          <input className={`${fieldClass} mt-1`} min="0" step="1000" type="number" value={capital} onChange={(event) => setCapital(event.target.value)} required />
        </label>
        <Button className="mt-5 w-full" disabled={analysis.isPending} type="submit">
          {analysis.isPending ? "Reading the season…" : "Run crop analysis"}
        </Button>
        {locations.isError && <p className="mt-3 text-sm text-clay">The API is not reachable. Start it on port 8000.</p>}
        {analysis.isError && <p className="mt-3 text-sm text-clay">{(analysis.error as Error).message}</p>}
      </form>

      <section className="space-y-5">
        {!result && (
          <div className="rounded-[28px] border border-dashed border-canopy/30 bg-paper/70 p-8">
            <h2 className="text-3xl">Five crops, three regions, one open ledger</h2>
            <p className="mt-3 max-w-2xl text-ink/75">
              The result keeps weather, market conditions, profit range, risk parts, and confidence visible side by side. Sample seed figures are labeled as sample data.
            </p>
          </div>
        )}
        {result && crop && (
          <>
            <div className="rounded-[28px] bg-canopy px-5 py-4 text-paper">
              <p className="text-sm">{result.disclaimer}</p>
              <p className="mt-2 text-xs uppercase tracking-[0.16em] text-paper/70">
                {result.location.province}, {result.location.region} · {result.farm_size_hectares} ha · planted {result.planting_date} · {result.horizon_months} months · capital {pesos(result.available_capital)}
              </p>
              <p className="mt-1 text-xs text-paper/70">
                AI service {result.ai.status} · scoring {result.scoring_version} · prediction {result.model_versions.prediction}
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {result.crops.map((item, index) => (
                <button
                  key={item.crop}
                  className={`rise rounded-[24px] border bg-paper p-4 text-left shadow-ledger ${index === selected ? "border-canopy" : "border-line"}`}
                  style={{ animationDelay: `${index * 60}ms` }}
                  type="button"
                  onClick={() => setSelected(index)}
                >
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-2xl">{item.crop}</h3>
                    <span className="text-xs uppercase tracking-wide text-leaf">{item.risk.overall_label} risk</span>
                  </div>
                  <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                    <Metric label="Weather" value={percent(item.weather.overall_score)} />
                    <Metric label="Market" value={percent(item.market.favorability)} />
                    <Metric label="Profit" value={`${pesos(item.profit.conservative)}–${pesos(item.profit.optimistic)}`} />
                    <Metric label="Risk" value={`${item.risk.overall}/100`} />
                    <Metric label="Confidence" value={percent(item.confidence)} />
                    <Metric label="Sentiment" value={item.sentiment.status} />
                  </dl>
                </button>
              ))}
            </div>
            <Comparison crops={result.crops} />
            <CropDetail crop={crop} />
            <form
              className="rounded-[28px] border border-line bg-paper p-5"
              onSubmit={(event) => {
                event.preventDefault();
                explore.mutate();
              }}
            >
              <h3 className="text-2xl">Knowledge explorer</h3>
              <p className="text-sm text-ink/70">Asks the document store. A local model answers only when it is up; otherwise you get the passages themselves.</p>
              <textarea className={`${fieldClass} mt-3 min-h-24`} value={question} onChange={(event) => setQuestion(event.target.value)} />
              <Button className="mt-3" type="submit" variant="line" disabled={explore.isPending}>
                {explore.isPending ? "Searching…" : "Ask the guides"}
              </Button>
              {answer && (
                <div className="mt-4 space-y-3 text-sm leading-6">
                  <p className="text-xs uppercase tracking-[0.16em] text-gold">Answer · {answer.llm}</p>
                  <p className="whitespace-pre-wrap">{answer.answer}</p>
                  <EvidenceList evidence={answer.evidence} />
                </div>
              )}
            </form>
          </>
        )}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-ink/50">{label}</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  );
}

function Comparison({ crops }: { crops: CropAnalysis[] }) {
  return (
    <div className="overflow-x-auto rounded-[28px] border border-line bg-paper">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-ink/50">
          <tr>
            <th className="px-4 py-3">Metric</th>
            {crops.map((crop) => (
              <th className="px-4 py-3" key={crop.crop}>
                {crop.crop}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <Row label="Weather" values={crops.map((crop) => percent(crop.weather.overall_score))} />
          <Row label="Temperature" values={crops.map((crop) => percent(crop.weather.temperature_score))} />
          <Row label="Rainfall" values={crops.map((crop) => percent(crop.weather.rainfall_score))} />
          <Row label="Market" values={crops.map((crop) => percent(crop.market.favorability))} />
          <Row label="Expected profit" values={crops.map((crop) => pesos(crop.profit.expected))} />
          <Row label="Profit range" values={crops.map((crop) => `${pesos(crop.profit.conservative)} – ${pesos(crop.profit.optimistic)}`)} />
          <Row label="Weather risk" values={crops.map((crop) => `${crop.risk.weather} ${crop.risk.weather_label}`)} />
          <Row label="Market risk" values={crops.map((crop) => `${crop.risk.market} ${crop.risk.market_label}`)} />
          <Row label="Production risk" values={crops.map((crop) => `${crop.risk.production} ${crop.risk.production_label}`)} />
          <Row label="Data confidence risk" values={crops.map((crop) => `${crop.risk.data} ${crop.risk.data_label}`)} />
          <Row label="Overall risk" values={crops.map((crop) => `${crop.risk.overall}/100`)} />
          <Row label="Confidence" values={crops.map((crop) => percent(crop.confidence))} />
        </tbody>
      </table>
    </div>
  );
}

function Row({ label, values }: { label: string; values: string[] }) {
  return (
    <tr className="border-t border-line/80">
      <th className="px-4 py-2 font-medium">{label}</th>
      {values.map((value, index) => (
        <td className="px-4 py-2" key={`${label}-${index}`}>
          {value}
        </td>
      ))}
    </tr>
  );
}

function CropDetail({ crop }: { crop: CropAnalysis }) {
  const weeks = useMemo(() => weekly(crop.timeline), [crop]);
  const scenarios = [
    { name: "Conservative", profit: crop.profit.conservative },
    { name: "Expected", profit: crop.profit.expected },
    { name: "Optimistic", profit: crop.profit.optimistic },
  ];
  const risks = [
    { name: "Weather", score: crop.risk.weather, label: crop.risk.weather_label },
    { name: "Market", score: crop.risk.market, label: crop.risk.market_label },
    { name: "Production", score: crop.risk.production, label: crop.risk.production_label },
    { name: "Data", score: crop.risk.data, label: crop.risk.data_label },
  ];
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <article className="rounded-[28px] border border-line bg-paper p-5 xl:col-span-2">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-3xl">{crop.crop}</h3>
            <p className="text-sm text-ink/60">{crop.scientific_name} · {crop.growing_period_days} growing days</p>
          </div>
          <p className="text-sm text-ink/70">
            Forecast days {crop.freshness.forecast_days} · climate-normal days {crop.freshness.climatology_days} · prices {crop.freshness.prices_as_of ?? "missing"} · costs {crop.freshness.costs_as_of ?? "missing"} · sentiment {crop.freshness.sentiment_status}
            {crop.freshness.sentiment_as_of ? ` as of ${crop.freshness.sentiment_as_of}` : ""}
          </p>
        </div>
        {crop.capital_constrained && (
          <p className="mt-3 rounded-xl bg-[#f6e4d8] px-3 py-2 text-sm text-clay">Estimated cost is above available capital. The range is still shown.</p>
        )}
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={weeks}>
              <CartesianGrid stroke="#eadfcb" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="rain" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="temp" orientation="right" tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar yAxisId="rain" dataKey="rain" fill="#7ea183" radius={4} name="Rain mm" />
              <Line yAxisId="temp" dataKey="temp" stroke="#a86b12" strokeWidth={2} dot={false} name="Mean °C" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-xs text-ink/55">Weekly rain bars and mean temperature. Hatched weeks in the table below mix forecast and climate normals. Stage labels are rule-of-thumb splits of the variety duration.</p>
      </article>
      <article className="rounded-[28px] border border-line bg-paper p-5">
        <h3 className="text-2xl">Profit scenarios</h3>
        <p className="text-sm text-ink/60">Yield {Math.round(crop.yield.min)}–{Math.round(crop.yield.max)} kg · price {crop.market.price_range.min}–{crop.market.price_range.max} {crop.market.unit}</p>
        <div className="mt-3 h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={scenarios}>
              <CartesianGrid stroke="#eadfcb" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value) => pesos(Number(value))} />
              <Bar dataKey="profit" fill="#1e4632" radius={6} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-sm">Expected revenue {pesos(crop.revenue.expected)} · expected cost {pesos(crop.cost.expected)} · conservative cost {pesos(crop.cost.conservative)}</p>
      </article>
      <article className="rounded-[28px] border border-line bg-paper p-5">
        <h3 className="text-2xl">Risk {crop.risk.overall}/100</h3>
        <p className="text-sm text-ink/60">{crop.risk.overall_label}. The parts stay visible.</p>
        <ul className="mt-4 space-y-3">
          {risks.map((item) => (
            <li key={item.name}>
              <div className="flex justify-between text-sm">
                <span>{item.name}</span>
                <span>{item.score} · {item.label}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-mist">
                <div className="h-2 rounded-full bg-clay" style={{ width: `${item.score}%` }} />
              </div>
            </li>
          ))}
        </ul>
      </article>
      <article className="rounded-[28px] border border-line bg-paper p-5 xl:col-span-2">
        <h3 className="text-2xl">Why this result</h3>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{crop.explanation}</p>
        <h4 className="mt-4 text-lg">Assumptions</h4>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {crop.assumptions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <h4 className="mt-4 text-lg">Evidence</h4>
        <EvidenceList evidence={crop.evidence} />
      </article>
    </div>
  );
}

function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) return <p className="mt-2 text-sm text-ink/60">No document passage matched.</p>;
  return (
    <ul className="mt-3 space-y-3">
      {evidence.map((item) => (
        <li className="rounded-2xl bg-[#f7f3ea] p-3 text-sm" key={`${item.document_id}-${item.section}`}>
          <p className="font-semibold">{item.title}{item.section ? ` · ${item.section}` : ""}</p>
          {item.source && <p className="text-xs uppercase tracking-wide text-gold">{item.source}</p>}
          <p className="mt-1 text-ink/75">{item.excerpt}</p>
        </li>
      ))}
    </ul>
  );
}

function weekly(timeline: CropAnalysis["timeline"]) {
  const rows = [];
  for (let index = 0; index < timeline.length; index += 7) {
    const slice = timeline.slice(index, index + 7);
    const temp = slice.reduce((sum, day) => sum + (day.temp_min + day.temp_max) / 2, 0) / slice.length;
    const rain = slice.reduce((sum, day) => sum + day.rainfall, 0);
    const sources = new Set(slice.map((day) => day.source));
    rows.push({
      label: slice[0].date.slice(5),
      temp: Number(temp.toFixed(1)),
      rain: Number(rain.toFixed(1)),
      stage: slice[Math.floor(slice.length / 2)].stage,
      source: sources.size > 1 ? "mixed" : slice[0].source,
    });
  }
  return rows;
}
