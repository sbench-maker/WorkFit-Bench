# Mosaic research brief

This is a deterministic, fictional lab snapshot dated 2026-08-31. It is an ideation pack, not a literature corpus and not a claim about real deployments.

## Research challenge

Mosaic operates 96 indoor delivery robots across 12 warehouse-like sites. Each robot must continually adapt a visual safety-and-anomaly detector as lighting, layout, cameras, packaging, and rare incident classes change. The current recipe is a 32 MB replay buffer, an int8 shared backbone, local pseudo-labeling, and nightly federated averaging. The lab has plateaued: mean validation F1 looks stable while rare-incident recall falls under compound and site-transfer drift. Retreat participants need research directions that change the problem or mechanism, not another scale-up, compression pass, or optimizer sweep.

## Non-negotiable deployment envelope

- Raw images never leave a robot.
- Safety alerts must remain below 80 ms p95.
- Adaptation averages no more than 2.0 W over a shift.
- Each robot may upload at most 8 MB per day.

A useful direction can question conventions around these limits but cannot silently violate them. Ideas should be testable with the capabilities in `enablers.csv` or should name a missing dependency explicitly.

## Pack map

- `lab_observations.csv`: frozen local observations (`OBS-*`), including measurements, qualitative findings, and confidence.
- `assumptions.csv`: hard, soft, and hidden assumptions (`ASM-*`) plus linked observations.
- `mechanism_cards.jsonl`: distant-domain mechanisms (`MEC-*`) described by relational structure, transfer affordance, and boundary condition. These are prompts, not authorities.
- `enablers.csv`: currently available prototypes (`ENB-*`) and their limits.
- `prior_ideas.csv`: ideas already tested, rejected, or paused (`IDEA-*`); relabeling one of them is not a new direction.

IDs are the stable citation handles for this snapshot.
