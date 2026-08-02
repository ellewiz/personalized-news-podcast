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
