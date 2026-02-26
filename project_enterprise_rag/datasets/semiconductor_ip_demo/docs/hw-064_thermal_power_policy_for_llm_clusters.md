# Thermal and Power Policy for LLM Clusters

## Metadata
- Document ID: HW-064
- Domain: Cross-Stack Systems
- Tags: thermal, power, llm, gpu, datacenter
- Dataset: semiconductor_ip_demo (hardware refresh)

## Technical Brief
Large LLM clusters require coordinated thermal and power policy at device, node, and rack levels. Control loops ingest real-time telemetry to tune fan curves, pump rates, and clock governors while preserving SLA latency. Smart policy accounts for bursty decoding phases and memory-bound periods to avoid oscillation. Reliability controls include hotspot forecasting and staged load shedding before hard throttling events. Operational dashboards track joules-per-token and sustained utilization to guide capacity planning.
