# use-hpc hook: private vLLM OpenAI-compatible server for this job (sourced by stage.sh).
# Needs VLLM_MODEL (Hugging Face id, cached in HF_HOME on scratch by the setup stage); optional VLLM_ARGS, VLLM_SERVED_NAME.
export HF_HOME="${HF_HOME:-$SCRATCH/use-hpc-eval/hf_cache}"
_port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
export VLLM_URL="http://127.0.0.1:$_port" OPENAI_BASE_URL="http://127.0.0.1:$_port/v1" OPENAI_API_KEY="${OPENAI_API_KEY:-local}"
python -m vllm.entrypoints.openai.api_server --model "$VLLM_MODEL" --served-model-name "${VLLM_SERVED_NAME:-$VLLM_MODEL}" \
    --host 127.0.0.1 --port "$_port" ${VLLM_ARGS:-} > "$LOG_ROOT/env/vllm_${JOB_TAG}_r${SLURM_RESTART_COUNT:-0}.log" 2>&1 &
SERVICE_PIDS+=($!)
curl -sf --retry 300 --retry-delay 2 --retry-connrefused --retry-all-errors -m 5 "$VLLM_URL/v1/models" >/dev/null \
    || { log_error "vLLM did not become ready (see env/vllm_*.log)"; return 1; }
log_info "vLLM ready at $OPENAI_BASE_URL serving ${VLLM_SERVED_NAME:-$VLLM_MODEL}"
