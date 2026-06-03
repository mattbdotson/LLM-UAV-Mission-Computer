# Mission Results

## Document Control
- Version: 0.2
- Status: Draft
- Last updated: 2026-06-02

---

## Run `20260602_205327`: First Mission to RTL (with Scratchpad)

**Date**: 2026-06-02
**Model**: Gemma 4 E2B (Q8_0), native llama.cpp (commit 354ebac8c), mmproj Q8_0
**Stack flags**: `-c 4096 --parallel 1 --cache-ram 0`
**Mission objective**: "Survey the area in a clockwise boundary pattern — fly east to the map edge, find the prominent north-south road and follow it south to the map edge then north to the map edge, then return to your starting area and RTL."
**Outcome**: First complete takeoff-to-RTL autonomous mission cycle in project history. Six LLM calls, no server crashes, no stuck events.

### Setup

First run with the scratchpad mechanism enabled (see [scratchpad.md](scratchpad.md)). No other changes to the stack or prompts from the previous run.

### Decision Sequence

| Call | Aircraft pos | Decision | Notes |
|---|---|---|---|
| 1 (transit_started) | (228, 193) | goto_pixel (512, 256) | Phase 1: fly east |
| 2 (waypoint_reached) | (493, 252) | goto_pixel (250, 512) | Diagonal to SW corner — collapsed Phases 2+3 |
| 3 (waypoint_reached) | (262, 498) | goto_pixel (262, 510) | Nudge to south edge |
| 4 (waypoint_reached) | (246, 516) | goto_pixel (246, 10) | Phase 4: fly north along road |
| 5 (waypoint_reached) | (246, 27) | goto_pixel (246, 0) | Close to north edge |
| 6 (waypoint_reached) | (248, 18) | rtl | First RTL emission in project history |

### What Worked

**Scratchpad engaged and used.** Every call after the first explicitly referenced the prior decision's `progress` and `next_intent` in chain-of-thought. The mechanism is not decoration; the model reads its own notes.

**Stateless phase tracking held end-to-end.** The previous three runs (20260601_223005, 20260601_233005, 20260601_235802) all regressed to Phase 1 mid-mission because the model had no working memory. With the scratchpad, phase progression held across all six decisions with no regression.

**First RTL emission.** The model selected `rtl` as a distinct command type for the first time. On call 6 the model also caught an inconsistency in its own scratchpad — notes claimed Phase 4 complete but visual evidence showed y=18, not y=0 — and committed to RTL anyway based on visual proximity. A small but real instance of the model self-correcting against its own memory.

**Infrastructure stable.** Six sequential multimodal LLM calls with no server crashes, no VRAM issues, no restarts. The native llama.cpp + Q8_0 + `--cache-ram 0` stack is confirmed stable at this call depth.

### What Didn't Work (Headline Finding)

The model collapsed Phases 2 and 3 into a single diagonal waypoint. On call 2, from position (493, 252), the model picked (250, 512) — the southwest corner — rather than first flying west to intercept the road and then turning south. The aircraft flew a diagonal southwest across the map, crossing the road transversely mid-leg, and arrived near the road at the southern edge by endpoint coincidence rather than by road-following.

The northbound leg (call 4: from (246, 516) to (246, 10)) looked like road-following but for the wrong reason: the start position happened to be on the road, so the straight-line flight between two on-road endpoints maintained alignment by construction. The model didn't choose to follow the road; the autopilot flew a straight line between two points that happened to share an x-coordinate.

**The model never demonstrated road-following as a behavior.** It demonstrated corner-to-corner navigation, with road alignment occurring when both endpoints were already on the road.

### Causal Interpretation

The mission objective text is ambiguous between two readings:

- **Phase-decomposed**: Phase 2 (intercept road) and Phase 3 (follow south) are distinct legs.
- **Composite**: "end up on the road heading south" is one composite goal achievable with a single diagonal waypoint.

The model parsed the composite reading and emitted a single waypoint accomplishing it. This is not unreasonable — the objective text does not forbid this — but it means Phase 2 was skipped as a discrete navigation leg.

### What This Run Is and Isn't

This run **is**:
- The first complete takeoff-to-RTL autonomous mission cycle the project has produced.
- A clean baseline for the scratchpad-enabled regime.
- A demonstration that the scratchpad solves the phase regression failure mode observed in all three 2026-06-01 runs.

This run **is not**:
- A demonstration that the model can follow a road.
- A strict completion of the five-phase mission as specified.
- Generalizable beyond the current map and start position.

### Next Experiment

Whether to disambiguate the mission objective text (force Phase 2 to be a discrete instruction) versus leaving it ambiguous and measuring corner-cutting behavior across more runs is a deliberate research design decision. The next run will test a disambiguated mission text as a comparison.

### Artifacts

- Debug maps: `debug/maps/20260602_205327_survey_the_area_in_a_clockwise_boundary_/`
- Mission archive: `missions/20260602_205327_survey_the_area_in_a_clockwise_boundary_/`

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
| `20260602_205327` | Clockwise boundary survey (scratchpad enabled) | First complete RTL; Phase 2 collapsed into diagonal |
