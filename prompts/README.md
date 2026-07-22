# prompts/

Versioned prompt templates. Convention: `<agent>_v<N>.md` (e.g. `scriptwriter_v3.md`). Never edit a shipped
version in place - bump N and note the change in `CHANGELOG.md` so prompt regressions are bisectable. At v2,
prompt versions + eval scores are tracked in Langfuse.

Special file: **`editorial-profile.md`** - the learned taste model (ADR-0010), not a template; it's read on
every script run and updated from user signals.
