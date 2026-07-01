# Provenance Guard

A backend system for classifying submitted creative text as AI-generated or human-written, with calibrated confidence scoring, transparent user-facing labels, an appeals workflow, rate limiting, and structured audit logging.

## Architecture Overview

A creator submits text to `POST /submit` along with their `creator_id`. The system generates a unique `content_id`, then passes the raw text independently to two detection signals: a Groq LLM signal (semantic judgment) and a stylometric signal (structural/statistical measurement). Both signals return a score between 0 and 1. These are combined via a weighted average into a single confidence score, which is mapped to one of three label categories and matching transparency label text. Every submission is written to a structured audit log (content ID, both signal scores, combined confidence, attribution, timestamp). The response returns `content_id`, `attribution`, `confidence`, and `label`.

For appeals, a creator submits `content_id` + `creator_reasoning` to `POST /appeal`. The system looks up the original log entry by `content_id`, updates its status to `under_review`, and appends the appeal reasoning to that same entry. No automatic re-classification occurs — the system flags the case for human review rather than re-judging itself.
SUBMISSION FLOW:
POST /submit {text, creator_id}
│  (raw text)
▼
[Signal 1: Groq LLM] ──► llm_score (0-1)
▼
[Signal 2: Stylometrics] ──► stylo_score (0-1)
▼
[Confidence Scoring: weighted avg] ──► combined_score
▼
[Label Generator: threshold mapping] ──► label text
▼
[Audit Log: structured entry written]
▼
Response {content_id, attribution, confidence, label}
APPEAL FLOW:
POST /appeal {content_id, creator_reasoning}
▼
[Lookup record by content_id]
▼
[Update status → "under_review"]
▼
[Audit Log: appeal entry linked to content_id]
▼
Response {status: "under_review", message}

## Detection Signals

**1. LLM-based (Groq, llama-3.3-70b-versatile).** Sends the submitted text to the model with a prompt asking it to output a single 0–1 likelihood score that the text is AI-generated. This signal was chosen because it captures *semantic and stylistic coherence holistically* — it reads the text roughly the way a human judge would, picking up on tone, phrasing patterns, and the generic "AI voice" that's hard to reduce to a formula.

*Blind spot:* it can mistake formal, structured human writing (academic prose, non-native English formal writing) for AI, since both share the "no typos, polished tone" surface trait the model may over-index on.

**2. Stylometric heuristics (pure Python).** Computes sentence-length variance and type-token ratio (vocabulary diversity) with no language understanding at all — pure counting and statistics. Chosen specifically because it's *independent* of the LLM signal: one is semantic, one is structural, so when they agree, confidence is reinforced; when they disagree, that disagreement itself is informative.

*Blind spot:* on short text samples (3–4 sentences), both metrics become statistically noisy and lose discriminating power — see Known Limitations below for real observed evidence of this.

**Combination:** `combined_score = 0.6 × llm_score + 0.4 × stylo_score`. The LLM signal is weighted higher because it captures meaning, which proved to be the stronger and more reliable signal in testing.

## Confidence Scoring

Thresholds:
- 0.0 – 0.40 → **likely human**
- 0.40 – 0.75 → **uncertain**
- 0.75 – 1.0 → **likely AI**

The "likely AI" threshold is deliberately set above the midpoint (0.75, not 0.5). This reflects an explicit design principle: on a creative platform, falsely accusing a human writer of using AI causes real, disproportionate harm (lost trust, reputational damage) compared to letting one AI-generated piece slip through mislabeled. Requiring stronger evidence before an "AI" verdict, and defaulting ambiguous cases to "uncertain," directly encodes that asymmetry.

**Validation approach:** rather than trust the scoring formula on faith, it was tested against 4 deliberately chosen inputs spanning the confidence range — a clearly-AI paragraph, a clearly-human casual review, and two borderline cases (formal human writing, lightly-edited AI text). Two real example results from that testing:

- **Higher-confidence case:** A formal AI-generated paragraph about AI's societal impact scored `llm=0.80`, `stylo=0.44`, **combined confidence = 0.66** → category: *uncertain* (still below the 0.75 "likely AI" bar by design, consistent with the false-positive-avoidance principle).
- **Lower-confidence case:** A casual first-person restaurant review scored `llm=0.20`, `stylo=0.40`, **combined confidence = 0.28** → category: *likely human*.

The ~0.38 gap between these two real test cases confirms the scoring produces meaningful variation rather than collapsing to a constant.

## Transparency Label Design

Exact label text returned by the system, by category:

- **High-confidence AI** (score ≥ 0.75): *"Our system found strong indicators this content was AI-generated. Confidence: {confidence}%."*
- **High-confidence Human** (score ≤ 0.40): *"Our system found this content likely human-written, with no strong AI indicators. Confidence: {confidence}%."*
- **Uncertain** (0.40 < score < 0.75): *"Our system could not confidently determine whether this content was AI-generated or human-written. Confidence: {confidence}%. The creator may appeal this classification."*

All three were confirmed reachable by submitting real test inputs during Milestone 5 and observing distinct label text returned for each score range.

## Appeals Workflow

