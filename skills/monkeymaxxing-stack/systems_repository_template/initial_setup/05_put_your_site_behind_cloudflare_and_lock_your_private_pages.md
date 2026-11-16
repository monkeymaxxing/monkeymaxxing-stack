# Chapter 5: Put your site behind Cloudflare and lock your private pages

**When:** after chapter 4 (sign up for the outside services the Stack uses).
Complete steps 1 through 6 (host names, tunnels, DNS, Access, MMHotline's Access settings, and the Cache Rule) before chapter 7 (install everything on the production servers). The roles read the tunnel tokens, and MMHotline reads the
Access settings.

**What this chapter does:** Cloudflare gets ready to bring users' requests
to the servers through tunnels. Cloudflare Access, a sign-in, goes in front
of the private pages, and a Cache Rule lets Cloudflare cache what each app
marks as cacheable.

**Who acts:** you, the coding agent, do every step from this systems desk,
through Cloudflare's API. The person approves the alert dashboard's host
name, opens the links, and signs in once, as each step's messages say.

**Tell the person when the chapter starts:**

> Next, I set up Cloudflare for your site: tunnels, a sign-in for your
> private pages, and a cache rule for your apps.
> Users never reach your servers directly.
> Users reach Cloudflare, and Cloudflare reaches your servers through tunnels.
> A tunnel is a connection that your servers open out to Cloudflare.
> So no server needs an open web port, and a scan of the internet finds no web server of yours to attack.
> Cloudflare also filters what comes in.
> A sign-in, Cloudflare Access, goes in front of your private pages.
> Your part is small: approve one web address, open the links I give you, and test the sign-in once.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, and "Tell the person
  after" with the result and its link. Say each message when its step
  comes, in your own words, with the team's own names and links.
- **Commands that source the person's token file,** `~/.config/monkeymaxxing-stack/example_systems.env`,
  run only in the person's own desk terminal, as the secrets rule in
  [The rules](../AGENTS.md#the-rules) says.
- **Every Cloudflare request goes through the API proxy.** Use Cloudflare's
  API from this systems desk for the tunnels and DNS records, the Access
  applications and policies, and the cache rule. The coding agent sends
  every request to the API proxy at
  `http://127.0.0.1:8082/`, which stands for `https://api.cloudflare.com/client/v4/`
  and adds the person's desk token, so the agent never reads the token.
- **The IDs in the requests.** `ACCOUNT_ID` in a request is
  `vars.cloudflare_account_id` in `mmx_project_settings.yml`, and `ZONE_ID`
  is the domain's zone ID: `result[0].id` of
  `GET http://127.0.0.1:8082/zones?name=example.com`.
- **The links.** Each "Tell the person after" gives the link that shows
  the step's result at Cloudflare. Cloudflare asks which domain when the
  account has several.

## Steps

1. **The private pages' host names:** set
   `util01_private_page_host_names` under `vars` in
   `mmx_project_settings.yml` before creating the Cloudflare resources.
   Set `mmhotline` for MMHotline's dashboard, such as `ops.example.com`.
   Propose only a name that is available: a name is available when the
   domain has no DNS record for the name.

   **Ask the person:**

   > Your alert dashboard needs its own web address. I propose `ops.example.com`.
   > Your domain has no DNS record for `ops.example.com`, so the name is free.
   > Only your team can open the alert dashboard, after a sign-in.
   > Do you want `ops.example.com`, or another name?

   **Tell the person after:** no message, because step 3 shows the
   name's DNS record at Cloudflare.

   **Check:** `util01_private_page_host_names.mmhotline` holds the name the
   person approved, and the domain still has no DNS record for the name.

2. **Two tunnels, each locally managed.** The
   routes live in the systems repository's `cloudflared_config.yml`
   templates.
   Production and staging use
   `roles/tunnel_connector_and_caddy/files/cloudflared_config.yml`.
   The private pages use `roles/util_server/files/cloudflared_config.yml`.
   The templates read the host-name settings and need no edits during
   chapter 5 (put your site behind Cloudflare and lock your private pages).

   `set-up-outside-services cloudflare`, in
   [chapter 4 (sign up for the outside services the Stack uses)](04_sign_up_for_the_outside_services_the_stack_uses.md#chapter-4-sign-up-for-the-outside-services-the-stack-uses),
   created each tunnel below through the API, with `"config_src": "local"`,
   and saved each tunnel's token in the vault. Find each tunnel's ID
   through the proxy, for the DNS records:
   `GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/cfd_tunnel?name=example_systems-util01&is_deleted=false`,
   `result[0].id`.

   | Tunnel name | Vault key for the tunnel's token | Host names routed through the tunnel |
   | --- | --- | --- |
   | `example_systems-apps` | `apps_cloudflare_tunnel_token` | Each app's production host name, in `public_host_names.production` in `inventories/servers.yml` |
   | `example_systems-util01` | `util01_cloudflare_tunnel_token` | MMHotline's dashboard: `mmhotline` under `util01_private_page_host_names` in `mmx_project_settings.yml` |

   **Tell the person first:**

   > Next, I check the two tunnels that chapter 4 made at Cloudflare.
   > Your apps use the tunnel `example_systems-apps`, and your private pages use the tunnel `example_systems-util01`.
   > Each tunnel has its own settings and its own access key.
   > So a change to one tunnel leaves the other tunnel as it is.

   **Ask the person,** only when a tunnel or its token is missing:

   > Cloudflare has no tunnel `example_systems-util01`, or your vault has no token for the tunnel.
   > Please run this command in your own terminal on your systems desk, in the systems repository:
   > `. ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services cloudflare`
   > The command prints a link for a new link token, as in chapter 4, and makes only what is missing.
   > Tell me when the command ends.

   **Tell the person after:**

   > Your two tunnels are ready at Cloudflare: [tunnels](https://one.dash.cloudflare.com/?to=/:account/networks/tunnels).
   > Your servers connect to the tunnels only after their setup in chapter 7.

   **Check:** the request above returns each tunnel's ID, and
   `sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage` shows
   each tunnel's vault key as defined.

3. **DNS:** for each host name, create a proxied CNAME record. A proxied
   record sends the host name's web requests through Cloudflare.
   The CNAME's content is the tunnel's `TUNNEL_ID.cfargotunnel.com`
   (`POST .../zones/ZONE_ID/dns_records` with `"proxied": true`).
   Never create the status page's DNS
   record yourself: `set-up-outside-services cloudflare` created the
   record in chapter 4, through `mmhotline status-page set-up`, and a rerun
   creates the record when the domain was still Pending then.
   [Chapter 8 (check that alerts reach your phone and backups restore)](08_check_that_alerts_reach_your_phone_and_backups_restore.md#chapter-8-check-that-alerts-reach-your-phone-and-backups-restore)
   checks the status page.

   **Tell the person first:**

   > Next, I add a DNS record for each web address: `shop.example.com` for your app, and `ops.example.com` for your alert dashboard.
   > Each DNS record points the web address at a tunnel, not at a server.
   > So no DNS record shows a server's address.

   **Tell the person after:**

   > Your domain's DNS records now send `shop.example.com` and `ops.example.com` to the tunnels: [DNS records](https://dash.cloudflare.com/?to=/:account/:zone/dns/records).
   > If Cloudflare asks which domain, pick `example.com`.

   **Check:** the zone's DNS records, read through the proxy, list one
   proxied CNAME for each host name, to the tunnel in step 2's table.

4. **Access:** a self-hosted Access application is a Cloudflare setting
   that protects a page served by the company's servers.
   Create an Access application for each private host name
   (`POST .../accounts/ACCOUNT_ID/access/apps`):
   MMHotline's dashboard; [Add staging01](../operating_procedures/add_staging01.md)
   adds the staging host names' applications the same way.
   Use the host name set under `mmhotline` in
   `util01_private_page_host_names` in `mmx_project_settings.yml`.

   An Access policy says who may open a protected page.
   Give each application an Allow policy that admits only the company's
   people. The policy names emails ending in `@example.com` or the
   company's GitHub organization, never everyone who signs in.

   A policy that names email addresses needs a login method that proves
   each person's address. Use One-time PIN, Cloudflare's own: Access
   emails a code to the address. A new Zero Trust organization has only
   the Cloudflare identity provider, which signs in people who have a
   Cloudflare account, and One-time PIN isn't added automatically, so
   `set-up-outside-services cloudflare` added it in chapter 4 (sign up for the outside services the Stack uses).
   Read each `type` in
   `GET .../accounts/ACCOUNT_ID/access/identity_providers` to check that
   the login method exists.

   **Tell the person first:**

   > Next, I lock your alert dashboard, `ops.example.com`, behind Cloudflare Access.
   > Only people with an email address that ends in `@example.com` can open the alert dashboard.
   > To sign in, a person types a company email address.
   > Access then emails a one-time code to the address, and the person types the code.

   **Ask the person,** after the application exists:

   > Please open https://ops.example.com and sign in with your company email address and the code that Cloudflare emails you.
   > After the code, Cloudflare shows its error page "Error 1033".
   > Error 1033 means that no server is connected to the dashboard's tunnel yet: `util01` connects in chapter 7.
   > So the error is expected until chapter 7, and it shows that your sign-in passed.
   > Tell me when you see it.

   **Tell the person after:**

   > Your sign-in works. The Access application admits only addresses that end in `@example.com`: [Access applications](https://one.dash.cloudflare.com/?to=/:account/access/apps).

   **Check:** every Allow rule names the domain, and the person saw
   Error 1033 after the code. Mark `company_email` as
   `done` in `monkeymaxxing_stack_checklist.yml` after the item's
   `verification` passes. The item's `verification` includes the person's
   sign-in.

5. **MMHotline's Access settings,** in `mmhotline_settings.yml`, which came
   with the template ([chapter 7 (install everything on the production servers)](07_install_everything_on_the_production_servers.md#chapter-7-install-everything-on-the-production-servers) fills in the rest):
   `cloudflare_access.team_domain`, from `result.auth_domain` of
   `GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/access/organizations`,
   such as `example.cloudflareaccess.com`; and
   `cloudflare_access.audience_tag`, the Application Audience (AUD) Tag of
   MMHotline's application, `result.aud` of its creation.

   **Tell the person:** no message, because the two settings only let
   MMHotline check the sign-ins of step 4.

   **Check:** `cloudflare_access.team_domain` is the account's
   `auth_domain`, and `cloudflare_access.audience_tag` is the `aud` of
   MMHotline's application, not the template's zeros.

6. **The Cache Rule,** so Cloudflare caches what each app marks with its
   `Cache-Control` header (the item `cloudflare_caches_what_the_app_marks`):
   one rule in the zone's cache settings, for every production host name
   in `public_host_names.production`. Retrieve the zone's cache rules
   through Cloudflare's API:
   `GET .../zones/ZONE_ID/rulesets/phases/http_request_cache_settings/entrypoint`.
   The request for the zone's cache rules answers 404 when the zone has no
   cache rules. Then create the zone's cache ruleset containing the rule:

   ```sh
   # This systems desk, as the coding agent; the API proxy adds the token:
   curl -fsS -X PUT -H "Content-Type: application/json" \
       "http://127.0.0.1:8082/zones/ZONE_ID/rulesets/phases/http_request_cache_settings/entrypoint" \
       -d '{"rules": [{"description": "The apps: cache what each app marks with Cache-Control",
            "expression": "(http.host in {\"shop.example.com\"})", "action": "set_cache_settings",
            "action_parameters": {"cache": true, "edge_ttl": {"mode": "respect_origin"}, "browser_ttl": {"mode": "respect_origin"}}}]}'
   ```

   The entrypoint is the zone's cache ruleset, which holds the cache rules
   Cloudflare runs for the zone.

   **Tell the person first:**

   > Next, I add a cache rule for your app at Cloudflare.
   > A cache stores responses for reuse, so your servers do less work.
   > Only responses that your app allows for shared use enter Cloudflare's cache.
   > Private responses stay outside Cloudflare's cache.

   **Ask the person,** only when an existing rule already covers a
   production host name (see [If something is different](#if-something-is-different)):

   > Your domain already has a cache rule that covers `shop.example.com`. Here is the existing rule: [the rule's settings].
   > My rule caches only what your app marks with its `Cache-Control` header.
   > Do you approve changing the existing rule?

   **Tell the person after,** which also ends the chapter:

   > Cloudflare now caches what your app marks as cacheable: [Cache Rules](https://dash.cloudflare.com/?to=/:account/:zone/caching/cache-rules).
   > Your tunnels, DNS records, Access application, and cache rule now exist at Cloudflare.
   > Your servers connect only after their setup in chapter 7.

   **Check:** the zone's cache ruleset has a rule with `respect_origin`
   for every production host name. Then Cloudflare's API must list the
   tunnels, the tunnels' DNS records, the Access applications, and the
   cache rule, before you tell the person the settings exist at
   Cloudflare. Chapter 9 (go live) marks
   `cloudflare_caches_what_the_app_marks` as `done`.

## If something is different

- **The proposed host name is in use** (step 1): the domain has a DNS
  record for the name. Propose another name to the person.
- **A policy names the GitHub organization** (step 4): the policy uses the
  `github` login method instead of One-time PIN; read each `type` in
  `GET .../accounts/ACCOUNT_ID/access/identity_providers` to check that
  the `github` login method exists.
- **The zone has cache rules already** (step 6): add the rule that follows
  the apps' `Cache-Control` headers with
  `POST .../zones/ZONE_ID/rulesets/RULESET_ID/rules` instead.
  `RULESET_ID` is `result.id` from the request for the zone's cache rules.
  Use `POST` because a `PUT` replaces every rule in the zone's cache
  ruleset.
- **An existing rule already covers a production host name** (step 6):
  show the existing rule to the person, and change the existing rule only
  with the person's approval.
- **With `staging01`:** [Add staging01](../operating_procedures/add_staging01.md)
  adds the staging host names' DNS records and Access applications, as in
  steps 3 and 4.

## Why the chapter works this way

**Locally managed tunnels.** A tunnel made in Cloudflare's dashboard keeps
its routes at Cloudflare instead, so `set-up-outside-services cloudflare`
made each tunnel through the API with `"config_src": "local"`. Then the
routes live in the systems repository's `cloudflared_config.yml`
templates, and a rebuilt server gets the routes from Git.

**What separate tunnels leave shared.** The two tunnels still depend on
the team's Cloudflare account and on Cloudflare's tunnel service.

**The desk token only reads login methods.** Reason: the desk token can
only read login methods. A login method
decides whose address Access believes, so a token in the API token
proxy that could add one would let a mistake admit anyone. The command
adds One-time PIN with a short-lived token that it deletes at once.

**Error 1033 before chapter 7.** Error 1033 means that Cloudflare finds
no running `cloudflared` for the tunnel
([Cloudflare Tunnel troubleshooting](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/troubleshoot-tunnels/common-errors/)).
Access checks the sign-in first, so the error page proves the sign-in.

**MMHotline checks the sign-in too.** MMHotline uses
`cloudflare_access.team_domain` and `cloudflare_access.audience_tag` to
check each person's Access sign-in itself, so a request that reaches
`util01` without Cloudflare Access's sign-in gets no dashboard.

**The laptop holds no production credential.** The laptop receives no Cloudflare administration token, production vault passphrase, or production SSH key.
Systems-side Access checks run from the desk.

Next: [Chapter 6: Create your three production servers: app, database, and tools](06_create_your_three_production_servers.md).
