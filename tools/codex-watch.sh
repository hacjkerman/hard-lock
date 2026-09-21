#!/usr/bin/env bash
# Event stream for a Codex run started by tools/codex-run.sh. Meant for Claude's Monitor tool:
# every stdout line becomes a notification. Emits each new progress line, FINISHED when the
# final message lands, STALLED when the log stops growing, and exits on either terminal state.
#
#   tools/codex-watch.sh <name> [stall-minutes]
set -uo pipefail
name="${1:?name}"; stall_min="${2:-8}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
log="$repo/run/codex/$name.log"
progress="$repo/run/codex/$name.progress"
last="$repo/run/codex/$name.last.md"
seen=0; stall=0; lastsize=0
while true; do
  sleep 5
  if [ -f "$progress" ]; then
    total=$(wc -l < "$progress")
    if [ "$total" -gt "$seen" ]; then
      tail -n +"$((seen+1))" "$progress" | sed "s#^#[$name] #"
      seen=$total
    fi
  fi
  if [ -f "$last" ]; then echo "[$name] FINISHED: final message at run/codex/$name.last.md"; exit 0; fi
  size=$( [ -f "$log" ] && wc -c < "$log" || echo 0 )
  if [ "$size" = "$lastsize" ]; then stall=$((stall+1)); else stall=0; fi
  lastsize=$size
  if [ $((stall*5)) -ge $((stall_min*60)) ]; then echo "[$name] STALLED: no log output for $stall_min minutes"; exit 2; fi
  if grep -q "^codex exited" "$log" 2>/dev/null && [ ! -f "$last" ]; then echo "[$name] EXITED WITHOUT FINAL MESSAGE: $(grep '^codex exited' "$log" | tail -1)"; exit 3; fi
done
