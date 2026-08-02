"""bot/ - the Discord control plane (discord.py 2.6).

Responsibility: the human-in-the-loop surface. Renders Components V2 cards for the three gates
(script pick/edit, audio approval, final review), bridges button/modal interactions into LangGraph
`Command(resume=...)`, and streams progress into the control channel.

Rules: minimal Gateway Intents (no Message Content unless required); gate buttons are DynamicItems
(regex custom_ids) so they survive restarts; heavy work never blocks the event loop (graph calls run
via asyncio.to_thread); final review attaches the sub-10MB faststart proxy (master path in the message).
"""
