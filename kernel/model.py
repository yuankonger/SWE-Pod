"""Model clients for the stand-in harness.

A client turns (system, tools, messages) into a Reply. `AnthropicModel` calls Claude through the official SDK;
`OpenAIFormatModel` calls a gateway's OpenAI-format endpoint (`/chat/completions`) over plain HTTP;
`ScriptedModel` plays fixed tool calls, for testing the kernel and for the oracle team (no tokens).

Whichever client is used, the conversation the kernel keeps and the event log are in one shape: content blocks
of type `text`, `thinking`, `tool_use` and `tool_result`. A model's reasoning is always logged as `thinking`.
"""
import itertools
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
# Dollars per million tokens: input, output, cache read. Prices are those published on 3 November 2026.
# Writing to the cache costs a multiple of the input price that depends on how long the cache lives: 1.25 for five
# minutes, 2 for an hour. The API reports how many of the written tokens went to the one-hour cache.
# SEEDCO_CACHE_TTL says how this harness marks what to cache: `5m` (default) or `1h` mark the system prompt and the
# conversation so far; `gateway` marks nothing, for a gateway that places its own cache points (a request may
# carry four at most, so the harness's and the gateway's together can be too many).
CACHE_TTL = os.environ.get("SEEDCO_CACHE_TTL", "5m")
CACHE_CONTROL = {"5m": {"type": "ephemeral"}, "1h": {"type": "ephemeral", "ttl": "1h"}, "gateway": None}[CACHE_TTL]
PRICES = {"claude-opus-5-5": (4.00, 20.00, 0.20), "claude-fable-5-2": (8.00, 40.00, 0.20),
          "claude-sonnet-5-5": (2.00, 10.00, 0.10), "claude-haiku-5-5": (0.10, 0.50, 0.01)}


@dataclass
class Reply:
    content: list            # goes back into the conversation unchanged as the assistant turn
    tool_uses: list          # [{"id", "name", "input"}]
    text: str
    stop_reason: str
    usage: dict = field(default_factory=dict)
    cost: float = 0.0        # what this call cost, in dollars: what the shared budget is counted in
    logged: list = field(default_factory=list)  # JSON-safe copy of `content` for the event log


def total_tokens(usage: dict) -> int:
    """Every token one call read or wrote, cached or not. Reported beside the cost; the budget is in dollars."""
    return sum(int(usage.get(k) or 0) for k in USAGE_KEYS)


def dollars(model: str, usage: dict) -> float:
    """What one call cost. Cached reads are cheap and output is dear, so this is not proportional to tokens."""
    if model not in PRICES:
        raise ValueError("no price is known for {}; add it to kernel.model.PRICES".format(model))
    inp, out, read = PRICES[model]
    written, hour = usage.get("cache_creation_input_tokens", 0), usage.get("cache_creation_1h_input_tokens", 0)
    return (usage.get("input_tokens", 0) * inp + ((written - hour) * 1.25 + hour * 2.0) * inp
            + usage.get("cache_read_input_tokens", 0) * read + usage.get("output_tokens", 0) * out) / 1e6


class ModelRefused(RuntimeError):
    """The model declined the request (stop_reason "refusal"): the episode is invalid, not a score."""


class AnthropicModel:
    """One Messages API call per turn. The conversation prefix is cached; thinking is adaptive (the default)."""

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "high", max_tokens: int = 16000):
        import anthropic  # imported here so scripted runs need neither the SDK nor credentials

        dollars(model, {})   # fail now, not after the first call, if the model has no price
        self.client = anthropic.Anthropic(max_retries=4)
        self.model, self.effort, self.max_tokens = model, effort, max_tokens

    def call(self, agent: str, system: str, tools: list, messages: list) -> Reply:
        # with cache points of its own, the harness caches the system prompt and the conversation so far: each turn only appends
        caching = {"cache_control": CACHE_CONTROL} if CACHE_CONTROL else {}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[dict({"type": "text", "text": system}, **caching)],
            tools=tools,
            messages=messages,
            output_config={"effort": self.effort},
            thinking={"type": "adaptive", "display": "summarized"},     # so the reasoning is in the trajectory, not an empty block
            **caching,
        )
        if response.stop_reason == "refusal":
            raise ModelRefused("{} refused: {}".format(agent, getattr(response, "stop_details", None)))
        uses = [{"id": b.id, "name": b.name, "input": b.input} for b in response.content if b.type == "tool_use"]
        text = "\n".join(b.text for b in response.content if b.type == "text")
        usage = {k: int(getattr(response.usage, k, 0) or 0) for k in USAGE_KEYS}
        usage["cache_creation_1h_input_tokens"] = int(getattr(getattr(response.usage, "cache_creation", None), "ephemeral_1h_input_tokens", 0) or 0)
        return Reply(content=response.content, tool_uses=uses, text=text, stop_reason=response.stop_reason,
                     usage=usage, cost=dollars(self.model, usage), logged=[b.model_dump(mode="json") for b in response.content])


