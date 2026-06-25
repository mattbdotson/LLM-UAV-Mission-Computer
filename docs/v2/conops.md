# Concept of Operations — V2.0 ("Sight" Increment)

## Document Control
- Version: 0.1
- Status: Draft
- Applies to: V2.0 increment, SITL + Gazebo simulation phase only
- Last updated: 2026-05-08

> This is the first left-arm artifact of the V2.0 increment (one V per increment).
> System requirements are derived from this ConOps and live in a separate document.

---

## 1. Increment Purpose

V2.0 gives the system sight. V1.0 reasons over a synthetic top-down map; V2.0 adds a gimbaled onboard (simulated) camera and a perception pipeline that turns what the aircraft sees into structured, geo-located inputs the reasoning layer can use. The 2B VLM is never asked to interpret raw, unlabeled camera frames — that is the perception layer's job; the VLM continues to reason over the distilled map view, as it did in V1.0.

## 2. Operational Context

The system is an autonomous fixed-wing UAV capability in which a vision-language model serves as the mission-level autonomy. Functionally it is a stack of logical layers, each a role rather than a fixed piece of hardware:

- **Flight control** — the autopilot. Owns the aircraft's control loops; speaks MAVLink. (In this phase it is simulated.)
- **Mission management** — a harness (the Mission Manager) between the autopilot and the reasoning layer. It ingests telemetry, maintains mission state, recognizes when a decision is due, invokes the reasoning layer, and translates the returned intent into autopilot commands.
- **Reasoning** — the event-driven VLM, called by the harness at decision points to make mission-level choices.
- **Perception (new in V2.0)** — a continuous vision layer that turns the onboard camera stream into a structured world model the reasoning layer can draw on.

The layers are logical, not physical. The reasoning and perception layers run on flight-representative edge hardware; the mission-management harness — and, in this phase, the simulated autopilot and world — run on the workstation. The boundaries between the layers are logical, so the same stack would carry onto a real airframe with only the simulated layers replaced by reality.

## 3. Core Operational Idea — Perception and Reasoning Are Separate Layers

A specialized vision model performs continuous perception; the VLM stays event-driven and reasons over a distilled world model. The VLM never touches raw frames.

## 4. Primary Actors / External Entities

These are the entities *outside* the system boundary (the autonomy stack) that the system interacts with. The system's own internal layers — the mission-management harness, the reasoning layer, and the perception layer — are described in §2 and decomposed in the architecture arm, not listed here.

| Actor | Role |
|---|---|
| Autopilot (ArduPlane SITL) | Owns flight control; speaks MAVLink |
| Simulation (Gazebo) | Provides the simulated world, camera, gimbal, and boresight rangefinder; hosts authored scenarios |
| Operator | Authors missions and scenarios; reviews decision and perception logs |

## 5. Sensor Concept

A single active-pointing gimbaled camera, steerable but operable in a stabilized-nadir subset. A simulated **boresight laser rangefinder**, co-aligned with the camera, measures actual range along the line of sight to whatever the camera observes. Camera pointing is abstracted as a pose-source, so fixed, stabilized, and active modes are configurations rather than rewrites.

The boresight rangefinder collapses geo-projection from "ray ∩ assumed ground plane" to "ray + measured range = point," deleting the flat-ground assumption for the observed target. It subsumes a nadir altimeter — in stabilized-nadir mode the same sensor reports AGL. It measures one ray (the boresight), so it precisely geo-locates the centered/tracked object; off-axis detections elsewhere in the wide frame fall back to ground-plane projection.

## 6. Reasoning-Controls-Attention Concept

The VLM may direct the sensor at the intent level (`observe {track_id}`), expressed over symbolic registry references — never over pixels or appearance. Closed-loop tracking is delegated to the perception/gimbal layer, exactly as flight control is delegated to the autopilot. The VLM issues one intent command; deterministic layers expand it into delegated control (the aircraft orbits the target; the gimbal holds it). Sustained tracking failure escalates back to the VLM as an event, mirroring the V1.0 STUCK pattern.

## 7. Initial Capability Scope

Target and landmark detection first — detections *write to the map* and stay *out of the flight-safety loop*. The aircraft may reason and navigate using detected features, but perception never commands flight control directly in this increment. Observed targets may be **slow-moving**: the registry maintains kinematic tracks, and the autopilot orbit re-centers on a target's live position.

## 8. Explicitly Deferred

- GPS-denied navigation (map-matching), terrain following, and forward-looking acquisition — all move the camera *into* the safety loop; separate, later effort.
- Fast-moving-target pursuit (lead/intercept geometry) — beyond the orbit-with-re-centering maneuver.
- Track *modes* (whether `observe` is a transient command or a sustained mission state).
- Multi-camera arrays / sensor fusion, stereo ranging.
- Real-camera hardware; detection-methodology specifics.

## 9. Guiding Invariants

