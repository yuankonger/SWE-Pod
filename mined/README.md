# Mined tasks (experimental)

A mined task is a real repository at a real commit, graded by that repository's own tests at a later commit.
Nothing here is written for the task: the code, the tests and the description of the work are the project's.

    mined/<task>/task.json      the repository, the two commits, what the agent is handed, how tests are run
    mined/<task>/Dockerfile     the environment: the project's toolchain and locked dependencies, no source
    tools/mined_pilot.py        prepare a workspace, run an agent on it through the kernel, score the result

The repository itself is not kept here. `tools/mined_pilot.py` takes the path of a clone.

What the agent gets: the base commit's tree with no history, the work described in the project's own words, the
public API contract at the target (for Saleor, `schema.graphql`), and the shared test fixtures at the target.
The fixtures are handed over because the project's tests cannot start without the names they import: they are
the test side's contract. The test files themselves stay hidden.

The reward is the share of new tests passed (tests that pass at the target and not at the base) times the share
of preserved tests passed (tests that pass at both), over the project's whole suite.

Only permissively licensed repositories are used. Saleor is BSD-3-Clause.
