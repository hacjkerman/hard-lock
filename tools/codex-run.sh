#!/usr/bin/env bash
# Launch a non-interactive Codex run for this repo on the Mac with the standard sandbox and
# progress protocol, so Claude can watch it with tools/codex-watch.sh instead of being asked.
# Copied from modpacks/tools/codex-run.sh and adapted to macOS (no cygpath, no Java).
#
#   tools/codex-run.sh <name> <model> <effort> <prompt-file> [extra codex args...]
#
#   name         short slug; files land in run/codex/<name>.{log,progress,last.md}
#   model        gpt-6-astra (reviews, code) or gpt-5.6-sol (research)
#   effort       low | medium | high
#   prompt-file  the task text; the progress protocol below is prepended automatically
#
# Environment facts baked in (learned 2026-09-21 on the first iOS run):
#   - The Codex sandbox cannot write .git: Codex writes files, Claude commits per task.
#   - xcodebuild cannot resolve packages or reach CoreSimulator under the sandbox. Package
#     tests run with `swift test --disable-sandbox` and /tmp caches; the app is compile-checked
#     with ios/scripts/check-sdk.sh. No `xcodebuild test`, ever: the Mac is shared and low on memory.
set -euo pipefail
name="${1:?name}"; model="${2:?model}"; effort="${3:?effort}"; promptfile="${4:?prompt-file}"; shift 4
repo="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$repo/run/codex"
log="$repo/run/codex/$name.log"
progress="$repo/run/codex/$name.progress"
last="$repo/run/codex/$name.last.md"
: > "$progress"
rm -f "$last"

CODEX="${CODEX_CLI_PATH:-/Applications/ChatGPT.app/Contents/Resources/codex}"
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
export PATH="/Applications/Xcode.app/Contents/Developer/usr/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

{
  cat <<EOF
PROGRESS PROTOCOL (mandatory). Claude is watching the file below and relays each line to the user,
so nobody has to ask how it is going. Append exactly one line to it at every task boundary:
    TASK <n> START | <what you are about to do, one line>
    TASK <n> DONE  | <what landed, one line, include test counts or verified outputs>
    TASK <n> BLOCKED | <what stopped you and what you did instead>
    FINISHED | <one-line summary>      (the very last thing you write before your final message)
File: $progress
Write it with:  printf '%s\n' 'TASK 1 START | ...' >> '$progress'
Never batch these; write each line when it happens.

SANDBOX FACTS: you cannot write .git (do not branch, stage, commit, stash or clone; leave your
changes in the working copy and Claude commits per task). Package tests:
    cd ios/HardLockKit && DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \\
      CLANG_MODULE_CACHE_PATH=/tmp/hardlock-module-cache swift test --disable-sandbox \\
      --cache-path /tmp/hardlock-swift-cache --jobs 2
App compile check: ios/scripts/check-sdk.sh. Do not run xcodebuild test or boot a simulator.
Writes outside this repo and /tmp are refused. No network is needed.

EOF
  cat "$promptfile"
} > "$repo/run/codex/$name.prompt.md"

echo "launching codex $model/$effort as '$name'; log $log"
"$CODEX" exec -C "$repo" -m "$model" -s workspace-write \
  -c "model_reasoning_effort=$effort" -c sandbox_workspace_write.network_access=false \
  --color never -o "$last" "$@" - < "$repo/run/codex/$name.prompt.md" > "$log" 2>&1
echo "codex exited $? for '$name'"
