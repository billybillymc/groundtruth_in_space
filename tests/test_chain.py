"""Tests for LCEL chain with mocked LLM and retriever."""

from unittest.mock import MagicMock, patch

from src.synthesis.prompts import RAG_PROMPT_TEMPLATE


def test_prompt_template_has_required_placeholders():
    """Prompt template should have {context} and {question} placeholders."""
    assert "{context}" in RAG_PROMPT_TEMPLATE
    assert "{question}" in RAG_PROMPT_TEMPLATE


def test_prompt_template_has_citation_instruction():
    """Prompt should instruct LLM to cite file_path:line_numbers."""
    assert "file_path" in RAG_PROMPT_TEMPLATE
    assert "line_numbers" in RAG_PROMPT_TEMPLATE or "start_line-end_line" in RAG_PROMPT_TEMPLATE


def test_prompt_template_has_fallback_instruction():
    """Prompt should include the 'I cannot find' fallback."""
    assert "I cannot find the answer in the provided codebase context" in RAG_PROMPT_TEMPLATE


def test_format_context():
    """Context formatter should produce readable output with citations."""
    from src.synthesis.chain import _format_context

    mock_doc = MagicMock()
    mock_doc.metadata = {
        "file_path": "adamant/src/foo.ads",
        "start_line": 1,
        "end_line": 10,
        "chunk_type": "spec",
        "component_name": "foo",
    }
    mock_doc.page_content = "package Foo is end Foo;"

    result = _format_context([mock_doc])
    assert "adamant/src/foo.ads:1-10" in result
    assert "package Foo is end Foo;" in result
    assert "spec" in result
