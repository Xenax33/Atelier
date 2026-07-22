# 0005 — Publish as a private draft; the human clicks "Publish"
Status: Accepted
Date: 2026-07-22

## Context
The user will publish manually (for now) and wants the pipeline to hand off a finished video. Separately,
YouTube's 2026 "inauthentic / mass-produced content" policy penalizes zero-touch automated channels, and
full auto-publish would trigger the YouTube API Compliance Audit.

## Decision
The Publisher uploads the finished short as **`privacyStatus=private`** (a draft) with the
**altered/synthetic-content disclosure flag hard-coded on**, plus drafted title/description/tags. The user
flips it Public in YouTube Studio. Auto-publish is deferred to v2+ behind a clean seam.

## Consequences
- Easy: sidesteps the Compliance Audit; the publish click is exactly the human oversight the policy rewards.
- Hard: not fully hands-off (by design, and a compliance feature not a bug).
- Revisit when: volume + trust justify auto-publish, or a second platform (IG) is automated in v2.

## Alternatives rejected
- **Full auto-publish now** — Compliance Audit + inauthentic-content risk for marginal convenience.
