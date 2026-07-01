# Development & Test Plan — V2.0 ("Sight" Increment)

## Document Control
- Version: 0.1
- Status: Draft
- Applies to: V2.0 increment, SITL + Gazebo simulation phase only
- Last updated: 2026-06-30

> Right-arm artifact of the V2.0 increment. The left arm defined *what* the system must be — the ConOps ([conops.md](conops.md)), the L0 system requirements ([L0_requirements.md](L0_requirements.md)), and the system architecture ([architecture.md](architecture.md), Sentinel-Spine). This plan defines *how it gets built and proven*: the development approach, the de-risking spikes that precede the build, and the verification/validation activities that climb the right arm of the V. It is a plan, not a controlled artifact — it will be revised as the spikes report back.

---

## 1. Purpose & Scope

This plan governs the implementation and test of the V2.0 "Sight" increment against the Sentinel-Spine architecture. It covers:

- The **de-risking spikes** to run *before* committing to the build — chief among them the **edge-budget feasibility test** (L0-SIM-01), which can invalidate the single-edge-box assumption the whole architecture rests on.
- The **development build order** — an incremental, delta-from-V1 sequence organized by fault domain so each piece is testable as it lands.
- The **four verification levels** (unit → integration → system verification → validation), each tied to the left-arm artifact it verifies, per the V.
- How the **deferred numeric bounds** (the L0 Open Items) get pinned empirically during the test campaign, now that formal L1 requirements are descoped (§2).

Out of scope: a formal L1 requirements specification (see §2), the TensorRT backend, real-hardware HIL, and everything in ConOps §8 (GPS-denied nav, fast-mover pursuit, multi-camera). See §9.

## 2. Place in the SE V — and the L1 Decision

The V pairs each left-arm definition rung with a right-arm activity that verifies it. This plan owns the right arm and the vertex.

| Left arm (definition) | Artifact | Right-arm counterpart (this plan) | Section |
|---|---|---|---|
| Concept of Operations | [conops.md](conops.md) | **Validation / Acceptance** — vignette-driven end-to-end missions | §5.4 |
| L0 System Requirements | [L0_requirements.md](L0_requirements.md) | **System Verification** — the 62-requirement verification matrix | §5.3, App. A |
| System Architecture | [architecture.md](architecture.md) | **Integration Test** — component data-flows & invariants | §5.2 |
| Detailed design *(code-level)* | the source tree | **Unit Test** — per-component behavior | §5.1 |
| — (vertex) | — | **Implementation** — the build | §4 |

**On L1 requirements.** A formal L1 requirements specification is **deliberately descoped** for this increment as disproportionate to a single-developer research rig: the architecture's Appendix A already allocates every L0 requirement to a component, and the code *is* the detailed design. The work a formal L1 pass would have done — pinning the deferred numeric bounds — is instead done empirically during the test campaign and recorded in a values ledger (§6). This keeps the "one V per increment" discipline while refusing to write requirements fiction for bounds that can only be learned by measurement.

## 3. De-Risking Spikes (Do First)

These are short, throwaway experiments run **before** the main build. Each answers a question that, if answered badly, changes the plan. They are cheap relative to building on an unverified assumption.

### 3.1 Edge-Budget Feasibility (L0-SIM-01) — the go/no-go gate

**Question.** Can the perception pipeline and `llama-server` (Gemma 4 E2B) run **concurrently** inside the edge tier's budget — a single Jetson Orin Nano Super, 8 GB unified memory — with headroom for sustained operation?

**Why it gates everything.** Sentinel-Spine (and every surviving candidate) assumes perception + reasoning co-resident on one edge box. If they don't fit, the single-edge-box assumption breaks and the architecture ranking can change (a second edge unit converts the in-process registry write into a network write and erodes Sentinel-Spine's simplicity advantage — architecture §10.1).

