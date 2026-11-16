# Moving an app from Bolt

Start with the [short Bolt guide](../../../docs/app-platform-migrations/from-bolt.md).
Ask your coding agent to identify the app framework, backend, hosting, and jobs before exporting.

Use the [Supabase example](../from-supabase/README.md) for a Supabase backend.
Use the [Netlify example](../from-netlify/README.md) for Netlify services your app actually uses.
Adapt those examples to your app's schema and authentication methods.

This directory contains routing instructions only. There is no separate Bolt app, exporter, or container to copy.
No Bolt-hosted source app, native export, or Stack deployment was tested for this guide.
The sibling examples' test records describe their own results, not a tested Bolt migration.
