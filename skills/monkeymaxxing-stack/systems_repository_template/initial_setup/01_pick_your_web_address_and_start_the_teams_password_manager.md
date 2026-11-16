# Chapter 1: Pick your web address and start the team's password manager

**When:** right after chapter 0's map. Moving the domain to Cloudflare can
take a day, so the move starts in chapter 1 (pick your web address and start the team's password manager).

**What this chapter does:** the person names the domain, where most users
are, and the smallest or the fuller system. The team's password manager
starts. The person sets up the Cloudflare account with two-step sign-in,
adds the domain, and starts the domain's move to Cloudflare.

**Who acts:** the person does every step on a website: cloudflare.com, the
registrar, and the password manager. You, the coding agent, ask the
questions, explain each step, and check the result. The systems repository
does not exist yet, so you record the answers, and chapter 2 (set up your
laptop and your systems desk) writes them into the systems repository.

**Tell the person when the chapter starts:**

> The first step is your app's domain, such as `example.com`: the address
> your users type. Cloudflare receives the requests for your app and sends
> the requests to your servers. Moving your domain to
> Cloudflare can take a day, so the move starts now. Every login
> goes into your password manager as it is made, so no account depends on
> one person's memory.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, and "Tell the person
  after" with the result and its link. Say each message when its step
  comes, in your own words, with the team's own names and links.

## Steps

1. **The domain** the apps answer at, such as `example.com`.

   **Ask the person:**

   > What domain will your app use, such as `example.com`?
   > If your team has no domain yet, tell me, and you register one at Cloudflare in step 7.

   **Tell the person after:** no message, because step 7 adds the domain
   at Cloudflare.

   **Check:** you recorded the domain, or that the team has none yet.

2. **Where most of the app's users are,** a city or a region. The users'
   city or region determines the server provider's location in [chapter 6 (create your three production servers: app, database, and tools)](06_create_your_three_production_servers.md#chapter-6-create-your-three-production-servers-app-database-and-tools), and
   Backblaze's region in [chapter 4 (sign up for the outside services the Stack uses)](04_sign_up_for_the_outside_services_the_stack_uses.md#chapter-4-sign-up-for-the-outside-services-the-stack-uses).
   Use the answer to pick the quiet hours for the servers' schedules:
   `nightly_work_starts_at` (UTC), a time when most users are away; and
   `maintenance_window`, a weekday evening there. The full database backup
   and the weekly restore drill run on Sunday, `weekly_work_day`, by
   default; no question. Record the two answers now. Chapter 2 writes them
   into `mmx_project_settings.yml` once the systems repository exists.

   **Ask the person:**

   > Your servers go near most of your users, so each request travels a shorter distance.
   > Where are most of your app's users: a city or a region?

   **Tell the person after:**

   > Your servers do their nightly work at [the nightly time] your time, when most of your users are away.
   > Database updates and reboots wait for [the weekday evening] your time.
   > The weekly restore drill runs on Sunday. Your team can move the drill to another day later with one setting.

   Give the chosen times in the person's local time. `weekly_work_day` in
   `mmx_project_settings.yml` gives the reason for Sunday and the steps to
   move the drill.

   **Check:** you recorded the users' city or region and the two times.

3. **The smallest system, or the fuller one.** The template is the
   smallest system, so the smallest needs no change. Record the answer;
   with the fuller system, chapter 2 (set up your laptop and your systems
   desk) writes it into the checklist, and chapter 7 (install everything
   on the production servers) adds `staging01` and `app002` with
   [Add staging01](../operating_procedures/add_staging01.md) and
   [Add an app server](../operating_procedures/add_an_app_server.md).
   Recommend the smallest system for an app without paying customers yet.

   **Tell the person first:**

   > The smallest system is three production servers, `app001`, `db01`, and `util01`, beside your systems desk.
   > The fuller system adds `staging01`, a test server where each new app version runs with invented test data before customers get it.
   > It also adds a second app server, `app002`, so the site keeps answering when one app server fails.
   > Each adds one server to the monthly bill. Chapter 6 shows the prices before anything is created.
   > I recommend the smallest system until you have paying customers, because you can add either server later.

   **Ask the person:**

   > Do you want the smallest system or the fuller system?

   **Tell the person after:** no message, because chapter 6 (create your
   three production servers: app, database, and tools) shows the servers
   and their prices.

   **Check:** you recorded the answer.

4. **The password manager:** use the team's existing password manager when
   the team has a password manager. Otherwise, use a new password manager
   that shares logins among the team's people.
   From here on, every login and recovery code goes into the password
   manager as the login or code is made.

   **Ask the person:**

   > Your password manager stores your team's logins and recovery codes, so no account depends on one person's memory.
   > Does your team already use a password manager? If not, please start one that shares logins among your team's people.
   > Tell me which password manager you use.

   **Tell the person after:** no message, because step 5 saves the first
   login in the password manager.

   **Check:** the person names the password manager.

5. **The Cloudflare account,** on cloudflare.com, by the person: the
   team's existing Cloudflare account when the team has one, its login and
   recovery codes into the password manager.

   **Ask the person:**

   > Please sign in to your team's Cloudflare account on cloudflare.com, or make one if your team has none.
   > Save the login and the recovery codes in your password manager.
   > Tell me when you see Cloudflare's home page for the account.

   **Tell the person after:** no message, because step 6 protects the new
   login.

   **Check:** the person sees the account's home page.

6. **Two-step sign-in** on the person's login (My Profile, Authentication;
   [open the page](https://dash.cloudflare.com/profile/authentication)),
   with an authenticator app or a passkey. The person saves the
   recovery codes in the password manager.

   **Tell the person first:**

   > Your Cloudflare account controls your domain's DNS and the requests that reach your app.
   > Two-step sign-in asks for a second proof after the password, so a stolen password alone opens nothing.

   **Ask the person:**

   > Please open [Authentication](https://dash.cloudflare.com/profile/authentication) and turn on two-step sign-in.
   > Use a code from an authenticator app on your phone, or a passkey: a sign-in that your phone or computer approves with a fingerprint, a face, or a PIN.
   > Save the recovery codes in your password manager.
   > Then sign out, sign in again with the password and the second step, and tell me when that works.

   **Tell the person after:** no message, because the person just saw the
   second step work.

   **Check:** the person signs out and signs in again with the password
   and the second step.

7. **The domain, added to the account.** Without a domain, the person registers a domain at Cloudflare (Domain Registration)
   now, once the Cloudflare account exists, at the price Cloudflare
   shows, with the person's approval.
   The new domain is active at once.
   Before the domain's nameservers
   change, compare the DNS records Cloudflare imported with the records
   at the registrar. Add any records Cloudflare missed, starting with
   the MX records that deliver the company's email. After the domain's
   nameservers change, only Cloudflare's records count.

   **Tell the person first:**

   > DNS records direct internet traffic for your domain, such as your email.
   > Your registrar is the company where you registered the domain.
   > Cloudflare must get a copy of every record first, the email records above all, or your company's email stops arriving.

   **Ask the person:**

   > Please add `example.com` to your Cloudflare account, then open the list of DNS records that Cloudflare imported.
   > Open the DNS records at your registrar too, and add any record that Cloudflare missed, the MX records first.
   > Tell me when both lists match.

   **Tell the person after:** no message, because step 9 starts the move
   that the records prepare.

   **Check:** the person says that Cloudflare's records match the
   registrar's.

8. **DNSSEC,** only when the registrar has DNSSEC on: the person turns it
   off at the registrar before the nameserver change, or the domain stops
   resolving. Cloudflare can turn it on again once the domain is active.

   **Ask the person,** only when DNSSEC is on:

   > Your registrar signs your domain with DNSSEC. The old signature does not match Cloudflare's records, so your domain would stop answering.
   > Please turn DNSSEC off at your registrar, and tell me when the registrar shows it off.

   **Tell the person after:** no message, because step 9 follows at once.

   **Check:** the registrar shows DNSSEC off.

9. **The nameservers.** The person replaces the
   domain's nameservers at the registrar with the two that Cloudflare
   names.

   **Ask the person:**

   > Please replace your domain's nameservers at your registrar with the two that Cloudflare names.
   > Then open your domain's overview at Cloudflare, and tell me whether it says "Pending" or "Active".

   **Tell the person after:**

   > Cloudflare shows your domain as "Pending". Cloudflare emails you when the domain is "Active".
   > Tests that use your domain need "Active", such as your apps' public health checks and the MMHotline sign-in.
   > Chapter 2 can continue while the domain move waits.

   **Check:** the domain's overview at Cloudflare says "Pending", or
   "Active" once Cloudflare has activated the domain. Cloudflare also
   emails when the domain is active.
   Look again before [chapter 8 (check that alerts reach your phone and backups restore)](08_check_that_alerts_reach_your_phone_and_backups_restore.md#chapter-8-check-that-alerts-reach-your-phone-and-backups-restore).

## If something is different

- **The team has no domain** (step 1): the person registers one at
  Cloudflare in step 7. The new domain is active at once, so steps 8 and 9
  have nothing to change.
- **The team changes its mind about the system's size later** (step 3):
  the team follows the same operating
  procedures, or "Removing staging01" in
  [Add staging01](../operating_procedures/add_staging01.md#removing-staging01)
  and [Remove a server](../operating_procedures/remove_a_server.md).

## Why the chapter works this way

**The smallest system first.** Reason: the smallest system costs least and has the fewest parts to
learn, and either server can be added on a later day with one operating
procedure, with no change to what exists.

**Two-step sign-in, without more.** The account needs no hardware key and
no second administrator now. The team adds a second administrator when a
second person joins, so one person leaving never locks the team out.

Next: [Chapter 2: Set up your laptop and your systems desk](02_set_up_the_laptop_and_the_systems_desk.md).
