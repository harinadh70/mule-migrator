# MuleSoft Knowledge Base

This directory contains reference documentation for MuleSoft Anypoint Platform
connectors, DataWeave patterns, and configuration idioms. These documents are
automatically indexed into the `mulesoft_docs` Qdrant collection at startup and
used by the RAG retriever to augment LLM prompts during migration.

## Structure

| File | Description |
|---|---|
| `http_connector.md` | HTTP Listener and Request connector XML reference with configuration examples |
| `db_connector.md` | Database connector (Select, Insert, Update, Delete, Stored Procedure) XML reference |
| `dataweave_patterns.md` | Common DataWeave 2.0 transformation patterns and their Java/Spring equivalents |

## Adding New Documents

1. Create a Markdown (`.md`) file in this directory.
2. Use heading-based sections so the chunker can split on logical boundaries.
3. Include XML snippets wrapped in fenced code blocks for accurate retrieval.
4. Re-run the indexer: `DocumentIndexer().index_mulesoft_knowledge()`.

## Conventions

- Each document should focus on a single connector or topic.
- Provide both the MuleSoft XML syntax **and** the recommended Spring Boot equivalent.
- Include at least one complete, runnable example per section.
