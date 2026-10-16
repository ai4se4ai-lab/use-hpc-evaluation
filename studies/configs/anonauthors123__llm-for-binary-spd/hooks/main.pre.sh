export HF_HUB_OFFLINE=1 VLLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct VLLM_SERVED_NAME=Qwen2.5-Coder-7B-Instruct
export VLLM_ARGS="--dtype bfloat16 --max-model-len 32768 --gpu-memory-utilization 0.88"
