"""Static catalog for node definitions."""

from enums import InputNodeFormat, NodeType, OutputNodeFormat, ValidatorType
from schemas import (
    NodeCatalogItem,
    NodeFieldDataSource,
    NodeFieldDataSourceKind,
    NodeFieldSpec,
    NodeFieldUI,
    NodeFieldWidget,
    NodeGraphSpec,
)


def build_node_catalog() -> dict[NodeType, NodeCatalogItem]:
    """Build static node catalog used by node usecase and UI metadata."""
    input_fields = (
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Input label",
            ),
            default="Input node",
        ),
        NodeFieldSpec(
            name="format",
            required=True,
            validators={ValidatorType.SELECT.value: [InputNodeFormat.TXT.value]},
            ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
            default=InputNodeFormat.TXT.value,
        ),
    )

    llm_fields = (
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="LLM label",
            ),
            default="LLM node",
        ),
        NodeFieldSpec(
            name="llm_provider_id",
            required=True,
            validators={ValidatorType.GE.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.PROVIDER,
                label="Provider",
            ),
            datasource=NodeFieldDataSource(kind=NodeFieldDataSourceKind.LLM_PROVIDER),
        ),
        NodeFieldSpec(
            name="model",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(widget=NodeFieldWidget.MODEL, label="Model"),
            datasource=NodeFieldDataSource(
                kind=NodeFieldDataSourceKind.LLM_MODEL,
                depends_on="llm_provider_id",
            ),
            default="",
        ),
        NodeFieldSpec(
            name="system_prompt",
            required=True,
            validators={},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXTAREA,
                label="System prompt",
                placeholder="You are a helpful assistant.",
            ),
            default="",
        ),
    )

    output_fields = (
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Output label",
            ),
            default="Output node",
        ),
        NodeFieldSpec(
            name="format",
            required=True,
            validators={ValidatorType.SELECT.value: [OutputNodeFormat.TXT.value]},
            ui=NodeFieldUI(widget=NodeFieldWidget.SELECT, label="Format"),
            default=OutputNodeFormat.TXT.value,
        ),
    )

    web_search_fields = (
        NodeFieldSpec(
            name="label",
            required=True,
            validators={ValidatorType.MIN_LENGTH.value: 1},
            ui=NodeFieldUI(
                widget=NodeFieldWidget.TEXT,
                label="Label",
                placeholder="Web search label",
            ),
            default="Web Search node",
        ),
        NodeFieldSpec(
            name="max_results",
            required=True,
            validators={
                ValidatorType.GE.value: 1,
                ValidatorType.LE.value: 10,
            },
            ui=NodeFieldUI(
                widget=NodeFieldWidget.NUMBER,
                label="Max results",
                help="How many search results to include in output.",
            ),
            default=5,
        ),
    )

    return {
        NodeType.INPUT: NodeCatalogItem(
            type=NodeType.INPUT,
            label="Input",
            icon_key="input",
            graph=NodeGraphSpec(has_input=False, has_output=True),
            fields=input_fields,
        ),
        NodeType.LLM: NodeCatalogItem(
            type=NodeType.LLM,
            label="LLM",
            icon_key="llm",
            graph=NodeGraphSpec(has_input=True, has_output=True),
            fields=llm_fields,
        ),
        NodeType.WEB_SEARCH: NodeCatalogItem(
            type=NodeType.WEB_SEARCH,
            label="Web Search",
            icon_key="web_search",
            graph=NodeGraphSpec(has_input=True, has_output=True),
            fields=web_search_fields,
        ),
        NodeType.OUTPUT: NodeCatalogItem(
            type=NodeType.OUTPUT,
            label="Output",
            icon_key="output",
            graph=NodeGraphSpec(has_input=True, has_output=False),
            fields=output_fields,
        ),
    }
