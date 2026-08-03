# Pipeline R&D sweep — 2026-08-03

> Scope: everything up to the finished `master.mp4` (research → script → fact-check → TTS →
> images → captions → assembly). Publishing/post-generation excluded by owner request.
>
> Method: 19-agent pass — per-subsystem code map → web research → **adversarial verification**
> (every license claim checked against the primary LICENSE/model-card text per ADR-0006; every
> hardware claim checked against RDNA1/gfx1010 + ZLUDA/Vulkan + 8 GB VRAM + 16 GB RAM + Windows
> constraints) → completeness critique. Verdicts: KEEP (license + feasibility verified),
> CAVEAT (usable with the stated correction), KILL (disqualified — recorded so it is not
> re-litigated).

---

## 0. Priority shortlist (owner-suggested adoption order)

**Weekend-sized quick wins (small effort, immediately visible):**
1. Beat-synced cuts from `words.json` (§3.6) — fixes the visible narration/image desync; zero deps.
2. ASS/libass karaoke captions + OFL font (§3.2) — biggest perceived-quality jump per hour of work.
3. Music bed + sidechain ducking + −14 LUFS loudnorm (§3.3) and the voice post-chain (§5.3).
4. Pronunciation lexicon via misaki phonemes (§5.1) — kills mangled science names, the most audible failure mode.
5. Beat-level TTS with pauses + model-singleton fix (§5.2).
6. AYS scheduler at 10–12 steps (§1.2) — buys back PAG's 2× cost; then spend the savings on hires-fix (§1.3).
7. Checkpoint swap: RealVisXL V5.0 (cinematic) / DreamShaper XL (painterly), both OpenRAIL++ (§1.1).
8. llama.cpp bump + scalar Vulkan flash-attention + q8_0 KV A/B (§6.1); snapshot/shield the MIOpen+ZLUDA caches (§6.6).
9. Real-ESRGAN-ncnn-vulkan 2× upscale before Ken-Burns (§6.7).

**The two biggest structural levers (from the completeness critique):**
- **Multi-shot per beat / cut-ins (§7.1)** — visual change cadence is the top retention lever after
  the hook; cropped re-frames of an approved still are extra shots for free.
- **Forced alignment: captions from the KNOWN script, ASR for timing only (§7.3)** — eliminates
  misspelled science terms in burned captions as an error class.

**Medium-term:** VLM QC gate + ImageReward re-roll ranking (§2.4, §2.5), IP-Adapter house style +
recurring characters (§2.1, §2.2), DepthFlow parallax (§3.1), RIFE 60 fps (§3.5), evidence reranker
(§4.3), NLI + Wikidata fact-check hardening (§4.4, §4.5), primary-source adapters (§4.6), promptfoo
regression suite (§4.7), ComfyUI `POST /free` handoff + overnight seed sweeps (§6.4).

**Strategic:** Manim template layer (§3.4), Z-Image Turbo pilot (§1.6), Qwen3.5 brain swap (§4.1),
the RAM-vs-3090 decision (§6.8, §6.9) — and the **integration-budget matrix (§7.8) is a prerequisite
before stacking more than a couple of the image recs**.

---

## 1. Image quality (SDXL stack)

### 1.1 KEEP · small — License-verified checkpoint swap: RealVisXL V5.0 + DreamShaper XL
Replace `sd_xl_base_1.0.safetensors` per preset: **SG161222/RealVisXL_V5.0** for `cinematic`,
**Lykon/dreamshaper-xl-1-0** (non-turbo/non-lightning file!) for `painterly`. Both verified
`openrail++` on their HF cards — same license class as base, no revenue cap. Same UNet arch ⇒
identical VRAM/ZLUDA footprint; make `ckpt_name` a per-preset field in `STYLE_PRESETS`; keep base
1.0 for the retired `vector` preset (DD LoRA was tuned on it). Community-consensus first upgrade:
better lighting/texture/composition at identical step cost.
**Verified exclusions:** Juggernaut XL (paid RunDiffusion commercial license), ZavyChromaXL
(contact-for-commercial), Kolors (MAU registration), Playground v2.5 (own community license) — all
off-allowlist. ELLA was never released for SDXL (SD1.5 only) — dead end.
Sources: HF cards for both models.

### 1.2 KEEP · small — AYS (Align-Your-Steps) scheduler: 32 steps → 10–12
`AlignYourStepsScheduler` (ComfyUI **core** node, `model_type=SDXL`) + `SamplerCustomAdvanced` +
`KSamplerSelect(dpmpp_2m)`. Reported ~20–30-step quality at 10 steps; PAG composes unchanged (it's
a model patch). Render drops ~6–7 min → ~2.5–3.5 min with PAG on. Do NOT combine AYS with
Lightning-distilled models (artifacts). A/B at 10/12/14 steps vs 32/karras, same seeds.

### 1.3 KEEP · medium — Two-pass hires-fix + tiled VAE; RealESRGAN_x4plus only
Pass 1 as today → `LatentUpscale` 1.25–1.5× (to ~1152×2016) → second sampler at denoise 0.25–0.35,
10–15 steps → `VAEDecodeTiled` (tile 512) through the existing cudnn-off passthrough. Finally
implements the tiled decode SETUP-COMFYUI says to plan for. Crisper frames that survive Ken-Burns
zoom. Expect one 30–60 min MIOpen re-tune on first render at the new shape.
**License trap confirmed: 4x-UltraSharp is CC-BY-NC-SA — banned from frames. RealESRGAN_x4plus is
BSD-3 — clean.**

### 1.4 CAVEAT · medium — FaceDetailer (Impact Pack) on `has_people` beats
Fix anatomy instead of hiding it behind painterly: FaceDetailer (face_yolov8m + SAM-ViT-B,
guide 512/max 1024, denoise 0.4–0.5) appended for people beats; +1–3 min/beat. Detector licenses
are infra-only (masks; pixels still come from the openrail++ checkpoint).
**Caveat:** ComfyUI-Zluda issue #430 reports FaceDetailer hitting the same cuDNN "GET engine" error
class as VAE decode — its internal VAE round-trip does NOT pass through our CUDNNToggle node.
Likely needs process-wide `torch.backends.cudnn.enabled=False` or a patched Impact Pack. Budget
debugging; first people-beat render is the acceptance test.

