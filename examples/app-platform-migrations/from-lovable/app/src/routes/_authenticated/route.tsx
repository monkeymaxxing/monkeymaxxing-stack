import { createFileRoute, Link, Outlet, redirect, useNavigate, useRouter } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { portal, request } from "@/lib/portal-client";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async () => {
    const { data, error } = await portal.auth.getUser();
    if (error || !data.user) throw redirect({ to: "/login" });
    return { user: { id: data.user.id, email: data.user.email ?? "" } };
  },
  component: AppLayout,
});

const nav = [
  { to: "/records", label: "Records" },
  { to: "/documents", label: "Documents" },
  { to: "/reports", label: "Reports" },
  { to: "/account", label: "Account" },
] as const;

function AppLayout() {
  const { user } = Route.useRouteContext();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const router = useRouter();

  async function logout() {
    await queryClient.cancelQueries();
    queryClient.clear();
    // scope "global" revokes the refresh token / session server-side.
    await portal.auth.signOut();
    await router.invalidate();
    navigate({ to: "/login", replace: true });
  }

  return (
    <div className="min-h-screen md:flex">
      <aside className="bg-sidebar text-sidebar-foreground md:w-60 md:shrink-0">
        <div className="flex items-center justify-between px-5 py-4 md:block">
          <p className="text-sm font-bold text-sidebar-primary">MMX Source Lovable Portal</p>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {nav.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              className="rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
              activeProps={{ className: "bg-sidebar-accent font-bold text-sidebar-accent-foreground" }}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="hidden px-5 py-6 md:block">
          <p className="truncate text-xs text-sidebar-foreground/70" title={user.email}>{user.email}</p>
        </div>
      </aside>
      <div className="flex-1">
        <header className="flex items-center justify-end gap-3 border-b bg-card px-6 py-3">
          <span className="hidden text-sm text-muted-foreground sm:inline">{user.email}</span>
          <Button variant="outline" size="sm" onClick={logout}>Log out</Button>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
