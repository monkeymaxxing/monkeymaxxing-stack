import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { portal, request } from "@/lib/portal-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { DetailRow, DetailsPanel, PageHeader } from "@/components/DetailsPanel";


const BUCKET = "documents";

export const Route = createFileRoute("/_authenticated/documents")({
  head: () => ({ meta: [{ title: "Documents — MMX Source Lovable Portal" }] }),
  component: DocumentsPage,
});

function DocumentsPage() {
  const { user } = Route.useRouteContext();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [recordId, setRecordId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: async () => {
      return request("documents");
    },
  });
  const records = useQuery({
    queryKey: ["records", "options"],
    queryFn: async () => {
      return request("records");
    },
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      await request("documents", "POST", file, { "x-file-name": file.name, "x-record-id": recordId });
    },
    onSuccess: () => {
      toast.success("File uploaded");
      if (fileRef.current) fileRef.current.value = "";
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const file = fileRef.current?.files?.[0];
    if (!file) return setError("Choose a file to upload.");
    if (file.size > 20 * 1024 * 1024) return setError("Files must be 20 MB or smaller.");
    upload.mutate(file);
  }

  return (
    <>
      <PageHeader title="Documents" description="Private files. Only you can list or download them." />
      <form onSubmit={onSubmit} className="mb-8 grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end" noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="file">File</Label>
          <input id="file" ref={fileRef} type="file" className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-secondary-foreground" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="record">Attach to record (optional)</Label>
          <select id="record" value={recordId} onChange={(e) => setRecordId(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm">
            <option value="">None</option>
            {records.data?.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
          </select>
        </div>
        <Button type="submit" disabled={upload.isPending}>{upload.isPending ? "Uploading…" : "Upload"}</Button>
      </form>
      {error && <p role="alert" className="-mt-6 mb-6 text-sm text-destructive">{error}</p>}

      {docs.isLoading && <p className="text-muted-foreground">Loading…</p>}
      {docs.error && <p role="alert" className="text-destructive">{(docs.error as Error).message}</p>}
      {docs.data?.length === 0 && <p className="text-muted-foreground">No documents yet.</p>}
      <ul className="space-y-3">
        {docs.data?.map((d) => <DocItem key={d.id} doc={d} />)}
      </ul>
    </>
  );
}

type Doc = { id: string; user_id: string; record_id: string | null; file_name: string; object_key: string; sha256: string; byte_count: number; created_at: string };

function DocItem({ doc }: { doc: Doc }) {
  const qc = useQueryClient();

  async function download() {
    try {
      const data = await request(`documents/${doc.id}/download`);
      window.location.assign(data.signedUrl);
    } catch (error) { toast.error((error as Error).message); }
  }

  const del = useMutation({
    mutationFn: async () => {
      await request(`documents/${doc.id}`, "DELETE");
    },
    onSuccess: () => { toast.success("Document deleted"); qc.invalidateQueries({ queryKey: ["documents"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <li className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-bold">{doc.file_name}</p>
          <p className="text-xs text-muted-foreground">{doc.byte_count.toLocaleString()} bytes · {new Date(doc.created_at).toLocaleString()}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="outline" onClick={download}>Download</Button>
          <Button size="sm" variant="ghost" className="text-destructive" disabled={del.isPending}
            onClick={() => { if (confirm(`Delete "${doc.file_name}"?`)) del.mutate(); }}>Delete</Button>
        </div>
      </div>
      <DetailsPanel>
        <DetailRow label="Document UUID" value={doc.id} />
        <DetailRow label="Object key" value={doc.object_key} />
        <DetailRow label="Byte count" value={doc.byte_count} />
        <DetailRow label="SHA-256" value={doc.sha256} />
        <DetailRow label="Record UUID" value={doc.record_id ?? "—"} />
      </DetailsPanel>
    </li>
  );
}