### 1.5 KEEP · small — Free guidance knobs: Detail Daemon, SEG/NAG/FDG (already installed!), FreeU_V2
(a) `LyingSigmaSampler` (Jonseed/ComfyUI-Detail-Daemon, MIT), dishonesty −0.05…−0.10 (stay within
−0.1 per author), rides the AYS custom-sampler path. (b) **`git pull` the already-installed
pamparamm/sd-perturbed-attention pack** — it now ships SEG, NAG, TPG, FDG, SWG as drop-in
alternatives to PAG; A/B FDG and SEG vs PAG 3.0. NAG restores negative-prompt control on distilled
few-step models (pairs with the draft tier, where CFG=1 makes negatives inert). (c) FreeU_V2
(b1 1.1 / b2 1.15 / s1 0.85 / s2 0.35) — accept only if the same-seed A/B wins. All zero-VRAM,
infra-only.

### 1.6 KEEP · medium — Draft tier: SDXL-Lightning 8-step or Hyper-SDXL LoRA; DMD2 banned
Draft renders at ~45–90 s for prompt/style iteration before Gate 2; finals keep the full pipeline.
`quality_tier` param on `render_beat_stills`; Lightning LoRA chained after style LoRA, 8 steps,
CFG 1–2 (or Hyper-SDXL CFG-preserving variant at CFG 3–5), euler/sgm_uniform, PAG off.
**Licenses verified in the actual LICENSE.md files:** SDXL-Lightning = OpenRAIL++-M (clean);
Hyper-SD repo contains THREE licenses — its SDXL files are ByteDance OpenRAIL++-M (clean), its
Flux files are FLUX-dev NC and SD3 files are Stability-capped (download ONLY the SDXL LoRAs);
**DMD2 = CC-BY-NC — banned.**

