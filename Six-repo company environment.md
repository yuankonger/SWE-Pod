# Six-repo company environment

Nov 13, 2026 · @Lilin

## Overview

The environment is one substrate, and solo, fixed team and lead-decides are three configurations of it. Six real repos run as deployed services, one image per repo. Agents work in separate workspaces and reach the services only through shared sidecars: they push code and exchange messages, and the sidecars deploy from main.

## Architecture

&#91;embedded content: environment architecture · 3 groups, 2 flows\]

Agents push code and send messages to the sidecars, and the sidecars deploy the six services from main. The git server is where write access is enforced.

## Tasks

Tasks come from two sources, because the repos' real history contains only single-repo work.

- **Single-repo tasks** are mined from commit history.
- **Cross-repo tasks** are synthesized from templates.
- **Integration glue** between the repos is written new and has no history.
- **Each task** starts only the services it touches.

## Evaluation

The three configurations are compared on the same tasks, with the same hidden end-to-end verifier.

- **Budget:** each condition gets an equal total token budget.
- **Stratification:** results are split by how tightly a task couples the repos.
- **Repeats:** each task runs with several seeds.
- **Process metrics:** messages, duplicated work and conflicts are tracked alongside success.

## Roles and permissions

Permissions are always set by the environment; roles are prescribed in one configuration and left to the agent in another.

- **Lead decides** is the target policy and the headline result.
- **Fixed roles** serve as the curriculum and as a diagnostic.
- **Team shape** varies across runs: two, three or six owners.
