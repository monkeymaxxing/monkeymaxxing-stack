# Testing changes to the Monkeymaxxing Stack

Test only what changed, with the smallest check that proves the change. If
one thing broke in one place, test that one thing.

On every push and pull request, GitHub Actions runs every test in `tests/`
and `go vet`, `go test` and `gofmt` in
`set_up_outside_services/`, with MMX built from the release the template
pins (`.github/workflows/checks.yml`). The checks below say what to run
before that, and what only real servers prove.

A test that runs MMX needs the MMX release that `stack_software.mmx` in the
template's `mmx_project_settings.yml` pins, or a later one: the restore drill
needs its `mmx mark-node-work-failed`, which records the work of an older run
whose saved ssh_config path is gone ([A Stack release pins its own
programs](design.md#a-stack-release-pins-its-own-programs)).

| What changed | The check that proves the change |
| --- | --- |
| Text only | Check that links resolve. Have a fresh reader read new or heavily changed guide text. No servers are needed. |
| The systems repository template | Run `python3 tests/staging_server_test.py` with MMX on PATH or `MMX_BINARY` set: it runs `mmx validate` on a copy of the template with the setup's values filled in, with and without `staging01`. `mmx validate` on the template itself refuses, because the template ships the values only the setup knows empty. |
| The utility-server helper, `run_mmx_on_util01` | Run `python3 tests/run_mmx_on_util01_test.py`. |
| Break-in containment, evidence, or the status switch | Run `python3 tests/break_in_response_test.py` with MMX on PATH or `MMX_BINARY` set. Prove the two-desk drill in `operating_procedures/respond_to_a_break_in.md` on disposable guests, including an active MMX job, fresh SSH and HTTPS MMX after undo, and an HTTP client. |
| `set-up-outside-services`, the account and secret setup command | Run `go vet ./...` and `go test ./...` in `set_up_outside_services/`. For a change to its requests, its root step, or its files, also apply the desk role through MMX on a disposable Debian 13 desk, so the role installs the release from `build_release_archive.sh`, and run each changed command as the person, in a terminal, against `internal/standins/serve` over TLS. Before a release, a short live run at Backblaze and Cloudflare checks what stand-ins cannot: the providers' permission checks, the lock's enforcement, the permission groups' names, and the dashboard links. |
| The release build, `set_up_outside_services/build_release_archive.sh`, or the refusal of a pin of zeros | Run `python3 tests/release_build_test.py`, and `python3 tests/pinned_program_releases_test.py` with MMX on PATH or `MMX_BINARY` set. A real release build runs on Linux with Go. |
| The systems desk server button, `run-mmx-on-the-servers` | Run `python3 tests/run_mmx_on_the_servers_test.py`, then prove the account, socket, Git, MMX and API boundaries on disposable guests. |
| Server-side Bash helpers | Run `python3 tests/server_scripts_test.py`. |
| A provider guide's scripts in `provider_guides/` (DigitalOcean, Vultr, Scaleway, OVHcloud), or the script contract in `server_management_scripts/README.md` | Run the guide's `python3 tests/PROVIDER_provider_scripts_test.py`, such as `tests/vultr_provider_scripts_test.py`: it builds the five scripts from the guide's code blocks and runs them with each `bash` on the machine against a stand-in of the provider's API, through the proxy and with `util01`'s token. A change to a request or a right needs a round on a real account with `util01`'s rights: create with first-boot data, list, power off twice, destroy twice, the price. At OVHcloud, the round also runs the restore drill with `util01`'s narrow rules, and checks the price script's monthly prices by hand against the provider's catalog. |
| The uploaded-file restores in `restore_an_uploaded_file.md` | Run `python3 tests/restore_uploaded_files_test.py` with MMX on PATH or `MMX_BINARY` set. It validates both one-time playbooks as written and runs the whole-app restore's counting step against a stand-in rclone. A real B2 and R2 must still prove `--b2-version-at` and the copy back into R2. |
| App container confinement or shutdown | Run `python3 tests/app_container_apparmor_test.py`, then the real-system shutdown checks below. For the read-only file system, start each framework example's web and job containers with `--read-only --read-only-tmpfs` and the app's `writable_temporary_directories`, and check that they serve (2026-11-07: only Laravel needs directories, and the Django and FastAPI examples switch off gunicorn's control socket). |
| A database moving into the Stack | Run `python3 tests/database_moving_in_test.py` with MMX on PATH, or set `MMX_BINARY`. Render the URLs and peers, then prove copy, switch, timeout recovery, replica state, unchanged containers, and a backup on disposable servers. The Node driver change also runs `npm test` in `skills/monkeymaxxing-stack/files_for_your_app/node/` inside a test guest. |
| Database password rotation | Run `python3 tests/end_connections_that_use_an_old_database_password_test.py`. |
| First-boot data, WireGuard enrollment, or private SSH | Run `python3 tests/private_server_access_test.py` and `python3 tests/restore_drill_test.py`; validate with MMX built from the WireGuard-access implementation. On a disposable server, prove IPv4/IPv6 TCP 22 closes before ssh.service or ssh.socket can accept traffic, first-boot enrollment, metadata HTTP closure, and console recovery. |
| The row recovery, `playbooks/recover_rows_from_a_restored_copy.yml`, or the restore01 steps in `steps_for_a_server_this_run_creates.bash` | Run `python3 tests/recover_rows_from_a_restored_copy_test.py` and `python3 tests/restore_drill_test.py` with MMX on PATH or `MMX_BINARY` set. The row-recovery test runs the playbook's program with stand-ins for the provider, `wg`, the inner `restore_database` and `ssh`; with PostgreSQL's `initdb`, `pg_ctl` and `psql` on PATH, `ssh` runs the copy and the transaction against two real local clusters, otherwise those tests are skipped. A real system must still prove the preview and the real run against a real B2 backup, with `util01`'s copy clean and no `restore01` or runtime peer left afterwards. |
| The main copy of the systems repository on `util01`: the `util_server` role's bare repository, MMHotline's clone of it, or where the desk's commands read pushed `main` | Run `python3 tests/main_copy_on_util01_test.py` with MMX on PATH or `MMX_BINARY` set, and `python3 tests/run_mmx_on_the_servers_test.py`, `python3 tests/systems_desk_door_test.py` and `python3 tests/desk_repository_and_lock_out_button_test.py`. A real `util01` must still prove the first push from the desk over WireGuard, MMHotline's clone as `root@127.0.0.1`, and a push from MMHotline's server replacement. |
| Restore drill or scheduled jobs, or which commit `util01` runs | Run `python3 tests/restore_drill_test.py` and `python3 tests/timers_run_only_trusted_commits_test.py` with MMX on PATH or `MMX_BINARY` set, then prove the changed workflow on the standing test system. The drill giving way must be proved on real servers: from the waiting marker to a free lock (the design estimates the provider's destroy plus 30 to 40 seconds), `mmx stop` exiting 3, `mmx mark-node-work-failed --node restore01 --json` exiting 0 after the inner `mmx run` process ended, the unit exiting 75 and `mmx status` showing no unconfirmed work; and a failed cleanup (the mark command exiting 2, 3 or 4) failing the unit, with `cleanup_failure_reason` in `latest_result.json`. |
| The replacement of a failed server: `replace_failed_servers`, `destroy_replaced_servers`, their programs in `server_management_scripts/`, or the reboot playbook's window reason | Run `python3 tests/replace_failed_servers_test.py` and `python3 tests/destroy_replaced_servers_test.py` with MMX on PATH or `MMX_BINARY` set; they need bash 4 or later, git and jq. Each copies the template into a Git repository with a bare Git host beside it, takes the env from `mmx explain`, and runs the program with stand-in provider scripts, ssh and wg, real Git and real `mmx validate`. Also run `python3 tests/restore_drill_test.py`, which shares the create steps, and `python3 tests/alert_pauses_test.py`. The tests cover jobs servers and load-balancer servers too (the new name and address, the inventory edit, refusals, destroy by trailer ID); a change to `check-that-this-server-does-its-work` also needs `python3 tests/check_that_this_server_does_its_work_test.py`. Test servers at a real provider must still prove these walks: the only app server dies, a bad new server, the pool failing again, more than half silent, a reboot that never returns, one approval covering three runs, a failed jobs server and the only jobs server replaced (jobs run again on the new one), and a failed load-balancer server replaced while its partner carries every request (the users' error count, and how soon Cloudflare stops sending requests to the powered-off connector). With MMHotline's server replacement and `routine_fixes_and_server_work`, they must also prove three cases on the only app server: the site recovers during the replacement (MMHotline's one warning as `replace_failed_servers` starts, the triage agent's reports at info, the SOS's resolved message, and no wake); `every_server` fails (the person on call woken at once); the replacement passes `sos_waits_for_a_server_replacement_minutes` (woken at the limit). They must show the price lines: `replace_failed_servers`'s last lines with the new server's type and monthly price, and the triage agent's reports that carry it; and the team's fifth script, `read_the_monthly_price_at_the_provider`, at Hetzner, where no guide gives it whole. The time from the replacement's start to the site answering again sets the rules' usual time (about 3 minutes, measured 2026-11-13: 2 m 11 s to 2 m 21 s at Hetzner) and the setting's default (7). The next run must also prove: the agent alone, from a plain failure (the app server stopped at the provider, no reboot), requests `replace_failed_servers` even when it replaced a server of the pool earlier the same day, and the playbook's own refusals (tries, the failure within the setting's hours, the bound) decide; save each run's per-stage and per-server times, with the provider's create and boot, the wait for first boot and `util01` joining WireGuard, and the time from the replacement's start to a serving site (the table in `docs/design.md`, "Where the minutes go"); after `destroy_replaced_servers`, `mmx status` lists no unconfirmed work of the destroyed server; with a pinned `mmx mark-node-work-failed` that exits 2, the run stops and commits nothing more. |
| Adding and removing app servers with the load: `add_an_app_server_for_the_load`, `remove_server` (with or without `server_name`), their programs, `check-whether-the-load-changes-the-app-pool`, `util01`'s two load checks, or the shared steps file | Run `python3 tests/app_pool_with_the_load_test.py` (the rule with a stand-in for `mmwatchdog fleet readings`, and the checks rendered by MMX), `python3 tests/add_an_app_server_for_the_load_test.py`, `python3 tests/remove_an_app_server_for_the_load_test.py` and `python3 tests/replace_failed_servers_test.py`, which shares the steps file, with MMX on PATH or `MMX_BINARY` set; also `tests/task_outputs_after_a_secret_test.py` and `tests/sudoers_triage_test.py`. Test servers at a real provider must still prove: load on the app servers until `util01`'s add check warns, the warning, the add, `every_server`, the site faster; the load removed and a shortened low-load window, the removal with the server out of the tunnel before its destroy; Stop pressed once; the largest and smallest numbers refusing; the real readings' JSON and recorded limits as the rule reads them; what the phone gets for an add and a removal (MMWatchdog's warning from `util01`, MMHotline's warning is the only sound, the triage agent's info reports, its outcome at info too, and a warn only for a failed or refused change), and with the other two answers the app servers' CPU warning with the triage agent's report at info. `tests/app_pool_with_the_load_test.py` also renders the app servers' CPU check at info only with the third answer, and runs `util01`'s two check scripts for each of the rule's exit codes. |
| `util01`'s alert pauses (`util01-alert-pause`), the come-back wait (`come_back_wait_after_a_reboot`) and the pauses that follow from it, or MMHotline's rules for the three answers | Run `python3 tests/alert_pauses_test.py` and `python3 tests/triage_agent_server_work_test.py` with MMX on PATH or `MMX_BINARY` set. A change to `mmhotline_settings.yml` or the MMHotline pin also needs the pinned release's own `mmhotline settings check` on the rendered settings of each of the three answers, with well-formed stand-in secrets. A real `util01` must prove that `public_sites` stays out of maintenance during `reboot_util01_after_updates` (`mmwatchdog status --json`, `maintenance`). |
| Check groups or the triage user's sudo lines | Run `python3 tests/sudoers_triage_test.py` from the stack repository's root. |
| The pinned programs' release checks, `pinned_program_releases` in `mmwatchdog_checks/util_server.yml`, or `stack_software` | Run `python3 tests/pinned_program_releases_test.py` with MMX on PATH or `MMX_BINARY` set. It renders the real `every_server` playbook for `util01` and runs each generated script against a stand-in GitHub API. A real `util01` must still prove the checks against GitHub itself: `mmwatchdog check-now pinned_program_releases` there. |
| Which check file a server gets (`mmwatchdog_check_file`, the role `mmwatchdog_joined_node`) | Run `python3 tests/server_connections_test.py`: a new pool's servers get `every_server.yml` and the pool's file. A change to which files a running server gets also needs a dryrun of the MMWatchdog stages on test servers that proposes no change on the servers whose checks stay. |
| Which pool talks to which: `connections_between_server_pools`, the role `work_out_who_this_server_talks_to`, the WireGuard template, or the firewall task | Run `python3 tests/server_connections_test.py` with MMX on PATH, or set `MMX_BINARY`. It takes each server's inputs from `mmx explain` of the real playbooks, runs the role's program, renders `wg0`, and compares every server's peers and firewall rules in four states with what they were before the table; no servers are needed. A change to what the table gives a running server also needs a proof on test servers: `wg show wg0 allowed-ips` and `ufw show added` on every server before and after the run, and the dryrun between them. |
| The phone-code lockout settings, the go-live switch for the public-address checks, or the setup protections' rendered files (automatic updates, needrestart, journald limits) | Run `python3 tests/phone_code_lockout_test.py` and `python3 tests/setup_protections_test.py` with MMX on PATH, or set `MMX_BINARY`. Render only; no servers are needed. |
| The triage agent's coding agent: `triage_agent_coding_agent`, the Codex tasks in `util_server`, or the `stack_software.codex` pin | Run `python3 tests/triage_agent_coding_agent_test.py` with MMX on PATH, or set `MMX_BINARY`. A new Codex pin also needs the real-system proof below: the pinned release installed through MMX on a disposable Debian 13 `util01`, MMHotline's setup test, and one test alert that Codex answers with a note. |
| The order of a role's node tasks, or a schedule, name or path that reads a node task's output | Run `python3 tests/task_outputs_after_a_secret_test.py` with MMX on PATH, or set `MMX_BINARY`. It fails when such a value reads the output of a node task that MMX hides: one that reads a secret or a value made from one, or that starts after a node task that used a secret on the server. |
| `staging01`'s fleet stages, its database role, or the template's inventory shape | Run `python3 tests/staging_server_test.py` with MMX on PATH, or set `MMX_BINARY`. It validates and explains the template as it ships, without `staging01`, and with the inventory edits of `operating_procedures/add_staging01.md`. A real `staging01` must still prove the procedure: the stages run, the seed fills the database, and no backup timer exists. |
| The AWS EC2 or Google Compute Engine guide's provider scripts or request function | Run `python3 tests/aws_ec2_provider_scripts_test.py` or `python3 tests/google_compute_engine_provider_scripts_test.py`: each builds the scripts from the guide's code blocks and runs them with every `bash` on the machine against a stand-in that checks the signature or the token's JWT. Then repeat the provider's real round below with a throwaway server. |
| One operating procedure | Run the changed operating procedure on the standing lab system. |

For app container shutdown, apply the AppArmor tasks from `every_server` and
the `app_server` role through MMX on a disposable Debian 13 server. Use the
rendered Quadlets with Debian's Podman and crun. Run a Node cluster master
with two workers. After `systemctl stop`, the service must report
`ExecMainStatus=0` and `Result=success`. During a deploy, the old web and job
containers must exit with code 0, and the new release must answer its health
check. Check the shared jobs Quadlet and the migration helper too.
Plain `process.kill(child.pid)` must succeed inside a container.
Record each process's `/proc/<pid>/attr/current` label and the kernel audit
log for each interval. The app profile must remain enforced, with no
AppArmor denial during shutdown. Check separately that the policy still
denies a signal to an unconfined host process.

For a managed-source move, use a Debian 13 relay with PGDG PgBouncer 1.26.1 or newer, session pooling, and `track_extra_parameters = lock_timeout`.
Use a TLS-only source with a private CA.
Verify `lock_timeout=5s` reaches the migration backend.
Verify a later client without options reads zero on the reused backend.
Before copying, warm the relay while the source is writable, then `DISABLE` and `KILL` the moving app entry.
Existing app clients must disconnect, and fresh app clients must be refused. The separate copy entry must remain reachable.
Set the database read-only and end app backends. A direct fresh source session must report read-only and refuse an insert.
The app entry must stay disabled despite PgBouncer's cached writable default.
Reset database defaults, then `ENABLE` the app entry and `RESUME` the app entry if paused. Verify app writes resume.
Force a switch failure after the relay fence and prove the helper restores source writes while retaining subscriptions and read-only Stack roles.
Prove the CA is required, replication and app connections use TLS, and the source administrator is not a superuser.
Keep HTTP writes running across the switch and powering off the relay and source.
Check each acknowledged write's row contents on both Stack database servers.
Record the old database's last write and the Stack's first write, and prove no old write follows the relay fence.
Detect reused IDs, because an ID alone can match a different write after a failed fence.
Also check rows and a sequence outside `public`, and large-object contents and permissions.
Repeat a self-hosted switch with the database-level fence.

A full initial setup run happens only before a release of the
Monkeymaxxing Stack is reviewed, not for each change. When the initial
setup is done, take server snapshots so the standing lab system can be
reset to that point without setting it up again. Test operating procedures
one at a time, forward and back: for example, add a server, then remove it.

Full initial setup runs use the newest Debian release the Stack supports.
A new Debian release joins the Stack only after two runs pass on it: a
full initial setup on the new release, and moving a lab system that holds
data from the currently supported release to the new release, database
servers included, with the existing data intact.
Reason: a new Debian release brings a new Postgres major version, and
[Replace a server](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/replace_a_server.md)
alone cannot move a database across Postgres major versions.

A database that starts new or is rewound to a snapshot writes the
database's backups to a fresh backup folder, because pgBackRest ties a
backup folder to one database system.

Set up the accounts at other companies, including keys, tokens, and
buckets, once. Reuse the accounts, keys, tokens, and buckets for every lab
run. A lab makes what it needs by script with its own keys. A lab never
repeats the website steps that a person does. Once a month, a computer-use
agent walks the websites that the
[initial setup](../skills/monkeymaxxing-stack/systems_repository_template/initial_setup/)
and the
[operating procedures](../skills/monkeymaxxing-stack/systems_repository_template/operating_procedures/)
send people to. The initial setup and the operating procedures are updated
where a page changed.

Every brief for a coding agent that runs a lab test states what changed,
the lab test's one check, and the lab test's time limit.
Delete lab servers and what a run made for them as soon as the test is done.

Bash changes also require `bash -n`, including Bash embedded in playbooks
and scheduled jobs. Repository tests use Python's standard library on the
contributor machine. A team's laptop needs no Python for Stack operations.
Fake-command tests prove refusals, arguments, and cleanup ownership; a real
provider drill must still prove creation, restoration, checks, and deletion.

Private-access proof on the standing lab system also needs a fresh
desk SSH connection over wg0 to every production and staging server, simultaneous
MMX and terminal connections, an unreachable Postgres and MMX HTTPS port
from a desk peer, and public TCP 22 closed on every public address before
and after a reboot. Stop WireGuard on a disposable server and verify a
root login through the provider console. Run the restore drill and verify
the runtime peer disappears on success and failure. A broken WireGuard
change must restore access within two minutes. Desk access also needs two proofs on a disposable desk: the phone-code lockout (wrong codes until the ban, then a fresh code logs in) and one alert for a burst of wrong phone codes.

### WireGuard answers within 30 seconds after a reload

Acceptance limit: after `systemctl reload wg-quick@wg0` on a machine, every WireGuard peer of that machine answers
a ping to its private address within **30 seconds**.
Reason for 30 seconds: WireGuard's own handshake retry is 5 seconds and a keepalive is 25 seconds, so a healthy pair
answers within one retry or one keepalive; 12+ minutes, which a test system showed when a NAT-rewritten source port
went stale, fails the limit by a wide margin. The limit is a setting of this check and a team may lengthen it.
`tests/wireguard_direct_port_test.py` proves the rendered files; only real servers prove this.

The check, on `util01` and then on each server (the person running the test runs it with `run-command`; a desk runs the
second part on itself):

```sh
# On the machine under test. Needs root. Prints one line a peer and exits 1 when any peer misses the limit.
limit_in_seconds=30
systemctl reload wg-quick@wg0
peers=$(wg show wg0 allowed-ips | awk '{ sub("/32", "", $2); print $2 }')
failed=0
for peer in $peers; do
  if ! ping -c 1 -W "$limit_in_seconds" "$peer" > /dev/null 2>&1; then
    echo "NOT OK $peer did not answer within ${limit_in_seconds} s of the wg0 reload"; failed=1
  else
    echo "OK $peer answered"
  fi
done
exit $failed
```

Also run it once after 150 seconds of silence between all peers, before the reload: a stale source port shows only after the firewall's connection-tracking entry has expired, which such a silence allows.
