# Architecture Decision Records

Numbered, append-only. Every non-obvious decision gets an ADR **before** it's merely encoded in the source.
To supersede one, add a new ADR and set the old one's status to `Superseded by NNNN`.

| # | Decision | Status |
|---|---|---|
| [0001](0001-vulkan-not-rocm.md) | Vulkan/ZLUDA, never ROCm, for the RX 5700 XT | Accepted |
| [0002](0002-cpu-moe-30b-brain.md) | Qwen3-30B-A3B via `--cpu-moe` as primary brain | Superseded by 0011 (until RAM upgrade) |
| [0003](0003-langgraph-sqlite-spine.md) | LangGraph + SqliteSaver as the durable HITL spine | Accepted |
| [0004](0004-no-local-ai-video.md) | No local AI video; fake motion instead | Accepted |
| [0005](0005-private-draft-publish.md) | Publish as private draft; human clicks Publish | Accepted |
| [0006](0006-apache-only-model-invariant.md) | Every published frame Apache-2.0/MIT/OpenRAIL++/CC-0 | Accepted |
| [0007](0007-windows-native-runtime.md) | Windows-native runtime (Vulkan/ZLUDA) | Accepted |
| [0008](0008-flat-vector-visual-style.md) | Flat-vector / illustrative visual style | Accepted |
| [0009](0009-kokoro-narrator-voice.md) | Kokoro neutral preset narrator | Accepted |
| [0010](0010-editorial-taste-model.md) | Two-tier memory + learned editorial taste model | Accepted |
| [0011](0011-16gb-ram-8b-brain.md) | 16 GB RAM reality: Qwen3-8B primary brain until RAM upgrade | Accepted |
