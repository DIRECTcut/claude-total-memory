"""
Semantic Text Chunker — split text into meaningful chunks by topic/paragraph.

Supports plain text and code. Uses paragraph-based splitting with smart
merging of small blocks and sentence-level splitting for oversized ones.
No external dependencies.
"""

from __future__ import annotations

import re
import sys

LOG = lambda msg: sys.stderr.write(f"[memory-chunker] {msg}\n")


class SemanticChunker:
    """Split text into semantic chunks -- by topic/paragraph, not fixed size."""

    MAX_CHUNK_TOKENS: int = 500
    MIN_CHUNK_TOKENS: int = 50
    OVERLAP_SENTENCES: int = 1

    # Patterns for code function/class detection
    _FUNC_PATTERNS: list[re.Pattern[str]] = [
        # Python: def/class at top level or indented
        re.compile(r"^(?:async\s+)?(?:def|class)\s+\w+", re.MULTILINE),
        # Go: func ...
        re.compile(r"^func\s+", re.MULTILINE),
        # JS/TS: function, arrow, class, export
        re.compile(
            r"^(?:export\s+)?(?:async\s+)?(?:function\s+\w+|class\s+\w+|const\s+\w+\s*=\s*(?:async\s+)?\()",
            re.MULTILINE,
        ),
        # PHP: function/class
        re.compile(r"^(?:public|private|protected|static|\s)*function\s+\w+", re.MULTILINE),
    ]

    _SENTENCE_SPLIT: re.Pattern[str] = re.compile(
        r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])"
    )

    def chunk(self, text: str, content_type: str = "text") -> list[dict]:
        """Split text into semantic chunks.

        For short texts (< MAX_CHUNK_TOKENS): single chunk.
        For longer texts: split by paragraphs, merge small ones, split large ones.

        Returns list of {"content": str, "index": int, "token_estimate": int}.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        total_tokens = self.estimate_tokens(text)

        if total_tokens <= self.MAX_CHUNK_TOKENS:
            return [{"content": text, "index": 0, "token_estimate": total_tokens}]

        if content_type == "code":
            return self.chunk_code(text)

        paragraphs = self._split_paragraphs(text)
        merged = self._merge_small(paragraphs)
        final_blocks: list[str] = []
        for block in merged:
            if self.estimate_tokens(block) > self.MAX_CHUNK_TOKENS:
                final_blocks.extend(self._split_large(block))
            else:
                final_blocks.append(block)

        # Add overlap sentences between chunks for context continuity
        chunks: list[dict] = []
        for i, block in enumerate(final_blocks):
            content = block
            if i > 0 and self.OVERLAP_SENTENCES > 0:
                prev_sentences = self._SENTENCE_SPLIT.split(final_blocks[i - 1])
                overlap = prev_sentences[-self.OVERLAP_SENTENCES :]
                if overlap:
                    overlap_text = " ".join(s.strip() for s in overlap if s.strip())
                    if overlap_text and self.estimate_tokens(overlap_text) < 80:
                        content = overlap_text + "\n\n" + content

            chunks.append(
                {
                    "content": content.strip(),
                    "index": i,
                    "token_estimate": self.estimate_tokens(content),
                }
            )

        LOG(f"Chunked {total_tokens} tokens into {len(chunks)} chunks")
        return chunks

    def chunk_code(self, code: str, language: str | None = None) -> list[dict]:
        """Split code by functions/classes. Each function = one chunk.

        Fallback: split by blank lines if can't detect functions.
        """
        if not code or not code.strip():
            return []

        # Try to detect function/class boundaries
        boundaries: list[int] = []
        lines = code.split("\n")

        for pattern in self._FUNC_PATTERNS:
            for match in pattern.finditer(code):
                line_num = code[: match.start()].count("\n")
                boundaries.append(line_num)
            if boundaries:
                break

        if not boundaries:
            # Fallback: split by double blank lines
            return self._chunk_code_by_blanks(code)

        boundaries = sorted(set(boundaries))
        # Add start and end
        if boundaries[0] != 0:
            boundaries.insert(0, 0)

        chunks: list[dict] = []
        for i, start_line in enumerate(boundaries):
            end_line = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
            block = "\n".join(lines[start_line:end_line]).strip()
            if not block:
                continue

            token_est = self.estimate_tokens(block)
            if token_est > self.MAX_CHUNK_TOKENS:
                # Large function: split by blank lines within it
                sub_chunks = self._chunk_code_by_blanks(block)
                for sc in sub_chunks:
                    sc["index"] = len(chunks)
                    chunks.append(sc)
            elif token_est >= self.MIN_CHUNK_TOKENS:
                chunks.append(
                    {"content": block, "index": len(chunks), "token_estimate": token_est}
                )
            elif chunks:
                # Merge tiny block into previous chunk
                prev = chunks[-1]
                prev["content"] += "\n\n" + block
                prev["token_estimate"] = self.estimate_tokens(prev["content"])
            else:
                chunks.append(
                    {"content": block, "index": 0, "token_estimate": token_est}
                )

        LOG(f"Chunked code into {len(chunks)} chunks")
        return chunks

    def _chunk_code_by_blanks(self, code: str) -> list[dict]:
        """Fallback code chunking by double blank lines."""
        blocks = re.split(r"\n\s*\n", code)
        merged = self._merge_small(blocks)
        chunks: list[dict] = []
        for i, block in enumerate(merged):
            block = block.strip()
            if not block:
                continue
            if self.estimate_tokens(block) > self.MAX_CHUNK_TOKENS:
                # Last resort: split by single newlines
                sub_lines = block.split("\n")
                current: list[str] = []
                for line in sub_lines:
                    current.append(line)
                    if self.estimate_tokens("\n".join(current)) > self.MAX_CHUNK_TOKENS:
                        chunk_text = "\n".join(current[:-1]).strip()
                        if chunk_text:
                            chunks.append(
                                {
                                    "content": chunk_text,
                                    "index": len(chunks),
                                    "token_estimate": self.estimate_tokens(chunk_text),
                                }
                            )
                        current = [line]
                if current:
                    chunk_text = "\n".join(current).strip()
                    if chunk_text:
                        chunks.append(
                            {
                                "content": chunk_text,
                                "index": len(chunks),
                                "token_estimate": self.estimate_tokens(chunk_text),
                            }
                        )
            else:
                chunks.append(
                    {"content": block, "index": len(chunks), "token_estimate": self.estimate_tokens(block)}
                )
        return chunks

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4 if text else 0

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split by double newlines, preserving structure."""
        raw = re.split(r"\n\s*\n", text)
        return [p.strip() for p in raw if p.strip()]

    def _merge_small(self, paragraphs: list[str]) -> list[str]:
        """Merge consecutive small paragraphs to reach MIN_CHUNK_TOKENS."""
        if not paragraphs:
            return []

        merged: list[str] = []
        current = paragraphs[0]

        for para in paragraphs[1:]:
            if self.estimate_tokens(current) < self.MIN_CHUNK_TOKENS:
                current = current + "\n\n" + para
            else:
                merged.append(current)
                current = para

        if current:
            # If the last block is too small, merge with previous
            if (
                merged
                and self.estimate_tokens(current) < self.MIN_CHUNK_TOKENS
            ):
                merged[-1] = merged[-1] + "\n\n" + current
            else:
                merged.append(current)

        return merged

    def _split_large(self, paragraph: str) -> list[str]:
        """Split paragraphs > MAX_CHUNK_TOKENS by sentences."""
        sentences = self._SENTENCE_SPLIT.split(paragraph)
        if len(sentences) <= 1:
            # Can't split by sentences; split by words
            words = paragraph.split()
            chunks: list[str] = []
            current_words: list[str] = []
            for word in words:
                current_words.append(word)
                if self.estimate_tokens(" ".join(current_words)) > self.MAX_CHUNK_TOKENS:
                    chunk_text = " ".join(current_words[:-1])
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_words = [word]
            if current_words:
                chunks.append(" ".join(current_words))
            return chunks

        result: list[str] = []
        current_sentences: list[str] = []

        for sentence in sentences:
            current_sentences.append(sentence)
            combined = " ".join(current_sentences)
            if self.estimate_tokens(combined) > self.MAX_CHUNK_TOKENS:
                # Push all but last sentence
                if len(current_sentences) > 1:
                    result.append(" ".join(current_sentences[:-1]))
                    current_sentences = [sentence]
                else:
                    # Single sentence exceeds limit; keep it as-is
                    result.append(combined)
                    current_sentences = []

        if current_sentences:
            result.append(" ".join(current_sentences))

        return result
