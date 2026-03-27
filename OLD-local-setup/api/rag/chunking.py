"""
Code-aware document chunker for the RAG subsystem.

Splits text, XML (MuleSoft flows), Java source, and Markdown documents into
overlapping chunks that respect logical boundaries (sentences, XML elements,
class/method definitions, heading sections).  Each chunk carries metadata about
its origin (source type, section name, line range).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import uuid4

from api.rag.config import RAGConfig, rag_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token helpers (simple word-split to avoid tiktoken dependency)
# ---------------------------------------------------------------------------

def _count_tokens(text: str) -> int:
    """Approximate token count via whitespace split."""
    return len(text.split())


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to at most *max_tokens* words."""
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens])


# ---------------------------------------------------------------------------
# Chunk data container
# ---------------------------------------------------------------------------

@dataclass
class RawChunk:
    """Intermediate representation before being converted to a ``Chunk`` schema."""

    content: str
    metadata: Dict[str, str] = field(default_factory=dict)
    line_start: int = 0
    line_end: int = 0


# ---------------------------------------------------------------------------
# Main chunker
# ---------------------------------------------------------------------------

class CodeAwareChunker:
    """
    Splits documents into overlapping, metadata-annotated chunks that respect
    the logical structure of the source format.

    Usage::

        chunker = CodeAwareChunker()
        chunks = chunker.chunk_text(long_text)
        chunks = chunker.chunk_xml(mulesoft_xml)
        chunks = chunker.chunk_java(java_source)
        chunks = chunker.chunk_markdown(md_content)
    """

    def __init__(self, config: RAGConfig | None = None) -> None:
        self._cfg = (config or rag_config).chunk
        self._max_tokens = self._cfg.max_tokens
        self._min_tokens = self._cfg.min_tokens
        self._overlap_ratio = self._cfg.overlap_ratio

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_text(
        self,
        text: str,
        max_tokens: int | None = None,
        overlap: float | None = None,
        source_type: str = "text",
    ) -> List[RawChunk]:
        """
        Sliding-window chunker that tries to break on sentence boundaries.

        Args:
            text: The full input text.
            max_tokens: Override for the maximum chunk size in tokens.
            overlap: Override for the overlap ratio (0-1).
            source_type: Label stored in chunk metadata.

        Returns:
            A list of ``RawChunk`` objects.
        """
        max_tok = max_tokens or self._max_tokens
        olap = overlap if overlap is not None else self._overlap_ratio
        overlap_tokens = int(max_tok * olap)

        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks: List[RawChunk] = []
        current_words: List[str] = []
        current_count = 0
        line_cursor = 1

        for sentence in sentences:
            s_words = sentence.split()
            s_count = len(s_words)

            if current_count + s_count > max_tok and current_words:
                chunk_text = " ".join(current_words)
                line_end = line_cursor + chunk_text.count("\n")
                chunks.append(RawChunk(
                    content=chunk_text,
                    metadata={"source_type": source_type, "section_name": ""},
                    line_start=line_cursor,
                    line_end=line_end,
                ))
                # Overlap: keep the last *overlap_tokens* words
                keep = current_words[-overlap_tokens:] if overlap_tokens else []
                current_words = keep
                current_count = len(keep)
                line_cursor = max(1, line_end - chunk_text.count("\n"))

            current_words.extend(s_words)
            current_count += s_count

        # Flush remaining
        if current_words:
            chunk_text = " ".join(current_words)
            chunks.append(RawChunk(
                content=chunk_text,
                metadata={"source_type": source_type, "section_name": ""},
                line_start=line_cursor,
                line_end=line_cursor + chunk_text.count("\n"),
            ))

        # Drop chunks below minimum token threshold
        chunks = [c for c in chunks if _count_tokens(c.content) >= self._min_tokens]
        return chunks

    # ------------------------------------------------------------------
    # XML (MuleSoft flows)
    # ------------------------------------------------------------------

    _XML_SECTION_RE = re.compile(
        r"(<(?:flow|sub-flow|http:listener-config|http:request-config"
        r"|db:config|apikit:config|batch:job|error-handler)[^>]*>.*?</\1>)",
        re.DOTALL | re.IGNORECASE,
    )

    # More robust: match top-level XML elements of interest with a simpler pattern
    _FLOW_RE = re.compile(
        r"(<(?:flow|sub-flow)\s[^>]*>.*?</(?:flow|sub-flow)>)",
        re.DOTALL,
    )
    _CONFIG_RE = re.compile(
        r"(<(?:[\w:-]+:(?:config|listener-config|request-config))\s[^>]*(?:/>|>.*?</[\w:-]+:(?:config|listener-config|request-config)>))",
        re.DOTALL,
    )

    def chunk_xml(self, xml_content: str) -> List[RawChunk]:
        """
        Chunk MuleSoft XML by respecting element boundaries.

        Extracts top-level ``<flow>``, ``<sub-flow>``, and connector config
        elements as individual chunks.  Any remaining content that doesn't
        match these patterns is chunked as plain text.
        """
        chunks: List[RawChunk] = []
        matched_spans: List[tuple[int, int]] = []

        for pattern, section_type in [
            (self._FLOW_RE, "flow"),
            (self._CONFIG_RE, "config"),
        ]:
            for match in pattern.finditer(xml_content):
                element_text = match.group(0)
                start_line = xml_content[:match.start()].count("\n") + 1
                end_line = start_line + element_text.count("\n")

                # Extract the name attribute if present
                name_match = re.search(r'name=["\']([^"\']+)["\']', element_text)
                section_name = name_match.group(1) if name_match else section_type

                tok_count = _count_tokens(element_text)
                if tok_count > self._max_tokens:
                    # Large element: sub-chunk with text chunker
                    sub_chunks = self.chunk_text(element_text, source_type="xml")
                    for sc in sub_chunks:
                        sc.metadata["section_name"] = section_name
                    chunks.extend(sub_chunks)
                elif tok_count >= self._min_tokens:
                    chunks.append(RawChunk(
                        content=element_text,
                        metadata={"source_type": "xml", "section_name": section_name},
                        line_start=start_line,
                        line_end=end_line,
                    ))
                matched_spans.append((match.start(), match.end()))

        # Remaining content outside matched elements
        remaining = self._extract_unmatched(xml_content, matched_spans)
        if remaining.strip():
            chunks.extend(self.chunk_text(remaining, source_type="xml"))

        return chunks

    # ------------------------------------------------------------------
    # Java source
    # ------------------------------------------------------------------

    _JAVA_CLASS_RE = re.compile(
        r"((?:@\w+(?:\([^)]*\))?\s*\n\s*)*"
        r"(?:public|protected|private)?\s*(?:abstract\s+|final\s+|static\s+)*"
        r"(?:class|interface|enum)\s+(\w+)[^{]*\{)",
        re.MULTILINE,
    )
    _JAVA_METHOD_RE = re.compile(
        r"((?:@\w+(?:\([^)]*\))?\s*\n\s*)*"
        r"(?:public|protected|private)\s+"
        r"(?:static\s+|final\s+|synchronized\s+|abstract\s+)*"
        r"[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)\s*"
        r"(?:throws\s+[\w,\s]+)?\s*\{)",
        re.MULTILINE,
    )

    def chunk_java(self, java_content: str) -> List[RawChunk]:
        """
        Chunk Java source respecting class and method boundaries.

        Uses regex heuristics (not a full AST parser) to identify method
        bodies and class-level segments.
        """
        lines = java_content.split("\n")
        methods = self._extract_java_methods(java_content)

        if not methods:
            # Fallback to plain-text chunking
            return self.chunk_text(java_content, source_type="java")

        chunks: List[RawChunk] = []
        covered_lines: set[int] = set()

        for method_name, start_line, end_line, body in methods:
            tok_count = _count_tokens(body)
            if tok_count > self._max_tokens:
                sub_chunks = self.chunk_text(body, source_type="java")
                for sc in sub_chunks:
                    sc.metadata["section_name"] = method_name
                chunks.extend(sub_chunks)
            elif tok_count >= self._min_tokens:
                chunks.append(RawChunk(
                    content=body,
                    metadata={"source_type": "java", "section_name": method_name},
                    line_start=start_line,
                    line_end=end_line,
                ))
            covered_lines.update(range(start_line, end_line + 1))

        # Remaining lines (imports, class-level fields, etc.)
        remaining_lines = [
            lines[i] for i in range(len(lines)) if (i + 1) not in covered_lines
        ]
        remaining_text = "\n".join(remaining_lines).strip()
        if remaining_text and _count_tokens(remaining_text) >= self._min_tokens:
            chunks.extend(self.chunk_text(remaining_text, source_type="java"))

        return chunks

    def _extract_java_methods(
        self, source: str
    ) -> List[tuple[str, int, int, str]]:
        """
        Return a list of (method_name, start_line, end_line, body_text) tuples.
        """
        results: List[tuple[str, int, int, str]] = []
        for match in self._JAVA_METHOD_RE.finditer(source):
            method_name = match.group(2)
            start_pos = match.start()
            start_line = source[:start_pos].count("\n") + 1

            # Walk forward to find the matching closing brace
            brace_depth = 0
            pos = match.end() - 1  # positioned at the opening '{'
            while pos < len(source):
                ch = source[pos]
                if ch == "{":
                    brace_depth += 1
                elif ch == "}":
                    brace_depth -= 1
                    if brace_depth == 0:
                        break
                pos += 1

            end_pos = pos + 1
            body = source[start_pos:end_pos]
            end_line = start_line + body.count("\n")
            results.append((method_name, start_line, end_line, body))

        return results

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    _MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def chunk_markdown(self, md_content: str) -> List[RawChunk]:
        """
        Split Markdown content on headings, keeping each section as a chunk.

        Sections that exceed ``max_tokens`` are further split with the
        sliding-window text chunker.
        """
        sections = self._split_by_headings(md_content)
        chunks: List[RawChunk] = []

        for heading, body, line_start, line_end in sections:
            full_text = f"{heading}\n{body}".strip() if heading else body.strip()
            tok_count = _count_tokens(full_text)

            if tok_count > self._max_tokens:
                sub_chunks = self.chunk_text(full_text, source_type="markdown")
                for sc in sub_chunks:
                    sc.metadata["section_name"] = heading.strip("# ").strip() if heading else ""
                chunks.extend(sub_chunks)
            elif tok_count >= self._min_tokens:
                chunks.append(RawChunk(
                    content=full_text,
                    metadata={
                        "source_type": "markdown",
                        "section_name": heading.strip("# ").strip() if heading else "",
                    },
                    line_start=line_start,
                    line_end=line_end,
                ))

        return chunks

    def _split_by_headings(
        self, text: str
    ) -> List[tuple[str, str, int, int]]:
        """Return list of (heading, body, line_start, line_end)."""
        lines = text.split("\n")
        sections: List[tuple[str, str, int, int]] = []
        current_heading = ""
        current_body_lines: List[str] = []
        section_start = 1

        for i, line in enumerate(lines, start=1):
            if self._MD_HEADING_RE.match(line):
                # Flush previous section
                if current_body_lines or current_heading:
                    sections.append((
                        current_heading,
                        "\n".join(current_body_lines),
                        section_start,
                        i - 1,
                    ))
                current_heading = line
                current_body_lines = []
                section_start = i
            else:
                current_body_lines.append(line)

        # Flush last section
        if current_body_lines or current_heading:
            sections.append((
                current_heading,
                "\n".join(current_body_lines),
                section_start,
                len(lines),
            ))

        return sections

    # ------------------------------------------------------------------
    # Utility: auto-detect format and chunk
    # ------------------------------------------------------------------

    def chunk_auto(self, content: str, filename: str = "") -> List[RawChunk]:
        """
        Auto-detect the file type by extension and use the appropriate chunker.
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("xml", "mxml"):
            return self.chunk_xml(content)
        if ext in ("java", "kt", "scala"):
            return self.chunk_java(content)
        if ext in ("md", "markdown"):
            return self.chunk_markdown(content)
        return self.chunk_text(content)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text on sentence boundaries (period, newline, semicolon)."""
        parts = re.split(r"(?<=[.!?;])\s+|\n{2,}", text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _extract_unmatched(text: str, spans: List[tuple[int, int]]) -> str:
        """Return text content NOT covered by any of the given (start, end) spans."""
        if not spans:
            return text
        sorted_spans = sorted(spans)
        parts: List[str] = []
        cursor = 0
        for start, end in sorted_spans:
            if cursor < start:
                parts.append(text[cursor:start])
            cursor = max(cursor, end)
        if cursor < len(text):
            parts.append(text[cursor:])
        return "".join(parts)
