"""bot/ — the Discord control plane (discord.py 2.6).

Responsibility: the human-in-the-loop surface. Renders Components V2 cards for the three gates
(script pick/edit, audio approval, final review), bridges button/modal interactions into LangGraph
`Command(resume=...)`, and streams progress into the control channel.

Rules: minimal Gateway Intents (no Message Content unless required); register **persistent** Views so
gates survive a restart; heavy work never blocks the event loop (offload via run_in_executor/subprocess);
final review is delivered as a Caddy/cloudflared LINK (masters exceed Discord's 10 MB cap).
"""