### 1.7 KEEP · large — Z-Image Turbo pilot (Apache-2.0, 6B S3-DiT, 8-step, no CFG)
The 2025–2026 architecture upgrade candidate: decisively better prompt adherence than SDXL-class,
**renders legible text** (would relax the Visual Director's no-text rule), official ComfyUI support,
GGUF quants ~6 GB. 8 steps no-CFG ≈ 8 UNet evals vs ~64 today — plausibly 2–4 min/image even at
ZLUDA per-step penalty. Verifier found a **gfx1010-family success report** (ROCm/TheRock #3167,
RX 5600M running Z-Image Turbo GGUF in ComfyUI). Squeeze: the Qwen3-4B text encoder offloads to
CPU RAM — tight on 16 GB, comfortable post-RAM-upgrade. Acceptance test: 10-image timing run.
Note: no negative prompts at all on Turbo (distilled, CFG-free).
Backups (all license-checked): Lumina-Image-2.0 (Apache, 2.6B, 6 GB-VRAM-optimized);
FLUX.2-klein-4B is Apache but its card says ~13 GB VRAM min — weak backup on 8 GB;
Chroma1-HD Apache but 8.9B + real CFG — post-NVIDIA only; **Sana weights NC — banned.**

---

## 2. Control & consistency

### 2.1 KEEP · medium — House-style lock: IPAdapter Plus "style transfer" + precomputed embeds
The queued IP-Adapter idea, made concrete: cubiq/ComfyUI_IPAdapter_plus with
`ip-adapter-plus_sdxl_vit-h.safetensors` (**h94/IP-Adapter, Apache-2.0**), 2–4 curated past frames
per preset encoded ONCE via IPAdapterEncoder, embeds cached to disk keyed by preset;
`IPAdapterAdvanced` weight_type=`style transfer`, weight 0.6–0.9, end_at 0.85. With cached embeds
the ViT-H encoder never loads during renders ⇒ steady-state overhead <1 GB on the 8 GB card
(vs 2.5–4 GB uncached — the caching is what makes it fit). Needs no xformers, no insightface.
Gotcha: the vit-h adapter needs the ViT-H encoder from the repo's **SD1.5** `image_encoder` folder
(the sdxl_models one is bigG — wrong); the Unified Loader "PLUS (high strength)" preset sidesteps
this. ~+10–20% step time.

### 2.2 KEEP · medium — Recurring characters: one master ref + same-file IPAdapter reuse; FaceID/InstantID banned
For a historical figure recurring across beats: render ONE approved half-body master ref (fixed
seed + verbatim "anchor description"), then apply IPAdapterAdvanced with the SAME file (never
regenerate per beat) at weight 0.7–0.8, weight_type `linear`, plus the anchor phrase verbatim in
each beat prompt. Stack house-style embeds at ~0.4 when both needed. `recurring_character` field in
the spec schema; visdir inserts the anchor phrase.
**License finding (verified at deepinsight/insightface README): InsightFace pretrained models are
non-commercial ⇒ IP-Adapter-FaceID, InstantID, and every mainstream "character consistency"
tutorial that uses them would violate ADR-0006.** Plain ip-adapter-plus needs no insightface and is
sufficient for illustration-style identity. Per-episode LoRA training is not viable (no gfx1010
training path; per-video CivitAI violates the no-per-video-cloud rule). Seed anchoring alone
demonstrably fails — skip.

### 2.3 CAVEAT · large — 9:16 composition control: xinsir ControlNet-Union ProMax + procedural templates
One Apache-2.0 model (~2.5 GB) covers depth/canny/scribble/pose/tile. Control images for free:
~6 procedural PIL depth templates (visdir picks via a `composition` enum), depth from best past
frames via **Depth-Anything-V2-SMALL ONLY (Apache; Base/Large are CC-BY-NC — banned since the
depth map steers frame content)**, cv2 Canny from approved archival images. Strength 0.4–0.6,
end_percent 0.5–0.6.
**Caveats:** needs `SetUnionControlNetType` node (set type explicitly; auto-detect unreliable);
~7.5 GB of models on the 8 GB card relies on RAM offload — genuinely zero-headroom with 16 GB
system RAM. Use selectively on composition-critical beats now; comfortable post-RAM-upgrade.

### 2.4 KEEP · medium — Automated render QC: Qwen3-VL-2B-Instruct (Apache) on CPU + targeted re-rolls
Second llama-server instance CPU-only (`-ngl 0`) serving Qwen3-VL-2B GGUF Q4_K_M (~1.1 GB +
~0.8 GB mmproj — official Qwen GGUFs; llama.cpp mtmd supports it) while ZLUDA owns the GPU. One
schema-constrained call per render (downscale frame to ~896 px):
`{subject_present, matches_scene, anatomy_ok, unwanted_text_or_symbols, garbage_render, reason}`.
Fail ⇒ re-roll new seed (max 2); text detected ⇒ append offender to negative; subject missing twice
⇒ archival fallback. Closes the run-20260729-a8fea8 failure class (garbage shipping to Gate 3).
~15–45 s/image on the 5600, ~2.5–3 GB RAM; reuses the chat_json gateway. Florence-2-base (MIT) is
the fallback if vision prefill is too slow.

### 2.5 KEEP · small — ImageReward (Apache-2.0) scorer for re-roll ranking + cheap best-of-N
`pip install image-reward` (BLIP-based, CPU ~1–3 s/image): (a) score all re-roll attempts, keep the
best (not the last); (b) hero beats: 3 seeds at 12 steps no-PAG (~1–1.5 min each) → score → re-render
only the winner at full quality (best-of-3 for +4 min instead of +14). Calibrate the threshold on
~20 own painterly renders (distribution shifts on illustration styles) exactly like
ARCHIVAL_MIN_SCORE. Skip LAION aesthetic predictors (blind to prompt match).

### 2.6 KEEP · small — Visual Director vocabulary: enforced shot-type + lighting slots, 60-token hard cap
Extend the required prompt order to five slots: subject → action → setting → exactly ONE shot-type
term (close-up, medium shot, wide shot, low angle, overhead view, profile view) → exactly ONE
lighting term (golden hour, rim lighting, backlit, soft window light, candlelight, volumetric
light, chiaroscuro, overcast light) — whitelist-validated with corrective retry like `_BANNED`.
Keep short natural-language phrasing (SDXL dual-encoder preference); hard-fail >60 CLIP tokens
(use the CLIP tokenizer already shipped for archival scoring, not a word-count heuristic). Also
feeds §2.3: shot-type ↔ composition template agreement check.

---

## 3. Motion & assembly

### 3.1 CAVEAT · medium — DepthFlow 2.5D parallax per beat (the ADR-0004 promise, implemented)
Depth: **Depth-Anything-V2-Small-hf** (Apache; use the `-hf` repo — the raw-checkpoint repo does
NOT work with `transformers.pipeline`, verified) on CPU, ~1–5 s/still, runs alongside llama-server.
Render: `pip install depthflow` (AGPL = infra-only; output is our own stills warped by a GLSL
shader) — vendor-neutral OpenGL, no CUDA/ZLUDA; comfortably faster than realtime on the 5700 XT;
<10 min/short. Subtle settings (height ~0.15–0.25) — strong parallax smears painterly depth edges.
Route only full-bleed SDXL stills; archival letterboxed frames keep Ken-Burns (blurred-bg
letterbox ⇒ garbage depth).
**Caveat:** DepthFlow's Python API has churned across versions and current docs 404 — pin the
version and verify `DepthScene`/`.input()`/presets against the installed package before writing
`parallax.py`. Custom depth maps are supported per the official site.

### 3.2 KEEP · medium — ASS/libass karaoke captions burned by ffmpeg (replace MoviePy TextClips)
pysubs2 builds an .ass from the existing `words.json`: each chunk one dialogue line, per-word
`\kf<centiseconds>` sweep — the strongest "not a slideshow" caption cue on Shorts. Ship an OFL
font in-repo (Archivo Black / Montserrat ExtraBold — both verified SIL OFL 1.1) via `fontsdir`,
which also kills the `C:/Windows/Fonts/arialbd.ttf` portability bug. PlayResX/Y=1080×1920;
safe area: caption block above y≈1540, MarginL 80 / MarginR 140 (right rail). Burn with
`-vf "subtitles=short.ass:fontsdir=assets/fonts"` (gyan.dev/BtbN builds have libass — check
`ffmpeg -version`). Also removes per-TextClip PIL compositing ⇒ faster assembly.

### 3.3 KEEP · medium — Music bed + sidechain ducking + two-pass −14 LUFS loudnorm
Sources verified against Google's own support page: **YouTube Audio Library** (monetizable for YPP,
guaranteed no Content ID; CC-BY tracks need description credit — deliver node already writes
credits) and **Kevin MacLeod CC-BY 4.0** with the exact credit string.
**Avoid: Pixabay (contributors register tracks with Content ID — claims happen, documented on
Pixabay's own blog), FMA (many NC), Uppbeat free tier (revocable credit-system terms).**
One filtergraph: `sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400` (music ducked
under voice), then two-pass `loudnorm I=-14:TP=-1.5:LRA=11` with measured_* linear mode — YouTube's
target, so no re-gain. 3–5 vetted tracks in `assets/music/` tagged by mood.

### 3.4 KEEP · large — Manim CE diagram layer via GBNF-locked parameterized templates (never freeform codegen)
The evidence (Manimator etc.): freeform LLM→Manim is unreliable even for big models — a 4B must
never emit Python. Hand-write 4–6 parameterized Scene templates (NumberReveal, FormulaReveal,
Timeline, CompareBars, OrbitDiagram); visdir optionally emits `{template, params}` under a strict
JSON schema (GBNF ⇒ a 4B literally cannot produce invalid input); deterministic validator + one
retry. Render `-qh --format=mov -t` (transparent) on CPU (~10–60 s/scene), composite in the
caption-free upper-middle band; use the OFL caption font inside Manim for visual unity. Manim CE
is MIT (LICENSE fetched). Skip MathTex initially to avoid the MiKTeX install. This unlocks the
numbers/formulas queue item at 4B scale.

### 3.5 KEEP · small — rife-ncnn-vulkan 60 fps master (MIT, standalone Vulkan exe)
nihui's portable exe: ncnn+Vulkan, explicitly Intel/AMD/NVIDIA — the box's proven-good API, no
ZLUDA. Extract frames → `rife-ncnn-vulkan -m rife-v4.6 -n <2×frames>` → re-mux at 60 fps. Makes
parallax pans and karaoke sweeps feel produced (Shorts serves 60 fps). ~2–4 GB transient frames
(`-f jpg` halves). No published 5700 XT throughput — benchmark first (~3–10 min/short estimated);
feature flag; interpolate before burning captions if text edges ghost.

### 3.6 KEEP · small — Beat-synced cuts from words.json + license-free ffmpeg grade/grain
(1) Replace `_beat_durations`' word-count proportion (a known drift source) with actual per-word
timestamps: map each beat's narration to its `words.json` span, cut at last word end + ~120 ms.
Highest impact-per-line change in this report — cuts land on natural pauses. Crossfade 0.2–0.25 s
only where narration flows across the cut; hard cuts on pause boundaries; no wipe/slide (template
smell). (2) House grade procedurally (LUT packs' "free" terms are un-auditable — skip them):
`eq=contrast=1.04:saturation=1.08`, gentle S-curve, faint vignette, `noise=alls=6:allf=t+u` (also
masks SDXL sky banding). Check the proxy still fits Discord's 10 MB cap (grain raises bitrate).

### 3.7 KEEP · small — Reality check: no local i2v on RDNA1 in 2026; pre-clear the future licenses
Confirmed dead on this GPU — ADR-0004 stands; stills+parallax+Manim is the right motion strategy.
Append to ADR-0004's revisit clause: **Wan 2.2 = Apache-2.0, the future default pick**; CogVideoX =
modified-Apache, audit per checkpoint; HunyuanVideo = Tencent community license with EU/UK/KR
territory exclusions — fails a clean-license bar; LTX stays banned.

---

## 4. Research & script intelligence

### 4.1 CAVEAT · small — Brain: Qwen3.5-4B swap + Qwen3.5-9B A/B (Apache-2.0, llama.cpp-ready)
Qwen3.5 small series (Feb 2026, Apache-2.0 verified on cards): 4B as the new default (same flags,
chat_json is model-agnostic), 9B Q4_K_M (6.17 GB + ~1 GB KV with q8_0 — sole-occupant fits 8 GB;
IQ4_XS fallback) replacing schema-flaky Qwen3-8B in the A/B slot; expect ~40–55 tok/s at 9B.
**Corrections from verification:** (1) use temp 0.7 / top_p 0.8 for non-thinking mode (the
temp 1.0 / top_p 0.95 numbers are the THINKING-mode settings; thinking is off by default on
0.8B–9B, enable via `--chat-template-kwargs '{"enable_thinking":true}'`); (2) the 4B is a
multimodal hybrid-thinking model — a bigger behavioral delta than "drop-in" implies; verify the
chat template and gate on the promptfoo suite (§4.7) before promoting.
**Gemma 3 rejected:** custom Gemma Terms + Prohibited Use Policy, not on the ADR-0006 allowlist,
and script text lands in frames.

### 4.2 CAVEAT · small — Speculative decoding: skip two-model draft; canary MTP
Verified in llama.cpp primary sources: two-model draft on a single Vulkan device serializes graph
submissions (issue #23126: draft per-token time inflates ~100,000×) — a 0.6B draft would make the
brain SLOWER. The real path is Qwen3.5's **MTP self-speculation** (`--spec-type draft-mtp`, merged
May 2026, ~2.3× on CUDA) — but Vulkan support is incomplete (partial seq_rm; garbage-output
reports), though a later RDNA3.5 mainline report shows ~1.2× working. Action: 10-minute same-seed
canary script re-run on each llama.cpp bump (test 4B-MTP first; MTP heads cost ~0.3–0.5 GB);
subscribe to PRs #22400/#22673 (not #23184 — misidentified, it's an unrelated closed request).

### 4.3 KEEP · medium — Over-fetch then rerank evidence: bge-reranker-v2-m3 (Apache) on CPU
`gather_evidence()` currently keeps the FIRST 10 items in source order. Over-fetch 30–50 snippets,
score (query, snippet) pairs with BAAI/bge-reranker-v2-m3 (568M cross-encoder, CPU, ~2.3 GB RAM,
seconds per run; bge-reranker-base 278M fallback; ONNX int8 halves latency), keep the BEST 10
(max score across subject + keyword queries). Reuse at fact-check time: top-3 evidence items PER
CLAIM instead of showing the 4B all 10 — shorter, more relevant premises ⇒ better entailment from
a small model. New `src/tools/rerank.py`, lazy-load, fail-soft.

### 4.4 KEEP · medium — NLI second opinion: DeBERTa-v3-base-mnli-fever-anli (MIT) per beat
184M CPU model literally trained for claim-vs-evidence verdicts; run each claim against its top-3
reranked snippets; agreement matrix drives Gate 1 (LLM+NLI agree ⇒ green; disagree or
contradiction ⇒ red with the conflicting snippet quoted). While wiring: refactor claim extraction
PER BEAT (enables "regenerate just beat 3" later) and add the all-neutral tripwire — if every
claim is NLI-neutral vs every snippet, the evidence pack was junk (the silent-failure mode the
blanket try/excepts create). 45 pairs ≈ <10 s on the 5600. Gotcha: DeBERTa-v3 sentencepiece may
need the slow tokenizer path.

### 4.5 KEEP · medium — Wikidata SPARQL micro-verifier for dates/names/numbers (CC0, keyless)
LLM entailment is weakest exactly where Shorts scripts err: years, spellings, "first/discovered-by".
Regex-extract years/names/superlatives → `wbsearchentities` → SPARQL on query.wikidata.org:
P569/P570 (birth/death — age arithmetic + spelling via existing title_similarity), P575 + P61
(discovery/inventor), P166 (awards + point-in-time). Mismatch ⇒ advisory red flag at Gate 1 with
the Wikidata value shown ("script says 1897, Wikidata P575 says 1896"). Fail-soft, single-threaded,
existing UA convention. Property IDs verified.

### 4.6 KEEP · medium — Primary-source adapters: Chronicling America, IA/Open Library, NASA ADS
The evidence ceiling today is Wikipedia intros + 400-char snippets; these add the pre-1990 primary
record the arXiv/EuropePMC/S2 trio structurally lacks. (1) Chronicling America — **the legacy
chroniclingamerica.loc.gov API was retired Aug 2025; use the loc.gov JSON API** (verified; pre-2025
tutorials hit a dead endpoint). Query subject + date-range facet for how discoveries were reported
AT THE TIME; pre-1929 scans are PD ⇒ also feed the archival adapter (fifth source). (2) Internet
Archive full-text + Open Library `search.json` (keyless) + IA Scholar for historical journal runs.
(3) NASA ADS (free token, quota ≫ 1 video/day) — the only source with the 1840s–1970s astronomy
record. Route everything through the reranker (§4.3) so volume can't dilute the pack. loc.gov has
burst rate limits — keep single-threaded.

### 4.7 KEEP · medium — promptfoo regression suite (MIT, fully local)
Verdict on "worth it at 1 video/day": yes, as an offline regression harness, not a per-run judge.
Points at llama-server directly (openai:chat provider + apiBaseUrl). One config per agent surface
with ~20 frozen topic+evidence packs from past runs. Deterministic asserts do the work (is-json,
word budgets in code, contains-none for banned patterns/digits); llm-rubric by the 4B is a noisy
tie-breaker only. `promptfoo eval` gives the {prompt v1,v2} × {Qwen3-4B, Qwen3.5-4B, 9B} matrix —
the promotion gate §4.1 needs. ~20–40 min unattended per run. Skip Langfuse (tracing server +
ClickHouse; nothing at single-user scale).

### 4.8 CAVEAT · small — Typed hook + beat-sheet scaffold in the SCHEMA, budgets enforced in code
`hook_type` enum ({question, surprising_fact, bold_claim, whats_wrong_here, myth_bust}) — Editor
critique names which type won, taste profile learns hook-type performance instead of one-off
quotes. Per-field word budgets validated deterministically (extend the existing word-count retry).
Payoff-answers-hook check via the §4.4 NLI model (hook as question, payoff as premise; flag if
neutral). Few-shot: inject top-2 past scripts by pick-signal as exemplars (current prompt has
zero). **Correction from verification: 14 words ≠ 2 s — at the pipeline's own pacing (~3.7 w/s),
14 words ≈ 3.8 s. A sub-2-second hook is ~7 words; pick the budget deliberately.** Retention
percentages in the cited sources are creator-blog-grade — directional only.

---

## 5. TTS & audio

### 5.1 KEEP · small — Pronunciation lexicon: misaki G2P + `[word](/phonemes/)` overrides
misaki (Apache) is the G2P Kokoro was trained with; kokoro-onnx's README recommends it for v1.0.
Two-stage: `g2p(text)` → `kokoro.create(phonemes, is_phonemes=True)` (real API, verified in
source). Maintain `config/pronunciation_lexicon.json` (Lavoisier, Huygens, chirality…) applied via
misaki's inline override syntax. **Critical: Kokoro is NOT standard IPA — unknown phonemes are
silently dropped; validate lexicon entries against misaki's EN_PHONES.md + unit test.** Log OOV
words hitting the espeak fallback; confirm pronunciations at Gate 2. Directly targets the most
audible failure mode of a science-history channel. Keep per-call phonemes under Kokoro's ~510-token
limit (pairs with §5.2).

### 5.2 KEEP · small — Beat-level synthesis, programmable pauses, pacing knob + singleton fix
Per-beat Kokoro calls, trim edge silence, concatenate with explicit gaps (~250 ms sentence,
400–600 ms beat; numpy zeros — Kokoro is deterministic, joins inaudible). Prosody is
punctuation-driven; keep chunks <~500 chars. Expose `speed` (default 1.05–1.1 for Shorts pacing;
per-video knob, checked at Gate 2). Side benefit: exact per-beat timestamps for free (hardens
visual sync; enables §7.3). Fix verified code issues: Kokoro() reloads the ONNX model from disk on
EVERY call — hoist to a module singleton; make `_MODEL/_VOICES` paths absolute.

### 5.3 KEEP · small — Voice post-chain in ffmpeg (binary already present via imageio_ffmpeg)
`highpass=f=80` → `deesser` → `acompressor` (3:1 gentle) → two-pass `loudnorm I=-14:TP=-1.5`
linear mode; `-ar 48000`; `apad=pad_dur=0.3` tail. Consistent loudness across episodes, no YouTube
re-gain, tamed sibilance on phone speakers. Keep the pre-chain WAV for Gate 2 A/B.

### 5.4 KILL — Orpheus-3B (the ADR-0009 named upgrade) — license disqualified
The engineering route existed (llama-server Vulkan + SNAC ONNX sidecar, ~1.0–1.3× realtime on this
box), **but the "Apache-2.0" label is false: Orpheus is a Llama-3.2-3B finetune; the HF discussion
documents the mislabeling and Canopy's "this is a mistake on our end" admission, unresolved for
over a year. Effective license = Llama 3.2 Community License — not on the ADR-0006 allowlist —
and TTS output is audible frame content on a monetized channel.** Amend ADR-0009: Orpheus is
rejected-on-license, not deferred-on-hardware. Revisit only if retrained on a clean base.

### 5.5 KEEP · medium — Signature narrator (own voice only): NeuTTS Air primary, Chatterbox-Nano runner-up
Two CPU-viable, license-clean cloning routes that post-date ADR-0009: **NeuTTS Air** (748M
Qwen-0.5B-backbone — clean base, no Orpheus-style conflict; Apache-2.0 verified; official GGUF
Q4/Q8 ~0.5–0.9 GB; realtime-on-CPU target; clones from 3–15 s of reference; repo:
`neuphonic/neutts-air`). **Chatterbox-Nano** (110M, MIT; ~1.5–2× realtime est. on the 5600; output
carries Resemble's inaudible Perth watermark — fine to publish, worth knowing). Own recorded voice
only (ADR-0006/R8 stands — no third-party or "predefined voice" packs). Backend registry in
`tts.py` (kokoro | neutts | chatterbox); A/B at Gate 2.

### 5.6 CAVEAT · small — Non-picks recorded (so they're not re-litigated)
Dia-1.6B (dialogue model, unstable single-narrator identity — skip); Zonos, CosyVoice2 (GPU-first
PyTorch, no Vulkan path — post-NVIDIA); MeloTTS, Kitten-TTS (below Kokoro for narration); Piper
(engine MIT but per-VOICE dataset licenses vary — audit each voice). **Maya1** (Apache-2.0
verified, from-scratch 3B + SNAC, 20+ emotion tags) is the cleanest post-NVIDIA expressive option —
record it in ADR-0009 as such, with Orpheus marked rejected-on-license (correction to the survey's
own framing).

---

## 6. Runtime & throughput

### 6.1 KEEP · small — llama.cpp bump: scalar Vulkan flash-attention + q8_0 KV cache A/B
"FA off on AMD Vulkan" is stale: PR #13324 added a scalar FA shader for non-coopmat GPUs (exactly
gfx1010), later optimized; scalar FA supports quantized KV. `llama-bench -fa 0,1`, then
`-fa on -ctk q8_0 -ctv q8_0`; adopt only if ≥ current 93/670 (older reports show FA can degrade
AMD Vulkan — the bench gate is load-bearing; V-cache quant REQUIRES FA on). Main win: ~50% KV VRAM
⇒ headroom for long research contexts. Historical per-build gains on this exact card are real —
bump the b10092 pin after the schema-JSON smoke passes.

### 6.2 CAVEAT · small — DeepCache (the one UNet cache that applies; TeaCache/FBCache are DiT-only)
Caches deep U-Net features, recomputes shallow ones: reported ~1.7–2.6× on SDXL (3× was with
OneDiff compilation — unavailable under ZLUDA). Pure forward-hooks, no Triton — should run under
ZLUDA. **Caveats:** the -Fix node is an unlicensed 8-commit 2024 repo whose defaults target LCM —
retune for 32 steps (interval 3, start ~6, end ~26) is mandatory; unproven on 2026 ComfyUI and
under ZLUDA; PAG interaction untested anywhere (PAG perturbs attention every step; cached steps
skip it). Time-boxed experiment gated on same-seed A/B — and **pointless if AYS (§1.2) is adopted**
(see §7.8).

### 6.3 KEEP · medium — stable-diffusion.cpp Vulkan as the tested disaster-recovery backend
Survey conclusion: nothing in 2026 beats the 3–4 min warm ZLUDA render on gfx1010 (Amuse/DirectML
closed + RDNA4-targeted; torch-DirectML 2–4× slower; SHARK targets RDNA3+). But the
"ComfyUI-Zluda house of cards" needs a fallback that isn't `--directml`: sd.cpp (MIT) is
ggml+Vulkan (the box's proven path), supports SDXL + LoRA (via `<lora:name:strength>` prompt
syntax) + dpm++2m/karras + built-in VAE tiling. No PAG ⇒ degraded emergency mode. Download once,
benchmark once, record a reference image; replace the `--directml` line in the fallback ladder.
Watch issue #563 (Vulkan quality artifacts on some AMD iGPUs) — first run IS the acceptance test.

### 6.4 KEEP · medium — Warm-process VRAM handoff (`POST /free`) + overnight seed sweeps
Stop killing the ComfyUI process: `POST /free {"unload_models":true,"free_memory":true}` releases
SDXL weights while keeping the ZLUDA-initialized process + warm MIOpen state alive. New handoff:
render → /free → **health-gate VRAM (mandatory — the caching allocator may not return every MB)** →
start llama-server. Reload-from-disk is the only per-switch cost. Plus: after Gate 2, queue 3–4
seeds per beat overnight via `/prompt`; CLIP (or ImageReward, §2.5) ranks them in the morning —
best-of-N at zero daytime cost (~90–120 min overnight GPU per episode).

### 6.5 CAVEAT · large — Episode pipelining (same-episode CPU overlap now; cross-episode post-RAM)
Same-episode overlaps work today (whisper, MoviePy pre-assembly of archival beats during renders).
Cross-episode (research N+1 on a `-ngl 0` CPU llama at ~10–15 tok/s during N's render) is
realistically post-RAM-upgrade (16 GB is near-zero headroom with --lowvram offload). Either way:
formalize the implicit GPU ordering into an explicit process-level mutex, and note SqliteSaver
concurrent writers need WAL mode / per-thread connections or you'll hit "database is locked".

### 6.6 KEEP · small — Snapshot + shield the ZLUDA/MIOpen kernel caches (55-min recompile insurance)
Zip `%LOCALAPPDATA%\ZLUDA\ComputeCache` + `~/.miopen` (+ `~/.triton`) after a verified warm render,
next to the venv snapshot. Defender exclusions for F:\ComfyUI-Zluda + both cache dirs (also kills
the DLL false-positive/file-lock failures). Relocate via documented `MIOPEN_USER_DB_PATH` +
`MIOPEN_CUSTOM_CACHE_DIR` (verified real) out of cleaner-targeted profile dirs. Re-snapshot when
the first render after an auto-git-pull runs slow.

### 6.7 KEEP · small — Keep 768×1344 (verified: it IS the closest official SDXL bucket to 9:16) + ncnn upscale
832×1472 is NOT a native bucket (+18% pixels, more 8 GB risk) — stay put. The real gap: Ken-Burns
zooms a 768×1344 source below 1080p. Fix: `realesrgan-ncnn-vulkan` (MIT exe; models BSD-3;
AMD-supported Vulkan) at `-s 2` after each batch (~5–10 s/image, runs when SDXL is idle) ⇒
1536×2688 source keeps 1.3–1.4× zooms above native. Test x4plus vs the anime model on painterly;
archival scans benefit too. Feeds the §7.4 >1080p delivery lever.

### 6.8 CAVEAT · small — RAM upgrade math (Aug 2026): ~$300–400 and rising — decide NOW
DDR4 EOL + DRAM shortage inverted the math: the natural 2×32 GB DDR4-3200 kit is ~$397 (was
$60–90/32 GB in Oct 2025), shortage projected into 2027 — waiting is losing. Unlocks: 30B-A3B
`--cpu-moe` at a realistic ~12–15 tok/s on DDR4 (the ~30 figure is DDR5-class — benchmark before
committing, per ADR-0011), brain resident through renders (~2 GB VRAM), CPU VLMs, comfortable
episode pipelining, Z-Image encoder headroom. **Correction: "B450M = exactly 2 DIMM slots" is
board-model-dependent (many B450M boards have 4) — verify the actual board first; a 4-slot board
changes the buy.** At ~$400 vs a ~$800–1050 used 3090, commit only if the 30B brain is the
priority — but if so, buy soon.

### 6.9 CAVEAT · large — Used-NVIDIA math: skip the mid-tiers; only the 3090 changes what's possible
Analysis holds, prices were stale-low: used 3090 24 GB tracks **~$800–1050** (not $700), used 3060
12 GB ~$317–365, 4060 Ti 16 GB ~$424 new. 3060 = 5–8× render speed but no new capabilities;
4060 Ti = weakest LLM bus of the three, poor $/capability; **3090 = the actual unlock** (30B-class
in VRAM at interactive speed — obsoletes the RAM plan, SDXL in 10–20 s, IP-Adapter/ControlNet
stacks trivial, Wan-class i2v plausibly in reach ⇒ reopens ADR-0004). Risks: ex-mining stock,
350 W transients (PSU ≥750 W check), no warranty. Redo the math with current tracker prices before
acting; the model-gateway seam makes any of these a backend swap.

---

## 7. Gaps the sweep itself missed (completeness critique)

### 7.1 Shot design — question one-still-per-beat (likely worth more than all image-quality recs combined)
6–8 beats × one still = 7–10 s per visual; well-performing Shorts cut every 2–4 s. Two cheap moves:
2–3 shots per beat (wide + close-up derivable from the §2.6 shot-type vocabulary — AYS/draft-tier
savings fund exactly this), and zero-cost **cut-ins**: cropped/re-framed variants of the SAME
approved still or archival scan (a 40% face crop and a detail crop = two extra shots free).

### 7.2 Image repair — masked inpaint tier instead of whole-image re-rolls
Gate 3 is binary approve/re-render today; §2.4's QC only re-rolls whole images (composition
lottery, 3–7 min each). The already-recommended ControlNet-Union ProMax includes inpaint modes:
VLM (or human at Gate 3) identifies the failing region → mask → re-diffuse only that region at
denoise 0.5–0.7, same checkpoint/prompt. Zero new heavy downloads; converts gates into targeted
feedback.

### 7.3 Captions — forced alignment of the KNOWN script; ASR for timing only
The pipeline WROTE the script; burned captions should never contain ASR misspellings of exactly
the terms the channel lives on (Lavoisier, Roentgen…). whisperX `align()` accepts our own
transcript; §5.2's per-beat synthesis gives beat boundaries free. Bonus tripwire: diff ASR text vs
script text ⇒ automatic Kokoro-mispronunciation detector feeding the §5.1 OOV log.

### 7.4 Delivery encode — unexamined and cheap to fix
Add bt709 color tags (untagged H.264 washes out in players and after transcode), pick CRF/preset
deliberately — and **master above 1080p** (2160×3840 via the §6.7 upscaler) so YouTube assigns the
VP9/AV1 ladder instead of the low-bitrate AVC ladder that smears grain, caption edges and painterly
texture. The §3.6 grain rec makes this worse without it. One of the highest quality-per-effort
platform levers; costs only idle encode time.

### 7.5 Sound design — the missing SFX/ambience layer
Voice+music-only is the most audible template-AI marker. Small curated CC0 kit (freesound
license=cc0 filter; check per-pack terms on Sonniss) tagged by function (whoosh/riser on cuts,
room-tone ambience per scene mood, accent hit under the hook word, sting under the payoff), placed
programmatically from data the pipeline already has (cut times from words.json, mood from
visdir/Editor), mixed in the §3.3 filtergraph. CC0-only — SFX is audible frame content.

### 7.6 Format strategy — 60 s is not a law of nature; design the loop seam
Shorts accepts up to 3 min (since Oct 2024, monetized the same); 90–120 s changes what a science-
history script can do and doubles watch-time per view. Also unaddressed: Shorts LOOP — design the
last frame/words to flow into the first (no dead-air outro, payoff re-arms the hook), and make the
first frame the boldest image (it doubles as the feed impression). Cheap: a second word-budget
profile in the §4.8 schema.

### 7.7 Archival retrieval — the scorer is a 2021 model
CLIP ViT-B-32 @ 0.28 is the weakest link in the archival-first path — and §4.6 is about to flood it
with newspaper scans. Upgrade: **SigLIP 2** (Apache-2.0, google/siglip2-*, CPU-fast, much better
text-image retrieval; recalibrate the threshold — scores aren't CLIP-comparable), then point the
§2.4 Qwen3-VL instance at the top candidate (right person? right apparatus? engraving vs photo?)
before it wins over SDXL. Better retrieval = less GPU and fewer factual-visual errors.

### 7.8 Integration budget — 2–3 frozen graphs with measured VRAM peaks (prerequisite!)
Individually each image rec fits 8 GB; the implied combined graph (checkpoint + style LoRA +
IPAdapter + ControlNet + FaceDetailer + hires pass) does NOT co-fit, and several recs conflict:
DeepCache is pointless-to-harmful under AYS 10–12 steps; Detail Daemon's sigma lying interacts
with AYS's optimized schedule; PAG/SEG/FDG + FreeU + Lightning each change the guidance math the
others were tuned against. Define canonical per-preset graphs (e.g. draft / final-painterly /
final-cinematic), measure VRAM peaks, keep a same-seed regression baseline per graph. Adopt image
recs one at a time against that baseline.

---

## 8. Banned/trap ledger from this sweep (verified against primary license texts)

| Item | Status | Why |
|---|---|---|
| Juggernaut XL, ZavyChromaXL, Kolors, Playground v2.5 | off-allowlist | paid/contact/MAU/community licenses |
| 4x-UltraSharp upscaler | BANNED | CC-BY-NC-SA |
| DMD2 distill | BANNED | CC-BY-NC |
| Hyper-SD Flux/SD3 files | BANNED | FLUX-dev NC / Stability cap (SDXL files are clean) |
| Sana | BANNED | NC weights |
| IP-Adapter-FaceID / InstantID / InsightFace models | BANNED | InsightFace pretrained models non-commercial |
| Depth-Anything-V2 Base/Large/Giant | BANNED | CC-BY-NC (Small is Apache — use only Small) |
| **Orpheus-3B** | **BANNED** | Llama-3.2 finetune; "Apache" label admitted mistaken; effective Llama license off-allowlist |
| Gemma 3 (as brain) | rejected | Gemma Terms + Prohibited Use Policy off-allowlist |
| Pixabay / FMA / Uppbeat music | avoid | Content-ID claims / NC tracks / revocable terms |
| Third-party LUT packs | avoid | un-auditable "free" terms; grade procedurally |
| ELLA for SDXL | dead end | never released for SDXL |
| Two-model speculative decoding on one Vulkan GPU | dead end | llama.cpp #23126 (draft serializes, ~10⁵× slower) |
| Local i2v on RDNA1 | confirmed dead | ADR-0004 stands; Wan 2.2 (Apache) is the future pick |

---

*Full agent transcripts and per-recommendation source URLs: workflow run `wf_09643b7f-b4a`
(19 agents, ~700k tokens). Each recommendation above retains its source list in the raw output;
this file is the curated synthesis.*

---

## 9. Verification addendum (2026-08-03, second pass against the live install + primary sources)

Local checks against this box (all pass, so the shortlist is cheaper than the doc assumes):

- AYS scheduler node already exists in our ComfyUI core (`comfy_extras/nodes_align_your_steps.py`) - section 1.2 needs zero installs.
- The installed sd-perturbed-attention pack ALREADY ships `fdg_nodes.py`, `nag_nodes.py`, `tpg_nodes.py`, `smc_nodes.py`, `pladis_nodes.py` - section 1.5(b) needs no git pull.
- Our bundled ffmpeg (imageio_ffmpeg -> gyan.dev 7.1 essentials) is compiled with libass and has `subtitles`, `ass`, `sidechaincompress`, `loudnorm`, `deesser` filters - sections 3.2, 3.3, 5.3 need zero new binaries.
- `tts.py` really does construct `Kokoro(...)` inside `render_narration` on every call, with relative model paths - the 5.2 singleton fix is real and trivial.
- `researcher.gather_evidence` really returns `evidence[:max_items]` in raw source order - the 4.3 premise is accurate.
- `words.json` already stores per-word `{word, start, end}` - sections 3.2 and 3.6 need no new data.
- `POST /free` exists in our ComfyUI `server.py` - section 6.4 is viable as written.
- kokoro-onnx 0.5.0 installed; its `create()` supports `is_phonemes=True` and enforces `MAX_PHONEME_LENGTH = 510` (batch-splits plain text itself; the cap becomes OUR job once we pass phonemes) - sections 5.1/5.2 as written.

License claims re-verified against primary sources (HF cards / LICENSE files): RealVisXL V5.0
openrail++, DreamShaper XL openrail++, SDXL-Lightning RAIL++-M (same text as SDXL base),
h94/IP-Adapter Apache-2.0, rife-ncnn-vulkan MIT with explicit AMD support, 4x-UltraSharp
CC-BY-NC-SA (ban stands), misaki Apache-2.0 with the `[word](/phonemes/)` override syntax,
NeuTTS Air Apache-2.0 with official Q4/Q8 GGUFs (527/803 MB), Chatterbox MIT with Perth
watermark and a 110M Nano variant. One soft spot: RealESRGAN_x4plus weights have no standalone
license file - they ride the repo's BSD-3 by convention; nothing marks them NC.

Corrections to the doc (three claims adjusted):

1. **Section 5.4 (Orpheus):** the license conflict is real (Llama-3.2-3B finetune tagged
   Apache-2.0; HF discussion #4 on canopylabs/orpheus-3b-0.1-pretrained), but Canopy never
   replied - there is NO admission on record. The ban stands on Meta's license terms alone.
   ADR-0009's amendment should cite the unresolved conflict, not an acknowledgment.
2. **Section 4.1 (Qwen3.5):** the model card says thinking mode is ON by default (the doc
   claims off). This is exactly the failure mode that disqualified Qwen3-8B (thinking tokens
   breaking schema JSON). The swap MUST ship with explicit thinking-off handling
   (chat-template kwargs / enable_thinking false) and pass the schema smoke test before
   promotion. temp 0.7 / top_p 0.8 for non-thinking confirmed.
3. **Section 1.2 (AYS):** "20-30-step quality at 10 steps" overstates the typical claim;
   ~20-step quality at 10 steps is what NVIDIA and community A/Bs support. Still worth it
   (32 -> 10-12 steps), just calibrate expectations for the same-seed A/B.

Scope notes from verification: the Z-Image gfx1010 report (TheRock #3167, RX 5600M) is via
ROCm/PyTorch on Linux, not our ZLUDA/Windows path, and is a single anecdote - the 1.7 pilot
stays speculative until the 10-image timing run. The speculative-decoding hazard (#23126) is
one documented case (780M iGPU) closed as stale - directionally right, not universal.
