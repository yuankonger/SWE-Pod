"""Model clients for the stand-in harness.

A client turns (system, tools, messages) into a Reply. `AnthropicModel` calls Claude through the official SDK;
`ScriptedModel` plays fixed tool calls, for testing the kernel and for the oracle team (no tokens).
"""
import itertools
from dataclasses import dataclass, field

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


@dataclass
class Reply:
    content: list            # goes back into the conversation unchanged as the assistant turn
    tool_uses: list          # [{"id", "name", "input"}]
    text: str
    stop_reason: str
    usage: dict = field(default_factory=dict)
    logged: list = field(default_factory=list)  # JSON-safe copy of `content` for the event log


def total_tokens(usage: dict) -> int:
    """What one call draws from the shared budget: every token read or written, cached or not."""
    return sum(int(usage.get(k) or 0) for k in USAGE_KEYS)


class ModelRefused(RuntimeError):
    """The model declined the request (stop_reason "refusal"): the episode is invalid, not a score."""


class AnthropicModel:
    """One Messages API call per turn. The conversation prefix is cached; thinking is adaptive (the default)."""

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "high", max_tokens: int = 16000):
        import anthropic  # imported here so scripted runs need neither the SDK nor credentials

        self.client = anthropic.Anthropic(max_retries=4)
        self.model, self.effort, self.max_tokens = model, effort, max_tokens

    def call(self, agent: str, system: str, tools: list, messages: list) -> Reply:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=messages,
            cache_control={"type": "ephemeral"},  # caches the conversation so far; each turn only appends
            output_config={"effort": self.effort},
        )
        if response.stop_reason == "refusal":
            raise ModelRefused("{} refused: {}".format(agent, getattr(response, "stop_details", None)))
        uses = [{"id": b.id, "name": b.name, "input": b.input} for b in response.content if b.type == "tool_use"]
        text = "\n".join(b.text for b in response.content if b.type == "text")
        usage = {k: int(getattr(response.usage, k, 0) or 0) for k in USAGE_KEYS}
        return Reply(content=response.content, tool_uses=uses, text=text, stop_reason=response.stop_reason,
                     usage=usage, logged=[b.model_dump(mode="json") for b in response.content])


class ScriptedModel:
    """Plays a fixed script per agent: a list of turns, each a list of (tool name, input) pairs.

    When an agent's script runs out it ends its turn with text and no tool call.
    """

    def __init__(self, scripts: dict, tokens_per_call: int = 0):
        self.scripts = {a: list(turns) for a, turns in scripts.items()}
        self.tokens_per_call = tokens_per_call
        self._ids = itertools.count(1)

    def call(self, agent: str, system: str, tools: list, messages: list) -> Reply:
        turns = self.scripts.get(agent) or []
        calls = turns.pop(0) if turns else []
        content = [{"type": "text", "text": "(scripted)"}]
        uses = []
        for name, args in calls:
            use = {"type": "tool_use", "id": "scripted_{}".format(next(self._ids)), "name": name, "input": args}
            content.append(use)
            uses.append({"id": use["id"], "name": name, "input": args})
        usage = {k: 0 for k in USAGE_KEYS}
        usage["output_tokens"] = self.tokens_per_call
        return Reply(content=content, tool_uses=uses, text="(scripted)", stop_reason="tool_use" if uses else "end_turn",
                     usage=usage, logged=content)
