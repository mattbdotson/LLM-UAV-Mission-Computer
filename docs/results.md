# Mission Results

## Document Control
- Version: 0.1
- Status: Draft
- Last updated: 2026-06-01

---

## Run: `20260601_232846_survey_the_area_in_a_clockwise_boundary_`

**Date**: 2026-06-01  
**Model**: Gemma 4 E2B (Q8_0), native llama.cpp build (commit 354ebac8c)  
**Mission**: Clockwise boundary survey — fly east to map edge, find and follow the prominent north-south road south then north, return to start  
**Outcome**: 5/5 correct phase decisions before a false `no_progress` termination on Phase 4

### Decision Sequence

| Call | Position | Waypoint Issued | Phase |
|---|---|---|---|
| 1 | (228, 193) | (512, 193) | Phase 1: fly east, preserve y |
| 2 | (493, 194) | (512, 256) | Phase 1: continue to eastern edge |
| 3 | (505, 238) | (300, 238) | Transition to Phase 2: visually identified road at x~300-320 |
| 4 | (317, 239) | (317, 512) | Phase 3: fly south along the road |
| 5 | (316, 493) | (320, 50) | Transition to Phase 4: fly north along the road |

Call 6 (stuck): fired at (314, 263) during Phase 4 transit. Model regressed to Phase 1, issuing (512, 263). Mission terminated.

### What This Demonstrated

**Genuine visual grounding**: the model identified the prominent north-south road by visual inspection rather than picking map center geometrically. Across all decisions where the road was referenced, the model consistently placed it at x~300-320. This is internally coherent and matches the map. The road was not named in any prompt.

**Stateless multi-phase tracking**: the model correctly inferred phase transitions (Phase 1 → 2 → 3 → 4) from its current position and visible features alone. No phase state was injected into the prompt between calls.

**Place-name recognition**: the model read "Jerrabomberra Nature Reserve" off the rendered map tile and referenced it in chain-of-thought reasoning.

### Failure Mode: Phase Regression After Stuck

The mission ended on call 6 because the 180s `no_progress` timer fired during the Phase 4 transit (a near-full-map leg from y=493 to y=50). This was a legitimate transit, not a real stuck condition.

When `stuck` re-prompted the model, it had no memory of having completed Phases 1–3. It read the mission objective from scratch, identified the first instruction ("fly east to the map edge"), and issued a Phase 1 waypoint. This undid 5 prior correct decisions.

This pattern — correct stateless inference during normal flight, regression on re-prompt — is the key open architectural issue. See [troubleshooting.md](troubleshooting.md) for the failure mode entry and the scoring spec (§1.2) for the planned phase-state-injection experiment that will quantify improvement.

The immediate workaround is the `no_progress` threshold raised to 600s. The proper fix is a distance-based progress check that doesn't fire during legitimate long-leg transits.

---

## Prior Runs (Summary)

| Run | Mission | Outcome |
|---|---|---|
| Mission 001 | Highway junction approach | Partial success |
| Mission 002 | Boundary pattern | Full success — 4/4 decisions correct |
| `20260601_232846` | Clockwise boundary survey | 5/5 correct, false stuck on Phase 4 |
