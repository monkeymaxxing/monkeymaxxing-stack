# Move a Bolt app to your own system

## Variances and guidance needs

This guide helps you move an app from Bolt to the Monkeymaxxing Stack.
Start by identifying your app's services, then follow the Supabase and Netlify migration guides below.
No Bolt-hosted migration or Stack deployment was proved for this guide.
Documentation checked on 2026-11-04.

- Direct code editing and terminal use in Bolt need a Chromium browser, such as Chrome or Vivaldi.
  Safari shows read-only code. See [supported browsers](https://support.bolt.new/reference/supported-technologies).
- GitHub linking needs the GitHub primary email to match the Bolt account email.
  This condition was observed during account setup, not independently reproduced in the migration check.
  Downloading code avoids GitHub linking.
- A code download does not contain live database records, user credentials, or uploaded file bytes.
  Export those separately before changing services.

## Find the parts your app uses

Bolt builds ordinary JavaScript apps, such as Vite/React or Next.js apps.
React builds the interface, Vite builds browser files, and Next.js can also run server code.
The backend stores records, signs users in, and keeps uploaded files.

Ask your coding agent to record the following from your actual project:

| Part | Where to look |
| --- | --- |
| App code | Read `package.json`, build scripts, dependency lockfiles, and Vite or Next.js configuration. |
| Backend | Compare Bolt's Database panel with the code's service URLs and Supabase client calls. |
| Hosting | Check Publish settings, the live domain, and any connected Netlify site. |
| Functions and jobs | List server functions, queue tables, schedules, integrations, and secret names. Keep secret values private. |

An app can use your own Supabase project or Bolt's built-in Supabase-backed database, authentication, storage, and functions.
See [Supabase's Bolt Cloud description](https://supabase.com/blog/bolt-cloud-launch).
Hosting can be [Bolt hosting or Netlify](https://support.bolt.new/integrations/netlify).
Netlify hosting alone does not mean Netlify stores your users or files.

## Get the code out

In your Bolt project, click the project title, then **Download**.
Unzip the archive and keep the source, lockfiles, migrations, and function files together.
See [Bolt's download instructions](https://support.bolt.new/managing-projects/projects-files).
Alternatively, clone the repository from the project's [GitHub connection](https://support.bolt.new/integrations/git).
Record the revision or archive checksum before editing.

For Bolt Database, first establish authorized backend access.
Default backends belong to Bolt's organization and do not automatically appear in your personal Supabase dashboard.
See [Supabase's ownership explanation](https://supabase.com/kb/troubleshooting/supabase-project-provisioned-via-bolt-not-visible-in-dashboard).
Bolt documents **Database → Advanced → Claim** into Supabase, requiring Bolt Pro or Teams and a destination Supabase organization owner.
Confirm the current flow and price before a paid change.
**Connect** replaces the database connection and can lose access to existing data.
See [Claim versus Connect](https://support.bolt.new/integrations/supabase#claim-your-bolt-database-in-supabase).

## Follow the guide for each service

- For Supabase or a successfully claimed Bolt backend, use [From Supabase](from-supabase.md).
  Inventory users, permissions, files, functions, and jobs before adapting the example to your schema.
  Claiming alone does not prove password or file export.
- For Netlify hosting and any Netlify services actually used, use [From Netlify](from-netlify.md).
  Keep the Supabase export route when Supabase owns the backend.
- For Bolt hosting, use your app's framework deployment steps after replacing the managed backend calls.
  A static browser app needs a serving process that meets the [Stack app contract](../design.md#the-app-contract).

Keep the source running until the selected guide's data checks and rollback preparation pass.
Enable pending jobs at only one location during cutover.
The [example README](../../examples/app-platform-migrations/from-bolt/README.md) records this guide's scope and proof limits.
