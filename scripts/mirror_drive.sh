#!/usr/bin/env bash
# Mirror the team Google Drive folder (shared "anyone with link") into data/drive_mirror/.
# Usage: bash scripts/mirror_drive.sh
set -u
cd "$(dirname "$0")/.."
OUT=data/drive_mirror
while IFS=$'\t' read -r id path; do
  [ -z "$id" ] && continue
  dest="$OUT/$path"; mkdir -p "$(dirname "$dest")"
  [ -s "$dest" ] && continue
  for i in 1 2 3 4; do
    curl -sSL --fail -o "$dest" "https://drive.usercontent.google.com/download?id=$id&export=download&confirm=t" && break
    sleep $((i*3))
  done
  echo "$(stat -c %s "$dest" 2>/dev/null) $path"
done < scripts/drive_manifest.tsv
