"""Shared citation checks; the legacy Ollama defaults retain their exact rules."""
import re


def validate_citations(answer, cited, known: set[str], *, require_every_paragraph: bool = True,
                       allow_empty: bool = False) -> str:
    if (not isinstance(answer, str) or not answer.strip() or len(answer) > 6000
            or not isinstance(cited, list) or (not cited and not allow_empty)
            or any(not isinstance(s, str) or s not in known for s in cited)
            or any(f"[{s}]" not in answer for s in cited)):
        raise ValueError("LLM returned invalid evidence references")
    inline = set(re.findall(r"\[([^\]]+)\]", answer))
    if inline != set(cited):
        raise ValueError("LLM returned inconsistent inline citations")
    if require_every_paragraph and any(not any(f"[{s}]" in paragraph for s in cited)
                                     for paragraph in answer.split("\n\n") if paragraph.strip()):
        raise ValueError("LLM returned an uncited paragraph")
    return answer.strip()
