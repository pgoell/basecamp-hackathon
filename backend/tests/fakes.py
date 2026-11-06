"""Scripted fake Anthropic client shared by the offline tests.

It plays every agent by looking at the tools it was given:
- has write_final_document -> coordinator: delegates to every member, then writes the deliverable
- has delegate             -> member: asks for 5 helpers + 1 agent outside its roster
- otherwise                -> helper: reads a file (and tries a path traversal)
"""

from __future__ import annotations

import asyncio
import itertools
from types import SimpleNamespace

_ids = itertools.count()


def tool(name, **inp):
    return SimpleNamespace(type="tool_use", id=f"tu_{next(_ids)}", name=name, input=inp)


def text(t):
    return SimpleNamespace(type="text", text=t)


def msg(content, stop="tool_use", model="fake-model"):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=content, stop_reason=stop, usage=usage, model=model)


class FakeClient:
    """Mimics client.beta.messages.stream(...) with a scripted policy."""

    def __init__(self):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        reply = self._policy(kwargs)

        class _Ctx:
            async def __aenter__(self_inner):
                async def final():
                    await asyncio.sleep(0.01)
                    return reply

                return SimpleNamespace(get_final_message=final)

            async def __aexit__(self_inner, *a):
                return False

        return _Ctx()

    @staticmethod
    def _policy(kw):
        turn = sum(1 for m in kw["messages"] if m["role"] == "assistant")
        tools = {t["name"]: t for t in kw["tools"]}
        roster = (
            tools.get("delegate", {}).get("input_schema", {}).get("properties", {}).get("agent", {}).get("enum", [])
        )

        if "write_final_document" in tools:
            if turn == 0:
                return msg(
                    [tool("delegate", agent=a, task=f"Analyse the input for lane {a}, read inputs/.") for a in roster]
                )
            if turn == 1:
                md = "## Executive summary\n" + "- point\n" * 30
                return msg([tool("write_final_document", title="Proposal", markdown=md, filename="proposal-response")])
            return msg([text("Done. Deliverable written.")], stop="end_turn")

        if "delegate" in tools:
            if turn == 0:
                calls = [
                    tool("delegate", agent=roster[0], task=f"Extract facts number {i} from inputs/") for i in range(5)
                ]
                calls.append(tool("delegate", agent="not-a-helper", task="Trying to call outside my roster."))
                calls.append(tool("write_work_file", path="work/notes.md", content="specialist notes"))
                return msg(calls)
            return msg([text("Specialist report.")], stop="end_turn")

        if turn == 0:
            return msg([tool("list_files"), tool("read_file", path="../../etc/passwd")])
        return msg([text("Helper findings.")], stop="end_turn")