**Method.**
1. Stand up `llama-server` with Gemma 4 E2B + vision projector on the Jetson (the known-good V1 deployment) and record its steady-state resident set and VRAM-equivalent unified-memory footprint while serving a representative map-view + prompt.
2. Stand up a **stand-in perception load** at the target frame cadence — a detector/tracker of the class intended for V2 (or a deliberately-sized proxy if the final model isn't chosen) plus the geo-projector math — and record *its* resident set and per-frame compute headroom.
3. Run **both together** under a representative mission tempo (continuous perception + periodic event-driven inference bursts) for a sustained window; watch for OOM, thermal throttling, swap, and inference-latency inflation when perception is active.

**Metrics.** Peak and steady unified-memory use (both processes + OS), swap activity, perception frame rate held vs. dropped, VLM inference latency idle vs. under perception load, thermal/throttle state over the sustained window.

**Decision fork.**
- **Fits with headroom** → proceed with Sentinel-Spine as drawn.
- **Tight / throttling** → mitigate on the same box (smaller/quantized perception model, cadence reduction, NVMe swap) and re-measure.
- **Does not fit** → escalate to the two-edge-unit variant and revisit the architecture ranking (the in-process-registry advantage weakens). This is a real architecture decision, not a tuning knob.

### 3.2 Gimbal Control over MAVLink (L0-IFC-02, architecture §10.2)

**Question.** Does gimbal/mount control ride MAVLink (mount / gimbal-manager protocol) cleanly through ArduPlane SITL to the Gazebo gimbal plant — and does the same command path plausibly hold on real hardware?

**Why.** The architecture routes gimbal pointing as a flight-tier MAVLink command from the executor (never through perception), and reports gimbal orientation back as mount status on the same MAVLink path that feeds the geo-projector. If that path doesn't exist end-to-end in sim, the observation-control and geo-projection designs need rework.

**Method.** Command a mount orientation from a MAVLink client, confirm the Gazebo gimbal slews, and confirm the orientation is reported back as telemetry. Verify the round trip closes.

**Decision.** Confirms (or refutes) the single-owner-MAVLink gimbal path assumed by the executor + geo-projector before either is built.

### 3.3 Sim Runtime Sanity — Gazebo-as-FDM + camera transport

**Question.** Does the baselined runtime hold up: Gazebo owning the flight-dynamics model with ArduPlane SITL, and the camera-frame stream crossing the LAN to the edge perception process at cadence without starving the MAVLink drain?

**Method.** Bring up the sim stack (Gazebo world + sensors, ArduPlane SITL, MAVProxy), publish camera frames to a stand-in edge subscriber over the baselined lightweight transport, and confirm frame cadence and MAVLink telemetry are both healthy under load.

**Decision.** Confirms the runtime baseline before Stage 0 of the build depends on it.

## 4. Development Approach & Build Order

**Principle.** Incremental, **delta-from-V1**, built **bottom-up by fault domain** so each stage is verifiable before the next depends on it. The V1 spine (telemetry → event check → FSM → executor, single-owner MAVLink) is kept and extended, not rewritten (architecture §1).

| Stage | Build | Depends on | First verified at |
|---|---|---|---|
| **0. Sim stack** | Gazebo world + simulated sensors (camera, boresight rangefinder, nadir altimeter, gimbal plant); ArduPlane SITL on Gazebo FDM; MAVProxy | Spikes 3.2, 3.3 | Infrastructure (§7) |
| **1. Perception service** | Edge process: frame ingest → detector → tracker → **geo-projector**. Publishes latest-value snapshot. Holds no MAVLink handle. | Spike 3.1; Stage 0 | Unit (§5.1), **nadir-first** (§4 note) |
| **2. Registry + renderers** | World-model registry (extended MissionContext: tracks, covariance, TTL, feature-confirm, prior-map substrate); NavMap renderer (full-fidelity geometry + pixel↔gps) and map-view renderer (schematic, labeled) split from V1 `map_compositor` | Stage 1 | Unit (§5.1) |
| **3. Spine extensions** | Event monitor + admissibility gate (detection / track_lost / observation_ended / feature_unconfirmed / reasoning_ready); Mission FSM OBSERVING sub-state + SAF-06 health gate; **Reasoning client** proxy (VLM off the hot thread) | Stage 2 | Integration (§5.2) |
| **4. Observation control** | Executor observation controller: `observe{track_id}` → orbit-and-hold + gimbal pointing, bounded termination; gimbal command path | Stages 2–3; Spike 3.2 | Integration (§5.2) |
| **5. Logging & scoring** | Run archive + dual logger (decision log, separate perception log, imagery, outcomes, shared clock); held-out scorer (offline, outside the SUT) | Stage 3 | System (§5.3) |

**Required hardening grafts (must land before baselining — architecture §7).** These are development tasks, not afterthoughts:
- **Graft A — de-block the executor.** The inherited V1 executor blocks the spine on mode-set/arm handshakes; make them non-blocking (issue, confirm on next telemetry tick, never sleep on the spine). Prerequisite for the per-tick orbit re-center. **Highest priority.**
- **Graft B — spine-resident observation watchdog.** Termination timer + feed-staleness watchdog that fires `observation_ended` / `track_lost` **independent of the perception feed**, so a whole-perception death still terminates the orbit (closes SAF-08).
- **Graft C — first-class `reasoning_ready` with an overlap policy.** At most one in-flight reasoning request; a newer high-priority trigger supersedes a stale one; a stale-context result is dropped; the FSM holds a defined safe default during the request window.

**Validation discipline — nadir before active (ConOps §10; L0 Open Items).** The geo-projector SHALL be proven in the **stabilized-nadir** regime before active gimbal pointing is enabled in test. This sequencing is a verification-plan rule, and it shapes Stage 1: build and prove the nadir-AGL + boresight geometry first, then enable off-axis active pointing.

## 5. Verification & Test Levels

### 5.1 Unit Test — verifies the code (detailed design)

Component-level, automated where practical, run against synthetic inputs with known-correct outputs. Representative cases:

- **Geo-projector:** boresight range along LOS → correct geodetic point (no flat-ground assumption, PER-10); nadir AGL as ground-plane height for off-axis fallback (PER-11); accuracy vs. known geometry (PER-03/08). Nadir cases first.
- **Tracker:** persistent unique IDs across frames (PER-04); velocity within slow-mover bound (PER-07).
- **Registry:** TTL / staleness expiry and flagging (PER-06); position covariance preserved, never rendered exact (PER-05).
- **Event gate:** the mission-state admissibility matrix — admissible in ON_TASK, suppressed in TAKEOFF/RETURNING, deferred-not-discarded (EVT-02); detection-during-observation persisted, no preempt (EVT-03).
- **Observation controller:** bounded termination guaranteed to fire even on an undecided outcome (TSK-04); single-observation concurrency guard (TSK-06).
- **Reasoning client:** structured command + reasoning parse; RTL fallback on parse/timeout/HTTP error (SAF-05); symbolic-reference-only tasking (TSK-07).
- **Renderers:** map view is vector-only, not raster (MAP-02); labels restricted to legitimately-known features (MAP-03a); label layer toggles (MAP-03b); NavMap uses full-fidelity geometry, never the schematic view (MAP-04).
- **Executor (Graft A):** mode-set/arm handshakes are non-blocking (no spine sleep).

### 5.2 Integration Test — verifies the architecture

Verifies the component **data flows and invariants** from architecture §3–§5. Representative cases:

- **Perception → registry:** the spine ingests perception's latest-value snapshot each tick; stale snapshots are dropped, never awaited.
- **Non-blocking drain under load (SAF-03):** with perception running hot and with perception **stalled**, measure the 10 Hz MAVLink drain jitter — it must not inflate. This is the topological-firewall claim, tested.
- **Frame firewall (MIS-05, IFC-01):** instrument every input to the reasoning service and assert no raw frame ever reaches it (only the rendered map view); assert frames never traverse the spine.
- **Single-owner MAVLink (IFC-01, SAF-01):** exactly one reader (telemetry listener) and one emitter (executor); assert only high-level GUIDED/LOITER/mount/RTL commands are emitted.
- **Gimbal path (SAF-02):** pointing is commanded by the executor over MAVLink, never by perception; a perception fault degrades pointing to "hold last orbit," not an unsafe slew.
- **Reasoning off the hot thread (Graft C):** decision request returns immediately; result arrives as `reasoning_ready`; overlap policy honored.
- **Detection interrupt (EVT-01/02/03):** a threshold detection wakes the FSM mid-leg in ON_TASK; is suppressed in an inadmissible state; a second detection mid-observation is persisted without preempting.
- **Observation escalation (TSK-05, SAF-08):** injected target-loss / feed-loss during an observation → hold last orbit → escalate to FSM, reusing the STUCK pattern; watchdog (Graft B) fires even when the whole perception domain is dead.
- **Degrade-not-die (SAF-04):** kill perception mid-mission → system reads "no detections" and keeps navigating on GPS + prior map.
- **Fallback (SAF-05):** inject reasoning timeout / parse failure / MAVLink-input loss → safe default (RTL/hold).
- **Health gate (SAF-06):** withhold reasoning health, then perception heartbeat — assert the mission does not arm in either case.

### 5.3 System Verification — verifies the L0 requirements

Every one of the 62 L0 requirements gets a verification method — **T**est, **A**nalysis, **D**emonstration, or **I**nspection — and a primary level. The full matrix is **Appendix A**. Method mix at a glance: most functional requirements are **T**; the structural safety/interface invariants are **I** (you verify a firewall by inspecting that the handle does not exist, then testing that the behavior holds); accuracy/timing bounds are **A**+**T**.

**Invariant & safety set (explicit, non-negotiable cases).** These carry the increment's safety story and each gets a named test/inspection, not just a matrix row:

| Requirement | How it is verified |
|---|---|
| SAF-02 / NAV-04b — perception out of the flight loop | **Inspection**: perception process holds no MAVLink handle; only the executor emits. Then **test** that a perception fault cannot command flight. |
| SAF-03 — perception cannot stall the drain | **Test**: drain jitter flat with perception hot and with perception stalled (§5.2). |
| SAF-04 — degrade to "no detections" | **Test**: kill perception; mission continues. |
| SAF-05 — safe-default fallback | **Test**: inject each failure class; observe RTL/hold. |
| SAF-08 — fail-safe mid-observation | **Test**: feed-loss during observe → hold last orbit + escalate; watchdog independent of feed. |
| MIS-05 / IFC-01 — VLM never sees raw frames; MAVLink+camera only | **Inspection + test**: no frame path to the VLM; interfaces are exactly MAVLink + inbound camera. |
| INT-01 / SIM-04 — no answer key | **Inspection**: no authored ground-truth path into any part of the SUT (sensors, world model, or prompts); the scorer runs offline on held-out truth. |
| SIM-01 — edge budget | **Test**: the §3.1 spike, plus a sustained-run confirmation. |

### 5.4 Validation / Acceptance — verifies the ConOps

Does the system do the mission the ConOps describes? Validation is **scenario-driven**, running the ConOps vignettes as acceptance tests.

- **Nominal mission (ConOps §11.1):** *"Search along the Monaro Highway and report any vehicles."* Demonstrate the full **detect → observe → act** cycle: bootstrap from the prior map, transit, search along the feature, detection interrupt, VLM assessment, delegated orbit-and-hold observation, closing validate/reject/inconclusive action, resume, and autonomous RTL on completion (MIS-08, NAV-01/02/03, ACT-01).
- **Off-nominal cases (ConOps §11.2):** each is an acceptance scenario — feature-not-confirmed / off-course escalation; bootstrap ambiguity; inconclusive observation with bounded re-observation (ACT-03); ambiguous classification; high position-uncertainty (observe-to-reduce); multiple candidates (one observation at a time); track-lost; target-outpaces-orbit; perception fault; stale registry; detection in an inadmissible state.
- **Operator flow (ConOps §12):** health-gated launch (SAF-06), side-by-side *perceived* vs. *decided* observability (LOG-01/02/04), operator abort (SAF-07), and post-run review from the archive (LOG-03).

**The research payload.** Acceptance here is not a single pass/fail. The mission-meaningful product is each target's **validate / reject / inconclusive** outcome, scored against **held-out** ground truth (SIM-04, INT-01) — with *inconclusive* counted as an abstention distinct from hit/miss. The primary validation question is the increment's research question: *what can the 2B VLM do as a mission planner with perception grounding?* — measured, not asserted. The label-on/off knob (MAP-03b) is a validation variable: runs with and without labels measure how much competence is spatial reasoning vs. label-reading.

## 6. Pinning the Deferred Bounds (since L1 is descoped)

The L0 Open Items list TBD bounds that a formal L1 pass would have set. Because most can only be learned by measurement, they are pinned **during the test campaign** and recorded in a **values ledger** (a small tracked table of `bound → value → how it was set → date`). Each starts at a seeded value and is tuned against observed behavior:

| Bound | Requirement(s) | How it gets set |
|---|---|---|
| Geo-location accuracy | PER-08 | Analysis (error budget) + measurement vs. ground truth in the geo-projector unit tests. |
| Detection-interrupt confidence | EVT-01 | Tuned in integration against false-interrupt vs. missed-detection rates on authored scenarios. |
| Slow-mover speed bound | PER-07 / TSK-03 | Set against the orbit-able limit found in observation-control integration tests. |
| Staleness / persistence / non-confirmation thresholds | PER-06 / TSK-05 / NAV-05 | Tuned against track-update cadence and escalation responsiveness. |
| "Objective satisfied" completion criterion | MIS-08 | Defined and demonstrated in validation missions. |
| Map-view legibility criterion | MAP-02 | A label read-back / element-contrast test defined in renderer unit tests. |
| Validate / reject / inconclusive criteria | ACT-01 | The research payload — defined via prompt engineering + the scoring harness, exercised in validation (§5.4). |
| Perception liveness/heartbeat signal | SAF-06 | Chosen in Stage 3 (e.g., snapshot freshness) and verified by the health-gate test. |
| TRANSIT detection-admissibility | EVT-02 | Decided and tested in the event-gate integration cases. |

## 7. Test Infrastructure & Environment

- **Two cleanly separated halves (ConOps §12.2):** simulation (Gazebo world + sensors, ArduPlane SITL) on the workstation; the flight stack (perception + reasoning) on flight-representative **edge** hardware. The edge constraint is discipline, not convenience — it keeps the sim honest about flight viability (SIM-01).
- **Authored scenarios (SIM-02):** Canberra-area 3D worlds with placed, perceivable entities (static or slow-moving) — targets to detect and landmarks to confirm.
- **Reproducibility (SIM-03):** identical authored content + seeded initial conditions yield comparable runs; deterministic replay of stochastic perception is *not* required this increment.
- **Held-out scorer (SIM-04, INT-01):** compares perceived world-state and target outcomes against authored truth **offline**, outside the system under test. Truth never enters the SUT — this is verified by inspection, not assumed.
- **Run archive as the evidence store (LOG-03):** per-run config/prompts/scenario ref, decision log, separate perception log, the imagery the VLM saw, and each target's outcome — all on a shared clock (LOG-04). The archive is where verification evidence and validation results both land.
- **Nadir-before-active gate (§4):** active pointing is not enabled in test until the geo-projector is proven in stabilized-nadir.

## 8. Phasing, Entry & Exit

| Phase | Entry | Exit (gate) |
|---|---|---|
| **Spikes** (§3) | Left arm baselined | Edge budget fits (or mitigation chosen); gimbal-MAVLink and runtime confirmed |
| **Build Stage 0–2** (§4) | Spikes passed | Perception + registry + renderers pass unit tests; geo-projector proven in nadir |
| **Build Stage 3–5** (§4) | Stages 0–2 done; Grafts A–C planned | Spine extensions + observation control + logging integrated; Grafts A–C landed |
| **System Verification** (§5.3) | Integration green | All 62 L0 requirements verified (App. A); invariant/safety set passed |
| **Validation** (§5.4) | System verification passed | ConOps nominal + off-nominal vignettes demonstrated; research scoring produced |

**Baseline gate.** The increment is not baselined until the three hardening grafts (A–C) are landed and the invariant/safety set (§5.3) passes — architecture §7.

## 9. Deferred / Out of Scope

- **Formal L1 requirements** — descoped as disproportionate (§2); bounds pinned in test (§6).
- **TensorRT backend, real-hardware HIL** — later increments (project upgrade path).
- **ConOps §8 deferrals** — GPS-denied / map-matching navigation, terrain following, forward-looking acquisition, fast-mover intercept, multi-camera / stereo, track-mode semantics. Any of these moving the camera *into* the safety loop is explicitly a separate, later effort.

## 10. Traceability

- **Right-arm → left-arm** correspondence is the table in §2; each verification level (§5.1–§5.4) names the artifact it verifies.
- **Requirement → verification** is the matrix in **Appendix A** (all 62 L0 IDs), the companion to architecture Appendix A (requirement → component).
- **Deferred bounds → resolution** is the ledger in §6.

---

## Appendix A — Requirements Verification Matrix

Method: **T** = Test, **A** = Analysis, **D** = Demonstration, **I** = Inspection. Level: primary level at which the requirement is verified (Unit / Integ / System / Valid). Requirements whose bound is TBD are verified with the seeded value and re-checked when the ledger value (§6) is set.

| ID | Method | Level | Verification approach |
|---|---|---|---|
| L0-MIS-01 | D | Valid | Run a mission from a natural-language objective end-to-end. |
| L0-MIS-02 | D+I | Valid | Demonstrate mission decisions originate from the VLM; inspect the decision path. |
| L0-MIS-03 | T | Unit | Schema-validate every decision as structured command + reasoning field. |
| L0-MIS-04 | T | Integ | Drive state transitions; assert mission state persists across the flight. |
| L0-MIS-05 | I+T | System | Inspect that no raw-frame path reaches the VLM; test its only image input is the map view. |
| L0-MIS-06 | T | Integ | Assert the VLM is invoked only on events/decision points, never on a timer. |
| L0-MIS-07 | T | Integ | Assert accumulated decision + world context is present in each invocation. |
| L0-MIS-08 | D | Valid | Demonstrate autonomous RTL/land on declared completion (criterion per §6). |
| L0-PER-01 | T | Integ | Assert perception runs at its own cadence while reasoning is idle. |
| L0-PER-02 | T | System | Detect/classify with class + confidence, scored vs. held-out truth. |
| L0-PER-03 | T+A | Unit | Geo-locate against known geometry; error within budget. |
| L0-PER-04 | T | Unit | Persistent unique track IDs across frames. |
| L0-PER-05 | T | Unit | Position covariance represented; never rendered as exact. |
| L0-PER-06 | T | Unit | Stale tracks expire/flag at the (seeded) staleness threshold. |
| L0-PER-07 | T | Unit | Velocity estimated within the (seeded) slow-mover bound. |
| L0-PER-08 | A+T | System | Accuracy budget (analysis) confirmed by measurement vs. ground truth. |
| L0-PER-09 | T | Integ | Confirm/deny expected prior-map feature beneath the aircraft. |
| L0-PER-10 | T | Unit | Boresight-range geo-loc of the gimbal-centered target; no flat-ground assumption. Nadir-first. |
| L0-PER-11 | T | Unit | Nadir AGL maintained independent of gimbal; used for off-axis fallback. |
| L0-TSK-01 | T | Integ | Reasoning layer tasks an observation on a specific registry track. |
| L0-TSK-02 | T | Integ | Observation runs as delegated closed-loop control with no reasoning calls during the loop. |
| L0-TSK-03 | T | Integ | Orbit + sensor stay centered on a live, updating slow-mover position. |
| L0-TSK-04 | T | Unit | Bounded termination fires even on an undecided outcome. |
| L0-TSK-05 | T | Integ | Un-continuable observation escalates within the (seeded) persistence bound. |
| L0-TSK-06 | T | Unit | At most one observation active (concurrency guard). |
| L0-TSK-07 | I+T | Unit | Tasking references are symbolic registry IDs, never pixels/appearance. |
| L0-EVT-01 | T | Integ | Threshold detection interrupts current activity and invokes reasoning. |
| L0-EVT-02 | T | Integ | State-admissibility matrix honored; suppressed detections retained. |
| L0-EVT-03 | T | Integ | Detection during observation persisted, does not preempt. |
| L0-SAF-01 | I | System | Only high-level MAVLink emitted; no control-surface commands. |
| L0-SAF-02 | I+T | System | Perception holds no MAVLink handle; cannot command flight. |
| L0-SAF-03 | T | System | Drain jitter flat with perception hot and stalled. |
| L0-SAF-04 | T | System | Perception killed → "no detections"; mission continues. |
| L0-SAF-05 | T | System | Reasoning/parse/flight-input failures → RTL/hold. |
| L0-SAF-06 | T | Integ | No arm unless reasoning + perception report healthy. |
| L0-SAF-07 | T+D | Valid | Operator abort commands RTL/hold at any time. |
| L0-SAF-08 | T | Integ | Feed-loss mid-observation → hold last orbit + escalate; watchdog independent of feed. |
| L0-IFC-01 | I | System | Interfaces are exactly MAVLink + inbound camera; emits only MAVLink. |
| L0-IFC-02 | A+I | System | Boundary inspection + gimbal-MAVLink spike; swap changes nothing inside. |
| L0-INT-01 | I | System | No authored ground-truth path into any part of the SUT. |
| L0-LOG-01 | T | Integ | Every decision logged with command + reasoning. |
| L0-LOG-02 | T | Integ | Perception output logged on a separate stream. |
| L0-LOG-03 | T | System | Per-run archive holds config, logs, imagery, outcomes. |
| L0-LOG-04 | T | Integ | Decisions and perception outputs share a clock and correlate. |
| L0-SIM-01 | T | System | Edge-budget spike (§3.1) + sustained-run confirmation. |
| L0-SIM-02 | D | Infra | Author a scenario with placed perceivable entities; confirm perceivable. |
| L0-SIM-03 | T | Infra | Same seed twice → comparable runs. |
| L0-SIM-04 | I+D | System | Held-out scorer runs offline; truth never enters the SUT. |
| L0-NAV-01 | D | Valid | Run a feature-referenced search mission. |
| L0-NAV-02 | D+T | Valid | Bootstrap navigation toward the feature from the prior map. |
| L0-NAV-03 | D | Valid | Navigate by reasoning over the map view at routine decision points. |
| L0-NAV-04a | I+T | Integ | Perception-grounding enters as advisory input only. |
| L0-NAV-04b | I | System | GPS + prior map authoritative; perception structurally cannot override. |
| L0-NAV-05 | T | Integ | Unconfirmed-feature surfaced; escalates past the (seeded) persistence bound. |
| L0-ACT-01 | D | Valid | Each observation concludes with validate/reject/inconclusive (criteria per §6). |
| L0-ACT-02 | T | System | Outcome recorded as a first-class gradeable result. |
| L0-ACT-03 | T | Integ | Bounded re-observations, then inconclusive + resume. |
| L0-MAP-01 | T | Unit | Prior reference map present from mission start. |
| L0-MAP-02 | I+T | Unit | Map view is vector primitives, not raster; legibility read-back (§6). |
| L0-MAP-03a | T | Unit | Labels restricted to legitimately-known features. |
| L0-MAP-03b | T | Unit | Label layer toggles on/off. |
| L0-MAP-04 | I | Unit | Coordinate math uses full-fidelity geometry, never the schematic view. |
