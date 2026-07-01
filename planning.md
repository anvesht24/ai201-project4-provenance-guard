Here's the complete, corrected planning.md — this version includes the API Surface section that was missing, and fixes the narrative length to match the "2-3 sentences" the spec asks for. Everything else is verified against both checklists.
Create the file:
powershellNew-Item -Path planning.md -ItemType File
Open it in your editor and paste this entire content:
markdown
# Provenance Guard — Planning

## Architecture

**Narrative:** A submission's raw text flows through two independent detection 
signals (Groq LLM + stylometric heuristics), which each produce a 0-1 score; 
these are combined into a single confidence score, mapped to one of three 
transparency labels, logged, and returned to the creator. An appeal looks up 
the existing record by content_id, updates its status to "under_review," and 
logs the dispute alongside the original decision — no re-classification occurs.
SUBMISSION FLOW:
POST /submit {text, creator_id}
│  (raw text)
▼
[Signal 1: Groq LLM]
│  (llm_score: 0-1)
▼
[Signal 2: Stylometrics]
│  (stylo_score: 0-1)
▼
[Confidence Scoring: weighted avg]
│  (combined_score: 0-1)
▼
[Label Generator: threshold mapping]
│  (label text + attribution category)
▼
[Audit Log: write structured entry]
│  (content_id, scores, label, timestamp)
▼
Response {content_id, attribution, confidence, label}
APPEAL FLOW:
POST /appeal {content_id, creator_reasoning}
│  (content_id, reasoning text)
▼
[Lookup original record by content_id]
│  (original decision record)
▼
[Update status → "under_review"]
│  (updated status)
▼
[Audit Log: write appeal entry linked to content_id]
│  (appeal logged, no re-classification)
▼
Response {status: "under_review", message}

## API Surface

| Endpoint | Method | Request Body | Response Body |
|---|---|---|---|
| `/submit` | POST | `{ text, creator_id }` | `{ content_id, attribution, confidence, label }` |
| `/appeal` | POST | `{ content_id, creator_reasoning }` | `{ status: "under_review", message }` |
| `/log` | GET | (none) | `{ entries: [ {content_id, creator_id, timestamp, attribution, confidence, llm_score, stylo_score, status} ] }` |

## Detection Signals

1. **LLM-based (Groq, llama-3.3-70b-versatile)**: Sends text to the model and 
   asks it to assess AI vs human likelihood. Outputs a 0-1 score. Captures 
   semantic/stylistic coherence holistically — reads the text the way a 
   human judge would.
   - Blind spot: can mistake formal/structured human writing for AI (e.g. 
     academic writing, non-native English formal prose) — false positive risk.

2. **Stylometric heuristics (pure Python)**: Computes sentence length 
   variance, type-token ratio (vocabulary diversity), and punctuation 
   density. Outputs a 0-1 score. Captures structural/statistical patterns 
   with zero understanding of meaning.
   - Blind spot: can mistake deliberately uniform human writing styles 
     (certain poetic forms, formal academic style) for AI, since it can't 
     distinguish "stylistic choice" from "AI uniformity."

These two signals are independent — one is semantic (meaning-based), one is 
purely structural (counting-based) — so when they agree, confidence is 
higher; when they disagree, that itself signals ambiguity.

**Combination:** `combined_score = 0.6 * llm_score + 0.4 * stylo_score` 
(LLM weighted higher since it captures meaning, a stronger signal than 
structure alone.)

## Uncertainty Representation

A confidence score of 0.6 means the system leans toward "AI-generated" but 
without strong conviction — it falls in the "uncertain" band, not a confident 
verdict either way.

Thresholds:
- 0.0 – 0.40  → "likely human"
- 0.40 – 0.75 → "uncertain"
- 0.75 – 1.0  → "likely AI"

The "likely AI" threshold is set above the midpoint (0.75, not 0.5) 
deliberately: false positives (accusing a human of using AI) are worse than 
false negatives on a creative platform, so the system requires stronger 
evidence before making that accusation. Borderline cases default to 
"uncertain" rather than a confident wrong answer.

## False Positive Scenario (Traced)

A human writer submits a formal, structurally uniform essay. Stylometrics 
sees low sentence-length variance and scores 0.72 (AI-likely). The LLM, less 
fooled by tone alone, scores 0.55. Combined: 0.6(0.55) + 0.4(0.72) = **0.618**. 
Under our thresholds, 0.618 falls into "uncertain" — not "likely AI" — 
because the higher AI threshold absorbed the risk. The uncertain-label text 
is shown, explicitly mentioning the appeal option. The writer appeals via 
`/appeal` with `content_id` + reasoning ("I write formally because I'm an 
academic"). Status updates to `under_review`, the appeal is logged next to 
the original decision, and no re-classification runs. A human moderator 
would review the original text, both scores, and the reasoning to make the 
final call.

## Transparency Label Design

- **High-confidence AI** (score ≥ 0.75): "Our system found strong indicators 
  this content was AI-generated. Confidence: {confidence}%."
- **High-confidence Human** (score ≤ 0.40): "Our system found this content 
  likely human-written, with no strong AI indicators. Confidence: 
  {confidence}%."
- **Uncertain** (0.40 < score < 0.75): "Our system could not confidently 
  determine whether this content was AI-generated or human-written. 
  Confidence: {confidence}%. The creator may appeal this classification."

## Appeals Workflow

- Anyone with a valid `content_id` (the original creator) can submit an appeal.
- Required fields: `content_id`, `creator_reasoning` (free text explaining why 
  they believe the classification is wrong).
- On receipt: system looks up the original record by `content_id`, updates its 
  status field to `under_review`, and writes a new audit log entry linking 
  the appeal to the original decision (same `content_id`).
- Automated re-classification does NOT occur — signals are not re-run.
- A human reviewer opening the appeal queue would see: the original 
  submitted text, both signal scores, the combined confidence score, the 
  label shown to the creator, and the creator's appeal reasoning.

## Anticipated Edge Cases

1. **Very short text (under ~20 words)**: Stylometric measures like sentence 
   length variance are statistically meaningless on tiny samples — a single 
   short sentence has no "variance" to measure, so the stylometric score 
   becomes noisy/unreliable for short submissions.
2. **Non-native English formal writing**: A non-native English speaker who 
   writes carefully, grammatically, and formally (to avoid errors) may 
   trigger both signals toward "AI-like" — the LLM may read formality as 
   AI-typical phrasing, and stylometrics may read careful uniform sentence 
   construction as low variance — despite being genuinely human-written.

## AI Tool Plan

- **M3 (submission endpoint + first signal)**: Provide the Detection Signals 
  section + Architecture diagram to the AI tool. Ask it to generate a Flask 
  app skeleton with a `POST /submit` route stub, plus the Groq LLM signal 
  function. Verify by calling the signal function directly with 2-3 sample 
  texts and inspecting output before wiring into the endpoint.

- **M4 (second signal + confidence scoring)**: Provide Detection Signals + 
  Uncertainty Representation sections + diagram. Ask for the stylometric 
  signal function and the confidence-scoring combination logic. Verify the 
  generated thresholds match this document exactly, and test using 4 
  example inputs (clearly AI, clearly human, 2 borderline) to confirm scores 
  match intuition.

- **M5 (production layer)**: Provide Transparency Label Design + Appeals 
  Workflow sections + diagram. Ask for the label-generation function and the 
  `POST /appeal` endpoint. Verify all three label variants are reachable with 
  different test inputs, and that an appeal correctly updates status to 
  `under_review` and logs correctly.