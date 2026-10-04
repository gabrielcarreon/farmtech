"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, uploadForm } from "@/lib/api";
import { CropSummary, LocationOption } from "@/lib/types";

type DocSummary = {
  id: number;
  title: string;
  source: string | null;
  document_type: string | null;
  region: string | null;
  province: string | null;
  crop: string | null;
  created_at: string | null;
  chunk_count: number;
  embedded_count: number;
  embedding_status: "ready" | "pending" | "partial";
};

type DocChunk = {
  id: number;
  chunk_index: number;
  section: string | null;
  content: string;
  embedding_status: string;
};

type DocDetail = DocSummary & {
  source_url: string | null;
  publication_date: string | null;
  language: string;
  metadata: Record<string, unknown>;
  chunks: DocChunk[];
};

type ImportJob = {
  id: number;
  filename: string;
  kind: string;
  status: string;
  errors: { row: number; message: string }[];
  row_count: number;
  metadata: Record<string, unknown>;
};

type EditState = {
  title: string;
  source: string;
  document_type: string;
  crop: string;
  region: string;
  province: string;
};

const fieldClass = "w-full rounded-xl border border-line bg-white/80 px-3 py-2 text-ink outline-none focus:border-canopy";
const DOC_TYPES = [
  { value: "production_guide", label: "Production guide" },
  { value: "manual", label: "Manual" },
  { value: "report", label: "Report" },
  { value: "other", label: "Other" },
];

