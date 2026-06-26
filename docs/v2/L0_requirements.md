# L0 System Requirements — V2.0 ("Sight" Increment)

## Document Control
- Version: 0.3
- Status: Draft
- Applies to: V2.0 increment, SITL + Gazebo simulation phase only
- Last updated: 2026-05-08

> Second left-arm artifact of the V2.0 increment, derived from the ConOps ([conops.md](conops.md)).
> **L0** requirements address the system as a whole. They are used to define the system
> architecture and to derive lower-level (L1+) requirements. Each requirement traces to the
> ConOps section(s) it satisfies (the `Trace` column refers to `conops.md` section numbers).
>
> v0.3 incorporates the findings of the L0 systems-engineering review (gap closure, requirement
> splits, term quantification deferred to Open Items, and traceability fixes).

## Conventions
- "SHALL" denotes a binding requirement.
- "The system" means the autonomy stack as defined in the ConOps (the Mission Manager, perception, and reasoning together — everything that is neither the autopilot nor the simulated world).
- "Routine decision point" means a non-interrupt point during mission execution at which the reasoning layer is invoked — e.g., a waypoint reached, a leg or segment completed, or a mission-state transition. (Distinct from an interrupt-driven invocation such as a detection.)
- IDs are stable: `L0-<CAT>-NN`. Retired IDs are not reused.

---

## 1. Mission & Reasoning (MIS)

| ID | Requirement | Trace |
|---|---|---|
| L0-MIS-01 | The system SHALL execute missions defined by a natural-language objective. | §12, §11 |
| L0-MIS-02 | The system SHALL use a vision-language model as the mission-level decision authority. | §2, §3 |
| L0-MIS-03 | The system SHALL express each mission decision as a structured command carrying a machine-readable reasoning field. | §11, §12 |
| L0-MIS-04 | The system SHALL maintain mission state across a flight. | §2 |
| L0-MIS-05 | The reasoning layer SHALL reason over a distilled map view derived from the world model and SHALL NOT be given raw camera frames. | §1, §3 |
| L0-MIS-06 | The system SHALL invoke the reasoning layer at decision points, not continuously or on a timer. | §2, §3 |
| L0-MIS-07 | The system SHALL provide accumulated decision and world context to the reasoning layer at each invocation. | §2, §11 |
| L0-MIS-08 | The system SHALL autonomously return to launch and land when the reasoning layer declares the mission objective satisfied, or on operator abort. | §11.1, §12 |

## 2. Perception (PER)

| ID | Requirement | Trace |
|---|---|---|
| L0-PER-01 | The system SHALL continuously perceive from the onboard camera stream, independent of the reasoning layer's cadence. | §3 |
| L0-PER-02 | The system SHALL detect and classify targets and landmarks, assigning each a class and confidence. | §7, §1 |
| L0-PER-03 | The system SHALL geo-locate detections into geodetic coordinates from sensor data and aircraft pose. | §5 |
| L0-PER-04 | The system SHALL maintain persistent, uniquely identified tracks for detected entities. | §6, §7 |
| L0-PER-05 | The system SHALL represent each track's position uncertainty and SHALL NOT present an uncertain position as exact. | §11.2 |
| L0-PER-06 | The system SHALL expire or flag stale tracks, using a defined and bounded staleness threshold, so out-of-date world state is not presented as current. | §11.2 |
| L0-PER-07 | The system SHALL estimate kinematic state (velocity) for tracked targets within the slow-mover speed bound (value TBD, derived at lower level). | §7 |
| L0-PER-08 | Geo-location accuracy SHALL meet a bound sufficient for the reasoning layer to act on (value TBD, derived at lower level). | §10 |
| L0-PER-09 | The system SHALL confirm prior-map features against the camera view, producing a confirmed-or-not result for whether an expected feature is present beneath the aircraft. | §7, §11.2 |
| L0-PER-10 | The system SHALL geo-locate the observed (gimbal-centered) target using the measured boresight range along the camera line of sight, without assuming a flat ground plane. | §5, §10 |
| L0-PER-11 | The system SHALL maintain a current nadir above-ground-level (AGL) height from the laser altimeter, independent of gimbal pointing, and SHALL use it as the ground-plane height for off-axis detections that fall back to ground-plane projection. | §5, §10 |

## 3. Sensor Tasking / Attention (TSK)

| ID | Requirement | Trace |
|---|---|---|
| L0-TSK-01 | The reasoning layer SHALL be able to task the sensor to observe a specific track held in the registry. | §6 |
| L0-TSK-02 | The system SHALL carry out an observation as delegated closed-loop control — the aircraft orbiting the target and the sensor holding it centered — without reasoning-layer involvement for the duration of the loop. | §6, §11 |
| L0-TSK-03 | The system SHALL keep the orbit and the sensor centered on a slow-moving target's live, continuously-updated position throughout an observation (slow-mover bound per PER-07). | §7 |
| L0-TSK-04 | Every observation SHALL have a defined, bounded termination condition, guaranteed to fire even when the target outcome is undecided. | §10, §11.3 |
| L0-TSK-05 | The system SHALL escalate to the reasoning layer when an observation cannot continue (target lost or un-observable), judged against a defined, bounded persistence threshold. | §6, §11.2 |
| L0-TSK-06 | The system SHALL conduct at most one observation at a time. | §11.2 |
| L0-TSK-07 | Sensor-tasking and target-selection references issued by the reasoning layer SHALL be symbolic registry references, not pixel coordinates or appearance descriptions. | §6 |

