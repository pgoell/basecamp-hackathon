"""Agent definitions as the runtime sees them.

The runtime knows no concrete agents: callers build a roster of `AgentSpec`s
(the app builds it from `backend/catalog`, see `app.hierarchy`) and say which
key is the root. `can_delegate_to` wires the tree.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    key: str
    name: str
    description: str
    model: str
    system: str
    effort: str = "medium"  # low | medium | high | xhigh | max
    # (skill name, SKILL.md content), injected into the system prompt.
    skills: tuple[tuple[str, str], ...] = ()
    # Keys of agents this agent may delegate to (empty = cannot delegate).
    can_delegate_to: tuple[str, ...] = ()
    # Gets the tool that writes the final deliverable (the root agent).
    can_write_final: bool = False

    def full_system_prompt(self, max_children: int | None = 0) -> str:
        parts = [self.system.strip(), SHARED_RULES.strip()]
        if self.can_write_final:
            parts.append(FINAL_RULES.strip())
        if self.can_delegate_to and max_children != 0:
            limit = (
                "There is no fixed limit on delegations, but every one costs time and money."
                if max_children is None
                else f"You may delegate at most {max_children} tasks in total - plan them carefully."
            )
            parts.append(DELEGATION_RULES.strip() + "\n" + limit)
        for name, text in self.skills:
            parts.append(f'<skill name="{name}">\n{text}\n</skill>')
        return "\n\n".join(parts)


SHARED_RULES = """
# Working environment
- Documents live in a shared workspace. `inputs/` holds the input document and
  our reference material (read-only). `work/` is a shared scratch area every
  agent can read and write - use it to hand over large artifacts by path instead
  of pasting them.
- Use `list_files` and `read_file` to look at documents. Do not invent facts that
  are not in the documents; when something is missing, say so explicitly.
- Cite the source file (and section, if possible) for every factual claim.
- Write in the language of the input document unless your task says otherwise.
- Your final message is the report your caller receives. Make it self-contained,
  structured and concise. Do not ask your caller questions - state assumptions.
"""

FINAL_RULES = """
# Deliverable
Produce the deliverable with the `write_final_document` tool (markdown in,
.md and branded .docx out). Call it once, with the complete document. Then reply
with a short summary: what was delivered, key numbers, open risks.
"""

DELEGATION_RULES = """
# Delegating
You can delegate with the `delegate` tool. A delegated agent sees none of your
conversation: each task must contain the goal, the relevant file paths, the
constraints, and the expected report format. Several `delegate` calls in the
same turn run in parallel - use that for independent pieces of work.
Keep work for yourself when it is small; delegation costs time and money.
"""
