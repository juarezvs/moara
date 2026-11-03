nvidia-smi --query-gpu=pstate,clocks.sm,clocks.mem,pcie.link.gen.current,pcie.link.width.current,power.limit,utilization.gpu --format=csv
docker logs moara-gpu-validation 2>&1 | grep -E 'offload|CUDA|buffer size|flash_attn|memory.required|memory.weights|n_ctx|n_batch|n_ubatch' | tail -55
