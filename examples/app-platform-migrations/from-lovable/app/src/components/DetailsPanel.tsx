import type { ReactNode } from "react";

/** Unobtrusive collapsible panel showing IDs for migration verification. */
export function DetailsPanel({ summary = "Details", children }: { summary?: string; children: ReactNode }) {
  return (
    <details className="mt-2 rounded-md bg-muted px-3 py-2 text-xs">
      <summary className="cursor-pointer select-none text-muted-foreground">{summary}</summary>
      <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1">{children}</dl>
    </details>
  );
}

export function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mono-id">{value}</dd>
    </>
  );
}

export function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
