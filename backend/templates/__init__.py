"""Global workflow template catalog."""

from templates.definition import TemplateDefinition
from templates.registry import TEMPLATE_DEFINITIONS, get_template_definition

__all__ = [
    "TEMPLATE_DEFINITIONS",
    "TemplateDefinition",
    "get_template_definition",
]
