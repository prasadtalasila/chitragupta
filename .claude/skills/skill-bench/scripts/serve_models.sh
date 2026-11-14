#!/usr/bin/env bash
# Starts one llama-server per GPU for the skill-bench skill, or stops them.
#
#   bash serve_models.sh N [FIRST]   GPUs FIRST..FIRST+N-1 (FIRST defaults to 0)
#   bash serve_models.sh --stop      stop every server this script started
#
# GPU i serves on port 18080+i with CUDA_VISIBLE_DEVICES=i, one slot and
# the 131,072-token context docs/examples/opencode/opencode-provider.json
# declares, under the name the bench asks for (qwen3.6-35b-a3b). One slot
# a server is deliberate: the bench gives each local job a server of its
# own, so two jobs never share a slot's context.
#
# The servers run detached (setsid), so they outlive the shell that
# started them: a long baseline survives its launcher. Their pids go to
# $BENCH_TOOLS/run/servers.pid for --stop, and their logs beside it. When
# every port answers /v1/models, the last line printed is the bench's
# --base-url arguments.
set -uo pipefail

BENCH_TOOLS=${BENCH_TOOLS:-$HOME/bench-tools}
LLAMA_SERVER=${LLAMA_SERVER:-$BENCH_TOOLS/llama.cpp-b11321/build/bin/llama-server}
MODEL_FILE=${MODEL_FILE:-$BENCH_TOOLS/models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf}
RUN=$BENCH_TOOLS/run
PIDS=$RUN/servers.pid
WAIT=${WAIT:-600}

if [[ ${1:-} == --stop ]]; then
  [[ -f $PIDS ]] || { echo "no servers recorded in $PIDS"; exit 0; }
  while read -r pid; do kill "$pid" 2>/dev/null; done <"$PIDS"
  rm -f "$PIDS"
  echo "stopped"
  exit 0
fi

count=${1:-}
first=${2:-0}
if ! [[ $count =~ ^[1-9][0-9]*$ && $first =~ ^[0-9]+$ ]]; then
  echo "usage: serve_models.sh N [FIRST] | --stop" >&2
  exit 2
fi
[[ -x $LLAMA_SERVER ]] || { echo "no llama-server at $LLAMA_SERVER: run install_tools.sh" >&2; exit 1; }
[[ -f $MODEL_FILE ]] || { echo "no model at $MODEL_FILE: run install_tools.sh" >&2; exit 1; }
mkdir -p "$RUN"

args=()
for ((gpu = first; gpu < first + count; gpu++)); do
  port=$((18080 + gpu))
  CUDA_VISIBLE_DEVICES=$gpu setsid nohup "$LLAMA_SERVER" -m "$MODEL_FILE" \
    --alias qwen3.6-35b-a3b --host 127.0.0.1 --port "$port" \
    -c 131072 -np 1 -ngl 99 --jinja >"$RUN/llama-server-$gpu.log" 2>&1 </dev/null &
  echo $! >>"$PIDS"
  args+=("--base-url http://127.0.0.1:$port/v1")
done

for ((gpu = first; gpu < first + count; gpu++)); do
  port=$((18080 + gpu))
  waited=0
  until curl -sf "http://127.0.0.1:$port/v1/models" >/dev/null; do
    if ((waited >= WAIT)); then
      echo "port $port did not answer in ${WAIT}s: see $RUN/llama-server-$gpu.log" >&2
      exit 1
    fi
    sleep 2
    waited=$((waited + 2))
  done
done
echo "${args[*]}"
