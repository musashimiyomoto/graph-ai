"""Curated catalog of popular Ollama models offered in the UI picker.

Ollama has no API to enumerate the registry (``/api/tags`` lists only what is
already installed), so we maintain a small hand-curated list to seed the picker.
Users can still type any other ``name:tag`` — this only provides suggestions.
Sizes are approximate download sizes; update this list to surface new models.
"""

from schemas import OllamaCatalogEntry, OllamaCatalogTag

OLLAMA_MODEL_CATALOG: list[OllamaCatalogEntry] = [
    OllamaCatalogEntry(
        name="llama3.2",
        description="Meta Llama 3.2 — small, capable general-purpose models.",
        tags=[
            OllamaCatalogTag(tag="llama3.2:1b", size_gb=1.3, params="1B"),
            OllamaCatalogTag(tag="llama3.2:3b", size_gb=2.0, params="3B"),
        ],
    ),
    OllamaCatalogEntry(
        name="llama3.1",
        description="Meta Llama 3.1 — strong 8B general-purpose model.",
        tags=[
            OllamaCatalogTag(tag="llama3.1:8b", size_gb=4.7, params="8B"),
        ],
    ),
    OllamaCatalogEntry(
        name="qwen2.5",
        description="Alibaba Qwen 2.5 — wide range of sizes.",
        tags=[
            OllamaCatalogTag(tag="qwen2.5:0.5b", size_gb=0.4, params="0.5B"),
            OllamaCatalogTag(tag="qwen2.5:1.5b", size_gb=0.9, params="1.5B"),
            OllamaCatalogTag(tag="qwen2.5:3b", size_gb=1.9, params="3B"),
            OllamaCatalogTag(tag="qwen2.5:7b", size_gb=4.7, params="7B"),
        ],
    ),
    OllamaCatalogEntry(
        name="mistral",
        description="Mistral 7B — solid all-round instruct model.",
        tags=[
            OllamaCatalogTag(tag="mistral:7b", size_gb=4.1, params="7B"),
        ],
    ),
    OllamaCatalogEntry(
        name="phi3",
        description="Microsoft Phi-3 — compact, high-quality models.",
        tags=[
            OllamaCatalogTag(tag="phi3:mini", size_gb=2.2, params="3.8B"),
            OllamaCatalogTag(tag="phi3:medium", size_gb=7.9, params="14B"),
        ],
    ),
    OllamaCatalogEntry(
        name="gemma2",
        description="Google Gemma 2 — efficient open models.",
        tags=[
            OllamaCatalogTag(tag="gemma2:2b", size_gb=1.6, params="2B"),
            OllamaCatalogTag(tag="gemma2:9b", size_gb=5.4, params="9B"),
        ],
    ),
]
