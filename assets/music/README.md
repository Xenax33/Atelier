# assets/music/ - the local music bed library

Drop 3-5 instrumental tracks here (mp3/wav/m4a/ogg/flac). The assembler picks one per
run (deterministic per run id), trims it to the video, ducks it under the narration via
sidechain compression, and normalizes the final mix to -14 LUFS. No files here = videos
ship voice-only, exactly as before.

## Where to get tracks (license-vetted 2026-08-03, docs/research/2026-08-03-pipeline-rnd.md section 3.3)

- **YouTube Audio Library** (Creator Studio > Audio Library): monetization-safe for YPP,
  guaranteed no Content ID claims per Google's own docs. Tracks marked with the CC icon
  require the credit text in the video description - paste it into metadata.md's credits.
- **Kevin MacLeod / incompetech.com** (CC-BY 4.0): allowed, use the exact credit string
  from the site in the description.

## Do NOT use

- Pixabay (contributors register tracks with Content ID - claims happen)
- Free Music Archive (many tracks are NC)
- Uppbeat free tier (revocable credit-system terms)

## Naming

Optional mood prefix helps future selection logic: `calm-*, wonder-*, tense-*`.
Keep filenames ASCII, no spaces.
