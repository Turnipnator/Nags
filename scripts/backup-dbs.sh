#!/usr/bin/env bash
# Verified SQLite backups for both live databases.
#
# WHY THIS EXISTS (6 Aug 2026): there was no scheduled backup at all. The only
# copies were made by hand with `cp` -- and racing.db runs in WAL mode, so the
# main file had not been written since 19 Jul while 4MB of commits sat in
# racing.db-wal. `cp` grabs the stale main file and leaves the WAL behind:
# racing.db.bak-20260727 contained data only to 19 Jul. Restoring it would have
# silently lost eight days of the money ledger with no error anywhere.
#
# RULES THIS ENCODES:
#   1. ALWAYS `sqlite3 .backup`, NEVER `cp`. Correct for WAL and DELETE modes
#      alike, and consistent even while the bot is mid-write.
#   2. VERIFY BEFORE ROTATING. Every snapshot gets integrity_check plus a
#      row-count floor check. Old backups are pruned ONLY after the new one
#      passes -- a job that deletes good copies to make room for a corrupt one
#      is worse than no job.
#   3. Read-only against live. This never alters, vacuums or checkpoints the
#      originals. Worst case on failure is no new backup and a loud log line.
#
# ⚠ ON-BOX ONLY. This protects against corruption, bad writes and accidental
# deletion -- NOT against losing the VPS. Off-site copying is still an open gap.
set -uo pipefail

DEST=/root/db-backups
KEEP=14
STAMP=$(date +%Y%m%d-%H%M)
mkdir -p "$DEST"

# name | path | table used for the row-count floor check
DBS=(
  "racing|/root/horse-racing-bot/data/racing.db|selections"
  "betfair|/opt/betfair-bot/data/betfair_bot.db|markets"
)

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | $*"; }

overall=0

for entry in "${DBS[@]}"; do
  IFS='|' read -r name path table <<<"$entry"

  if [[ ! -f "$path" ]]; then
    log "FAIL $name: $path does not exist"; overall=1; continue
  fi

  # Row count BEFORE the snapshot. The snapshot must contain at least this
  # many rows; it may contain more if the bot wrote during the backup, which
  # is fine. This catches an empty or truncated snapshot, which is the
  # failure mode that matters.
  before=$(sqlite3 "$path" "SELECT COUNT(*) FROM $table;" 2>/dev/null)
  if [[ -z "$before" ]]; then
    log "FAIL $name: cannot read $table from live DB"; overall=1; continue
  fi

  tmp="$DEST/.$name-$STAMP.tmp"
  rm -f "$tmp"
  if ! sqlite3 "$path" ".backup '$tmp'" 2>/dev/null; then
    log "FAIL $name: .backup failed"; rm -f "$tmp"; overall=1; continue
  fi

  integrity=$(sqlite3 "$tmp" "PRAGMA integrity_check;" 2>/dev/null | head -1)
  if [[ "$integrity" != "ok" ]]; then
    log "FAIL $name: integrity_check said '${integrity:-<no output>}' -- NOT rotating"
    rm -f "$tmp"; overall=1; continue
  fi

  after=$(sqlite3 "$tmp" "SELECT COUNT(*) FROM $table;" 2>/dev/null)
  if [[ -z "$after" || "$after" -lt "$before" ]]; then
    log "FAIL $name: snapshot has ${after:-?} rows vs live $before -- NOT rotating"
    rm -f "$tmp"; overall=1; continue
  fi

  out="$DEST/$name-$STAMP.db.gz"
  if ! gzip -c "$tmp" > "$out"; then
    log "FAIL $name: gzip failed"; rm -f "$tmp" "$out"; overall=1; continue
  fi
  rm -f "$tmp"

  size=$(du -h "$out" | cut -f1)
  log "OK   $name: $after rows (live $before), integrity ok, $size -> $(basename "$out")"

  # Prune ONLY now that a verified backup exists for this DB.
  mapfile -t old < <(ls -1t "$DEST/$name-"*.db.gz 2>/dev/null | tail -n +$((KEEP + 1)))
  for f in "${old[@]:-}"; do
    [[ -n "$f" ]] && rm -f "$f" && log "     pruned $(basename "$f")"
  done
done

if [[ $overall -ne 0 ]]; then
  log "BACKUP RUN FAILED -- see failures above. Old backups were NOT pruned for the failing DB(s)."
fi
exit $overall
