"""Template definition: co-locates catalog metadata and its portable graph."""

from dataclasses import dataclass

from schemas import WorkflowGraphTransfer


@dataclass(frozen=True)
class TemplateDefinition:
    """Full definition of a global workflow template in a single place.

    Registering a template means declaring one of these next to the graph it
    builds and adding it to ``TEMPLATE_DEFINITIONS`` in
    ``templates/registry.py`` — the same one-module-per-entry pattern as
    ``nodes/registry.py``.
    """

    key: str
    name: str
    description: str
    graph: WorkflowGraphTransfer
