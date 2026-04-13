"""ao_kernel.context — Context management for governed AI runtime.

Provides the write→read context loop:
    LLM Response → Decision Extractor → session context → Context Injector → LLM Request
"""

from ao_kernel.context.context_injector import build_context_preamble
from ao_kernel.context.decision_extractor import Decision, extract_decisions

__all__ = [
    "Decision",
    "extract_decisions",
    "build_context_preamble",
]
