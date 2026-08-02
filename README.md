# Personalized News Podcast — Build Spec

## Goal

Generate a personalized audio news podcast on a recurring basis, publish it
as an RSS feed, and make it subscribable from Pocket Casts (and any other
RSS-based podcast app).

## Content structure

Two tiers per episode:

### Tier 1 — Brief awareness (target: under ~1 minute of runtime)

- Pull from one or two digest-style general news sources, not raw
  per-article feeds
- Summarize the top few headlines in a handful of sentences total
- Explicit goal: "aware, not drowning" — never stack multiple articles
  about the same single story

### Tier 2 — Deep dive (the bulk of the episode)

- Categories: soccer / World Cup, tech & AI news, NFL, NWSL, WNBA
- Pull from category-specific feeds (URLs supplied separately, see Open
  Items)
- Depth per category scales with how much actually happened in that
  window — a quiet week for a given sport should get a short mention, not
  padded filler, so episode length should flex naturally rather than
  target a fixed runtime

## Pipeline

1. **Fetch** — pull new items from each configured RSS feed since the last
   run
2. **Filter / dedupe** — collapse near-duplicate coverage of the same
   story, restrict to a recency window (e.g. last 24–48h)
3. **Script generation** — turn filtered items into a spoken script
   - Tier 1 stays short and factual
   - Tier 2 gets more narrative treatment, but each segment is still a
     single narrator speaking (no two-host conversational format)
   - Each Tier 2 category gets its own distinct voice (e.g. one voice for
     soccer/World Cup, another for tech/AI, another for NFL, etc.); Tier 1
     uses its own consistent voice throughout
4. **Audio** — convert the script to speech via TTS (ElevenLabs), mapping
   each segment to its assigned per-category voice
5. **Publish** — output an MP3 and update an RSS feed XML with the new
   episode (title, description, pubDate, audio enclosure URL + length,
   duration)
6. **Host** — the feed XML and MP3 files need a stable public URL for
   podcast apps to poll; hosted via GitHub Pages (free static hosting,
   nothing dynamic needed server-side)

## Delivery

Once the feed is live at a public URL, subscribe in Pocket Casts by
pasting that feed URL directly (not via the built-in show directory).

## Scheduling

**Cadence: Monday through Friday** (weekdays only, no weekend episodes).

Not automatic by default — the pipeline needs something to trigger it on
that cadence. Options:

- A cron job / scheduled task (e.g. weekday mornings)
- Wired into existing automation infra (e.g. a scheduled Home Assistant
  action or shell script) for a fully hands-off cadence
- Manual run as a fallback whenever needed

## Open items (to fill in before/during build)

- [x] RSS feed URLs for general news digest, soccer/World Cup, tech/AI,
      NFL, NWSL, WNBA — all tracked in [`feeds.yaml`](./feeds.yaml).
      NWSL and WNBA currently share two general women's-sports sources
      (Just Women's Sports, The Gist); dedicated feeds can be added later
      if needed.
- [x] Episode cadence — Monday through Friday
- [x] Preferred TTS voice/provider — ElevenLabs, with a distinct voice per
      Tier 2 category
- [x] Single narrator vs. two-host conversational format — single
      narrator (no two-host conversational format)
- [x] Preferred hosting target — GitHub Pages

## Implementation

The pipeline is a small Python package:

```
feeds.yaml            RSS sources per tier/category
config/voices.yaml     ElevenLabs voice_id per tier/category (fill in real IDs)
podcast/
  config.py            env vars + config file loading
  models.py             FeedItem / ScriptSegment dataclasses
  fetch.py               pull + recency-filter each feed
  dedupe.py               collapse near-duplicate stories (title similarity)
  script.py                 build spoken scripts via the Anthropic API
  tts.py                     ElevenLabs synthesis + mp3 concatenation (ffmpeg)
  rss_feed.py                 rebuild docs/feed.xml from state/state.json
  pipeline.py                  orchestrates the full run
run.py                  entrypoint: `python run.py`
state/state.json        seen item guids + published episode metadata
docs/                   GitHub Pages root: feed.xml + episodes/*.mp3
scripts/publish.sh       run pipeline, then git add/commit/push docs + state
```

### Setup

1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. Install [ffmpeg](https://ffmpeg.org/) (used to concatenate segment audio into
   one episode file).
3. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`,
   `ELEVENLABS_API_KEY`, and `PODCAST_BASE_URL`.
4. Fill in real ElevenLabs `voice_id`s in `config/voices.yaml` (one per
   tier/category — pick from your ElevenLabs voice library).
5. In GitHub repo settings, enable **Pages** → deploy from branch `main`,
   folder `/docs`. `PODCAST_BASE_URL` should match the resulting Pages URL.

### Running

```
source .venv/bin/activate && set -a && source .env && set +a
python run.py
```

This fetches new items, dedupes, generates scripts, synthesizes audio,
writes `docs/episodes/<date>.mp3`, and rebuilds `docs/feed.xml`. It does
**not** commit/push — use `scripts/publish.sh` for the full run-and-publish
cycle (intended to be wired into cron/systemd-timer for the Monday–Friday
cadence).

### Notes / caveats

- `dedupe.py` uses a title-similarity heuristic (no LLM call) to collapse
  near-duplicate stories; it's intentionally simple and may need tuning once
  real episodes are generated.
- `state/state.json` is the source of truth for both "already seen" item
  guids and the full episode list used to rebuild `feed.xml` — it's
  committed to the repo (via `scripts/publish.sh`) so state persists across
  runs without a separate database.
- Feed fetching, script generation, and TTS all need real outbound network
  access and valid API keys; none of that was exercised end-to-end during
  scaffolding (dedupe logic and RSS generation were verified with sample
  data instead).
