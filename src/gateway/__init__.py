"""gateway/ - the OpenAI-compatible model gateway (SEAM #1).

Responsibility: the single choke point between agents and inference. Agents call this; it routes to the
local llama.cpp Vulkan server(s). 8 GB = one model instance, so requests are queued here.

This is also the AMD->NVIDIA upgrade seam: swap the backend URL/runtime, agents are untouched.
Implementation options: LiteLLM proxy, or a ~150-line FastAPI facade. See docs/adr/0001, 0002.
"""
