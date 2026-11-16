# Base44 migration feasibility

Checked against official documentation on 2026-11-04.
Base44 builds apps from prompts and supplies their hosted services.
The documentation suggests an independent Stack migration is feasible as a backend replacement project, subject to the checks below.
A code export alone leaves Base44 dependencies in place.
This is a documentation assessment. No account changes, purchases, exports, or hosted tests were performed.

## What a Base44 app contains

The documented app export is a React interface built with Vite.
See [project structure](https://docs.base44.com/developers/app-code/overview/project-structure).
The interface calls Base44 through its SDK, a library for using Base44 services.
Base44 supplies a managed NoSQL database, login and sessions, permissions, functions, integrations, and hosting.
NoSQL stores document-shaped records rather than Postgres tables.
The custom backend functions run TypeScript on Deno.
See [backend features](https://docs.base44.com/developers/backend/overview/features).

## What can leave, and on which plan

| Part | Documented route and plan | Export boundary |
| --- | --- | --- |
| Code and data definitions | ZIP export requires **Builder or higher**, edit access, and a computer. | Includes frontend, backend function source, and table fields and permissions. Excludes records, users, secrets, and version history. |
| Git repository | GitHub sync requires **Builder or higher**. Only the app owner can connect the repository. | Keeps app code outside Base44. Does not export the managed backend. |
| Business records | Dashboard → Data → select table → More actions → Export produces CSV. No separate paid export gate is stated. | Clear searches and filters for a full table export. Export every table and compare counts and IDs. |
| User profiles | The beta **List app users** API documents IDs, emails, names, roles, and timestamps. | Requires authorized editor or workspace-owner credentials. Permissions can narrow results. The checked page states no separate paid gate. |
| Passwords and sessions | No portable credential or session export was established in the checked docs on any plan. | A profile list does not preserve passwords or existing logins. |
| Uploaded files | Download bytes through each file's authorized app access route. No complete bulk-export route or paid export gate was established. | File links in CSV are not file bytes. Private-file coverage requires a live test. |

The [code-export guide](https://docs.base44.com/documentation/building-your-app/developer-tools#exporting-your-code)
defines ZIP contents and the Builder gate.
[GitHub instructions](https://docs.base44.com/developers/app-code/local-development/github)
define repository access.
The [data guide](https://docs.base44.com/Building-your-app/Managing-your-app-data#exporting-data)
defines CSV export and filtered exports.
The [user API reference](https://docs.base44.com/api-reference/list-app-users)
defines profile fields, permissions, and paging.
These routes are documented, not tested on a customer app here.

User uploads are separate from the editor's file library.
Private library files use temporary links.
Base44 also says generated app logos cannot be exported.
See [media and uploads](https://docs.base44.com/Building-your-app/Using-media).
For a later migration, inventory every file reference and owner, then verify downloaded byte lengths and SHA-256 checksums.
Re-create secrets from authorized private records outside the code export.

## Required price

**Builder is the minimum documented plan for ZIP, GitHub sync, and backend functions.**
The published price is **US$50 month to month**, or **US$40/month with annual billing**.
The annual rate means US$480 for a year, not a US$40 one-month purchase.
Starter costs US$20 monthly and permits code edits, but does not unlock the documented export route.
Builder includes 250 message credits and 10,000 integration credits monthly.
See the [official price table](https://base44.com/guides/how-much-does-base44-cost)
and [plan features](https://docs.base44.com/Account-and-billing/Billing-and-plans).
Confirm checkout totals and renewal terms before any separately approved purchase.
This feasibility review costs US$0 and needs no upgrade.

## Is a Stack guide feasible?

**A Stack guide appears feasible as a rewrite if the checks below pass.**
This conclusion is an inference from the documented export and replacement options.
A ready migration guide is not yet proved.
Base44 explicitly does not support self-hosting its backend.
Hosting exported frontend code elsewhere still uses Base44 for data, login, functions, and integrations.
See [running exported code elsewhere](https://docs.base44.com/documentation/building-your-app/developer-tools#running-it-elsewhere).

A coding agent would replace SDK calls with an app-owned API, Postgres tables and permissions, shared sessions, and private R2 storage.
The agent must port functions, integrations, schedules, and queued work.
Preserve user IDs and ownership mappings.
Propose a secure password-reset or identity-provider reconnection flow unless a tested credential export supports preserved passwords.
Do not promise existing sessions survive the move.

Before writing a full guide, prove complete record/profile export and authorized download of every private file on a synthetic app.
Then test returning-user login, owner isolation, byte equality, and pending/completed jobs on the replacement backend.
Freeze source writes and schedules for the final snapshot. Enable job execution at only one location during cutover.
Finally prove the [Stack app contract](../design.md#the-app-contract), database switching, two-server sessions, and recovery.
Until those checks pass, label the work a proposed migration rather than a completed platform exit.