class OpenAIFormatModel:
    """One call per turn to an OpenAI-format `/chat/completions` endpoint: OPENAI_BASE_URL, with OPENAI_API_KEY.

    The kernel's conversation is translated on the way out (a tool result becomes a `tool` message, a tool call a
    `tool_calls` entry) and the answer on the way back. Reasoning comes back as `reasoning_content` when the
    request sets `reasoning_effort`, and is kept as a `thinking` block. What to cache is left to the gateway.
    Usage: `prompt_tokens` counts everything read, of which `cached_tokens` came from the cache and
    `cache_write_tokens` were written to it; writes are priced as one-hour cache writes, which is what the
    gateway this was built against uses."""

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "high", max_tokens: int = 16000):
        dollars(model, {})   # fail now, not after the first call, if the model has no price
        self.model, self.effort, self.max_tokens = model, effort, max_tokens
        self.url = os.environ["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions"
        self.key = os.environ["OPENAI_API_KEY"]

    @staticmethod
    def _messages(system: str, messages: list) -> list:
        out = [{"role": "system", "content": system}]
        for m in messages:
            blocks = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
            if m["role"] == "assistant":
                calls = [{"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                         for b in blocks if b["type"] == "tool_use"]
                text = "\n".join(b["text"] for b in blocks if b["type"] == "text")
                out.append(dict({"role": "assistant", "content": text or None}, **({"tool_calls": calls} if calls else {})))
                continue
            for b in blocks:         # tool results first: they answer the assistant message just before
                if b["type"] == "tool_result":
                    out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]})
            text = "\n\n".join(b["text"] for b in blocks if b["type"] == "text")
            if text:
                out.append({"role": "user", "content": text})
        return out

    def _post(self, body: dict) -> dict:
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=600) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                if e.code not in (408, 409, 429) and e.code < 500 or attempt == 4:
                    raise RuntimeError("the endpoint answered {}: {}".format(e.code, detail)) from e
            except (urllib.error.URLError, OSError) as e:
                if attempt == 4:
                    raise RuntimeError("the endpoint could not be reached: {}".format(e)) from e
            time.sleep(2 ** attempt)

    def call(self, agent: str, system: str, tools: list, messages: list) -> Reply:
        answer = self._post({
            "model": self.model, "max_tokens": self.max_tokens, "messages": self._messages(system, messages),
            "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools],
            "reasoning_effort": self.effort})
        choice = answer["choices"][0]
        message, finish = choice["message"], choice.get("finish_reason")
        if finish == "content_filter" or message.get("refusal"):
            raise ModelRefused("{} refused: {}".format(agent, message.get("refusal") or finish))
        content = []
        if message.get("reasoning_content"):
            content.append({"type": "thinking", "thinking": message["reasoning_content"]})
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})
        uses = []
        for c in message.get("tool_calls") or []:
            try:
                given = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                given = {}
            uses.append({"id": c["id"], "name": c["function"]["name"], "input": given if isinstance(given, dict) else {}})
            content.append(dict(uses[-1], type="tool_use"))
        u = answer.get("usage") or {}
        details = u.get("prompt_tokens_details") or {}
        read, written = int(details.get("cached_tokens") or 0), int(details.get("cache_write_tokens") or details.get("cached_creation_tokens") or 0)
        usage = {"input_tokens": max(0, int(u.get("prompt_tokens") or 0) - read - written), "output_tokens": int(u.get("completion_tokens") or 0),
                 "cache_creation_input_tokens": written, "cache_read_input_tokens": read, "cache_creation_1h_input_tokens": written}
        stop = {"tool_calls": "tool_use", "stop": "end_turn", "length": "max_tokens"}.get(finish, finish)
        return Reply(content=content, tool_uses=uses, text=message.get("content") or "", stop_reason=stop, usage=usage,
                     cost=dollars(self.model, usage), logged=content)


class ScriptedModel:
    """Plays a fixed script per agent: a list of turns, each a list of (tool name, input) pairs.

    When an agent's script runs out it ends its turn with text and no tool call.
    """

    def __init__(self, scripts: dict, dollars_per_call: float = 0.0):
        self.scripts = {a: list(turns) for a, turns in scripts.items()}
        self.dollars_per_call = dollars_per_call
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
        return Reply(content=content, tool_uses=uses, text="(scripted)", stop_reason="tool_use" if uses else "end_turn",
                     usage={k: 0 for k in USAGE_KEYS}, cost=self.dollars_per_call, logged=content)
