# Heterogeneous GPU+TPU Cluster Design for Enterprise AI

## Metadata
- Document ID: HW-061
- Domain: Cross-Stack Systems
- Tags: gpu, tpu, cluster, scheduler, semantic-routing
- Dataset: semiconductor_ip_demo (hardware refresh)

## Technical Brief
Heterogeneous AI clusters combine GPU and TPU nodes to optimize training and inference economics across model families. The platform scheduler performs smart query planning over topology, memory pressure, and compiler constraints before dispatching workloads. GPU nodes handle operator-rich graphs and ecosystem-heavy workflows, while TPU nodes prioritize dense matrix throughput for large attention blocks. Cross-cluster interconnect relies on high-bandwidth fabrics with congestion-aware routing and admission control. Reliability policy includes preemption-safe checkpointing, staged rollout, and automated rollback when p95 latency or error budgets regress.
