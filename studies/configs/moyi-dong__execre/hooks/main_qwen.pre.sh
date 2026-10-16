export HF_HUB_OFFLINE=1 VLLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct VLLM_SERVED_NAME=qwen2.5-coder-32b-instruct
export VLLM_ARGS="--dtype bfloat16 --max-model-len 16384 --gpu-memory-utilization 0.92"
