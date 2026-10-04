"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { CropSummary, pesos } from "@/lib/types";

type Prices = {
  crop: string;
  unit: string;
  latest: number | null;
  average: number | null;
  volatility: number | null;
  points: { date: string; price: number; market: string; region: string; source: string }[];
};

type Sentiment = {
  crop: string;
  signals: { date: string; region: string; sentiment_index: number; article_count: number; confidence: number }[];
  articles: { id: number; title: string; source: string; date: string; crop: string; region: string | null; sentiment: string | null; score: number | null; confidence: number | null; status: string }[];
};

export function MarketBoard() {
  const crops = useQuery({ queryKey: ["crops"], queryFn: () => api<CropSummary[]>("/api/crops") });
  const [cropId, setCropId] = useState<number | null>(null);
  const selected = cropId ?? crops.data?.[0]?.id ?? null;
  const prices = useQuery({
    queryKey: ["prices", selected],
    queryFn: () => api<Prices>(`/api/market/prices?crop_id=${selected}`),
    enabled: selected != null,
  });
  const sentiment = useQuery({
    queryKey: ["sentiment", selected],
    queryFn: () => api<Sentiment>(`/api/market/sentiment?crop_id=${selected}`),
    enabled: selected != null,
  });
  const latestSignal = sentiment.data?.signals.at(-1);
  const regionCounts = prices.data?.points.length ?? 0;

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-gold">Market desk</p>
          <h1 className="text-4xl">Price, volatility, and the news signal</h1>
        </div>
        <label className="text-sm font-semibold">
          Crop
          <select
            className="mt-1 block rounded-xl border border-line bg-paper px-3 py-2"
            value={selected ?? ""}
            onChange={(event) => setCropId(Number(event.target.value))}
          >
            {(crops.data ?? []).map((crop) => (
              <option key={crop.id} value={crop.id}>
                {crop.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {(crops.isError || prices.isError) && <p className="text-sm text-clay">Market data is unavailable. Is the API running?</p>}
      {prices.data && (
        <div className="grid gap-4 md:grid-cols-4">
          <Stat label="Latest price" value={prices.data.latest == null ? "—" : `${pesos(prices.data.latest)}/kg`} />
          <Stat label="Average" value={prices.data.average == null ? "—" : `${pesos(prices.data.average)}/kg`} />
          <Stat label="Price volatility" value={prices.data.volatility == null ? "Insufficient points" : prices.data.volatility < 0.15 ? "Low" : prices.data.volatility < 0.3 ? "Medium" : "High"} />
          <Stat label="Sentiment" value={latestSignal ? `${latestSignal.sentiment_index.toFixed(2)} · ${sentiment.data?.articles.length ?? 0} articles` : "Pending"} />
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <article className="h-80 rounded-[28px] border border-line bg-paper p-4">
          <h2 className="text-2xl">Prices</h2>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={prices.data?.points ?? []}>
              <CartesianGrid stroke="#eadfcb" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line dataKey="price" stroke="#1e4632" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </article>
        <article className="h-80 rounded-[28px] border border-line bg-paper p-4">
          <h2 className="text-2xl">Sentiment index</h2>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={sentiment.data?.signals ?? []}>
              <CartesianGrid stroke="#eadfcb" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line dataKey="sentiment_index" stroke="#a86b12" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </article>
      </div>
      <p className="text-xs text-ink/50">{regionCounts} price observations. Sentiment is not converted into a profit figure.</p>
      <ul className="space-y-3">
        {(sentiment.data?.articles ?? []).map((article) => (
          <li className="rounded-[24px] border border-line bg-paper p-4" key={article.id}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-xl">{article.title}</h3>
              <span className="text-sm text-leaf">{article.sentiment ?? article.status}{article.score == null ? "" : ` · ${article.score.toFixed(2)}`}</span>
            </div>
            <p className="text-xs uppercase tracking-wide text-gold">
              {article.source} · {article.date} · {article.crop}{article.region ? ` · ${article.region}` : ""} · confidence {article.confidence ?? "—"}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-[24px] border border-line bg-paper p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-ink/50">{label}</p>
      <p className="mt-2 text-2xl">{value}</p>
    </article>
  );
}