## 4. Decision Triggers (EVT)

| ID | Requirement | Trace |
|---|---|---|
| L0-EVT-01 | The system SHALL invoke the reasoning layer when a detection meets the configured detection-interrupt confidence threshold (value TBD, derived at lower level), interrupting the current activity rather than waiting for the next routine decision point — except during an in-progress observation (see EVT-03). | §11.1, §11.3 |
| L0-EVT-02 | The system SHALL gate detection-triggered interrupts by mission state: admissible in ON_TASK, suppressed in TAKEOFF and RETURNING, TRANSIT-admissibility TBD. Suppressed or deferred detections SHALL NOT be discarded. | §11.3, §11.2 |
| L0-EVT-03 | A detection occurring while an observation is in progress SHALL be registered and persisted in the registry for later consideration but SHALL NOT preempt the running observation. | §11.2, §11.3 |

## 5. Safety & Degradation (SAF)

| ID | Requirement | Trace |
|---|---|---|
| L0-SAF-01 | The system SHALL delegate all low-level flight control to the autopilot and SHALL NOT issue control-surface commands. | §2 |
| L0-SAF-02 | The system SHALL keep perception out of the flight-safety loop in this increment: perception outputs SHALL NOT command flight control. (Perception's advisory role and the GPS/prior-map authority hierarchy are stated in NAV-04a/04b.) | §7, §9 |
| L0-SAF-03 | Continuous perception SHALL NOT block or stall the autopilot telemetry/command path. | §9 |
| L0-SAF-04 | A perception failure SHALL degrade to "no detections" and SHALL NOT disable the mission-management function. | §9 |
| L0-SAF-05 | The system SHALL fall back to a safe default (e.g., RTL or hold) on reasoning failure, command-parse failure, or loss of a flight-required input (autopilot telemetry / MAVLink link). Loss of advisory perception is handled per SAF-04, not here. | §9, §11.2 |
| L0-SAF-06 | The system SHALL NOT begin a mission unless the required reasoning and perception services report healthy — the reasoning backend reachable and returning a well-formed response within a timeout, and perception producing frames/heartbeat. | §9, §12 |
| L0-SAF-07 | The system SHALL allow the operator to abort the mission (command RTL/hold) at any time. | §12 |
| L0-SAF-08 | If perception or its registry feed fails while an observation is in progress, the delegated-control loop SHALL fail safe by holding the last commanded orbit, and SHALL escalate the loss to the reasoning layer. | §11.2, §9 |

## 6. Interfaces & Sim/Real Boundary (IFC)

| ID | Requirement | Trace |
|---|---|---|
| L0-IFC-01 | The autonomy stack SHALL interface with its environment only via MAVLink (telemetry from, and commands to, the autopilot) and an inbound camera-frame stream, and SHALL emit only MAVLink. | §9 |
| L0-IFC-02 | Replacing the simulated autopilot, world, or camera with real equivalents SHALL require no change inside the autonomy stack. | §9 |

## 7. Integrity (INT)

| ID | Requirement | Trace |
|---|---|---|
| L0-INT-01 | The system SHALL derive all world knowledge from its sensor and telemetry streams. Authored scenario ground-truth SHALL NOT be supplied to any part of the system as input — including via the sensor streams, the world model, or the reasoning layer's prompts. | §9, §12.1 |

## 8. Observability & Logging (LOG)

| ID | Requirement | Trace |
|---|---|---|
| L0-LOG-01 | The system SHALL log every reasoning decision together with its issued command and the reasoning behind it. | §11, §12 |
| L0-LOG-02 | The system SHALL log perception output (detections and tracks) separately from reasoning decisions, so the two can be reviewed independently. | §12.2 |
| L0-LOG-03 | The system SHALL archive, per run, the mission configuration (objective, prompts, scenario reference) together with the decision and perception logs, the imagery the system reasoned over, and the mission outcome (including each observed target's validate/reject/inconclusive result). | §12.2 |
| L0-LOG-04 | All logged decisions and perception outputs SHALL be timestamped and mutually correlatable, so the perceived world-state and the decisions taken can be aligned in time during review. | §12.2 |

## 9. Simulation & Test (SIM)

| ID | Requirement | Trace |
|---|---|---|
| L0-SIM-01 | The flight stack (perception + reasoning) SHALL be demonstrated within a flight-representative edge compute, power, and memory budget. | §10, §12 |
| L0-SIM-02 | The system SHALL support authored scenarios with placed, perceivable entities (static or slow-moving) in a 3D world. | §12 |
| L0-SIM-03 | Scenarios SHALL be reproducible: identical authored content and seeded initial conditions yield comparable runs. (Deterministic replay of stochastic model/perception components is not required in this increment.) | §12.2 |
| L0-SIM-04 | The system SHALL support a held-out scoring path comparing perceived world-state and target action outcomes (validate/reject/inconclusive) against authored ground-truth, subject to L0-INT-01 (truth never exposed to the system). | §12.1 |

## 10. Mission Execution / Navigation (NAV)

| ID | Requirement | Trace |
|---|---|---|
| L0-NAV-01 | The system SHALL support missions that reference a feature carried in the prior map and search along or within it. | §7 |
| L0-NAV-02 | The system SHALL bootstrap navigation toward a referenced feature using the prior reference map. | §7, §11.1 |
| L0-NAV-03 | The system SHALL navigate to execute the mission objective by reasoning over the map view, issuing navigation commands at routine decision points. | §7, §11.1 |
| L0-NAV-04a | The system SHALL use perception-grounding as advisory input to navigation. | §7 |
| L0-NAV-04b | GPS and the prior reference map SHALL remain authoritative for flight; perception SHALL NOT override them. | §7 |
| L0-NAV-05 | The system SHALL surface unconfirmed-feature conditions (from PER-09) to the reasoning layer and escalate when non-confirmation persists beyond a defined, bounded threshold. | §11.2 |

## 11. Action / Loop Closure (ACT)

| ID | Requirement | Trace |
|---|---|---|
| L0-ACT-01 | The system SHALL conclude each completed observation with a reasoning-layer action on the target: validate, reject, or inconclusive. | §7, §11.1 |
| L0-ACT-02 | Each observed target's action outcome SHALL be recorded as a first-class result with validate/reject/inconclusive (hit / miss / abstention) semantics for grading (scoring path per SIM-04). | §11.3, §12.1 |
| L0-ACT-03 | When an observation terminates without meeting the validate or reject criteria, the system SHALL permit a bounded number of re-observations of the same target; once that bound is exhausted it SHALL record the target as inconclusive, defer it, and resume the mission. The system SHALL NOT stall on an unresolved target. | §11.2, §11.3 |

## 12. Map & Rendering (MAP)

| ID | Requirement | Trace |
|---|---|---|
| L0-MAP-01 | The system SHALL maintain a prior reference map providing standing geography (roads, terrain, named features) available from mission start. | §3 |
| L0-MAP-02 | The map view presented to the reasoning layer SHALL be rendered from vector / map-data primitives, not a raster map tile. (A measurable legibility criterion is deferred to L1 — see Open Items.) | §3 |
| L0-MAP-03a | The map view SHALL label only features the system legitimately knows (prior-map features and perception-confirmed detections). | §3 |
| L0-MAP-03b | Label rendering SHALL be selectable (on/off) to support with/without-labels experimentation. | §3 |
| L0-MAP-04 | Coordinate computation (geo-projection and command execution) SHALL use full-fidelity geometry, not the schematic map view. | §3 |

---

## Summary

| Category | Prefix | Count |
|---|---|---|
| Mission & Reasoning | MIS | 8 |
| Perception | PER | 11 |
| Sensor Tasking / Attention | TSK | 7 |
| Decision Triggers | EVT | 3 |
| Safety & Degradation | SAF | 8 |
| Interfaces & Sim/Real Boundary | IFC | 2 |
| Integrity | INT | 1 |
| Observability & Logging | LOG | 4 |
| Simulation & Test | SIM | 4 |
| Mission Execution / Navigation | NAV | 6 |
| Action / Loop Closure | ACT | 3 |
| Map & Rendering | MAP | 5 |
| **Total** | | **62** |

## Open Items (to resolve at lower levels)
- **L0-PER-08** — geo-location accuracy bound is TBD; to be quantified when L1 requirements are derived (the ConOps sets it qualitatively via a "forgiving consumer").
- **L0-EVT-01** — detection-interrupt confidence threshold is TBD (derived at L1).
- **L0-MIS-08** — the "objective satisfied" completion criterion is TBD (derived at L1).
- **L0-PER-07 / L0-TSK-03** — the slow-mover speed bound is TBD, defined against the orbit-able limit (derived at L1).
- **L0-PER-06 / L0-TSK-05 / L0-NAV-05** — the staleness / persistence / non-confirmation thresholds are TBD (derived at L1).
- **L0-EVT-02** — detection admissibility during TRANSIT is TBD.
- **L0-MAP-02** — a measurable map-view legibility criterion (e.g., element-class bounds, line-contrast, label read-back test) is TBD at L1.
- **L0-ACT-01** — the validate / reject criteria and the inconclusive boundary are TBD; to be defined at the lower level.
- Reasoning-backend pluggability is treated as a design quality (architecture arm), not an L0 requirement.
- The stabilized-nadir-before-active-pointing validation sequence is an implementation/verification-plan item (right arm of the V), not an L0 requirement.
- Host separation of the flight stack from the simulation host (the deployment topology behind L0-SIM-01) is a design/architecture-arm concern, not an L0 requirement.
