# Prompt Design

## Document Control
- Version: 0.1
- Status: Draft
- Last updated: 2026-06-01

## Vision Is Functional — But Only If the Prompt Doesn't Short-Circuit It

Gemma 4 E2B vision is confirmed working on Pennyroyal. Direct curl tests show the model can read place names off saved debug maps, identify the aircraft marker, and locate the mission start position. The image is reaching the model and being processed.

However, if the prompt contains a textual description of the map's structure, the model has no incentive to use the image. It will solve the task by reading the text and doing arithmetic, and the visual input becomes irrelevant.

## What Constitutes a Textual Answer Key

Any of the following in the system or user prompt gives the model enough information to navigate without looking at the image:

- Naming specific landmarks: `"the Monaro Highway runs north-south through the center of the map"`
- Listing explicit pixel targets: `"fly west to approximately x=256"`
- Describing map structure verbosely: `"the road runs through the center at approximately x=240-260"`
- Phase-by-phase scripts embedded in the objective string that include road names or coordinates

## Current Prompt Strategy

Named landmarks and explicit coordinate targets have been removed from all active prompts. The prominent north-south road is referred to only as "the prominent road that runs north-south through the area". The model must locate it in the image.

The system prompt requires two grounding steps before a command can be issued:

1. Describe what is visible at the aircraft's current position (terrain, roads, landmarks).
2. Describe what is visible at the intended destination.

This forces the model to produce a visual description before committing to coordinates. It increases thinking-token usage — a single decision typically consumes 400–1000 thinking tokens — but produces more traceable reasoning.

The mission objective in `main.py` is a short high-level goal with no landmark names or phase coordinates. Phase descriptions live only in `prompts/waypoint_reached.txt`.

## Prompt Files and Their Roles

| File | Trigger | Notes |
|---|---|---|
| `prompts/system_prompt.txt` | Every request | Sets coordinate system, grounding requirements, output schema |
| `prompts/transit_started.txt` | First waypoint reached after takeoff | Sends the model east to begin the pattern |
| `prompts/waypoint_reached.txt` | Each subsequent waypoint reached | Contains the phase list; references road visually only |
| `prompts/stuck.txt` | STUCK state entry | Asks model to identify a new destination from the image |

## Caveats

- A 2B-parameter edge model will sometimes confabulate visual descriptions. The string `(Simulated based on the provided image)` has been observed in chain-of-thought. Treat self-reported visual reasoning as a signal, not ground truth, and cross-check against debug maps in `mission_manager/debug/maps/<run_id>/`.
- Removing the answer key raises the bar for the model. Regressions in task completion rate are expected and are informative — they reveal the gap between what the model can do with text hints vs. genuine visual reasoning.
- Thinking mode is enabled with a 3000-token budget. If the model runs out of tokens before emitting JSON, the backend logs a warning and the planner falls back to RTL.