Any creator with a valid `content_id` from an earlier submission can appeal via `POST /appeal`, providing `content_id` and `creator_reasoning`. The system looks up the matching audit log entry, sets its `status` to `under_review`, and appends `appeal_reasoning` to that same entry — no new duplicate record is created, and no automatic re-classification runs, since the whole point of an appeal is that it requires human judgment the algorithm can't perform on its own.

Example verified test (real, from Milestone 5 testing): submitting an appeal with reasoning *"I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical"* against a real `content_id` correctly updated that log entry's status to `under_review` and stored the reasoning text, while leaving all other log entries untouched. Submitting an appeal against a nonexistent `content_id` correctly returns a 404 error rather than silently succeeding.

## Rate Limiting

Applied via Flask-Limiter: **10 requests per minute, 100 per day**, on `POST /submit`.

**Reasoning:** a genuine writer submitting their own original work would rarely submit more than a handful of pieces within a single minute — 10/minute comfortably covers real usage patterns while blocking a script attempting to flood the endpoint. The 100/day ceiling allows for a very active user submitting many pieces across a day without enabling large-scale automated abuse.

**Verified evidence** (real output from a 12-request rapid-fire test):
200
200
200
200
200
200
200
200
200
200
429
429
The first 10 requests succeeded; the 11th and 12th were correctly rejected with `429 Too Many Requests`, confirming the limit triggers exactly as configured.

## Audit Log

Every submission and appeal writes a structured JSON entry containing `content_id`, `creator_id`, `attribution`, `confidence`, `llm_score`, `stylo_score`, `status`, and `timestamp`; appeal entries additionally include `appeal_reasoning`. Retrievable via `GET /log`. Example real entries (abbreviated):

```json
{
  "content_id": "ce2a9c1a-74ee-4258-b123-f60bb306f5ef",
  "creator_id": "test-ai",
  "attribution": "uncertain",
  "confidence": 0.66,
  "llm_score": 0.8,
  "stylo_score": 0.44,
  "status": "under_review",
  "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
  "timestamp": "2026-07-01T04:02:49.451093+00:00"
}
```

## Known Limitations

1. **Stylometric signal shows weak discrimination on short text (3–4 sentences).** During Milestone 4 testing, sentence-length variance and type-token ratio produced nearly identical scores (0.40–0.44) across a clearly-AI paragraph, a clearly-human review, and two borderline cases — a spread of only 0.04. This is a direct consequence of the metrics themselves: variance and vocabulary diversity require enough sentences to be statistically meaningful, and short creative submissions (a haiku, a short poem) simply don't provide that. Rather than force a third metric to mask this, the system keeps 2 signals and documents this limitation honestly.

2. **Lightly-edited AI text can be misclassified as human.** A test passage modeled on "AI-generated text with light human editing" scored `llm=0.20`, `stylo=0.44`, combined `confidence=0.29` — landing in "likely human," when it should arguably be closer to "uncertain" per the spec's own framing. This suggests the LLM signal is more attuned to catching unedited, formulaic AI phrasing than AI content that's been lightly smoothed by a human editor — a real, mechanism-specific weakness rather than a generic accuracy gap.

## Spec Reflection

**How the spec helped:** requiring the architecture diagram and API contract to be defined *before* any code (Milestone 1–2) meant that by the time implementation started, every function's expected input/output shape was already known. This made debugging much faster — for example, when the stylometric signal produced flat, undiscriminating scores in Milestone 4, having already documented "variance-based, 0–1 output" in `planning.md` made it immediately clear the *scaling* was wrong, not the underlying logic.

**Where implementation diverged:** the spec's suggested stylometric pairing allows 2–3 metrics; after observing weak discrimination with 2 metrics (sentence-length variance + type-token ratio) on short test inputs, the natural next step would have been adding a third metric (e.g., punctuation density) to force better separation. Instead, the decision was made to keep 2 metrics and document the weakness honestly rather than add a metric mainly to produce more favorable-looking test numbers — this follows the spec's own stated philosophy ("acknowledge uncertainty honestly") more than its suggested implementation detail.

## AI Usage

**Instance 1 — Stylometric signal miscalibration.** Directed the AI to generate the stylometric signal function using sentence-length variance and type-token ratio, per the planning.md spec. The first version normalized variance using a `/20` scaling factor, which produced scores of ~0.06 across all 4 test inputs — completely non-discriminating. Added a debug print to inspect raw values, found real variances were actually 37–60 (far higher than assumed), and revised the scaling factor to `/80` along with rescaling the type-token ratio around its observed real range (0.80–0.95) instead of the naive 0–1 range. This is a case where the AI-generated logic was structurally correct but numerically miscalibrated against real data, caught only by testing against concrete inputs rather than trusting the code on inspection alone.

**Instance 2 — False rate-limit failure diagnosis.** When first testing the 12-request rate-limit script, all 12 requests returned `429` instead of the expected 10×200/2×429 pattern. Rather than assume the Flask-Limiter code was broken and rewrite it, investigated the likely cause first: many earlier manual test requests during that same session had already consumed the "10 per minute" allowance before the test script even ran. Waited ~90 seconds for the window to reset and reran the identical script, which then produced the correct 10×200/2×429 pattern — confirming the original rate-limiting implementation was correct all along, and the earlier failure was a testing-methodology issue, not a code issue.