export function KnowledgeBoard() {
  const queryClient = useQueryClient();
  const crops = useQuery({ queryKey: ["crops"], queryFn: () => api<CropSummary[]>("/api/crops") });
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<LocationOption[]>("/api/locations") });

  const [cropFilter, setCropFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditState | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [crop, setCrop] = useState("");
  const [province, setProvince] = useState("");
  const [documentType, setDocumentType] = useState("production_guide");

  const regions = useMemo(() => {
    const values = new Set((locations.data ?? []).map((item) => item.region));
    return [...values].sort();
  }, [locations.data]);

  const selectedLocation = (locations.data ?? []).find((item) => item.province === province);
  const uploadRegion = selectedLocation?.region ?? "";

  const listQuery = useQuery({
    queryKey: ["rag-documents", cropFilter, regionFilter, search],
    queryFn: () => {
      const params = new URLSearchParams();
      if (cropFilter) params.set("crop", cropFilter);
      if (regionFilter) params.set("region", regionFilter);
      if (search.trim()) params.set("q", search.trim());
      const qs = params.toString();
      return api<{ documents: DocSummary[] }>(`/api/rag/documents${qs ? `?${qs}` : ""}`);
    },
  });

  const detailQuery = useQuery({
    queryKey: ["rag-document", selectedId],
    queryFn: () => api<DocDetail>(`/api/rag/documents/${selectedId}`),
    enabled: selectedId != null,
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a PDF, TXT, or Markdown file.");
      if (!source.trim()) throw new Error("Source is required.");
      const form = new FormData();
      form.append("file", file);
      form.append("kind", "documents");
      form.append("source", source.trim());
      form.append("document_type", documentType);
      form.append("title", title.trim() || file.name);
      if (crop) form.append("crop", crop);
      if (uploadRegion) form.append("region", uploadRegion);
      if (province) form.append("province", province);
      return uploadForm<ImportJob>("/api/data/import", form);
    },
    onSuccess: async (job) => {
      setUploadError(null);
      setUploadMessage(`Imported “${job.filename}” · ${job.row_count} chunks · status ${job.status}`);
      setFile(null);
      setTitle("");
      await queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
      const documentId = Number(job.metadata?.document_id);
      if (Number.isFinite(documentId) && documentId > 0) {
        setSelectedId(documentId);
      }
    },
    onError: (error: Error) => {
      setUploadMessage(null);
      setUploadError(parseError(error.message));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<{ status: string }>(`/api/rag/documents/${id}`, { method: "DELETE" }),
    onSuccess: async (_data, id) => {
      if (selectedId === id) setSelectedId(null);
      if (editingId === id) {
        setEditingId(null);
        setEditForm(null);
      }
      await queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
    },
  });

  const reembedMutation = useMutation({
    mutationFn: (id: number) => api<DocDetail>(`/api/rag/documents/${id}/reembed`, { method: "POST" }),
    onSuccess: async (doc) => {
      await queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
      await queryClient.invalidateQueries({ queryKey: ["rag-document", doc.id] });
    },
  });

  const patchMutation = useMutation({
    mutationFn: (payload: { id: number; body: EditState }) =>
      api<DocDetail>(`/api/rag/documents/${payload.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: payload.body.title,
          source: payload.body.source,
          document_type: payload.body.document_type,
          crop: payload.body.crop || null,
          region: payload.body.region || null,
          province: payload.body.province || null,
        }),
      }),
    onSuccess: async (doc) => {
      setEditingId(null);
      setEditForm(null);
      await queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
      await queryClient.invalidateQueries({ queryKey: ["rag-document", doc.id] });
      setSelectedId(doc.id);
    },
  });

  function startEdit(doc: DocSummary) {
    setEditingId(doc.id);
    setEditForm({
      title: doc.title,
      source: doc.source ?? "",
      document_type: doc.document_type ?? "production_guide",
      crop: doc.crop ?? "",
      region: doc.region ?? "",
      province: doc.province ?? "",
    });
  }

  return (
    <section className="space-y-5">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-gold">Knowledge desk</p>
        <h1 className="text-4xl">Upload guides and manage RAG sources</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">
          Documents are chunked for retrieval. Embeddings stay pending until the local AI worker runs; full-text search still works without them.
        </p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <form
          className="h-fit rounded-[28px] border border-line bg-paper p-5 shadow-ledger"
          onSubmit={(event) => {
            event.preventDefault();
            uploadMutation.mutate();
          }}
        >
          <h2 className="text-2xl">Upload</h2>
          <p className="mt-1 text-sm text-ink/60">PDF, TXT, or Markdown · max 10 MB</p>

          <label className="mt-4 block text-sm font-semibold">
            File
            <input
              className={`${fieldClass} mt-1`}
              accept=".pdf,.txt,.md,text/plain,application/pdf"
              type="file"
              onChange={(event) => {
                const next = event.target.files?.[0] ?? null;
                setFile(next);
                if (next && !title) setTitle(next.name.replace(/\.(pdf|txt|md)$/i, ""));
              }}
            />
          </label>
          <label className="mt-3 block text-sm font-semibold">
            Title
            <input className={`${fieldClass} mt-1`} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Tomato Production Guide" />
          </label>
          <label className="mt-3 block text-sm font-semibold">
            Source
            <input className={`${fieldClass} mt-1`} value={source} onChange={(event) => setSource(event.target.value)} placeholder="DA / research note / farm desk" required />
          </label>
          <label className="mt-3 block text-sm font-semibold">
            Document type
            <select className={`${fieldClass} mt-1`} value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              {DOC_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-3 block text-sm font-semibold">
            Crop
            <select className={`${fieldClass} mt-1`} value={crop} onChange={(event) => setCrop(event.target.value)}>
              <option value="">Any / unspecified</option>
              {(crops.data ?? []).map((item) => (
                <option key={item.id} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-3 block text-sm font-semibold">
            Province
            <select
              className={`${fieldClass} mt-1`}
              value={province}
              onChange={(event) => setProvince(event.target.value)}
            >
              <option value="">Any / unspecified</option>
              {(locations.data ?? []).map((item) => (
                <option key={item.id} value={item.province}>
                  {item.region} · {item.province}
                </option>
              ))}
            </select>
          </label>
          {uploadRegion && <p className="mt-2 text-xs text-ink/55">Region set from province: {uploadRegion}</p>}

          <Button className="mt-5 w-full" disabled={uploadMutation.isPending} type="submit">
            {uploadMutation.isPending ? "Uploading…" : "Import into knowledge base"}
          </Button>
          {uploadMessage && <p className="mt-3 text-sm text-leaf">{uploadMessage}</p>}
          {uploadError && <p className="mt-3 text-sm text-clay">{uploadError}</p>}
        </form>

        <div className="space-y-4">
          <div className="grid gap-3 rounded-[28px] border border-line bg-paper p-4 md:grid-cols-3">
            <label className="text-sm font-semibold">
              Filter crop
              <select className={`${fieldClass} mt-1`} value={cropFilter} onChange={(event) => setCropFilter(event.target.value)}>
                <option value="">All crops</option>
                {(crops.data ?? []).map((item) => (
                  <option key={item.id} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              Filter region
              <select className={`${fieldClass} mt-1`} value={regionFilter} onChange={(event) => setRegionFilter(event.target.value)}>
                <option value="">All regions</option>
                {regions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold">
              Search
              <input className={`${fieldClass} mt-1`} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title or source" />
            </label>
          </div>

          <div className="overflow-x-auto rounded-[28px] border border-line bg-paper">
            {listQuery.isError && <p className="p-4 text-sm text-clay">Could not load documents. Is the API running?</p>}
            {listQuery.isLoading && <p className="p-4 text-sm text-ink/60">Loading library…</p>}
            {listQuery.data && listQuery.data.documents.length === 0 && (
              <p className="p-4 text-sm text-ink/60">No documents yet. Upload a production guide to get started.</p>
            )}
            {listQuery.data && listQuery.data.documents.length > 0 && (
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-ink/50">
                  <tr>
                    <th className="px-4 py-3">Title</th>
                    <th className="px-4 py-3">Crop</th>
                    <th className="px-4 py-3">Region</th>
                    <th className="px-4 py-3">Chunks</th>
                    <th className="px-4 py-3">Embeddings</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {listQuery.data.documents.map((doc) => (
                    <tr key={doc.id} className={`border-t border-line/80 ${selectedId === doc.id ? "bg-mist/40" : ""}`}>
                      <td className="px-4 py-3">
                        <p className="font-semibold">{doc.title}</p>
                        <p className="text-xs text-ink/50">{doc.document_type ?? "—"} · {doc.source ?? "no source"}</p>
                      </td>
                      <td className="px-4 py-3">{doc.crop ?? "—"}</td>
                      <td className="px-4 py-3">
                        {doc.region ?? "—"}
                        {doc.province ? ` · ${doc.province}` : ""}
                      </td>
                      <td className="px-4 py-3">{doc.chunk_count}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={doc.embedding_status} embedded={doc.embedded_count} total={doc.chunk_count} />
                      </td>
                      <td className="px-4 py-3">{doc.created_at ? doc.created_at.slice(0, 10) : "—"}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button type="button" variant="line" onClick={() => setSelectedId(doc.id)}>
                            View
                          </Button>
                          <Button type="button" variant="ghost" onClick={() => startEdit(doc)}>
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            disabled={reembedMutation.isPending}
                            onClick={() => reembedMutation.mutate(doc.id)}
                          >
                            Re-embed
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            className="text-clay"
                            disabled={deleteMutation.isPending}
                            onClick={() => {
                              if (window.confirm(`Delete “${doc.title}” and its chunks?`)) {
                                deleteMutation.mutate(doc.id);
                              }
                            }}
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {editingId != null && editForm && (
            <form
              className="rounded-[28px] border border-line bg-paper p-5"
              onSubmit={(event) => {
                event.preventDefault();
                patchMutation.mutate({ id: editingId, body: editForm });
              }}
            >
              <h3 className="text-2xl">Edit metadata</h3>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="text-sm font-semibold">
                  Title
                  <input className={`${fieldClass} mt-1`} value={editForm.title} onChange={(event) => setEditForm({ ...editForm, title: event.target.value })} required />
                </label>
                <label className="text-sm font-semibold">
                  Source
                  <input className={`${fieldClass} mt-1`} value={editForm.source} onChange={(event) => setEditForm({ ...editForm, source: event.target.value })} />
                </label>
                <label className="text-sm font-semibold">
                  Document type
                  <select className={`${fieldClass} mt-1`} value={editForm.document_type} onChange={(event) => setEditForm({ ...editForm, document_type: event.target.value })}>
                    {DOC_TYPES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Crop
                  <select className={`${fieldClass} mt-1`} value={editForm.crop} onChange={(event) => setEditForm({ ...editForm, crop: event.target.value })}>
                    <option value="">Any / unspecified</option>
                    {(crops.data ?? []).map((item) => (
                      <option key={item.id} value={item.name}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Region
                  <select className={`${fieldClass} mt-1`} value={editForm.region} onChange={(event) => setEditForm({ ...editForm, region: event.target.value })}>
                    <option value="">Any / unspecified</option>
                    {regions.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Province
                  <select className={`${fieldClass} mt-1`} value={editForm.province} onChange={(event) => setEditForm({ ...editForm, province: event.target.value })}>
                    <option value="">Any / unspecified</option>
                    {(locations.data ?? [])
                      .filter((item) => !editForm.region || item.region === editForm.region)
                      .map((item) => (
                        <option key={item.id} value={item.province}>
                          {item.province}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <div className="mt-4 flex gap-2">
                <Button type="submit" disabled={patchMutation.isPending}>
                  {patchMutation.isPending ? "Saving…" : "Save metadata"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setEditingId(null);
                    setEditForm(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
              {patchMutation.isError && <p className="mt-3 text-sm text-clay">{(patchMutation.error as Error).message}</p>}
            </form>
          )}

          {selectedId != null && (
            <article className="rounded-[28px] border border-line bg-paper p-5">
              {detailQuery.isLoading && <p className="text-sm text-ink/60">Loading chunks…</p>}
              {detailQuery.isError && <p className="text-sm text-clay">Could not load document detail.</p>}
              {detailQuery.data && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-3xl">{detailQuery.data.title}</h3>
                      <p className="text-sm text-ink/60">
                        {detailQuery.data.crop ?? "Unspecified crop"} · {detailQuery.data.region ?? "Unspecified region"}
                        {detailQuery.data.province ? ` · ${detailQuery.data.province}` : ""} · {detailQuery.data.chunk_count} chunks
                      </p>
                    </div>
                    <StatusBadge
                      status={detailQuery.data.embedding_status}
                      embedded={detailQuery.data.embedded_count}
                      total={detailQuery.data.chunk_count}
                    />
                  </div>
                  <ul className="mt-4 space-y-3">
                    {detailQuery.data.chunks.map((chunk) => (
                      <li key={chunk.id} className="rounded-2xl bg-[#f7f3ea] p-3 text-sm">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <p className="font-semibold">
                            #{chunk.chunk_index}
                            {chunk.section ? ` · ${chunk.section}` : ""}
                          </p>
                          <span className="text-xs uppercase tracking-wide text-gold">{chunk.embedding_status}</span>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-ink/80">{chunk.content}</p>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </article>
          )}
        </div>
      </div>
    </section>
  );
}

function StatusBadge({ status, embedded, total }: { status: string; embedded: number; total: number }) {
  const tone = status === "ready" ? "bg-mist text-canopy" : status === "partial" ? "bg-[#f6e4d8] text-clay" : "bg-[#efe8d8] text-ink/70";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      {status} · {embedded}/{total}
    </span>
  );
}

function parseError(raw: string): string {
  try {
    const parsed = JSON.parse(raw);
    if (parsed?.detail?.errors?.[0]?.message) return parsed.detail.errors.map((item: { message: string }) => item.message).join("; ");
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch {
    /* plain text */
  }
  return raw;
}
