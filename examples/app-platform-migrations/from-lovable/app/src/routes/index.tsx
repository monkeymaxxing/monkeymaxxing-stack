import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MMX Source Lovable Portal" },
      { name: "description", content: "Sign in to manage your records, documents and reports." },
      { property: "og:title", content: "MMX Source Lovable Portal" },
      { property: "og:description", content: "Sign in to manage your records, documents and reports." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-lg text-center">
        <p className="text-sm font-bold tracking-wide text-primary">MMX Source Lovable Portal</p>
        <h1 className="mt-3 text-3xl font-bold">Your records, documents and reports in one place.</h1>
        <p className="mt-3 text-muted-foreground">Sign in or create an account to continue.</p>
        <div className="mt-8 flex justify-center gap-3">
          <Button asChild><Link to="/login">Log in</Link></Button>
          <Button asChild variant="outline"><Link to="/register">Register</Link></Button>
        </div>
      </div>
    </main>
  );
}
