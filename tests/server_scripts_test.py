#!/usr/bin/env python3
"""Check the server scripts' caller contracts.

Run: python3 tests/server_scripts_test.py

Only temporary copies have their fixed server paths redirected. No production
path overrides are needed. Date and stat stand-ins give bash a fixed clock
and marker age. Real jq handles JSON. JSON output is compared as parsed
values. Messages, exit codes, server commands and saved files are checked
exactly. Local JSON, clock and temporary-file helpers are logged separately.
"""

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "skills/monkeymaxxing-stack/systems_repository_template"
SCRIPTS = {
    "memory": "roles/app_server/files/check_memory_for_the_new_release",
    "ports": "roles/app_server/files/find_live_web_ports",
    "database": "roles/database_server/files/show_the_database_servers_and_their_health",
    "uploads": "roles/uploads_backup/files/copy_uploads_to_the_backup_bucket",
    "fleet": "roles/util_server/files/stop_fleet_hub_expecting_reports_from_removed_servers",
}
NOW = 1793577600.25
STAMP = datetime.datetime.fromtimestamp(NOW, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
DAY = 86400
MIB = 1024 * 1024

FAKE_COMMAND = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
arguments = sys.argv[1:]
helpers = name in ("jq", "date", "stat", "mv", "mktemp", "rm")
with open(os.environ["HELPER_LOG" if helpers else "COMMAND_LOG"], "a") as file:
    file.write(json.dumps([name, *arguments]) + "\n")
if name == "jq":
    os.execv(os.environ["REAL_JQ"], ["jq", *arguments])
if name == "date":
    if arguments == ["-u", "+%Y-%m-%dT%H:%M:%SZ"]:
        print(os.environ["CLOCK_STAMP"])
    elif arguments == ["+%s"]:
        print(os.environ["CLOCK_SECONDS"])
    else:
        sys.exit(f"unexpected date arguments: {arguments}")
    sys.exit(0)
if name == "stat":
    assert arguments[:2] == ["-c", "%Y"], arguments
    print(os.environ["MARKER_MTIME"])
    sys.exit(0)
if name == "mktemp":
    import tempfile
    descriptor, path = tempfile.mkstemp(dir=os.environ.get("TMPDIR"))
    os.close(descriptor)
    print(path)
    sys.exit(0)
if name == "rm":
    assert arguments[0] == "-f", arguments
    os.unlink(arguments[1])
    sys.exit(0)
if name == "mv":
    os.replace(arguments[-2], arguments[-1])
    sys.exit(0)
responses = json.loads(os.environ["RESPONSES"])
response = responses.get(" ".join([name, *arguments]), responses.get(name, {}))
sys.stdout.write(response.get("stdout", ""))
sys.stderr.write(response.get("stderr", ""))
if response.get("signal"):
    os.kill(os.getpid(), response["signal"])
sys.exit(response.get("exit", 0))
'''

# Reuse executable paths across cases. This also avoids repeated executable
# checks by the operating system for each otherwise identical stand-in.
TOOLS_DIRECTORY = tempfile.TemporaryDirectory()
TOOLS_BIN = Path(TOOLS_DIRECTORY.name)
for _command in ("systemctl", "pg_autoctl", "rclone", "mmwatchdog", "jq", "date", "stat", "mv", "mktemp", "rm"):
    _path = TOOLS_BIN / _command
    _path.write_text(FAKE_COMMAND.replace("#!/usr/bin/env python3", "#!" + sys.executable))
    _path.chmod(0o755)


def node(name, current="secondary", assigned=None, health=1):
    return {"nodename": name, "current_group_state": current,
            "assigned_group_state": current if assigned is None else assigned, "health": health}


# A deployed image tag is a full Git commit: 40 lowercase hexadecimal characters.
NEW_TAG = "a" * 40
OTHER_TAG = "b" * 40


def cases():
    apps = {"zoo": {"web_ports": [8101, 8102], "image": "ghcr.io/example/zoo"},
            "shop": {"web_ports": [8001, 8002], "image": "ghcr.io/example/shop"}}
    ports_env = {"APPS": json.dumps(apps), "DEPLOYED_IMAGE_TAGS": json.dumps({"shop": NEW_TAG, "zoo": OTHER_TAG})}
    yield "ports_new_server", "ports", {"env": ports_env}
    # A new app server runs the pool's live release, not deployed_image_tags.
    pool_env = {**ports_env, "APP_SERVERS": json.dumps(["app001", "app002", "app003"]),
                "LIVE_IMAGES_BY_APP_SERVER": json.dumps({
                    # The shape of MMX's .outputs.find_the_releases_the_app_servers_run.
                    "app001": {"recorded_live_images": {}},
                    "app002": {"recorded_live_images": {"shop": "ghcr.io/example/shop:live2"}},
                    "app003": {"recorded_live_images": {"shop": "ghcr.io/example/shop:live3"}}})}
    yield "ports_new_server_takes_the_pool_release", "ports", {"env": pool_env}
    yield "ports_running_server_keeps_its_own_release", "ports", {"env": pool_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "8002\n",
        "/etc/containers/systemd/shop-web-8002.container": "[Container]\nImage=own:release\n"}}
    yield "ports_pool_without_release_takes_deployed_tag", "ports", {"env": {
        **pool_env, "LIVE_IMAGES_BY_APP_SERVER": json.dumps({"app001": {"recorded_live_images": {}}, "app002": {"recorded_live_images": {}}})}}
    yield "ports_empty", "ports", {"env": {"APPS": "{}", "DEPLOYED_IMAGE_TAGS": "{}"}}
    yield "ports_live_second", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "8002\n",
        "/etc/containers/systemd/shop-web-8002.container": "[Container]\nImage=old:first\nImage= old:last \n"}}
    yield "ports_live_first_missing_quadlet", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "8001\n"}}
    yield "ports_quadlet_without_image", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "8001\n",
        "/etc/containers/systemd/shop-web-8001.container": "[Container]\nNotImage=ignored\n"}}
    yield "ports_invalid_live_port", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "9000\n"}}
    yield "ports_negative_live_port", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "-1\n"}}
    yield "ports_signed_live_port", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": " +008001 \n"}}
    for name, port in (("underscores", "8_001"), ("spaces", " 8001 "),
                       ("extra_newline", "8001\n\n"), ("empty_file", ""),
                       ("no_newline", "8001")):
        yield "ports_" + name, "ports", {"env": ports_env, "files": {
            "/var/lib/monkeymaxxing-stack/live_web_ports/shop": port}}
    yield "ports_escaped_image", "ports", {"env": {
        "APPS": json.dumps({"shop": {"web_ports": [8001, 8002], "image": 'é:a,b"\\'}}),
        "DEPLOYED_IMAGE_TAGS": json.dumps({"shop": NEW_TAG})}}
    # A short or movable tag is refused (one tag must always name one image).
    yield "ports_short_tag_is_refused", "ports", {"env": {**ports_env, "DEPLOYED_IMAGE_TAGS": json.dumps({"shop": "3f2a1c9", "zoo": OTHER_TAG})}}
    # A server that runs another release than deployed_image_tags is counted.
    yield "ports_running_another_release_is_reported", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "8001\n",
        "/etc/containers/systemd/shop-web-8001.container": "[Container]\nImage=ghcr.io/example/shop:" + "c" * 40 + "\n"}}
    yield "ports_running_the_deployed_release_is_not_reported", "ports", {"env": ports_env, "files": {
        "/var/lib/monkeymaxxing-stack/live_web_ports/shop": "8001\n",
        "/etc/containers/systemd/shop-web-8001.container": "[Container]\nImage=ghcr.io/example/shop:" + NEW_TAG + "\n"}}

    live = {"zoo": {"web_port": 8101}, "shop": {"web_port": 8002}}
    for name, available in (("enough", 800), ("equal", 350), ("insufficient", 349)):
        yield "memory_" + name, "memory", {"env": {"LIVE_WEB_CONTAINERS": json.dumps(live)}, "files": {
            "/proc/meminfo": f"MemTotal: 1024000 kB\nMemAvailable: {available * 1024} kB\n",
            "/sys/fs/cgroup/shop/memory.current": str(300 * MIB),
            "/sys/fs/cgroup/shop/memory.stat": f"anon 1\ninactive_file {50 * MIB}\n",
        }, "responses": {"systemctl show --property=ControlGroup --value shop-web-8002.service": {"stdout": "/shop\n"}}}
    yield "memory_empty", "memory", {"env": {"LIVE_WEB_CONTAINERS": "{}"}, "files": {
        "/proc/meminfo": "MemTotal: 1024001 kB\nMemAvailable: 819200 kB\n"}}
    yield "memory_cache_exceeds_current", "memory", {"env": {"LIVE_WEB_CONTAINERS": '{"shop":{"web_port":8001}}'}, "files": {
        "/proc/meminfo": "MemTotal: 1024000 kB\nMemAvailable: 819200 kB\n",
        "/sys/fs/cgroup/shop/memory.current": "100",
        "/sys/fs/cgroup/shop/memory.stat": "inactive_file 101\n",
    }, "responses": {"systemctl": {"stdout": "/shop\n"}}}
    yield "memory_no_inactive_file", "memory", {"env": {"LIVE_WEB_CONTAINERS": '{"shop":{"web_port":8001}}'}, "files": {
        "/proc/meminfo": "MemTotal: 1024000 kB\nMemAvailable: 819200 kB\n",
        "/sys/fs/cgroup/shop/memory.current": str(123 * MIB + 456),
        "/sys/fs/cgroup/shop/memory.stat": "anon 100\n",
    }, "responses": {"systemctl": {"stdout": "/shop\n"}}}

    formations = {
        "single": [node("db01", "single")],
        "replicas_sorted": [node("db03"), node("db01", "primary"), node("db02")],
        "no_primary": [node("db02")],
        "two_primaries": [node("db02", "primary"), node("db01", "primary")],
        "unhealthy": [node("db02", health=0), node("db01", "primary")],
        "catching_up": [node("db01", "wait_primary", "primary"), node("db02", "catchingup", "secondary")],
        "maintenance": [node("db01", "primary"), node("db02", "maintenance")],
        "missing_state_fields": [{"nodename": "db01"}],
        "empty": [], "not_a_list": {},
    }
    arguments = ["--monitor-data-directory", "/monitor data", "--formation", "production"]
    for name, formation in formations.items():
        yield "database_" + name, "database", {"args": arguments, "responses": {"pg_autoctl": {"stdout": json.dumps(formation)}}}
    yield "database_command_failed", "database", {"args": arguments, "responses": {"pg_autoctl": {"exit": 3, "stderr": "  cannot reach monitor\n"}}}
    yield "database_invalid_json", "database", {"args": arguments, "responses": {"pg_autoctl": {"stdout": "not JSON\n"}}}
    yield "database_long_invalid_json", "database", {"args": arguments, "responses": {"pg_autoctl": {"stdout": "x" * 310 + "\n"}}}
    yield "database_missing_arguments", "database", {}
    yield "database_missing_formation", "database", {"args": arguments[:2]}
    yield "database_missing_value", "database", {"args": ["--formation"]}
    yield "database_unknown_argument", "database", {"args": arguments + ["--unknown"]}
    yield "database_help", "database", {"args": ["--help"]}
    yield "database_short_help", "database", {"args": ["-h"]}
    yield "database_equals_arguments", "database", {"args": ["--monitor-data-directory=/monitor data", "--formation=production"], "responses": {"pg_autoctl": {"stdout": json.dumps([node("db01", "single")])}}}
    yield "database_abbreviated_arguments", "database", {"args": ["--mon", "/monitor data", "--form", "production"], "responses": {"pg_autoctl": {"stdout": json.dumps([node("db01", "single")])}}}
    yield "database_help_as_value", "database", {"args": ["--formation", "-h"]}
    yield "database_help_with_value", "database", {"args": ["--help=wrong"]}

    uploads = {"zoo": {"production_uploads_r2_bucket": "zoo-uploads"},
               "none": {"production_uploads_r2_bucket": ""},
               "shop": {"production_uploads_r2_bucket": "shop-uploads"}}
    warn = {"WARN_WHEN_ONE_COPY_HIDES_MORE_THAN_PERCENT": "10", "WARN_ONLY_WHEN_AN_APP_HAS_AT_LEAST_FILES": "10"}
    uploads_env = {"APPS": json.dumps(uploads), "UPLOADS_BACKUP_BUCKET": "backup-bucket", **warn}
    for name, age in (("first_full", None), ("recent", DAY), ("exactly_six_days", 6 * DAY),
                      ("over_six_days", 6 * DAY + .125), ("one_second_over_six_days", 6 * DAY + 1), ("old", 7 * DAY)):
        yield "uploads_" + name, "uploads", {"env": uploads_env, "marker_age": age}
    yield "uploads_no_apps", "uploads", {"env": {"APPS": "{}", "UPLOADS_BACKUP_BUCKET": "backup-bucket", **warn}}
    yield "uploads_no_buckets", "uploads", {"env": {"APPS": '{"none":{"production_uploads_r2_bucket":""}}', "UPLOADS_BACKUP_BUCKET": "backup-bucket", **warn}}
    for name, app in (("null", {"production_uploads_r2_bucket": None}), ("missing", {})):
        yield "uploads_empty_bucket_" + name, "uploads", {"env": {
            "APPS": json.dumps({"none": app}),
            "UPLOADS_BACKUP_BUCKET": "backup-bucket", **warn}}
    for name, failed in (("one_failure", {"shop": 7}), ("all_failures", {"shop": 7, "zoo": 9})):
        responses = {}
        for app, status in failed.items():
            command = ["rclone", "--config", "/var/lib/mmhotline/uploads_backup_rclone.conf", "sync",
                       f"uploads_r2:{app}-uploads", f"uploads_backup:backup-bucket/{app}", "--use-server-modtime",
                       "--stats", "10m", "--stats-one-line", "--stats-log-level", "NOTICE"]
            responses[" ".join(command)] = {"exit": status, "stdout": f"{app}: progress\n", "stderr": f"{app}: failed\n"}
        yield "uploads_" + name, "uploads", {"env": uploads_env, "marker_age": DAY, "responses": responses,
            "files": {"/var/lib/uploads_backup/latest_passed_copy": "previous copy\n"}}
    yield "uploads_failed_full", "uploads", {"env": uploads_env, "marker_age": 7 * DAY,
        "responses": {"rclone": {"exit": 5, "stderr": "copy failed\n"}},
        "files": {"/var/lib/uploads_backup/latest_passed_copy": "previous copy\n"}}
    yield "uploads_signal_terminated", "uploads", {"env": {
        "APPS": '{"shop":{"production_uploads_r2_bucket":"shop-uploads"}}',
        "UPLOADS_BACKUP_BUCKET": "backup-bucket", **warn},
        "responses": {"rclone": {"signal": 15}}}

    # The dry run before each copy lists what the copy hides: - gone from R2, * changed in R2.
    def dry_run(app):
        return " ".join(["rclone", "--config", "/var/lib/mmhotline/uploads_backup_rclone.conf", "sync", "--dry-run",
                         "--combined", "-", "--log-level", "ERROR", f"uploads_r2:{app}-uploads",
                         f"uploads_backup:backup-bucket/{app}", "--use-server-modtime"])

    def report(same=0, gone=0, changed=0, new=0):
        return "".join([f"= customers/kept{n}\n" for n in range(same)] + [f"- customers/gone{n}\n" for n in range(gone)]
                       + [f"* customers/changed{n}\n" for n in range(changed)] + [f"+ customers/new{n}\n" for n in range(new)])
    # shop: 2 of 10 hidden, 20% > 10%: warns. zoo: 1 of 11 hidden, 9%: quiet. New files never count.
    yield "uploads_hides_an_unusual_share", "uploads", {"env": uploads_env, "marker_age": DAY, "responses": {
        dry_run("shop"): {"stdout": report(same=8, gone=1, changed=1, new=5)},
        dry_run("zoo"): {"stdout": report(same=10, gone=1)}},
        "files": {"/var/lib/uploads_backup/apps_whose_latest_copy_hid_an_unusual_share": "an earlier warning\n"}}
    # Exactly 10%: not more than the setting, so quiet; the earlier warning's file is emptied.
    yield "uploads_hides_exactly_the_share", "uploads", {"env": uploads_env, "marker_age": DAY, "responses": {
        dry_run("shop"): {"stdout": report(same=9, changed=1)}},
        "files": {"/var/lib/uploads_backup/apps_whose_latest_copy_hid_an_unusual_share": "an earlier warning\n"}}
    # 9 files is below the smallest number, 10: every file hidden stays quiet.
    yield "uploads_hides_everything_below_the_smallest_number", "uploads", {"env": uploads_env, "marker_age": DAY,
        "responses": {dry_run("shop"): {"stdout": report(gone=9)}}}
    yield "uploads_dry_run_fails", "uploads", {"env": uploads_env, "marker_age": DAY, "responses": {
        dry_run("shop"): {"exit": 4, "stderr": "shop: listing failed\n"}},
        "files": {"/var/lib/uploads_backup/latest_passed_copy": "previous copy\n"}}

    fleet_env = {"INVENTORY_NODES": '{"util01":{},"app001":{}}'}
    for status in (0, 1, 3):
        yield f"fleet_list_status_{status}", "fleet", {"env": fleet_env, "responses": {"mmwatchdog": {
            "exit": status, "stdout": '{"nodes":[{"name":"app001"},{"name":"util01"}]}'}}}
    fleet = {"nodes": [{"name": "z-old"}, {"name": "util01"}, {"name": "a-old"}, {"name": "z-old"}]}
    for name, args in (("forget_sorted_unique", []), ("dryrun", ["--dryrun"]), ("other_args", ["ignored"]), ("extra_dryrun_args", ["--dryrun", "ignored"])):
        yield "fleet_" + name, "fleet", {"env": fleet_env, "args": args, "responses": {
            "mmwatchdog fleet --json": {"exit": 3, "stdout": json.dumps(fleet)},
            "mmwatchdog": {"stdout": "removed\n", "stderr": "forget diagnostic\n"}}}
    yield "fleet_empty", "fleet", {"env": fleet_env, "responses": {"mmwatchdog": {"stdout": '{"nodes":[]}'}}}
    yield "fleet_list_failed", "fleet", {"env": fleet_env, "responses": {"mmwatchdog": {"exit": 2, "stderr": "  hub unavailable\n"}}}


def run_case(kind, case):
    import shutil
    real_jq = shutil.which("jq")
    if not real_jq:
        raise RuntimeError("jq must be on PATH")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bin_dir = TOOLS_BIN
        temporary_files = root / "temporary"
        temporary_files.mkdir()
        # No production path or clock changes: only the copy being tested.
        paths = ["/proc/meminfo", "/sys/fs/cgroup", "/var/lib/monkeymaxxing-stack/live_web_ports",
                 "/etc/containers/systemd", "/var/lib/mmhotline/uploads_backup_rclone.conf", "/var/lib/uploads_backup"]
        for path in paths:
            (root / path.lstrip("/")).parent.mkdir(parents=True, exist_ok=True)
        (root / "var/lib/uploads_backup").mkdir(exist_ok=True)
        source = (TEMPLATE / SCRIPTS[kind]).read_text()
        for path in paths:
            source = source.replace(path, str(root / path.lstrip("/")))
        source = source.replace("/usr/local/bin/mmwatchdog", str(bin_dir / "mmwatchdog"))
        script = root / Path(SCRIPTS[kind]).name
        script.write_text(source)
        script.chmod(0o755)
        for path, content in case.get("files", {}).items():
            fixture = root / path.lstrip("/")
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text(content)
        age = case.get("marker_age")
        if age is not None:
            marker = root / "var/lib/uploads_backup/latest_passed_full_copy"
            marker.write_text("previous full copy\n")
            os.utime(marker, (NOW - age, NOW - age))
        responses = json.dumps(case.get("responses", {})).replace("/var/lib/mmhotline/uploads_backup_rclone.conf", str(root / "var/lib/mmhotline/uploads_backup_rclone.conf"))
        env = {**os.environ, **case.get("env", {}), "PATH": str(bin_dir) + ":" + os.environ["PATH"],
               "COMMAND_LOG": str(root / "commands"), "HELPER_LOG": str(root / "helpers"),
               "REAL_JQ": real_jq, "RESPONSES": responses, "CLOCK_STAMP": STAMP,
               "CLOCK_SECONDS": str(int(NOW)), "MARKER_MTIME": str(int(NOW - (age or 0))),
               "TMPDIR": str(temporary_files),
               "LC_ALL": "C", "COLUMNS": "80"}
        result = subprocess.run(["bash", str(script), *case.get("args", [])], env=env, capture_output=True, text=True)
        commands = [json.loads(line.replace(str(root), "<temporary>")) for line in (root / "commands").read_text().splitlines()] if (root / "commands").exists() else []
        markers = {path.name: path.read_text() for path in (root / "var/lib/uploads_backup").iterdir()}
        input_files = {path: (root / path.lstrip("/")).read_text()
                       for path in case.get("files", {}) if not path.startswith("/var/lib/uploads_backup/")}
        assert not list(temporary_files.iterdir()), "temporary files were not cleaned up"
        stdout = result.stdout
        if kind in ("memory", "ports", "database") and stdout:
            stdout = json.loads(stdout)
        return {"stdout": stdout, "stderr": result.stderr.replace(str(root), "<temporary>"),
                "exit": result.returncode, "commands": commands, "markers": markers, "input_files": input_files}


# Caller contracts: JSON values, messages, exit codes, commands and files.
EXPECTED = {'ports_new_server': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                 'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                         'shop': {'web_port': 8001,
                                                                  'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                 'new_web_containers': {'zoo': {'web_port': 8102,
                                                                'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                        'shop': {'web_port': 8002,
                                                                 'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                 'recorded_live_images': {},
                                 'apps_not_on_the_deployed_image_tags': [],
                                 'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'ports_empty': {'stdout': {'live_web_containers': {},
                            'new_web_containers': {},
                            'recorded_live_images': {},
                            'apps_not_on_the_deployed_image_tags': [],
                            'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'ports_live_second': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                  'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                          'shop': {'web_port': 8002, 'image': 'old:last'}},
                                  'new_web_containers': {'zoo': {'web_port': 8102,
                                                                 'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                         'shop': {'web_port': 8001,
                                                                  'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                  'recorded_live_images': {'shop': 'old:last'},
                                  'apps_not_on_the_deployed_image_tags': ['shop'],
                                  'number_of_apps_not_on_the_deployed_image_tags': 1}},
 'ports_live_first_missing_quadlet': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                                 'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                         'shop': {'web_port': 8001,
                                                                                  'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                 'new_web_containers': {'zoo': {'web_port': 8102,
                                                                                'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                        'shop': {'web_port': 8002,
                                                                                 'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                 'recorded_live_images': {'shop': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'},
                                                 'apps_not_on_the_deployed_image_tags': [],
                                                 'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'ports_quadlet_without_image': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                            'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                    'shop': {'web_port': 8001,
                                                                             'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                            'new_web_containers': {'zoo': {'web_port': 8102,
                                                                           'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                   'shop': {'web_port': 8002,
                                                                            'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                            'recorded_live_images': {'shop': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'},
                                            'apps_not_on_the_deployed_image_tags': [],
                                            'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'ports_invalid_live_port': {'stderr': "shop's live web container on this server listens on port 9000, which is not "
                                       'one of its web_ports [8001, 8002]: keep the live port in web_ports when '
                                       'changing them\n',
                             'exit': 1},
 'ports_negative_live_port': {'stderr': 'the live port file '
                                        '<temporary>/var/lib/monkeymaxxing-stack/live_web_ports/shop must contain one '
                                        'port number written with digits\n',
                              'exit': 1},
 'ports_signed_live_port': {'stderr': 'the live port file <temporary>/var/lib/monkeymaxxing-stack/live_web_ports/shop '
                                      'must contain one port number written with digits\n',
                            'exit': 1},
 'ports_escaped_image': {'stdout': {'live_web_containers': {'shop': {'web_port': 8001,
                                                                     'image': 'é:a,b"\\:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                    'new_web_containers': {'shop': {'web_port': 8002,
                                                                    'image': 'é:a,b"\\:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                    'recorded_live_images': {},
                                    'apps_not_on_the_deployed_image_tags': [],
                                    'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'memory_enough': {'stdout': {'memory_available_mib': 800,
                              'live_web_containers_mib': 250,
                              'margin_mib': 100,
                              'memory_needed_mib': 350},
                   'commands': [['systemctl', 'show', '--property=ControlGroup', '--value', 'shop-web-8002.service'],
                                ['systemctl', 'show', '--property=ControlGroup', '--value', 'zoo-web-8101.service']]},
 'memory_equal': {'stdout': {'memory_available_mib': 350,
                             'live_web_containers_mib': 250,
                             'margin_mib': 100,
                             'memory_needed_mib': 350},
                  'commands': [['systemctl', 'show', '--property=ControlGroup', '--value', 'shop-web-8002.service'],
                               ['systemctl', 'show', '--property=ControlGroup', '--value', 'zoo-web-8101.service']]},
 'memory_insufficient': {'stdout': {'memory_available_mib': 349,
                                    'live_web_containers_mib': 250,
                                    'margin_mib': 100,
                                    'memory_needed_mib': 350},
                         'stderr': 'this server has 349 MiB of memory available (MemAvailable), but the new release '
                                   'needs 350 MiB: 250 MiB for a second copy of its live web containers as they use '
                                   'memory now (shop 250 MiB, zoo 0 MiB), and 100 MiB, a tenth of its memory, for '
                                   'everything else while both releases run. The deploy changed nothing. The operating '
                                   'procedure: a bigger server, or a smaller WEB_CONCURRENCY for the app; on staging01, a bigger staging01 '
                                   '(operating_procedures/deploy_and_roll_back_an_app_release.md, "Memory for both '
                                   'releases"). When the live release uses more memory than it should, as one that '
                                   'leaks memory does, its rollback may run without this check: --var '
                                   'skip_the_memory_check=true.\n',
                         'exit': 1,
                         'commands': [['systemctl',
                                       'show',
                                       '--property=ControlGroup',
                                       '--value',
                                       'shop-web-8002.service'],
                                      ['systemctl',
                                       'show',
                                       '--property=ControlGroup',
                                       '--value',
                                       'zoo-web-8101.service']]},
 'memory_empty': {'stdout': {'memory_available_mib': 800,
                             'live_web_containers_mib': 0,
                             'margin_mib': 100,
                             'memory_needed_mib': 100}},
 'memory_cache_exceeds_current': {'stdout': {'memory_available_mib': 800,
                                             'live_web_containers_mib': 0,
                                             'margin_mib': 100,
                                             'memory_needed_mib': 100},
                                  'commands': [['systemctl',
                                                'show',
                                                '--property=ControlGroup',
                                                '--value',
                                                'shop-web-8001.service']]},
 'memory_no_inactive_file': {'stdout': {'memory_available_mib': 800,
                                        'live_web_containers_mib': 123,
                                        'margin_mib': 100,
                                        'memory_needed_mib': 223},
                             'commands': [['systemctl',
                                           'show',
                                           '--property=ControlGroup',
                                           '--value',
                                           'shop-web-8001.service']]},
 'database_single': {'stdout': {'switch_to_node_name': ''},
                     'commands': [['pg_autoctl',
                                   'show',
                                   'state',
                                   '--pgdata',
                                   '/monitor data',
                                   '--formation',
                                   'production',
                                   '--json']]},
 'database_replicas_sorted': {'stdout': {'switch_to_node_name': 'db02'},
                              'commands': [['pg_autoctl',
                                            'show',
                                            'state',
                                            '--pgdata',
                                            '/monitor data',
                                            '--formation',
                                            'production',
                                            '--json']]},
 'database_no_primary': {'stdout': {'switch_to_node_name': 'db02'},
                         'stderr': 'the formation production is not settled: db02 is secondary (assigned secondary, '
                                   'healthy)\n',
                         'exit': 1,
                         'commands': [['pg_autoctl',
                                       'show',
                                       'state',
                                       '--pgdata',
                                       '/monitor data',
                                       '--formation',
                                       'production',
                                       '--json']]},
 'database_two_primaries': {'stdout': {'switch_to_node_name': ''},
                            'stderr': 'the formation production is not settled: db01 is primary (assigned primary, '
                                      'healthy), db02 is primary (assigned primary, healthy)\n',
                            'exit': 1,
                            'commands': [['pg_autoctl',
                                          'show',
                                          'state',
                                          '--pgdata',
                                          '/monitor data',
                                          '--formation',
                                          'production',
                                          '--json']]},
 'database_unhealthy': {'stdout': {'switch_to_node_name': ''},
                        'stderr': 'the formation production is not settled: db01 is primary (assigned primary, '
                                  'healthy), db02 is secondary (assigned secondary, not healthy)\n',
                        'exit': 1,
                        'commands': [['pg_autoctl',
                                      'show',
                                      'state',
                                      '--pgdata',
                                      '/monitor data',
                                      '--formation',
                                      'production',
                                      '--json']]},
 'database_catching_up': {'stdout': {'switch_to_node_name': ''},
                          'stderr': 'the formation production is not settled: db01 is wait_primary (assigned primary, '
                                    'healthy), db02 is catchingup (assigned secondary, healthy)\n',
                          'exit': 1,
                          'commands': [['pg_autoctl',
                                        'show',
                                        'state',
                                        '--pgdata',
                                        '/monitor data',
                                        '--formation',
                                        'production',
                                        '--json']]},
 'database_maintenance': {'stdout': {'switch_to_node_name': ''},
                          'stderr': 'the formation production is not settled: db01 is primary (assigned primary, '
                                    'healthy), db02 is maintenance (assigned maintenance, healthy)\n',
                          'exit': 1,
                          'commands': [['pg_autoctl',
                                        'show',
                                        'state',
                                        '--pgdata',
                                        '/monitor data',
                                        '--formation',
                                        'production',
                                        '--json']]},
 'database_missing_state_fields': {'stdout': {'switch_to_node_name': ''},
                                   'stderr': 'the formation production is not settled: db01 is None (assigned None, '
                                             'not healthy)\n',
                                   'exit': 1,
                                   'commands': [['pg_autoctl',
                                                 'show',
                                                 'state',
                                                 '--pgdata',
                                                 '/monitor data',
                                                 '--formation',
                                                 'production',
                                                 '--json']]},
 'database_empty': {'stderr': 'the formation production has no node\n',
                    'exit': 1,
                    'commands': [['pg_autoctl',
                                  'show',
                                  'state',
                                  '--pgdata',
                                  '/monitor data',
                                  '--formation',
                                  'production',
                                  '--json']]},
 'database_not_a_list': {'stderr': 'the formation production has no node\n',
                         'exit': 1,
                         'commands': [['pg_autoctl',
                                       'show',
                                       'state',
                                       '--pgdata',
                                       '/monitor data',
                                       '--formation',
                                       'production',
                                       '--json']]},
 'database_command_failed': {'stderr': 'pg_autoctl show state failed: cannot reach monitor\n',
                             'exit': 2,
                             'commands': [['pg_autoctl',
                                           'show',
                                           'state',
                                           '--pgdata',
                                           '/monitor data',
                                           '--formation',
                                           'production',
                                           '--json']]},
 'database_invalid_json': {'stderr': 'pg_autoctl show state printed no JSON: not JSON\n',
                           'exit': 2,
                           'commands': [['pg_autoctl',
                                         'show',
                                         'state',
                                         '--pgdata',
                                         '/monitor data',
                                         '--formation',
                                         'production',
                                         '--json']]},
 'database_long_invalid_json': {'stderr': 'pg_autoctl show state printed no JSON: '
                                          'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n',
                                'exit': 2,
                                'commands': [['pg_autoctl',
                                              'show',
                                              'state',
                                              '--pgdata',
                                              '/monitor data',
                                              '--formation',
                                              'production',
                                              '--json']]},
 'database_missing_arguments': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory '
                                          'DIR --formation NAME\n',
                                'exit': 2},
 'database_missing_formation': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory '
                                          'DIR --formation NAME\n',
                                'exit': 2},
 'database_missing_value': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory DIR '
                                      '--formation NAME\n',
                            'exit': 2},
 'database_unknown_argument': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory '
                                         'DIR --formation NAME\n',
                               'exit': 2},
 'database_help': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory DIR '
                             '--formation NAME\n',
                   'exit': 2},
 'database_equals_arguments': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory '
                                         'DIR --formation NAME\n',
                               'exit': 2},
 'database_abbreviated_arguments': {'stderr': 'usage: show_the_database_servers_and_their_health '
                                              '--monitor-data-directory DIR --formation NAME\n',
                                    'exit': 2},
 'database_help_as_value': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory DIR '
                                      '--formation NAME\n',
                            'exit': 2},
 'database_help_with_value': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory '
                                        'DIR --formation NAME\n',
                              'exit': 2},
 'uploads_first_full': {'stdout': 'none keeps no uploads\n'
                                  'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop, every '
                                  'file again: no full copy passed in the last 6 days\n'
                                  'shop: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/shop\n'
                                  'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo, every file '
                                  'again: no full copy passed in the last 6 days\n'
                                  'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n'
                                  "every app's uploads were copied, every file again; the copy started at "
                                  '2026-11-02T00:00:00Z\n',
                        'commands': [['rclone',
                                      '--config',
                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                      'sync',
                                      '--dry-run',
                                      '--combined',
                                      '-',
                                      '--log-level',
                                      'ERROR',
                                      'uploads_r2:shop-uploads',
                                      'uploads_backup:backup-bucket/shop',
                                      '--use-server-modtime'],
                                     ['rclone',
                                      '--config',
                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                      'sync',
                                      'uploads_r2:shop-uploads',
                                      'uploads_backup:backup-bucket/shop',
                                      '--use-server-modtime',
                                      '--ignore-times',
                                      '--stats',
                                      '10m',
                                      '--stats-one-line',
                                      '--stats-log-level',
                                      'NOTICE'],
                                     ['rclone',
                                      '--config',
                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                      'sync',
                                      '--dry-run',
                                      '--combined',
                                      '-',
                                      '--log-level',
                                      'ERROR',
                                      'uploads_r2:zoo-uploads',
                                      'uploads_backup:backup-bucket/zoo',
                                      '--use-server-modtime'],
                                     ['rclone',
                                      '--config',
                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                      'sync',
                                      'uploads_r2:zoo-uploads',
                                      'uploads_backup:backup-bucket/zoo',
                                      '--use-server-modtime',
                                      '--ignore-times',
                                      '--stats',
                                      '10m',
                                      '--stats-one-line',
                                      '--stats-log-level',
                                      'NOTICE']],
                        'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                    'latest_passed_full_copy': '2026-11-02T00:00:00Z\n',
                                    'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_recent': {'stdout': 'none keeps no uploads\n'
                              'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop\n'
                              'shop: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/shop\n'
                              'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo\n'
                              'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n'
                              "every app's uploads were copied; the copy started at 2026-11-02T00:00:00Z\n",
                    'commands': [['rclone',
                                  '--config',
                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                  'sync',
                                  '--dry-run',
                                  '--combined',
                                  '-',
                                  '--log-level',
                                  'ERROR',
                                  'uploads_r2:shop-uploads',
                                  'uploads_backup:backup-bucket/shop',
                                  '--use-server-modtime'],
                                 ['rclone',
                                  '--config',
                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                  'sync',
                                  'uploads_r2:shop-uploads',
                                  'uploads_backup:backup-bucket/shop',
                                  '--use-server-modtime',
                                  '--stats',
                                  '10m',
                                  '--stats-one-line',
                                  '--stats-log-level',
                                  'NOTICE'],
                                 ['rclone',
                                  '--config',
                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                  'sync',
                                  '--dry-run',
                                  '--combined',
                                  '-',
                                  '--log-level',
                                  'ERROR',
                                  'uploads_r2:zoo-uploads',
                                  'uploads_backup:backup-bucket/zoo',
                                  '--use-server-modtime'],
                                 ['rclone',
                                  '--config',
                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                  'sync',
                                  'uploads_r2:zoo-uploads',
                                  'uploads_backup:backup-bucket/zoo',
                                  '--use-server-modtime',
                                  '--stats',
                                  '10m',
                                  '--stats-one-line',
                                  '--stats-log-level',
                                  'NOTICE']],
                    'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                'latest_passed_full_copy': 'previous full copy\n',
                                'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_exactly_six_days': {'stdout': 'none keeps no uploads\n'
                                        'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop\n'
                                        'shop: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/shop\n'
                                        'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo\n'
                                        'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n'
                                        "every app's uploads were copied; the copy started at 2026-11-02T00:00:00Z\n",
                              'commands': [['rclone',
                                            '--config',
                                            '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                            'sync',
                                            '--dry-run',
                                            '--combined',
                                            '-',
                                            '--log-level',
                                            'ERROR',
                                            'uploads_r2:shop-uploads',
                                            'uploads_backup:backup-bucket/shop',
                                            '--use-server-modtime'],
                                           ['rclone',
                                            '--config',
                                            '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                            'sync',
                                            'uploads_r2:shop-uploads',
                                            'uploads_backup:backup-bucket/shop',
                                            '--use-server-modtime',
                                            '--stats',
                                            '10m',
                                            '--stats-one-line',
                                            '--stats-log-level',
                                            'NOTICE'],
                                           ['rclone',
                                            '--config',
                                            '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                            'sync',
                                            '--dry-run',
                                            '--combined',
                                            '-',
                                            '--log-level',
                                            'ERROR',
                                            'uploads_r2:zoo-uploads',
                                            'uploads_backup:backup-bucket/zoo',
                                            '--use-server-modtime'],
                                           ['rclone',
                                            '--config',
                                            '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                            'sync',
                                            'uploads_r2:zoo-uploads',
                                            'uploads_backup:backup-bucket/zoo',
                                            '--use-server-modtime',
                                            '--stats',
                                            '10m',
                                            '--stats-one-line',
                                            '--stats-log-level',
                                            'NOTICE']],
                              'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                          'latest_passed_full_copy': 'previous full copy\n',
                                          'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_over_six_days': {'stdout': 'none keeps no uploads\n'
                                     'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop\n'
                                     'shop: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/shop\n'
                                     'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo\n'
                                     'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n'
                                     "every app's uploads were copied; the copy started at 2026-11-02T00:00:00Z\n",
                           'commands': [['rclone',
                                         '--config',
                                         '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                         'sync',
                                         '--dry-run',
                                         '--combined',
                                         '-',
                                         '--log-level',
                                         'ERROR',
                                         'uploads_r2:shop-uploads',
                                         'uploads_backup:backup-bucket/shop',
                                         '--use-server-modtime'],
                                        ['rclone',
                                         '--config',
                                         '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                         'sync',
                                         'uploads_r2:shop-uploads',
                                         'uploads_backup:backup-bucket/shop',
                                         '--use-server-modtime',
                                         '--stats',
                                         '10m',
                                         '--stats-one-line',
                                         '--stats-log-level',
                                         'NOTICE'],
                                        ['rclone',
                                         '--config',
                                         '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                         'sync',
                                         '--dry-run',
                                         '--combined',
                                         '-',
                                         '--log-level',
                                         'ERROR',
                                         'uploads_r2:zoo-uploads',
                                         'uploads_backup:backup-bucket/zoo',
                                         '--use-server-modtime'],
                                        ['rclone',
                                         '--config',
                                         '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                         'sync',
                                         'uploads_r2:zoo-uploads',
                                         'uploads_backup:backup-bucket/zoo',
                                         '--use-server-modtime',
                                         '--stats',
                                         '10m',
                                         '--stats-one-line',
                                         '--stats-log-level',
                                         'NOTICE']],
                           'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                       'latest_passed_full_copy': 'previous full copy\n',
                                       'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_old': {'stdout': 'none keeps no uploads\n'
                           'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop, every file '
                           'again: no full copy passed in the last 6 days\n'
                           'shop: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/shop\n'
                           'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo, every file again: '
                           'no full copy passed in the last 6 days\n'
                           'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n'
                           "every app's uploads were copied, every file again; the copy started at "
                           '2026-11-02T00:00:00Z\n',
                 'commands': [['rclone',
                               '--config',
                               '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                               'sync',
                               '--dry-run',
                               '--combined',
                               '-',
                               '--log-level',
                               'ERROR',
                               'uploads_r2:shop-uploads',
                               'uploads_backup:backup-bucket/shop',
                               '--use-server-modtime'],
                              ['rclone',
                               '--config',
                               '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                               'sync',
                               'uploads_r2:shop-uploads',
                               'uploads_backup:backup-bucket/shop',
                               '--use-server-modtime',
                               '--ignore-times',
                               '--stats',
                               '10m',
                               '--stats-one-line',
                               '--stats-log-level',
                               'NOTICE'],
                              ['rclone',
                               '--config',
                               '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                               'sync',
                               '--dry-run',
                               '--combined',
                               '-',
                               '--log-level',
                               'ERROR',
                               'uploads_r2:zoo-uploads',
                               'uploads_backup:backup-bucket/zoo',
                               '--use-server-modtime'],
                              ['rclone',
                               '--config',
                               '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                               'sync',
                               'uploads_r2:zoo-uploads',
                               'uploads_backup:backup-bucket/zoo',
                               '--use-server-modtime',
                               '--ignore-times',
                               '--stats',
                               '10m',
                               '--stats-one-line',
                               '--stats-log-level',
                               'NOTICE']],
                 'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                             'latest_passed_full_copy': '2026-11-02T00:00:00Z\n',
                             'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_no_apps': {'stdout': "every app's uploads were copied, every file again; the copy started at "
                               '2026-11-02T00:00:00Z\n',
                     'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                 'latest_passed_full_copy': '2026-11-02T00:00:00Z\n',
                                 'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_no_buckets': {'stdout': 'none keeps no uploads\n'
                                  "every app's uploads were copied, every file again; the copy started at "
                                  '2026-11-02T00:00:00Z\n',
                        'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                    'latest_passed_full_copy': '2026-11-02T00:00:00Z\n',
                                    'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_empty_bucket_null': {'stdout': 'none keeps no uploads\n'
                                         "every app's uploads were copied, every file again; the copy started at "
                                         '2026-11-02T00:00:00Z\n',
                               'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                           'latest_passed_full_copy': '2026-11-02T00:00:00Z\n',
                                           'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_one_failure': {'stdout': 'none keeps no uploads\n'
                                   'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop\n'
                                   'shop: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/shop\n'
                                   'shop: progress\n'
                                   'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo\n'
                                   'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n',
                         'stderr': 'shop: failed\n'
                                   'the copy of shop (rclone exit status 7) failed; the lines above say why\n',
                         'exit': 1,
                         'commands': [['rclone',
                                       '--config',
                                       '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                       'sync',
                                       '--dry-run',
                                       '--combined',
                                       '-',
                                       '--log-level',
                                       'ERROR',
                                       'uploads_r2:shop-uploads',
                                       'uploads_backup:backup-bucket/shop',
                                       '--use-server-modtime'],
                                      ['rclone',
                                       '--config',
                                       '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                       'sync',
                                       'uploads_r2:shop-uploads',
                                       'uploads_backup:backup-bucket/shop',
                                       '--use-server-modtime',
                                       '--stats',
                                       '10m',
                                       '--stats-one-line',
                                       '--stats-log-level',
                                       'NOTICE'],
                                      ['rclone',
                                       '--config',
                                       '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                       'sync',
                                       '--dry-run',
                                       '--combined',
                                       '-',
                                       '--log-level',
                                       'ERROR',
                                       'uploads_r2:zoo-uploads',
                                       'uploads_backup:backup-bucket/zoo',
                                       '--use-server-modtime'],
                                      ['rclone',
                                       '--config',
                                       '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                       'sync',
                                       'uploads_r2:zoo-uploads',
                                       'uploads_backup:backup-bucket/zoo',
                                       '--use-server-modtime',
                                       '--stats',
                                       '10m',
                                       '--stats-one-line',
                                       '--stats-log-level',
                                       'NOTICE']],
                         'markers': {'latest_passed_copy': 'previous copy\n',
                                     'latest_passed_full_copy': 'previous full copy\n',
                                     'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_all_failures': {'stdout': 'none keeps no uploads\n'
                                    'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop\n'
                                    'shop: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/shop\n'
                                    'shop: progress\n'
                                    'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo\n'
                                    'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n'
                                    'zoo: progress\n',
                          'stderr': 'shop: failed\n'
                                    'zoo: failed\n'
                                    'the copy of shop (rclone exit status 7), zoo (rclone exit status 9) failed; the '
                                    'lines above say why\n',
                          'exit': 1,
                          'commands': [['rclone',
                                        '--config',
                                        '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                        'sync',
                                        '--dry-run',
                                        '--combined',
                                        '-',
                                        '--log-level',
                                        'ERROR',
                                        'uploads_r2:shop-uploads',
                                        'uploads_backup:backup-bucket/shop',
                                        '--use-server-modtime'],
                                       ['rclone',
                                        '--config',
                                        '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                        'sync',
                                        'uploads_r2:shop-uploads',
                                        'uploads_backup:backup-bucket/shop',
                                        '--use-server-modtime',
                                        '--stats',
                                        '10m',
                                        '--stats-one-line',
                                        '--stats-log-level',
                                        'NOTICE'],
                                       ['rclone',
                                        '--config',
                                        '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                        'sync',
                                        '--dry-run',
                                        '--combined',
                                        '-',
                                        '--log-level',
                                        'ERROR',
                                        'uploads_r2:zoo-uploads',
                                        'uploads_backup:backup-bucket/zoo',
                                        '--use-server-modtime'],
                                       ['rclone',
                                        '--config',
                                        '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                        'sync',
                                        'uploads_r2:zoo-uploads',
                                        'uploads_backup:backup-bucket/zoo',
                                        '--use-server-modtime',
                                        '--stats',
                                        '10m',
                                        '--stats-one-line',
                                        '--stats-log-level',
                                        'NOTICE']],
                          'markers': {'latest_passed_copy': 'previous copy\n',
                                      'latest_passed_full_copy': 'previous full copy\n',
                                      'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_failed_full': {'stdout': 'none keeps no uploads\n'
                                   'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop, every '
                                   'file again: no full copy passed in the last 6 days\n'
                                   'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo, every '
                                   'file again: no full copy passed in the last 6 days\n',
                         'stderr': 'copy failed\n'
                                   'copy failed\n'
                                   'the copy of shop (rclone exit status 5 in the dry run before the copy), zoo '
                                   '(rclone exit status 5 in the dry run before the copy) failed; the lines above say '
                                   'why\n',
                         'exit': 1,
                         'commands': [['rclone',
                                       '--config',
                                       '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                       'sync',
                                       '--dry-run',
                                       '--combined',
                                       '-',
                                       '--log-level',
                                       'ERROR',
                                       'uploads_r2:shop-uploads',
                                       'uploads_backup:backup-bucket/shop',
                                       '--use-server-modtime'],
                                      ['rclone',
                                       '--config',
                                       '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                       'sync',
                                       '--dry-run',
                                       '--combined',
                                       '-',
                                       '--log-level',
                                       'ERROR',
                                       'uploads_r2:zoo-uploads',
                                       'uploads_backup:backup-bucket/zoo',
                                       '--use-server-modtime']],
                         'markers': {'latest_passed_copy': 'previous copy\n',
                                     'latest_passed_full_copy': 'previous full copy\n',
                                     'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_signal_terminated': {'stdout': 'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop, '
                                         'every file again: no full copy passed in the last 6 days\n',
                               'stderr': 'the copy of shop (rclone was stopped by signal 15 (SIGTERM) in the dry run '
                                         'before the copy) failed; the lines above say why\n',
                               'exit': 1,
                               'commands': [['rclone',
                                             '--config',
                                             '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                             'sync',
                                             '--dry-run',
                                             '--combined',
                                             '-',
                                             '--log-level',
                                             'ERROR',
                                             'uploads_r2:shop-uploads',
                                             'uploads_backup:backup-bucket/shop',
                                             '--use-server-modtime']],
                               'markers': {'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'fleet_list_status_0': {'commands': [['mmwatchdog', 'fleet', '--json']]},
 'fleet_list_status_1': {'commands': [['mmwatchdog', 'fleet', '--json']]},
 'fleet_list_status_3': {'commands': [['mmwatchdog', 'fleet', '--json']]},
 'fleet_forget_sorted_unique': {'stdout': 'removed\nforgot a-old\nremoved\nforgot z-old\n',
                                'stderr': 'forget diagnostic\nforget diagnostic\n',
                                'exit': 2,
                                'commands': [['mmwatchdog', 'fleet', '--json'],
                                             ['mmwatchdog', 'fleet', 'forget', 'a-old'],
                                             ['mmwatchdog', 'fleet', 'forget', 'z-old']]},
 'fleet_dryrun': {'stdout': 'would forget a-old\nwould forget z-old\n',
                  'exit': 2,
                  'commands': [['mmwatchdog', 'fleet', '--json']]},
 'fleet_other_args': {'stdout': 'removed\nforgot a-old\nremoved\nforgot z-old\n',
                      'stderr': 'forget diagnostic\nforget diagnostic\n',
                      'exit': 2,
                      'commands': [['mmwatchdog', 'fleet', '--json'],
                                   ['mmwatchdog', 'fleet', 'forget', 'a-old'],
                                   ['mmwatchdog', 'fleet', 'forget', 'z-old']]},
 'fleet_extra_dryrun_args': {'stdout': 'removed\nforgot a-old\nremoved\nforgot z-old\n',
                             'stderr': 'forget diagnostic\nforget diagnostic\n',
                             'exit': 2,
                             'commands': [['mmwatchdog', 'fleet', '--json'],
                                          ['mmwatchdog', 'fleet', 'forget', 'a-old'],
                                          ['mmwatchdog', 'fleet', 'forget', 'z-old']]},
 'fleet_empty': {'commands': [['mmwatchdog', 'fleet', '--json']]},
 'fleet_list_failed': {'stderr': 'mmwatchdog fleet --json failed: hub unavailable\n',
                       'exit': 1,
                       'commands': [['mmwatchdog', 'fleet', '--json']]},
 'database_short_help': {'stderr': 'usage: show_the_database_servers_and_their_health --monitor-data-directory DIR '
                                   '--formation NAME\n',
                         'exit': 2},
 'ports_underscores': {'stderr': 'the live port file <temporary>/var/lib/monkeymaxxing-stack/live_web_ports/shop must '
                                 'contain one port number written with digits\n',
                       'exit': 1},
 'ports_spaces': {'stderr': 'the live port file <temporary>/var/lib/monkeymaxxing-stack/live_web_ports/shop must '
                            'contain one port number written with digits\n',
                  'exit': 1},
 'ports_extra_newline': {'stderr': 'the live port file <temporary>/var/lib/monkeymaxxing-stack/live_web_ports/shop '
                                   'must contain one port number written with digits\n',
                         'exit': 1},
 'ports_empty_file': {'stderr': 'the live port file <temporary>/var/lib/monkeymaxxing-stack/live_web_ports/shop must '
                                'contain one port number written with digits\n',
                      'exit': 1},
 'ports_no_newline': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                 'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                         'shop': {'web_port': 8001,
                                                                  'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                 'new_web_containers': {'zoo': {'web_port': 8102,
                                                                'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                        'shop': {'web_port': 8002,
                                                                 'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                 'recorded_live_images': {'shop': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'},
                                 'apps_not_on_the_deployed_image_tags': [],
                                 'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'uploads_empty_bucket_missing': {'stdout': 'none keeps no uploads\n'
                                            "every app's uploads were copied, every file again; the copy started at "
                                            '2026-11-02T00:00:00Z\n',
                                  'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                              'latest_passed_full_copy': '2026-11-02T00:00:00Z\n',
                                              'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_one_second_over_six_days': {'stdout': 'none keeps no uploads\n'
                                                'shop: copying uploads_r2:shop-uploads to '
                                                'uploads_backup:backup-bucket/shop, every file again: no full copy '
                                                'passed in the last 6 days\n'
                                                'shop: the copy hides 0 of the 0 files in '
                                                'uploads_backup:backup-bucket/shop\n'
                                                'zoo: copying uploads_r2:zoo-uploads to '
                                                'uploads_backup:backup-bucket/zoo, every file again: no full copy '
                                                'passed in the last 6 days\n'
                                                'zoo: the copy hides 0 of the 0 files in '
                                                'uploads_backup:backup-bucket/zoo\n'
                                                "every app's uploads were copied, every file again; the copy started "
                                                'at 2026-11-02T00:00:00Z\n',
                                      'commands': [['rclone',
                                                    '--config',
                                                    '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                    'sync',
                                                    '--dry-run',
                                                    '--combined',
                                                    '-',
                                                    '--log-level',
                                                    'ERROR',
                                                    'uploads_r2:shop-uploads',
                                                    'uploads_backup:backup-bucket/shop',
                                                    '--use-server-modtime'],
                                                   ['rclone',
                                                    '--config',
                                                    '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                    'sync',
                                                    'uploads_r2:shop-uploads',
                                                    'uploads_backup:backup-bucket/shop',
                                                    '--use-server-modtime',
                                                    '--ignore-times',
                                                    '--stats',
                                                    '10m',
                                                    '--stats-one-line',
                                                    '--stats-log-level',
                                                    'NOTICE'],
                                                   ['rclone',
                                                    '--config',
                                                    '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                    'sync',
                                                    '--dry-run',
                                                    '--combined',
                                                    '-',
                                                    '--log-level',
                                                    'ERROR',
                                                    'uploads_r2:zoo-uploads',
                                                    'uploads_backup:backup-bucket/zoo',
                                                    '--use-server-modtime'],
                                                   ['rclone',
                                                    '--config',
                                                    '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                    'sync',
                                                    'uploads_r2:zoo-uploads',
                                                    'uploads_backup:backup-bucket/zoo',
                                                    '--use-server-modtime',
                                                    '--ignore-times',
                                                    '--stats',
                                                    '10m',
                                                    '--stats-one-line',
                                                    '--stats-log-level',
                                                    'NOTICE']],
                                      'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                                  'latest_passed_full_copy': '2026-11-02T00:00:00Z\n',
                                                  'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'ports_new_server_takes_the_pool_release': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                                        'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                'shop': {'web_port': 8001,
                                                                                         'image': 'ghcr.io/example/shop:live2'}},
                                                        'new_web_containers': {'zoo': {'web_port': 8102,
                                                                                       'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                               'shop': {'web_port': 8002,
                                                                                        'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                        'recorded_live_images': {},
                                                        'apps_not_on_the_deployed_image_tags': [],
                                                        'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'ports_running_server_keeps_its_own_release': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                                           'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                   'shop': {'web_port': 8002,
                                                                                            'image': 'own:release'}},
                                                           'new_web_containers': {'zoo': {'web_port': 8102,
                                                                                          'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                  'shop': {'web_port': 8001,
                                                                                           'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                           'recorded_live_images': {'shop': 'own:release'},
                                                           'apps_not_on_the_deployed_image_tags': ['shop'],
                                                           'number_of_apps_not_on_the_deployed_image_tags': 1}},
 'ports_pool_without_release_takes_deployed_tag': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                                              'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                      'shop': {'web_port': 8001,
                                                                                               'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                              'new_web_containers': {'zoo': {'web_port': 8102,
                                                                                             'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                     'shop': {'web_port': 8002,
                                                                                              'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                              'recorded_live_images': {},
                                                              'apps_not_on_the_deployed_image_tags': [],
                                                              'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'ports_short_tag_is_refused': {'stderr': 'the deployed image tag of shop is "3f2a1c9". Use the full Git commit of the '
                                          'app, 40 lowercase hexadecimal characters, so that one tag always names one '
                                          'image. Nothing changed.\n',
                                'exit': 1},
 'ports_running_another_release_is_reported': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                                          'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                  'shop': {'web_port': 8001,
                                                                                           'image': 'ghcr.io/example/shop:cccccccccccccccccccccccccccccccccccccccc'}},
                                                          'new_web_containers': {'zoo': {'web_port': 8102,
                                                                                         'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                 'shop': {'web_port': 8002,
                                                                                          'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                          'recorded_live_images': {'shop': 'ghcr.io/example/shop:cccccccccccccccccccccccccccccccccccccccc'},
                                                          'apps_not_on_the_deployed_image_tags': ['shop'],
                                                          'number_of_apps_not_on_the_deployed_image_tags': 1}},
 'ports_running_the_deployed_release_is_not_reported': {'stdout': {'live_web_containers': {'zoo': {'web_port': 8101,
                                                                                                   'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                           'shop': {'web_port': 8001,
                                                                                                    'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                                   'new_web_containers': {'zoo': {'web_port': 8102,
                                                                                                  'image': 'ghcr.io/example/zoo:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'},
                                                                                          'shop': {'web_port': 8002,
                                                                                                   'image': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}},
                                                                   'recorded_live_images': {'shop': 'ghcr.io/example/shop:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'},
                                                                   'apps_not_on_the_deployed_image_tags': [],
                                                                   'number_of_apps_not_on_the_deployed_image_tags': 0}},
 'uploads_hides_an_unusual_share': {'stdout': 'none keeps no uploads\n'
                                              'shop: copying uploads_r2:shop-uploads to '
                                              'uploads_backup:backup-bucket/shop\n'
                                              'shop: the copy hides 2 of the 10 files in '
                                              'uploads_backup:backup-bucket/shop\n'
                                              'zoo: copying uploads_r2:zoo-uploads to '
                                              'uploads_backup:backup-bucket/zoo\n'
                                              'zoo: the copy hides 1 of the 11 files in '
                                              'uploads_backup:backup-bucket/zoo\n'
                                              "every app's uploads were copied; the copy started at "
                                              '2026-11-02T00:00:00Z\n',
                                    'commands': [['rclone',
                                                  '--config',
                                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                  'sync',
                                                  '--dry-run',
                                                  '--combined',
                                                  '-',
                                                  '--log-level',
                                                  'ERROR',
                                                  'uploads_r2:shop-uploads',
                                                  'uploads_backup:backup-bucket/shop',
                                                  '--use-server-modtime'],
                                                 ['rclone',
                                                  '--config',
                                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                  'sync',
                                                  'uploads_r2:shop-uploads',
                                                  'uploads_backup:backup-bucket/shop',
                                                  '--use-server-modtime',
                                                  '--stats',
                                                  '10m',
                                                  '--stats-one-line',
                                                  '--stats-log-level',
                                                  'NOTICE'],
                                                 ['rclone',
                                                  '--config',
                                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                  'sync',
                                                  '--dry-run',
                                                  '--combined',
                                                  '-',
                                                  '--log-level',
                                                  'ERROR',
                                                  'uploads_r2:zoo-uploads',
                                                  'uploads_backup:backup-bucket/zoo',
                                                  '--use-server-modtime'],
                                                 ['rclone',
                                                  '--config',
                                                  '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                  'sync',
                                                  'uploads_r2:zoo-uploads',
                                                  'uploads_backup:backup-bucket/zoo',
                                                  '--use-server-modtime',
                                                  '--stats',
                                                  '10m',
                                                  '--stats-one-line',
                                                  '--stats-log-level',
                                                  'NOTICE']],
                                    'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                                'latest_passed_full_copy': 'previous full copy\n',
                                                'apps_whose_latest_copy_hid_an_unusual_share': 'shop: one copy hid 2 '
                                                                                               'of the 10 files in '
                                                                                               'uploads_backup:backup-bucket/shop, '
                                                                                               'more than 10 percent: '
                                                                                               'files deleted or '
                                                                                               'replaced in R2 since '
                                                                                               'the copy before. If '
                                                                                               'nobody did that on '
                                                                                               'purpose, follow '
                                                                                               'operating_procedures/restore_an_uploaded_file.md, '
                                                                                               '"Restore all of an '
                                                                                               "app's uploaded "
                                                                                               'files".\n'}},
 'uploads_hides_exactly_the_share': {'stdout': 'none keeps no uploads\n'
                                               'shop: copying uploads_r2:shop-uploads to '
                                               'uploads_backup:backup-bucket/shop\n'
                                               'shop: the copy hides 1 of the 10 files in '
                                               'uploads_backup:backup-bucket/shop\n'
                                               'zoo: copying uploads_r2:zoo-uploads to '
                                               'uploads_backup:backup-bucket/zoo\n'
                                               'zoo: the copy hides 0 of the 0 files in '
                                               'uploads_backup:backup-bucket/zoo\n'
                                               "every app's uploads were copied; the copy started at "
                                               '2026-11-02T00:00:00Z\n',
                                     'commands': [['rclone',
                                                   '--config',
                                                   '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                   'sync',
                                                   '--dry-run',
                                                   '--combined',
                                                   '-',
                                                   '--log-level',
                                                   'ERROR',
                                                   'uploads_r2:shop-uploads',
                                                   'uploads_backup:backup-bucket/shop',
                                                   '--use-server-modtime'],
                                                  ['rclone',
                                                   '--config',
                                                   '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                   'sync',
                                                   'uploads_r2:shop-uploads',
                                                   'uploads_backup:backup-bucket/shop',
                                                   '--use-server-modtime',
                                                   '--stats',
                                                   '10m',
                                                   '--stats-one-line',
                                                   '--stats-log-level',
                                                   'NOTICE'],
                                                  ['rclone',
                                                   '--config',
                                                   '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                   'sync',
                                                   '--dry-run',
                                                   '--combined',
                                                   '-',
                                                   '--log-level',
                                                   'ERROR',
                                                   'uploads_r2:zoo-uploads',
                                                   'uploads_backup:backup-bucket/zoo',
                                                   '--use-server-modtime'],
                                                  ['rclone',
                                                   '--config',
                                                   '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                   'sync',
                                                   'uploads_r2:zoo-uploads',
                                                   'uploads_backup:backup-bucket/zoo',
                                                   '--use-server-modtime',
                                                   '--stats',
                                                   '10m',
                                                   '--stats-one-line',
                                                   '--stats-log-level',
                                                   'NOTICE']],
                                     'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                                 'latest_passed_full_copy': 'previous full copy\n',
                                                 'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_hides_everything_below_the_smallest_number': {'stdout': 'none keeps no uploads\n'
                                                                  'shop: copying uploads_r2:shop-uploads to '
                                                                  'uploads_backup:backup-bucket/shop\n'
                                                                  'shop: the copy hides 9 of the 9 files in '
                                                                  'uploads_backup:backup-bucket/shop\n'
                                                                  'zoo: copying uploads_r2:zoo-uploads to '
                                                                  'uploads_backup:backup-bucket/zoo\n'
                                                                  'zoo: the copy hides 0 of the 0 files in '
                                                                  'uploads_backup:backup-bucket/zoo\n'
                                                                  "every app's uploads were copied; the copy started "
                                                                  'at 2026-11-02T00:00:00Z\n',
                                                        'commands': [['rclone',
                                                                      '--config',
                                                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                                      'sync',
                                                                      '--dry-run',
                                                                      '--combined',
                                                                      '-',
                                                                      '--log-level',
                                                                      'ERROR',
                                                                      'uploads_r2:shop-uploads',
                                                                      'uploads_backup:backup-bucket/shop',
                                                                      '--use-server-modtime'],
                                                                     ['rclone',
                                                                      '--config',
                                                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                                      'sync',
                                                                      'uploads_r2:shop-uploads',
                                                                      'uploads_backup:backup-bucket/shop',
                                                                      '--use-server-modtime',
                                                                      '--stats',
                                                                      '10m',
                                                                      '--stats-one-line',
                                                                      '--stats-log-level',
                                                                      'NOTICE'],
                                                                     ['rclone',
                                                                      '--config',
                                                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                                      'sync',
                                                                      '--dry-run',
                                                                      '--combined',
                                                                      '-',
                                                                      '--log-level',
                                                                      'ERROR',
                                                                      'uploads_r2:zoo-uploads',
                                                                      'uploads_backup:backup-bucket/zoo',
                                                                      '--use-server-modtime'],
                                                                     ['rclone',
                                                                      '--config',
                                                                      '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                                                      'sync',
                                                                      'uploads_r2:zoo-uploads',
                                                                      'uploads_backup:backup-bucket/zoo',
                                                                      '--use-server-modtime',
                                                                      '--stats',
                                                                      '10m',
                                                                      '--stats-one-line',
                                                                      '--stats-log-level',
                                                                      'NOTICE']],
                                                        'markers': {'latest_passed_copy': '2026-11-02T00:00:00Z\n',
                                                                    'latest_passed_full_copy': 'previous full copy\n',
                                                                    'apps_whose_latest_copy_hid_an_unusual_share': ''}},
 'uploads_dry_run_fails': {'stdout': 'none keeps no uploads\n'
                                     'shop: copying uploads_r2:shop-uploads to uploads_backup:backup-bucket/shop\n'
                                     'zoo: copying uploads_r2:zoo-uploads to uploads_backup:backup-bucket/zoo\n'
                                     'zoo: the copy hides 0 of the 0 files in uploads_backup:backup-bucket/zoo\n',
                           'stderr': 'shop: listing failed\n'
                                     'the copy of shop (rclone exit status 4 in the dry run before the copy) failed; '
                                     'the lines above say why\n',
                           'exit': 1,
                           'commands': [['rclone',
                                         '--config',
                                         '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                         'sync',
                                         '--dry-run',
                                         '--combined',
                                         '-',
                                         '--log-level',
                                         'ERROR',
                                         'uploads_r2:shop-uploads',
                                         'uploads_backup:backup-bucket/shop',
                                         '--use-server-modtime'],
                                        ['rclone',
                                         '--config',
                                         '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                         'sync',
                                         '--dry-run',
                                         '--combined',
                                         '-',
                                         '--log-level',
                                         'ERROR',
                                         'uploads_r2:zoo-uploads',
                                         'uploads_backup:backup-bucket/zoo',
                                         '--use-server-modtime'],
                                        ['rclone',
                                         '--config',
                                         '<temporary>/var/lib/mmhotline/uploads_backup_rclone.conf',
                                         'sync',
                                         'uploads_r2:zoo-uploads',
                                         'uploads_backup:backup-bucket/zoo',
                                         '--use-server-modtime',
                                         '--stats',
                                         '10m',
                                         '--stats-one-line',
                                         '--stats-log-level',
                                         'NOTICE']],
                           'markers': {'latest_passed_copy': 'previous copy\n',
                                       'latest_passed_full_copy': 'previous full copy\n',
                                       'apps_whose_latest_copy_hid_an_unusual_share': ''}}}  # END_EXPECTED


class ServerScripts(unittest.TestCase):
    def check_script(self, script):
        self.assertEqual(set(EXPECTED), {name for name, _, _ in cases()})
        for name, kind, case in cases():
            if kind != script:
                continue
            with self.subTest(case=name):
                expected = {"stdout": "", "stderr": "", "exit": 0, "commands": [], "markers": {},
                            "input_files": {path: text for path, text in case.get("files", {}).items()
                                            if not path.startswith("/var/lib/uploads_backup/")},
                            **EXPECTED[name]}
                self.assertEqual(run_case(kind, case), expected)

    def test_memory(self):
        self.check_script("memory")

    def test_ports(self):
        self.check_script("ports")

    def test_database(self):
        self.check_script("database")

    def test_uploads(self):
        self.check_script("uploads")

    def test_fleet(self):
        self.check_script("fleet")


if __name__ == "__main__":
    unittest.main()
