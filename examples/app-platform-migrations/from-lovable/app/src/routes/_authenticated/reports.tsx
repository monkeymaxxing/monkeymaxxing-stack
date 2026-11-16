import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { toast } from "sonner";
import { portal, request } from "@/lib/portal-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/DetailsPanel";
import { runPendingReport } from "@/lib/portal.functions";

export const Route = createFileRoute("/_authenticated/reports")({
  head: () => ({ meta: [{ title: "Reports — MMX Source Lovable Portal" }] }),
  component: ReportsPage,
});

function ReportsPage() {
  const { user } = Route.useRouteContext();
  const qc = useQueryClient();
  const runFn = useServerFn(runPendingReport);

  const jobs = useQuery({
    queryKey: ["report_jobs"],
    queryFn: async () => {
      return request("reports");
    },
  });

  const queue = useMutation({
    mutationFn: async () => {
      await request("reports", "POST", {});
    },
    onSuccess: () => { toast.success("Report queued (PENDING)"); qc.invalidateQueries({ queryKey: ["report_jobs"] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const run = useMutation({
    mutationFn: () => runFn(),
    onSuccess: (r) => {
      toast[r.processed ? "success" : "info"](r.processed ? `Report ${r.job?.id.slice(0, 8)} completed` : "No pending reports");
      qc.invalidateQueries({ queryKey: ["report_jobs"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const pending = jobs.data?.filter((j) => j.status === "PENDING").length ?? 0;

  return (
    <>
      <PageHeader title="Reports" description="Queued reports stay PENDING until you run them." />
      <div className="mb-6 flex flex-wrap gap-2">
        <Button onClick={() => queue.mutate()} disabled={queue.isPending}>Queue report</Button>
        <Button variant="outline" onClick={() => run.mutate()} disabled={run.isPending || pending === 0}>
          {run.isPending ? "Running…" : `Run pending report${pending ? ` (${pending})` : ""}`}
        </Button>
      </div>
      {jobs.isLoading && <p className="text-muted-foreground">Loading…</p>}
      {jobs.error && <p role="alert" className="text-destructive">{(jobs.error as Error).message}</p>}
      {jobs.data?.length === 0 && <p className="text-muted-foreground">No reports yet.</p>}
      {!!jobs.data?.length && (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-muted-foreground">
              <tr><th className="p-3">ID</th><th className="p-3">Status</th><th className="p-3">Requested</th><th className="p-3">Completed</th><th className="p-3">Output</th></tr>
            </thead>
            <tbody>
              {jobs.data.map((j) => (
                <tr key={j.id} className="border-t align-top">
                  <td className="p-3 mono-id">{j.id}</td>
                  <td className="p-3">
                    <Badge variant={j.status === "COMPLETED" ? "default" : j.status === "FAILED" ? "destructive" : "secondary"}>{j.status}</Badge>
                    {j.archived_at && <span className="ml-1 text-xs text-muted-foreground">archived</span>}
                  </td>
                  <td className="p-3 text-xs">{new Date(j.requested_at).toLocaleString()}</td>
                  <td className="p-3 text-xs">{j.completed_at ? new Date(j.completed_at).toLocaleString() : "—"}</td>
                  <td className="p-3"><pre className="mono-id whitespace-pre-wrap">{j.output ?? "—"}</pre></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
