# Evidence — ATS-style job fit workbench

A public, reusable application with a Python scoring engine running in the browser through Pyodide. Hosted on GitHub Pages. Upload a resume, paste a job description, add confirmed experience, review the evidence, and export an explainable assessment.

This is a personal job-search aid, not an employer ATS, automated hiring decision system, or interview-probability model. The initial matcher is deterministic and intentionally conservative; it is not an LLM or a semantic understanding model. It cannot reproduce a human-written assessment without review.

## Features

- PDF, DOCX, TXT and Markdown resume uploads, processed locally (8 MB limit).
- Separate additional-experience notes and resume-only vs broader-profile scores.
- Editable requirement extraction; core, preferred and eligibility classifications.
- Source excerpts, evidence levels and explanations for every scored requirement.
- Exact alias matching, with no credit inflation from repeated keywords.
- Manual evidence review with required rationale; eligibility met/unmet/unknown.
- Weighted category breakdown, gaps, strengths, Markdown reports and JSON save/restore.
- Responsive interface, worker-based Python execution, no accounts or API keys.
- No candidate records in the public repository. Demo data is fictional.

## Run locally

Requires Python 3.10+ for the local server and a current browser supporting module workers/WebAssembly.

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

Open http://127.0.0.1:8765. Do not open the HTML directly as a file. First startup needs an internet connection to load the pinned Pyodide runtime from jsDelivr; The bundled PDF parser is loaded on first use.

## Test

The scoring tests use only the Python standard library:

```sh
python -m unittest discover -s tests -v
```

Native Python PDF extraction additionally requires `pypdf`; browser PDF extraction uses the bundled pypdf 6.9.1 wheel (BSD 3-Clause license included inside the wheel). DOCX extraction uses standard-library ZIP/XML processing. Image-only PDFs require OCR text; password-protected PDFs are rejected.

## Deploy on GitHub Pages

1. Use a public repository and push these files to `main`.
2. In **Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions**.
3. Run the **Test and deploy** workflow, or push a commit to `main`.
4. The deployed site URL is shown in the workflow's deployment output.

The workflow publishes an explicit allowlist of files under `web/`, not the repository root. Private inputs should never be committed, even to ignored paths. GitHub Pages does not execute Python on the server: Python runs on the visitor's device via WebAssembly.

## Scoring methodology

1. Draft requirements are extracted using section headings, exact concept aliases and simple patterns. Inspect this draft: introductory prose can be misclassified, unrecognized requirements need manual scoring, compound requirements may need splitting, and AND/OR alternatives need human review.
2. Core categories have relative weights: Leadership 20, Architecture 20, Delivery 15, Reliability/security 20, AI/developer productivity 15, Business/domain 10. Present core categories are normalized to 100 points, or 85 when preferred requirements exist. Preferred qualifications collectively receive 15 points. A repeated concept is counted once, with core taking precedence.
3. Each requirement receives 0% (not evidenced), 25% (keyword/assertion), 50% (partial), 75% (substantial) or 100% (demonstrated). Automatic matches are capped at 75%; full credit requires review. An action verb plus a concept is only a suggested substantial match, not verification of the claim.
4. Evidence scores are averaged within each category. The app reports the decimal total and rounded display score. Adding/removing requirements can change weights, so scores are specific to the reviewed rubric and should not be compared as calibrated probabilities across unrelated jobs.
5. Unknown eligibility does not subtract points. A confirmed unmet mandatory condition overrides the recommendation. Years, degree, location and authorization conditions need user confirmation; dates are not automatically summed.
6. Recommendations: 80+ apply, 65–79 apply as a stretch, below 65 lower priority. These are transparent heuristics, not validated hiring thresholds. Confidence refers to review completeness, not objective predictive accuracy.
7. Resume-only score is an automatic estimate with the same requirement list but no additional experience or manual broader-profile scores. It must not be interpreted as an independently reviewed score.

## Evidence quality and limitations

Do not treat related capabilities as interchangeable: managing engineers is different from managing managers; zero-downtime deployments do not establish zero-downtime database migrations; listing a tool does not establish years of use; learning targets are not work experience. Avoid entering conflicting resume versions as if every claim were verified. The matcher detects some explicit negation but cannot reliably resolve chronology, contradictory metrics, scope, alternatives, partial negation or synonym ambiguity. Source excerpts and manual review are essential. No formatting/ATS-parser certification is implied by successful extraction.

## Privacy and security

Candidate documents, pasted descriptions and notes are processed in worker memory and are not uploaded. The app does not use analytics, localStorage, external AI APIs, cookies or a database. Runtime assets are downloaded from jsDelivr, which receives ordinary connection metadata but not document contents. GitHub receives ordinary site-request metadata. Downloaded reports and saved assessments contain personal information; users control their storage. Clear all data resets the worker and input fields. Refreshing loses unsaved work.

Uploaded text is rendered with DOM text nodes, never evaluated as code or inserted as HTML. File/text/ZIP-expansion/page limits reduce accidental resource overload; these are not a hardened adversarial file sandbox. Do not use this public client-side tool to make employment decisions about other people.

## Project layout

- `web/engine.py`: extraction, aliases, evidence rules, scoring and document parsing.
- `web/worker.js`: Python runtime and document-processing bridge.
- `web/app.js`: accessible browser interactions; no scoring logic.
- `web/index.html`, `web/style.css`: responsive interface.
- `web/vendor/`: pinned official Pyodide module bootstrap and MPL 2.0 license.
- `tests/test_engine.py`: scoring and parsing regression tests using fictional data.
- `.github/workflows/pages.yml`: CI and Pages deployment.

Pyodide bootstrap version: 314.0.7, from https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs. Its license is included in `web/vendor/LICENSE.pyodide`. Other runtime assets are fetched from the matching versioned CDN directory.

