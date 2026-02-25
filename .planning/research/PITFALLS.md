# Pitfalls Research

**Domain:** AI ecosystem monitoring agent — signal collection, LLM scoring, HITL Slack review, structured enrichment pipeline
**Researched:** 2026-02-24
**Confidence:** HIGH (critical pitfalls verified across multiple sources and production systems)

---

## Critical Pitfalls

### Pitfall 1: Signal Fatigue Kills Adoption Before It Even Starts

**What goes wrong:**
The reviewer (Lauren) gets too many Slack cards per day. She starts skimming, missing relevant signals, or simply ignores the bot. The system technically functions but is behaviorally abandoned. This is the #1 cause of death for monitoring systems of this type — not technical failure, but human disengagement from noise overload.

**Why it happens:**
Early source selection is too broad. Developers add sources to maximize coverage, not to maximize relevance. Every new RSS feed increases daily card volume. With 15-20 sources and no aggressive pre-filtering, it is easy to generate 30-50+ daily signals that require human attention. Even 15 cards per day from a background workstream is too many.

**How to avoid:**
- Set a hard daily cap on Slack cards sent to review: aim for 3-7 per day maximum at launch
- Apply a two-stage filter before Slack: first filter by LLM relevance score (discard low-confidence signals silently), second filter by novelty (discard if similar signal seen within N days)
- Track Lauren's approval rate weekly. If it drops below 20%, the scoring threshold is too low — raise it
- Default to silence over notification: only surface signals that cross a high-confidence threshold
- Implement a daily digest mode option (one batch message at a set time) rather than individual pings per signal

**Warning signs:**
- Approval rate drops below 30% within the first two weeks
- Lauren stops responding to cards for days at a time
- More than 10 cards per day arriving in the Slack channel
- "Reject" becomes the reflexive default without reading the card

**Phase to address:**
Phase 1 (foundation) — scoring thresholds and daily volume limits must be built in from the start, not added as a fix later. If Lauren abandons the queue early, the system loses its reason to exist.

---

### Pitfall 2: Deduplication Naivety Creates Phantom Conviction

**What goes wrong:**
The same product launch or capability update gets posted to Hacker News, Product Hunt, and three RSS feeds within 48 hours. Without proper clustering, Watchman surfaces five separate "new AI tool" cards for the same event. Lauren approves one and rejects the others as duplicates, wasting review time and creating confusion about what's already been processed.

**Why it happens:**
URL-based deduplication is the default because it's easy. But the same event appears at different URLs across different sources. Developers underestimate cross-source overlap — in a well-curated 15-source registry, the same major launch can appear 4-8 times across sources within 24 hours.

**How to avoid:**
- Use content-based deduplication, not URL-based: normalize titles (strip punctuation, lowercase, remove "Introducing" prefixes), compute similarity against signals seen in the past 7 days
- Use semantic fingerprinting: hash the (tool name + launch date) tuple as a dedup key, not the URL
- Cluster signals into "events" before scoring — score the cluster, not individual signals. Surface the highest-credibility source from the cluster
- Preserve provenance: when collapsing duplicates, store all source URLs in the signal card so Lauren can see coverage breadth
- Tune the dedup window: 7 days catches most cross-source echo, 30 days prevents the same tool appearing again after a minor update

**Warning signs:**
- Lauren is clicking "reject" and writing "already saw this" in the first week
- Multiple cards in the same Slack thread describing the same product
- The same tool name appearing more than once in the queue within 7 days

**Phase to address:**
Phase 1 (signal normalization and deduplication) — dedup logic must exist before the first Slack card is sent. Retrofitting dedup after launch is painful and requires re-processing the entire seen-signals store.

---

### Pitfall 3: Scraper Breakage Is Silent and Permanent

**What goes wrong:**
A scraper that worked perfectly for two months silently starts returning empty results or garbage HTML. No one notices for weeks because there is no alert. Lauren's queue goes quiet, which feels fine, but the system has stopped collecting signals entirely. The silence is indistinguishable from "nothing new happened."

**Why it happens:**
Websites change their HTML structure, add bot detection, or gate content behind login/JS rendering. Production scraper breakage rates are reported at 10-15% per week in 2025 for scrapers without active maintenance. For a cron-based background system with no active monitoring of its own health, breakage goes undetected.

