# use-hpc hook: private Ollama server for this job (sourced by stage.sh). Reuses the study-wide install and model
# store on scratch. Exports LLM_URL / OLLAMA_HOST / OPENAI_BASE_URL (Ollama's OpenAI-compatible API) for the steps.
OLLAMA_PREFIX="${OLLAMA_PREFIX:-$SCRATCH/autom2m_hpc/opt/ollama-0.30.6}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$SCRATCH/.ollama/models}"
_port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
export OLLAMA_HOST="127.0.0.1:$_port" OLLAMA_KEEP_ALIVE=24h OLLAMA_FLASH_ATTENTION=1 OLLAMA_MAX_QUEUE=2048
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-8}" OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-2}"
export LLM_URL="http://$OLLAMA_HOST" OPENAI_BASE_URL="http://$OLLAMA_HOST/v1" OPENAI_API_KEY="${OPENAI_API_KEY:-ollama}"
"$OLLAMA_PREFIX/bin/ollama" serve > "$LOG_ROOT/env/ollama_${JOB_TAG}_r${SLURM_RESTART_COUNT:-0}.log" 2>&1 &
SERVICE_PIDS+=($!)
curl -sf --retry 90 --retry-delay 2 --retry-connrefused --retry-all-errors -m 5 "$LLM_URL/api/version" >/dev/null \
    || { log_error "Ollama did not become ready"; return 1; }
# pull the models the stage needs (OLLAMA_PULL="a b"); cached models return immediately
for _m in ${OLLAMA_PULL:-}; do
    "$OLLAMA_PREFIX/bin/ollama" pull "$_m" > /dev/null 2>&1 || log_warn "pull $_m failed (offline node?)"
done
log_info "Ollama ready at $LLM_URL (models: $("$OLLAMA_PREFIX/bin/ollama" list 2>/dev/null | awk 'NR>1{print $1}' | tr '\n' ' '))"