- **Sim/real boundary is the design.** The autonomy stack — the Mission Manager, perception, and reasoning together, i.e. everything that is neither the autopilot nor the simulated world — sees only a MAVLink stream and a camera-frame stream, and emits MAVLink. Swapping Gazebo for a real aircraft changes nothing inside it.
- **No-answer-key invariant (carried forward from V1.0, corrected for a perception system).** The prohibition lives at the *system boundary*: the simulator's ground truth must never be injected as a shortcut — the system (perception + reasoning *together*) must earn its world knowledge from the sensor streams. Once the perception layer has *legitimately* detected and labeled something, that result may be handed to the VLM in whatever representation is most effective (text, structured fields, or marks on the map). Perception earned it; it is not an oracle leak.
- **Perception cannot stall the safety loop.** Continuous perception must not block the single-owner MAVLink drain, and a perception fault must degrade to "no detections," not a dead Mission Manager.

## 10. Key Constraints & Assumptions

- The flight-representative edge tier — currently a single Jetson Orin Nano Super (8GB unified memory) — runs the perception service and llama-server concurrently; memory/compute contention is acknowledged, and the edge tier may grow to additional units if needed.
- Geo-projection accuracy is bounded by attitude/timing/boresight error; the boresight rangefinder removes the ground-plane modeling error for the observed target. Acceptable accuracy is set by a forgiving consumer (a coarse, event-driven reasoner), since detections are out of the safety loop.
- Validation discipline: the geo-projector is proven in the stabilized-nadir regime before active pointing is enabled.
- Observations run continuous delegated control (the aircraft orbiting the target, the gimbal holding it); every observation must have a defined termination condition (mechanism TBD).

---

## 11. Operational Vignette (System / Mission View) — Patrol, Detect, Observe a Slow-Moving Ground Target

This vignette describes the *aircraft's* behavior during a mission. The operator-side counterpart — how a person stands up and runs a SITL session — is in Section 12.

### 11.1 Nominal Case

1. **Mission underway.** VLM navigates the patrol as in V1.0. Perception service runs on the edge compute alongside llama-server; gimbal in stabilized-nadir; boresight rangefinder reporting range/AGL.
2. **Continuous perception (VLM idle).** Perception detects ground features, geo-locates each via boresight range + pose, and writes geodetic tracks — class, confidence, position, velocity, uncertainty — to the registry. The reasoning layer is not involved.
3. **Detection interrupt.** A track crosses a class/confidence threshold → registry raises `detection` → interrupts the current leg and wakes the planner mid-flight.
4. **VLM assessment.** Planner composes the VLM's map view (map + current tracks, perception labels permitted); VLM reasons "investigate or ignore?" → emits `observe {track_id}` or `continue`.
5. **Tasking expansion (deterministic, no VLM).** The executor expands the single `observe track-7` intent into delegated control — the aircraft orbits track-7's live position and the gimbal holds the target on it — with no further VLM involvement. The rangefinder now measures range-to-target each frame.
6. **Observation.** Aircraft orbits the slowly-moving target, the orbit following the target's live position; the gimbal holds the target; multi-bearing, ranged observations refine its position/velocity and shrink uncertainty.
7. **Termination & resolution.** A defined termination condition ends the observation (mechanism TBD) → the delegated orbit-and-gimbal control is released → VLM decides next: log and resume patrol, or RTL.

### 11.2 Off-Nominal Cases

- **Ambiguous classification.** *Trigger:* a track's class/confidence sits near threshold. *Behavior:* either it stays sub-threshold (perception keeps watching, no interrupt), or it raises and the VLM may task an `observe` specifically to gather more views and let perception firm up the class. *Resolution:* confirmed → nominal; stays ambiguous → VLM `continue`s.

- **High position uncertainty.** *Trigger:* a real detection with a wide position covariance (off-axis, no boresight range, bad pose instant). *Behavior:* it registers *with* its uncertainty, never as a false-precise point; the VLM may receive it flagged low-confidence-position. *Resolution:* observation (orbit + boresight ranging) is the action that *reduces* the uncertainty — high uncertainty is a reason to observe, not a failure.

- **Multiple candidates.** *Trigger:* several tracks cross threshold together. *Behavior:* VLM selects one symbolically (`observe track-7`); the others persist in the registry. Only one observation runs at a time (one gimbal, one aircraft). *Resolution:* VLM may address deferred candidates sequentially.

- **Track lost during observation.** *Trigger:* gimbal/tracker loses the target (terrain occlusion, target out-slews the gimbal, drops below detectability). *Behavior:* perception attempts short-term re-acquisition (coast on last velocity, local search) without waking the VLM. *Resolution:* re-acquired → resume; sustained loss → `track_lost` event → VLM decides search / abandon / RTL. Mirrors STUCK.

- **Target outpaces the orbit.** *Trigger:* target speed approaches the orbit-able limit, or it exits map bounds. *Behavior:* executor detects the loiter geometry degrading and does **not** attempt pursuit (fast-mover intercept is out of scope) → raises `track_lost` (or an `observation_unviable` variant). *Resolution:* VLM abandons the observation and resumes, or RTLs.

