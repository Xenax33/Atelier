# Security Policy

## Supported versions

This project is pre-release (Phase 0). Only the `main` branch is supported; there are no released versions yet.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately to **saadkbr2@gmail.com** (or via GitHub's *Report a vulnerability* / private
security advisory on this repository). Include steps to reproduce and impact. You'll get an acknowledgement as
soon as possible, and credit if you'd like it once a fix is out.

## Handling secrets

This project talks to external accounts and runs local compute. Keep these safe:

- **Never commit** `.env`, OAuth client secrets, or tokens. They are git-ignored (see `.gitignore`).
- The **Discord bot token** and **YouTube OAuth** credentials should live in **separate scopes** (see
  `.env.example`). Prefer SOPS+age over a plaintext `.env` for anything shared.
- Give the Discord bot **minimal Gateway Intents** (no Message Content unless a feature requires it).
- Every irreversible action (upload, publish) is gated behind an explicit, logged human approval.

## Untrusted content

The research stage fetches web/wiki/API content. **All fetched content is treated as untrusted data, never as
instructions** (prompt-injection defense). The human approval gate sits between draft and publish by design -
do not add automation that bypasses it.
