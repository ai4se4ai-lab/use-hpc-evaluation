export HF_HUB_OFFLINE=1 VLLM_MODEL=Qwen/Qwen3.5-9B VLLM_SERVED_NAME=Qwen/Qwen3.5-9B
export VLLM_ARGS="--dtype bfloat16 --max-model-len 32768 --gpu-memory-utilization 0.88"
