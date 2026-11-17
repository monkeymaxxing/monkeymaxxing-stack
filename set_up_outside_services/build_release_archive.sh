#!/usr/bin/env bash
# Builds the release archive of set-up-outside-services for the systems
# desk, Linux on x86-64, prints its SHA-256, and writes the release's
# version, address and SHA-256 into stack_software.set_up_outside_services
# in the template's mmx_project_settings.yml, for the release commit.
#
#   ./build_release_archive.sh 0.1.0 /tmp/release
#
# The version must be the template's stack_version, the release's tag without its v.
# The address keeps the template's pattern with the new version in place
# of the old one.
# The build is reproducible: the same source, Go toolchain (go.mod's
# toolchain line), and version give the same archive, byte for byte, so
# anyone can check a published archive by building it again. Run it on
# Linux: it needs GNU tar for the archive's fixed file order and times.
set -euo pipefail
version=${1:?give the version, such as 0.1.0}
output_directory=${2:?give the output directory}
source_directory=$(cd "$(dirname "$0")" && pwd)
template="$source_directory/../skills/monkeymaxxing-stack/systems_repository_template"
stack_version=$(sed -n 's/^stack_version: *//p' "$template/monkeymaxxing_stack_checklist.yml")
[ "$version" = "$stack_version" ] || {
  printf 'build_release_archive.sh: the version is %s, but stack_version in the template'"'"'s monkeymaxxing_stack_checklist.yml is %s; give that version, or change stack_version first. Nothing was built.\n' "$version" "$stack_version" >&2
  exit 1
}
name="set-up-outside-services-$version-linux-amd64"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/$name" "$output_directory"
(
  cd "$source_directory"
  CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOFLAGS=-mod=readonly \
    go build -trimpath -buildvcs=false -ldflags "-s -w -buildid= -X main.version=$version" \
    -o "$work/$name/set-up-outside-services" .
)
cp "$source_directory/../LICENSE" "$work/$name/LICENSE"
chmod 0755 "$work/$name/set-up-outside-services"
chmod 0644 "$work/$name/LICENSE"
# The directory too: mkdir follows the umask, which differs between machines.
chmod 0755 "$work/$name"
tar --sort=name --mtime='2026-01-01 00:00:00Z' --owner=0 --group=0 --numeric-owner \
  -C "$work" -cf - "$name" | gzip -n -9 > "$output_directory/$name.tar.gz"
cd "$output_directory"
sha256sum "$name.tar.gz"
sha256=$(sha256sum "$name.tar.gz" | cut -d ' ' -f 1)
VERSION="$version" SHA256="$sha256" python3 -I - "$template/mmx_project_settings.yml" <<'PYTHON'
import os, re, sys
path = sys.argv[1]
text = open(path).read()
block = re.search(r'^    set_up_outside_services:\n      version: "([^"]*)"\n      download_url: (\S+)\n      sha256: "[0-9a-f]{64}"\n', text, re.M)
if not block:
    sys.exit(f'build_release_archive.sh: {path} has no stack_software.set_up_outside_services with version, download_url and sha256 in that order; the pin is unchanged.')
version, sha256 = os.environ['VERSION'], os.environ['SHA256']
pin = (f'    set_up_outside_services:\n      version: "{version}"\n'
       f'      download_url: {block[2].replace(block[1], version)}\n      sha256: "{sha256}"\n')
open(path, 'w').write(text[:block.start()] + pin + text[block.end():])
print(f'stack_software.set_up_outside_services now pins {version} with SHA-256 {sha256}.')
PYTHON
