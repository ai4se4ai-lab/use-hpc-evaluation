# Meta's repository is gated; unsloth/Meta-Llama-3.1-8B-Instruct is an ungated copy of the same weights
export HF_HUB_OFFLINE=1 VLLM_MODEL=unsloth/Meta-Llama-3.1-8B-Instruct VLLM_SERVED_NAME=llama-3.1-8b-instruct
export VLLM_ARGS="--dtype bfloat16 --max-model-len 16384 --gpu-memory-utilization 0.90"
