import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { DetailRow, PageHeader } from "@/components/DetailsPanel";
import { getAccountSummary } from "@/lib/portal.functions";

export const Route = createFileRoute("/_authenticated/account")({
  head: () => ({ meta: [{ title: "Account — MMX Source Lovable Portal" }] }),
  component: AccountPage,
});

function AccountPage() {
  const { user } = Route.useRouteContext();
  const fetchSummary = useServerFn(getAccountSummary);
  const summary = useQuery({ queryKey: ["account-summary"], queryFn: () => fetchSummary() });

  return (
    <>
      <PageHeader title="Account" description="Your sign-in details and usage." />
      <section className="rounded-lg border bg-card p-4">
        <h2 className="mb-3 font-bold">Signed in as</h2>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
          <DetailRow label="Email" value={user.email} />
          <DetailRow label="User UUID" value={user.id} />
        </dl>
      </section>
      <section className="mt-6 rounded-lg border bg-card p-4">
        <h2 className="mb-1 font-bold">Server check</h2>
        <p className="mb-3 text-xs text-muted-foreground">Fetched through an authenticated server function.</p>
        {summary.isLoading && <p className="text-muted-foreground">Loading…</p>}
        {summary.error && <p role="alert" className="text-destructive">{(summary.error as Error).message}</p>}
        {summary.data && (
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
            <DetailRow label="Server user UUID" value={summary.data.userId} />
            <DetailRow label="Records" value={summary.data.counts.records} />
            <DetailRow label="Documents" value={summary.data.counts.documents} />
            <DetailRow label="Reports" value={summary.data.counts.reports} />
            <DetailRow label="Checked at" value={summary.data.checkedAt} />
          </dl>
        )}
      </section>
    </>
  );
}
