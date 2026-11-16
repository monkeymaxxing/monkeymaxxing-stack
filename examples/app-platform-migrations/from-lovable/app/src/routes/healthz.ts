import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/healthz")({
  server: {
    handlers: {
      GET: async () =>
        Response.json(
          { status: "ok", service: "mmx-source-lovable-portal", time: new Date().toISOString() },
          { headers: { "cache-control": "no-store" } },
        ),
    },
  },
});
