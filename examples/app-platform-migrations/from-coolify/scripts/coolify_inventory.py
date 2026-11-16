#!/usr/bin/env python3
"""Save native Coolify configuration without printing secret-bearing responses."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def api(path, method="GET", body=None):
    token = Path(os.environ["COOLIFY_API_TOKEN_FILE"]).read_text().strip()
    request = Request(
        os.environ["COOLIFY_API_URL"].rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read().decode()
            if path == "/version":
                try:
                    return json.loads(payload)
                except json.JSONDecodeError:
                    return payload
            return json.loads(payload)
    except HTTPError as error:
        raise RuntimeError(f"Coolify API {method} {path}: HTTP {error.code}") from None


def export_inventory():
    os.umask(0o077)
    directory = Path(os.environ["EXPORT_DIR"])
    directory.mkdir(mode=0o700)
    application_uuid = quote(os.environ["COOLIFY_APPLICATION_UUID"], safe="")
    prefix = f"/applications/{application_uuid}"
    application = api(prefix)
    inventory = {
        "version": api("/version"),
        "application": application,
        "envs": api(prefix + "/envs"),
        "storages": api(prefix + "/storages"),
        "scheduled_tasks": api(prefix + "/scheduled-tasks"),
        "deployments": api("/deployments/applications/" + application_uuid),
    }
    project_uuid = quote(os.environ["COOLIFY_PROJECT_UUID"], safe="")
    environment_uuid = quote(os.environ["COOLIFY_ENVIRONMENT_UUID"], safe="")
    inventory["project"] = api(f"/projects/{project_uuid}")
    inventory["environments"] = api(f"/projects/{project_uuid}/environments")
    inventory["shared_envs"] = {
        "team": api("/team/envs"),
        "project": api(f"/projects/{project_uuid}/envs"),
        "environment": api(f"/projects/{project_uuid}/environments/{environment_uuid}/envs"),
    }
    inventory["task_executions"] = {
        task["uuid"]: api(prefix + "/scheduled-tasks/" + task["uuid"] + "/executions")
        for task in inventory["scheduled_tasks"]
    }
    if os.environ.get("COOLIFY_DATABASE_UUID"):
        database_uuid = quote(os.environ["COOLIFY_DATABASE_UUID"], safe="")
        inventory["database"] = api("/databases/" + database_uuid)
    (directory / "coolify.json").write_text(json.dumps(inventory, indent=2) + "\n")
    print("Native Coolify inventory saved; responses remain in the protected directory")


if __name__ == "__main__":
    export_inventory()
