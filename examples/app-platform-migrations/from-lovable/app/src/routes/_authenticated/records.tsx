import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { portal, request } from "@/lib/portal-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DetailRow, DetailsPanel, PageHeader } from "@/components/DetailsPanel";

export const Route = createFileRoute("/_authenticated/records")({
  head: () => ({ meta: [{ title: "Records — MMX Source Lovable Portal" }] }),
  component: RecordsPage,
});

function validateTitle(raw: string): string | null {
  const t = raw.trim();
  if (!t) return "Title is required.";
  if (t.length > 200) return "Title must be 200 characters or fewer.";
  return null;
}

function RecordsPage() {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const records = useQuery({
    queryKey: ["records"],
    queryFn: async () => {
      return request("records");
    },
  });

  const create = useMutation({
    mutationFn: async (t: string) => {
      await request("records", "POST", { title: t });
    },
    onSuccess: () => {
      setTitle("");
      toast.success("Record created");
      qc.invalidateQueries({ queryKey: ["records"] });
    },
    onError: (e: Error) => setFormError(e.message),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const err = validateTitle(title);
    setFormError(err);
    if (!err) create.mutate(title.trim());
  }

  return (
    <>
      <PageHeader title="Records" description="Create, edit and delete your records." />
      <form onSubmit={onSubmit} className="mb-8 flex flex-col gap-2 rounded-lg border bg-card p-4 sm:flex-row sm:items-end" noValidate>
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="new-title">New record title</Label>
          <Input id="new-title" value={title} maxLength={220} onChange={(e) => setTitle(e.target.value)} aria-invalid={!!formError} />
        </div>
        <Button type="submit" disabled={create.isPending}>{create.isPending ? "Adding…" : "Add record"}</Button>
      </form>
      {formError && <p role="alert" className="-mt-6 mb-6 text-sm text-destructive">{formError}</p>}

      {records.isLoading && <p className="text-muted-foreground">Loading…</p>}
      {records.error && <p role="alert" className="text-destructive">{(records.error as Error).message}</p>}
      {records.data?.length === 0 && <p className="text-muted-foreground">No records yet.</p>}
      <ul className="space-y-3">
        {records.data?.map((r) => <RecordItem key={r.id} record={r} />)}
      </ul>
    </>
  );
}

type Rec = { id: string; user_id: string; title: string; created_at: string; updated_at: string };

function RecordItem({ record }: { record: Rec }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(record.title);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async () => {
      await request(`records/${record.id}`, "PATCH", { title: title.trim() });
    },
    onSuccess: () => {
      setEditing(false);
      toast.success("Record updated");
      qc.invalidateQueries({ queryKey: ["records"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const del = useMutation({
    mutationFn: async () => {
      await request(`records/${record.id}`, "DELETE");
    },
    onSuccess: () => {
      toast.success("Record deleted");
      qc.invalidateQueries({ queryKey: ["records"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <li className="rounded-lg border bg-card p-4">
      {editing ? (
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            const err = validateTitle(title);
            setError(err);
            if (!err) save.mutate();
          }}
          noValidate
        >
          <Label htmlFor={`t-${record.id}`} className="sr-only">Title</Label>
          <Input id={`t-${record.id}`} value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
          <Button type="submit" size="sm" disabled={save.isPending}>Save</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => { setEditing(false); setTitle(record.title); setError(null); }}>Cancel</Button>
        </form>
      ) : (
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-bold">{record.title}</p>
            <p className="text-xs text-muted-foreground">Updated {new Date(record.updated_at).toLocaleString()}</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>Edit</Button>
            <Button size="sm" variant="ghost" className="text-destructive" disabled={del.isPending}
              onClick={() => { if (confirm(`Delete "${record.title}"?`)) del.mutate(); }}>Delete</Button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
      <DetailsPanel>
        <DetailRow label="Record UUID" value={record.id} />
        <DetailRow label="Owner UUID" value={record.user_id} />
        <DetailRow label="Created" value={record.created_at} />
      </DetailsPanel>
    </li>
  );
}