- **Perception fault.** *Trigger:* perception crashes, stalls, or stops producing detections. *Behavior:* system degrades to "no detections" — no `detection` events fire; aircraft continues on V1.0 map-based behavior. If it faults mid-observation, the delegated control loses its registry feed → executor fails safe (holds the last commanded orbit) and escalates to the VLM. *Invariant:* must not stall the MAVLink drain or take down the Mission Manager.

- **Stale registry data.** *Trigger:* a referenced track goes stale (no recent perception updates) while the VLM is reasoning over it. *Behavior:* registry TTL/decay flags or expires stale tracks; the VLM's map view does not present stale tracks as current. *Resolution:* an actively-observed track going stale is treated as `track_lost`.

- **Detection in an inadmissible state.** *Trigger:* a `detection` fires during TAKEOFF, RETURNING, or an already-running observation. *Behavior:* the interrupt is admissible only in mission states where acting makes sense (ON_TASK, and TRANSIT TBD); it is suppressed or deferred during TAKEOFF/RETURNING, and a new detection mid-observation is registered but does **not** preempt the current one. *Resolution:* deferred detections persist in the registry for later consideration.

### 11.3 Notes Forward to Requirements

- The `detection` event requires an admissibility gate tied to mission state — it is not a global interrupt.
- **Target-outpaces-orbit** and **track-lost** converge on the same escalation path; they may collapse into a single `track_lost` / `observation_ended` event carrying a reason code rather than two distinct events.
- Every observation requires a defined termination condition; the *mechanism* is deferred (track-mode question), but the *requirement* is firm.

---

## 12. SITL Operations Vignette (Operator View)

This vignette describes how a person stands up and runs a V2.0 SITL session. It is the operator-side counterpart to the system/mission view in Section 11, and it is deliberately mechanism-free — component placement, transports, and IPC boundaries are design-arm decisions derived later, not fixed here.

1. **Author the scenario.** The operator defines a run: a world (the Canberra area as a 3D environment), placed entities to be perceived (targets and landmarks — static or slow-moving), and a mission objective in natural language. This is new in V2.0 — V1.0 reasoned over a fixed map with no perceivable world; V2.0 sessions need an authored world with things in it to detect.

2. **Bring up the session — sim on the workstation, flight stack on flight-representative edge hardware.** The operator stands up two cleanly separated halves:
   - *The simulation side, on the dev workstation:* the simulated world and the autopilot / flight-dynamics simulation — everything that, in real flight, is *replaced by reality* (the actual airframe, the actual world).
   - *The flight stack, on edge compute:* the perception and reasoning capabilities — everything that, in real flight, *carries over unchanged because it physically flies on the aircraft*.

   The self-imposed constraint is that the flight stack runs on **aircraft-representative edge hardware**, not on the workstation's resources. This is deliberate discipline: it would be easier to run perception and reasoning on the dev machine's GPU, but that would let the simulation lie about whether the autonomy is feasible within an airframe's compute, power, and memory budget. By constraining the flight stack to edge-class hardware from the start, the sim stays honest about flight viability — what works in SITL is what could work onboard. The edge tier is treated as a *role*, not a single fixed box: it is the compute that would fly, and it may comprise one or more edge units as the perception + reasoning workload demands.

3. **Launch the mission.** The operator arms and launches; the aircraft takes off and begins flying the objective autonomously.

4. **Watch autonomous operation.** As the aircraft flies, it perceives the world through its sensor, accumulates world-state, and the reasoning layer makes mission decisions. The operator observes two distinct things side by side: **what the system *perceived*** (detections/tracks on the map) and **what the system *decided*** (the command stream with its reasoning).

5. **Observe events, rarely intervene.** Detections fire, the system reacts (investigate / observe / continue), and off-nominal paths play out (stuck, track lost). The operator mostly watches — the point is to see the autonomy behave — but retains the ability to abort.

6. **Mission completes.** The aircraft RTLs and lands, or the operator stops the run.

7. **Review the run.** The operator examines the archived artifacts — the decision log with reasoning, the perception/detection log, the imagery the system saw, and the mission outcome — to understand *why* the system did what it did. This extends V1.0's per-run archiving philosophy to perception.

### 12.1 The Operator Holds the Answer Key; the System Never Sees It

A discipline that is operational, not architectural: the operator authors ground truth (places the targets), but that ground truth exists for **scoring** — comparing what the system perceived against where things actually were — and is *never* fed to the system. The operator knows the answers; the aircraft flies blind and has to earn them. This is the no-answer-key invariant (Section 9) expressed as an operator practice.

### 12.2 Notes Forward to Requirements

- Scenario authoring with placed, perceivable entities (static or slow-moving) in a 3D world.
- Reproducible scenarios, so experiments are comparable across runs.
- Perception observability *separate from* reasoning observability.
- Combined decision + detection logging for post-run review.
- A held-out ground-truth / scoring path that stays out of the system under test.
- The flight stack (perception + reasoning) constrained to flight-representative edge hardware; the sim side (world + autopilot) on the workstation.
