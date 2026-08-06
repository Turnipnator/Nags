#!/usr/bin/env bash
# Off-site copy: PULL verified DB backups from the VPS to this Mac.
#
# WHY PULL, NOT PUSH (6 Aug 2026): the VPS has no outbound SSH keys. Giving it
# credentials to push here would mean a compromised VPS could reach and DELETE
# the off-site copies -- which is how ransomware defeats backups. Pulling keeps
# every credential on this machine and leaves the server unable to touch the
# destination. Read-only against the VPS: this never writes or deletes there.
#
# The VPS keeps 14 days (/root/backup-dbs.sh, cron 02:00). This keeps 60, so a
# problem that takes weeks to notice can still be rolled back past -- exactly
# the failure mode of the settler gap found on 6 Aug 2026, which went unnoticed
# from June to August.
#
# rsync can complete happily on a truncated or corrupt source, so EVERY pulled
# file is gunzipped and checked (integrity_check + a monotonic row-count floor)
# before it is trusted. Failures are quarantined, never silently kept.
set -uo pipefail

VPS_KEY="$HOME/.ssh/id_ed25519_vps"
VPS="root@149.102.144.190"
SRC="/root/db-backups/"
DEST="$HOME/Backups/nags-vps"
QUAR="$DEST/quarantine"
STATE="$DEST/.rowfloor"
KEEP_DAYS=60

mkdir -p "$DEST" "$QUAR" "$STATE"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | $*"; }

overall=0
log "pull start"

# NO --delete: the VPS prunes to 14 and this side must keep its longer history.
if ! rsync -az -e "ssh -i $VPS_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20" \
        --include='*.db.gz' --include='backup.log' --exclude='*' \
        "$VPS:$SRC" "$DEST/" 2>&1; then
    log "FAIL rsync could not pull from $VPS -- nothing verified, nothing pruned"
    exit 1
fi

verified=0
for f in "$DEST"/*.db.gz; do
    [[ -e "$f" ]] || continue
    base=$(basename "$f")
    name=${base%%-*}                      # racing | betfair
    marker="$STATE/$base.ok"
    [[ -f "$marker" ]] && continue        # already verified on a previous run

    tmp=$(mktemp -t nagsbk); trap 'rm -f "$tmp"' RETURN
    if ! gunzip -c "$f" > "$tmp" 2>/dev/null; then
        log "QUARANTINE $base: gunzip failed"; mv "$f" "$QUAR/"; rm -f "$tmp"; overall=1; continue
    fi
    integrity=$(sqlite3 "$tmp" "PRAGMA integrity_check;" 2>/dev/null | head -1)
    if [[ "$integrity" != "ok" ]]; then
        log "QUARANTINE $base: integrity_check said '${integrity:-<none>}'"
        mv "$f" "$QUAR/"; rm -f "$tmp"; overall=1; continue
    fi

    case "$name" in
        racing)  table=selections ;;
        betfair) table=markets ;;
        *)       log "SKIP $base: unknown database name"; rm -f "$tmp"; continue ;;
    esac
    rows=$(sqlite3 "$tmp" "SELECT COUNT(*) FROM $table;" 2>/dev/null)
    if [[ -z "$rows" ]]; then
        log "QUARANTINE $base: cannot read $table"; mv "$f" "$QUAR/"; rm -f "$tmp"; overall=1; continue
    fi
    # Monotonic floor: rows are only ever added (selections are superseded, not
    # deleted), so a snapshot with FEWER rows than the best we have already seen
    # means truncation, a bad restore on the server, or the wrong file.
    floor_file="$STATE/$name.maxrows"
    floor=$(cat "$floor_file" 2>/dev/null || echo 0)
    if (( rows < floor )); then
        log "QUARANTINE $base: $rows rows in $table, below the $floor already seen"
        mv "$f" "$QUAR/"; rm -f "$tmp"; overall=1; continue
    fi
    (( rows > floor )) && echo "$rows" > "$floor_file"

    rm -f "$tmp"; touch "$marker"
    verified=$((verified + 1))
    log "OK   $base: $rows rows in $table, integrity ok"
done

# Prune ONLY if something verified this run -- never trade a good old copy for
# a run that failed to bring anything usable.
if (( verified > 0 || overall == 0 )); then
    pruned=$(find "$DEST" -maxdepth 1 -name '*.db.gz' -mtime +$KEEP_DAYS -print -delete | wc -l | tr -d ' ')
    [[ "$pruned" != "0" ]] && log "pruned $pruned copies older than $KEEP_DAYS days"
    find "$STATE" -name '*.ok' -mtime +$KEEP_DAYS -delete 2>/dev/null
else
    log "nothing verified this run -- pruning skipped"
fi

total=$(ls -1 "$DEST"/*.db.gz 2>/dev/null | wc -l | tr -d ' ')
quar=$(ls -1 "$QUAR"/*.db.gz 2>/dev/null | wc -l | tr -d ' ')
log "pull done: $verified newly verified, $total held locally, $quar quarantined"
(( overall != 0 )) && log "RUN FAILED -- see QUARANTINE lines above"
exit $overall