**How to avoid:**
- Each collector must report its result count per run to a health log. If a collector returns 0 results for 2+ consecutive runs, generate an automatic Slack alert to Paul (not Lauren's review queue — separate channel or DM)
- Track baseline expected yield per source (e.g., "Product Hunt typically yields 3-8 signals per day"). Alert on deviation greater than 50%
- For scraped sources (not RSS/API), use lightweight selectors and test them against a saved snapshot during CI
- Prefer official APIs and RSS feeds over HTML scraping wherever possible — RSS feeds are stable; HTML scraping is fragile
- Log the raw response (status code, content length) for each collector run, not just the parsed output

**Warning signs:**
- A source that previously yielded signals goes quiet for 3+ consecutive days
- Collector run time drops to near-zero (returning instantly with empty results)
- HTTP 200 responses but empty parsed signal lists

**Phase to address:**
Phase 1 (collector infrastructure) — health monitoring for collectors must be built alongside the collectors themselves. Do not defer this to "later."

---

### Pitfall 4: LLM Scoring Threshold Drift Degrades Quality Over Time

**What goes wrong:**
The relevance scoring rubric (taxonomy fit, novelty, traction, credibility) is calibrated at launch against the initial source set. Over time, as sources expand and the AI tool landscape evolves, the rubric scores more signals above threshold. The daily card volume creeps upward silently. Lauren's queue gets noisier month-over-month with no visible cause.

**Why it happens:**
LLM-based classifiers are not calibrated against the classification task — they are calibrated against token prediction. Without explicit threshold management and periodic rubric review, the system drifts. Adding sources compounds this: each new source brings its own signal density, and the rubric was not tuned for it.

**How to avoid:**
- Store every scored signal with its raw rubric score breakdown (not just pass/fail). This creates a calibration dataset
- Treat the scoring threshold as a configurable parameter, not a hardcoded constant. Expose it in the source registry config
- Run a monthly calibration review: pull the last 30 days of Lauren's approve/reject decisions and compare against scores. If the average score of rejected signals is within 10 points of approved signals, raise the threshold
- Use Haiku for initial scoring (cheap), but implement a secondary pass with a stronger model for borderline signals (scores within 10% of threshold)
- Never let the rubric stay unchanged for more than 60 days without review

**Warning signs:**
- Weekly approved card count trending upward without a corresponding increase in Lauren's approval rate
- Lauren's rejections increasingly contain cards that scored above threshold
- The system is scoring promotional content and marketing fluff as high-relevance

**Phase to address:**
Phase 2 (scoring and classification) — build score logging and the calibration mechanism in the same phase as the scorer. Threshold tuning after-the-fact requires data that wasn't captured.

---

### Pitfall 5: Enrichment Runs on Rejected Signals, Wasting Tokens

**What goes wrong:**
The enrichment pipeline (capabilities, pricing, API surface, integration details) is triggered too early in the workflow — either immediately on signal detection or before Lauren's first approval. Expensive LLM enrichment runs on signals that Lauren will reject, burning Haiku/Sonnet tokens on content that gets discarded.

**Why it happens:**
Developers optimize for completeness — they want the full card ready for approval. The enrichment-on-approval pattern requires more workflow complexity (callback handling after Slack interaction), so the simpler path is to enrich everything upfront.

**How to avoid:**
- Enforce the two-gate architecture from the start: surface card (title, source, date, 2-sentence summary, raw link) → Lauren approves → enrichment runs → Lauren approves schema entry
- The surface card must be cheap to generate. Summary should come from the source content itself (RSS description, headline), not from LLM generation
- Only trigger enrichment after first approval. Use the Slack action callback (approve button) to enqueue the enrichment job
- Estimate enrichment cost per signal and report it in the weekly health log. If cost per enriched signal is rising, the enrichment prompt needs tightening

**Warning signs:**
- LLM API costs are high relative to the number of approved signals (implies enriching rejects)
- Enrichment runs completing within seconds of signal detection (means it is not waiting for approval)
- Monthly API bill growing faster than the approved signal count

**Phase to address:**
Phase 2 (workflow orchestration) — the enrichment trigger point must be designed as part of the Slack interaction flow, not bolted on afterward.

---

### Pitfall 6: Schema Compatibility With IcebreakerAI Is Assumed, Not Verified

**What goes wrong:**
Watchman generates structured tool entries throughout development using an assumed schema. When integration with IcebreakerAI is attempted, the schema is incompatible in 3-4 fields. All previously generated entries need to be re-enriched and re-generated, or a translation layer needs to be built. This is discovered late when it is expensive to fix.

**Why it happens:**
IcebreakerAI's tool registry schema is not formally documented or validated against during Watchman development. Developers work from a remembered or assumed schema. The downstream consumer is a "future integration" so schema validation is deferred.

**How to avoid:**
- Obtain the exact IcebreakerAI tool registry JSON schema before writing the first enrichment prompt
- Store the schema as a versioned artifact in Watchman's config directory and validate generated entries against it using Pydantic models
- Build schema validation into the pipeline: every generated schema entry must pass Pydantic validation before it is stored or surfaced in the second approval gate
- If IcebreakerAI's schema evolves, treat schema version bumps as a breaking change for Watchman

**Warning signs:**
- Generated entries have fields that don't map to IcebreakerAI's known fields
- Enrichment prompts reference field names that are guesses rather than confirmed schema fields
- "We'll worry about the schema when we integrate" thinking in design discussions

**Phase to address:**
Phase 1 (project setup) — get the IcebreakerAI schema before writing any enrichment code. This is a zero-cost task that prevents a high-cost rework.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| URL-based deduplication only | Simple to implement | Same event appears multiple times across sources; Lauren's queue fills with duplicates | Never — content-based dedup should be built from the start |
| Hardcoded scoring thresholds | Simpler config | Threshold drift degrades quality silently over months | Never — make threshold configurable from day one |
| Enrich all signals upfront | Complete cards ready for review | LLM token waste on rejected signals; cost scales with noise, not with value | Never for production; acceptable for first local test only |
| Single SQLite file for signal state | Zero infrastructure | Becomes a bottleneck if run on multiple machines; not portable | Acceptable for v1 local deployment; add migration path before multi-machine deployment |
| Skip collector health monitoring | Faster to ship | Silent breakage goes undetected for weeks | Never — health logging is one hour of work; omitting it costs weeks of missed signals |
| Infer IcebreakerAI schema from memory | No coordination needed | Schema mismatch discovered at integration time; costly rework | Never — read the actual schema file before writing enrichment prompts |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Slack Bolt (Python) | Not calling `ack()` within 3 seconds of button interaction — Slack shows an error spinner to the user | Always `await ack()` immediately in the action handler, then do the work asynchronously |
| Slack interactive messages | Updating a message after button click requires `client.chat_update()` with the original `channel` and `ts` from the action payload — many implementations lose the `ts` | Store `(channel, ts)` for every sent card in the signal state store; retrieve on callback |
| Slack interactive messages | Buttons remain clickable after Lauren has already approved/rejected — Lauren can double-approve | After action handling, update the message to replace buttons with a status indicator ("Approved by Lauren") |
| Product Hunt API | Ignoring complexity-based rate limits (6250 complexity points per 15 min) — simple queries look cheap but nested data fields compound fast | Check complexity cost of each GraphQL query; cache results rather than re-fetching |
| RSS feeds | Assuming `pubDate` is always present and correctly formatted — many feeds have malformed or absent dates | Default to `datetime.utcnow()` when `pubDate` is absent; never crash on missing fields |
| Web scrapers (Tier 3) | Scraping at a fixed fast cadence and getting IP-blocked | Respect `robots.txt`, add jitter to request timing, rotate user agents, prefer official APIs where available |
| LLM scoring (Haiku) | Sending raw HTML or full article text to the classifier — expensive and noisy | Pre-extract: title + first 500 characters of body + source domain. That is sufficient for relevance scoring |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous collector runs in a single process | Collectors with slow scrapers block each other; a 30-second scrape delays the entire cron run | Run collectors as async tasks or in a thread pool; set per-collector timeouts | At 5+ sources with any Tier 3 (scrape) sources |
| Loading full signal history into memory for dedup | Memory usage grows without bound; dedup check slows as history grows | Use a seen-signals index (SQLite with title hash + date) for O(1) lookup | Around 10,000 signals in history (~6-12 months of operation) |
| Blocking Slack message delivery on enrichment | If enrichment is slow (LLM latency), Slack message delivery is delayed; ack() times out | Decouple enrichment from Slack delivery entirely — enqueue enrichment, deliver confirmation message immediately | First time enrichment takes >3 seconds |
| No batching on LLM scoring calls | Cost grows linearly with signal volume; cold-start latency per call | Batch signals into groups of 5-10 for a single LLM call with structured output | At >20 signals per cron run |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Slack bot token and LLM API keys in the codebase or a committed config file | Credential exposure if repo is ever shared or made public | Use environment variables; load from `.env` file that is gitignored; validate presence at startup |
| Logging full scraped content to disk without size limits | Log files grow unbounded; scraped content may include PII or sensitive source content | Log metadata only (URL, status code, signal count); never log raw scraped HTML to persistent storage |
| No validation of Slack action payloads | A crafted request to the Slack action endpoint could trigger enrichment jobs without Lauren's actual approval | Verify Slack request signatures on all incoming action callbacks (Bolt does this automatically in Socket Mode — do not bypass it) |
| Trusting LLM-generated schema entries without validation | Hallucinated field values or incorrect data types enter the IcebreakerAI pipeline | Run Pydantic validation on every generated schema entry before storage; treat validation failure as a pipeline error, not a warning |

---

## UX Pitfalls

Common user experience mistakes in the Slack review interface.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Sending individual Slack messages for each signal as it is collected throughout the day | Lauren gets interrupted multiple times per day by the bot; background workstream becomes intrusive | Batch signals into a single daily digest posted at a consistent time (e.g., 9 AM Lauren's timezone) |
| Signal cards with too much text | Lauren skims and misses key details; cards feel like homework | Card format: tool name (bold), one-sentence what-it-does, source + date, relevance score, three Slack buttons (Approve / Reject / Snooze-7-days). Nothing else |
| No "snooze" option | Lauren has to reject interesting signals that are too early to act on; they may resurface as new signals later | Implement a snooze action that suppresses re-surfacing of the same tool for N days |
| Buttons that still work after a decision is made | Lauren approves, then accidentally clicks reject later; state corruption in the pipeline | Update the message immediately after any button click to remove the action buttons and show the decision taken |
| No feedback on what happened after approval | Lauren approves a signal but never sees the enriched card or knows if a schema entry was generated | Send Lauren a follow-up card in the same thread when enrichment completes: "Enrichment done. Schema entry drafted. [Review]" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Signal collection:** Collectors run and return results — but is health monitoring reporting on yield per source? Verify that a zero-result run generates a Slack alert to Paul.
- [ ] **Deduplication:** Dedup runs on same-source duplicates — but does it cluster cross-source duplicates? Verify by manually submitting the same tool URL twice from two different sources and checking only one card appears.
- [ ] **Slack cards:** Cards appear in Slack — but do buttons still work after a decision is made? Verify that clicking Approve disables both Approve and Reject buttons immediately.
- [ ] **Enrichment pipeline:** Enrichment runs and produces output — but is it gated on Lauren's first approval? Verify no enrichment jobs are queued until the Slack approve button is clicked.
- [ ] **Schema generation:** Schema entries are generated — but do they pass Pydantic validation against the actual IcebreakerAI schema? Verify by running the validator on a generated entry before claiming this phase is done.
- [ ] **Second approval gate:** Second gate exists in Slack — but is the enriched card different enough from the first card to justify the second review? Verify Lauren sees the full enriched card (capabilities, pricing, API surface) before the second gate, not a repeat of the first card.
- [ ] **Scoring:** LLM scorer is running — but is the raw score being stored for calibration? Verify the score breakdown is persisted in the signal store, not just the pass/fail result.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Signal fatigue — Lauren has disengaged | MEDIUM | Raise scoring threshold by 20 points; implement daily digest mode if not already in place; apologize to Lauren and explain the fix; resume with tighter volume caps |
| Silent scraper breakage discovered weeks later | MEDIUM | Identify the broken collector, fix the selector or switch to an API alternative, replay the missed collection window manually if important sources, add health monitoring before re-enabling |
| Schema incompatibility with IcebreakerAI | HIGH | Obtain correct schema, update Pydantic models, re-run enrichment on all approved signals in the queue, regenerate schema entries. Avoid by getting the schema before Phase 2 |
| Duplicate cards already approved by Lauren | LOW | Run a retroactive dedup pass on the approved signals store; deduplicate before entries reach IcebreakerAI; add content-based dedup before next collection run |
| LLM cost overrun from enriching rejected signals | LOW | Audit the enrichment trigger point in the workflow; confirm it is gated on Slack approval callback, not on signal detection; no data recovery needed, just a code fix |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Signal fatigue | Phase 1 — build scoring thresholds and daily volume cap before first Slack card is sent | Lauren's queue stays under 7 cards/day in the first week |
| Deduplication naivety | Phase 1 — content-based dedup built alongside normalization | Manual test: same tool submitted from two sources yields one card |
| Silent scraper breakage | Phase 1 — health logging built with collectors | Zero-result run triggers a Slack alert within one cron cycle |
| LLM score threshold drift | Phase 2 — score logging and calibration mechanism built with scorer | Score breakdown is stored in signal store and queryable |
| Enrichment waste on rejects | Phase 2 — enrichment trigger wired to Slack approval callback | No enrichment jobs appear in logs before a Slack approval event |
| IcebreakerAI schema incompatibility | Phase 1 (setup) — schema obtained and Pydantic models written before Phase 2 | Generated entry passes Pydantic validation on first generation attempt |
| Slack button state bugs | Phase 2 — message update on action callback | Approve click removes both buttons and shows status in message |

---

## Sources

- [Alert Fatigue in Monitoring: How to Cut Noise, Reduce Burnout (Better Stack)](https://betterstack.com/community/guides/monitoring/best-practices-alert-fatigue/)
- [Alert Fatigue Reduction with AI Agents (IBM)](https://www.ibm.com/think/insights/alert-fatigue-reduction-with-ai-agents)
- [Deduplication & Canonicalization: Preventing Double Counts and Phantom Signals (Potent Pages)](https://potentpages.com/web-crawler-development/web-crawlers-and-hedge-funds/deduplication-canonicalization-preventing-double-counts-and-phantom-signals)
- [Deduplication Skill — Feedly AI](https://blog.feedly.com/deduplication-skill-feedlyai/)
- [Top Web Scraping Challenges in 2025 (ScrapingBee)](https://www.scrapingbee.com/blog/web-scraping-challenges/)
- [10 web scraping challenges and solutions in 2025 (Apify / DEV)](https://dev.to/apify/10-web-scraping-challenges-solutions-in-2025-5bhd)
- [Orchestrating Data Workflows: Scheduling and Monitoring Web Scraping Jobs (Grepsr)](https://www.grepsr.com/blog/orchestrating-data-workflows-scheduling-and-monitoring-web-scraping-jobs/)
- [Building AI Content Moderation with Human-in-the-Loop Using Motia, Slack, and OpenAI](https://blog.motia.dev/building-ai-content-moderation-with-human-in-the-loop-using-motia-slack-and-openai/)
- [Human In The Loop Slack Cannot Update Approve/Disapprove Button After Interaction (n8n Community)](https://community.n8n.io/t/human-in-the-loop-slack-cannot-update-approve-disapprove-button-after-interaction/119544)
- [Product Hunt API: Rate Limits](https://api.producthunt.com/v2/docs/rate_limits/headers)
- [Using LLMs to filter out false positives from static code analysis (Datadog)](https://www.datadoghq.com/blog/using-llms-to-filter-out-false-positives/)
- [Confidence in Classification using LLMs (Crime de Coder)](https://crimede-coder.com/blogposts/2026/ConfClassification)
- [10 Data Pipelines Mistakes That Block AI Success in 2025 (BizData360)](https://www.bizdata360.com/data-pipelines/)

---

*Pitfalls research for: AI ecosystem monitoring agent (Watchman)*
*Researched: 2026-02-24*
