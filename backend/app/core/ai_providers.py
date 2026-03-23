import logging
from collections.abc import Awaitable, Callable, Sequence
from enum import StrEnum
from typing import SupportsFloat, cast

from httpx import TimeoutException
from pydantic_ai import ModelAPIError, UsageLimitExceeded
from pydantic_ai.embeddings import EmbeddingResult
from pydantic_ai.embeddings.google import GoogleEmbeddingModel, GoogleEmbeddingSettings
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

from app.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LLM_MAX_TOKENS = 128_000
GOOGLE_LARGE_MODEL = "gemini-2.5-pro"
GOOGLE_STANDARD_MODEL = "gemini-2.5-flash"
GOOGLE_SMALL_MODEL = "gemini-2.5-flash-lite"
GOOGLE_EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_MAX_TOKENS = 8192
EMBEDDING_MAX_TEXTS = 200  # This is a guess
EMBEDDING_DIMENSIONS = 3072 // 2


# https://ai.google.dev/gemini-api/docs/embeddings#task-types
class EmbeddingTaskType(StrEnum):
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    """Embeddings optimized to assess text similarity."""
    CLASSIFICATION = "CLASSIFICATION"
    """Embeddings optimized to classify texts according to preset labels."""
    CLUSTERING = "CLUSTERING"
    """Embeddings optimized to cluster texts based on their similarities."""
    RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
    """Embeddings optimized for document search."""
    RETRIEVAL_QUERY = "RETRIEVAL_QUERY"
    """Embeddings optimized for general search queries. Use RETRIEVAL_QUERY for queries;
    RETRIEVAL_DOCUMENT for documents to be retrieved."""
    CODE_RETRIEVAL_QUERY = "CODE_RETRIEVAL_QUERY"
    """Embeddings optimized for retrieval of code blocks based on natural
    language queries. Use CODE_RETRIEVAL_QUERY for queries; RETRIEVAL_DOCUMENT
    for code blocks to be retrieved."""
    QUESTION_ANSWERING = "QUESTION_ANSWERING"
    """Embeddings for questions in a question-answering system, optimized for
    finding documents that answer the question. Use QUESTION_ANSWERING for questions;
    RETRIEVAL_DOCUMENT for documents to be retrieved."""
    FACT_VERIFICATION = "FACT_VERIFICATION"
    """Embeddings for statements that need to be verified, optimized for retrieving
    documents that contain evidence supporting or refuting the statement.
    Use FACT_VERIFICATION for the target text; RETRIEVAL_DOCUMENT
    for documents to be retrieved."""


vertex_provider = GoogleProvider(
    location=settings.GOOGLE_CLOUD_LOCATION or "",
    project=settings.GOOGLE_CLOUD_PROJECT or "",
)

gemini_settings = GoogleModelSettings(timeout=15, temperature=0.3)

model_gemini_flash = GoogleModel(
    GOOGLE_STANDARD_MODEL,
    provider=vertex_provider,
    settings=gemini_settings,
)

model_gemini_flash_lite = GoogleModel(
    GOOGLE_SMALL_MODEL,
    provider=vertex_provider,
    settings=gemini_settings,
)

fallback_exceptions = (TimeoutException, ModelAPIError, UsageLimitExceeded)

google_only_backup = FallbackModel(
    model_gemini_flash,
    model_gemini_flash_lite,
    fallback_on=fallback_exceptions,
)

embedder = GoogleEmbeddingModel(GOOGLE_EMBEDDING_MODEL, provider=vertex_provider)


def is_valid_embedding(embedding: list[float]) -> bool:
    return (
        isinstance(embedding, Sequence)
        and all(isinstance(x, SupportsFloat) for x in embedding)
        and len(embedding) == EMBEDDING_DIMENSIONS
    )


async def embed_query(text: str) -> list[float]:
    """Embed a single query and return its embedding."""
    response = await embedder.embed(
        text,
        input_type="document",
        settings=GoogleEmbeddingSettings(
            google_task_type=EmbeddingTaskType.RETRIEVAL_QUERY
        ),
    )
    logger.info(f"Embedded query with {response.usage.input_tokens} tokens.")
    return cast(list, response.embeddings[0])


async def embed_queries(texts: list[str]) -> list[list[float]]:
    """Embed multiple queries and return their embeddings."""
    return await embed_batch(
        texts,
        lambda texts: embedder.embed(
            texts,
            input_type="query",
            settings=GoogleEmbeddingSettings(
                google_task_type=EmbeddingTaskType.RETRIEVAL_QUERY
            ),
        ),
    )


async def embed_document(text: str) -> list[float]:
    """Embed a single document and return its embedding."""
    embeddings = await embed_documents([text])
    return embeddings[0]


async def embed_documents(texts: list[str]) -> list[list[float]]:
    return await embed_batch(
        texts,
        lambda texts: embedder.embed(
            texts,
            input_type="document",
            settings=GoogleEmbeddingSettings(
                google_task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT
            ),
        ),
    )


async def embed_batch(
    texts: list[str],
    embedding_func: Callable[[Sequence[str]], Awaitable[EmbeddingResult]],
) -> list[list[float]]:
    """Embed multiple documents and return their embeddings."""
    total_tokens = sum([await embedder.count_tokens(text) for text in texts])
    # total_tokens = sum([await embedder.count_tokens(text) for text in texts])
    if len(texts) <= EMBEDDING_MAX_TEXTS and total_tokens < EMBEDDING_MAX_TOKENS:
        response = await embedding_func(texts)
        logger.info(
            f"Embedded {len(texts)} texts with {response.usage.total_tokens} tokens."
        )
        embeddings = cast(list[list[float]], response.embeddings)
    elif len(texts) > 1:
        cut_point = len(texts) // 2
        first_half = texts[:cut_point]
        second_half = texts[cut_point:]
        embeddings = await embed_documents(first_half) + await embed_documents(
            second_half
        )
    else:
        raise ValueError(
            "Document too large to embed: "
            + f"{total_tokens} tokens (max {EMBEDDING_MAX_TOKENS})"
        )

    return embeddings


def empty_embedding() -> list[float]:
    """Returns an empty embedding vector."""
    return [0.0] * EMBEDDING_DIMENSIONS
