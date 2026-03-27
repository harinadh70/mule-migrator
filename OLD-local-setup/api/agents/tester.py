"""
TesterAgent — generates JUnit 5 test files for controllers and services.

Generates:
  - Controller tests using ``@WebMvcTest`` and ``MockMvc``
  - Service tests with ``@MockBean`` and ``@ExtendWith(MockitoExtension.class)``
  - Error-path tests for exception handlers
  - Integration test skeletons with ``@SpringBootTest``
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import structlog

from api.agents.base import BaseAgent
from api.agents.context import AgentContext
from api.agents.guardrails import AgentGuardrails
from api.agents.result import AgentResult

logger = structlog.get_logger(__name__)


class TesterAgent(BaseAgent):
    """Generates JUnit 5 test suites for migrated Spring Boot code."""

    name = "tester"
    role = "Spring Boot test generation specialist"
    system_prompt = """You are a senior Java test engineer specializing in Spring Boot 3.2 testing.

Generate JUnit 5 test classes for the provided source file. Follow these rules:

For Controllers:
- Use @WebMvcTest(ControllerClass.class)
- Inject MockMvc via @Autowired
- Mock services with @MockBean
- Test happy path, validation errors, and error responses
- Use MockMvc's perform(), andExpect(), andReturn()

For Services:
- Use @ExtendWith(MockitoExtension.class)
- Mock dependencies with @Mock and inject with @InjectMocks
- Test business logic, edge cases, and exception paths
- Use BDDMockito (given/when/then) style

For all tests:
- Use AssertJ assertions (assertThat)
- Include @DisplayName annotations
- Test error/exception paths
- Use meaningful test method names: should_<expected>_when_<condition>

Return ONLY the complete test class in a ```java fence.
Include all necessary imports."""

    # ------------------------------------------------------------------
    #  Core execution
    # ------------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate tests for all controller and service files."""
        generated_files: Dict[str, str] = context.get_artifact("generated_files") or {}
        if not generated_files:
            return AgentResult.success(
                output={"test_files": {}, "message": "No source files to test"},
            )

        test_files: Dict[str, str] = {}
        errors: List[str] = []
        total_tokens = 0
        rag_queries: List[str] = []
        rag_results_used = 0

        # Filter to testable files
        testable = {
            fp: content
            for fp, content in generated_files.items()
            if fp.endswith(".java") and self._is_testable(fp, content)
        }

        for filepath, content in testable.items():
            test_code, tokens, rq, rr = await self._generate_test(
                context, filepath, content,
            )
            total_tokens += tokens
            rag_queries.extend(rq)
            rag_results_used += rr

            if test_code:
                test_path = self._test_path(filepath)
                test_files[test_path] = test_code
            else:
                errors.append(f"Failed to generate test for: {filepath}")

        # Store test files as artifacts
        all_files = dict(generated_files)
        all_files.update(test_files)
        context.set_artifact("generated_files", all_files)
        context.set_artifact("test_files", test_files)

        context.update(self.name, {
            "tests_generated": len(test_files),
            "errors": len(errors),
        })

        status = "success" if not errors else ("partial" if test_files else "error")
        return AgentResult(
            status=status,
            output={
                "test_files": test_files,
                "tests_generated": len(test_files),
                "errors": errors,
            },
            token_usage=total_tokens,
            rag_queries=rag_queries,
            rag_results_used=rag_results_used,
            error="; ".join(errors) if errors else None,
        )

    # ------------------------------------------------------------------
    #  Single-file test generation
    # ------------------------------------------------------------------

    async def _generate_test(
        self,
        context: AgentContext,
        filepath: str,
        content: str,
    ) -> tuple[Optional[str], int, List[str], int]:
        """Generate a test class for a single source file.

        Returns:
            (test_code, tokens, rag_queries, rag_results_used)
        """
        total_tokens = 0
        rag_queries: List[str] = []
        rag_results_used = 0

        # 1. Determine file type
        file_type = self._classify_source(filepath, content)

        # 2. RAG: retrieve testing patterns
        rag_context = ""
        if self.retriever is not None:
            query = f"Spring Boot JUnit 5 test pattern for {file_type}"
            rag_queries.append(query)
            results = await self.query_rag(query, top_k=3)
            if results:
                rag_results_used = len(results)
                rag_context = self.format_rag_results(results)

        # 3. Build prompt
        prompt = self._build_test_prompt(filepath, content, file_type, rag_context)

        # 4. Generate with validation
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.call_llm_with_retry(prompt)
                total_tokens += len(prompt) // 4 + len(response) // 4
                test_code = self.extract_code_block(response)

                # Validate
                is_valid, issues = AgentGuardrails.validate_java_syntax(test_code)
                if is_valid and self._has_test_annotations(test_code):
                    return test_code, total_tokens, rag_queries, rag_results_used

                # Retry with feedback
                prompt += (
                    f"\n\nPrevious attempt issues: {issues}\n"
                    "Ensure the test class has @Test annotations and proper imports."
                )
            except Exception as exc:
                logger.warning(
                    "tester.generation_failed",
                    filepath=filepath,
                    attempt=attempt,
                    error=str(exc),
                )

        # Fallback: generate a skeleton
        skeleton = self._generate_skeleton(filepath, content, file_type)
        return skeleton, total_tokens, rag_queries, rag_results_used

    # ------------------------------------------------------------------
    #  Prompt building
    # ------------------------------------------------------------------

    def _build_test_prompt(
        self,
        filepath: str,
        content: str,
        file_type: str,
        rag_context: str,
    ) -> str:
        parts: List[str] = []

        if rag_context:
            parts.append("=== Test pattern references ===")
            parts.append(rag_context)
            parts.append("=== End references ===\n")

        parts.append(f"Generate JUnit 5 tests for this {file_type}:")
        parts.append(f"File: {filepath}")
        parts.append(f"\n```java\n{content[:5000]}\n```\n")

        # Extract class name and methods for targeted testing
        class_name = self._extract_class_name(content)
        methods = self._extract_public_methods(content)

        if class_name:
            parts.append(f"Class under test: {class_name}")
        if methods:
            parts.append(f"Public methods to test: {', '.join(methods)}")

        parts.append("\nGenerate comprehensive tests including error paths.")
        parts.append("Return the complete test class in a ```java fence.")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    #  Classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_testable(filepath: str, content: str) -> bool:
        """Determine if a file should have tests generated."""
        fp_lower = filepath.lower()
        # Skip test files, configs, DTOs, and models
        if "test" in fp_lower:
            return False
        if any(kw in fp_lower for kw in ("config", "application.", "pom.", "build.")):
            return False
        # Must contain a class definition
        return bool(re.search(r'\bclass\s+\w+', content))

    @staticmethod
    def _classify_source(filepath: str, content: str) -> str:
        fp_lower = filepath.lower()
        if "controller" in fp_lower or "@RestController" in content:
            return "REST controller"
        if "service" in fp_lower or "@Service" in content:
            return "service"
        if "repository" in fp_lower or "Repository" in content:
            return "repository"
        return "component"

    @staticmethod
    def _test_path(filepath: str) -> str:
        """Derive test file path from source path."""
        # src/main/java/... -> src/test/java/...Test.java
        path = filepath.replace("src/main/java", "src/test/java")
        if path.endswith(".java"):
            path = path[:-5] + "Test.java"
        return path

    @staticmethod
    def _extract_class_name(content: str) -> Optional[str]:
        m = re.search(r'\bclass\s+(\w+)', content)
        return m.group(1) if m else None

    @staticmethod
    def _extract_public_methods(content: str) -> List[str]:
        return re.findall(r'public\s+\w+\s+(\w+)\s*\(', content)

    @staticmethod
    def _has_test_annotations(code: str) -> bool:
        return "@Test" in code or "@ParameterizedTest" in code

    # ------------------------------------------------------------------
    #  Skeleton fallback
    # ------------------------------------------------------------------

    def _generate_skeleton(
        self, filepath: str, content: str, file_type: str
    ) -> str:
        """Generate a minimal test skeleton without LLM."""
        class_name = self._extract_class_name(content) or "Unknown"
        methods = self._extract_public_methods(content)

        if file_type == "REST controller":
            return self._controller_test_skeleton(class_name, methods)
        return self._service_test_skeleton(class_name, methods)

    @staticmethod
    def _controller_test_skeleton(class_name: str, methods: List[str]) -> str:
        test_methods = ""
        for method in methods[:10]:
            test_methods += f"""
    @Test
    @DisplayName("Should handle {method} request")
    void should_handle_{method}() throws Exception {{
        // TODO: Implement test for {method}
        // mockMvc.perform(get("/endpoint"))
        //     .andExpect(status().isOk());
    }}
"""
        return f"""package com.example.test;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.bean.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

// TODO: Import the controller and service classes
// @WebMvcTest({class_name}.class)
class {class_name}Test {{

    @Autowired
    private MockMvc mockMvc;

    // TODO: Add @MockBean for service dependencies
{test_methods}
}}
"""

    @staticmethod
    def _service_test_skeleton(class_name: str, methods: List[str]) -> str:
        test_methods = ""
        for method in methods[:10]:
            test_methods += f"""
    @Test
    @DisplayName("Should {method} correctly")
    void should_{method}_correctly() {{
        // TODO: Implement test for {method}
        // given(mockDependency.someMethod()).willReturn(expectedValue);
        // var result = service.{method}();
        // assertThat(result).isNotNull();
    }}
"""
        return f"""package com.example.test;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class {class_name}Test {{

    // TODO: Add @Mock for dependencies
    // @Mock
    // private SomeDependency mockDependency;

    @InjectMocks
    private {class_name} service;
{test_methods}
}}
"""

    # ------------------------------------------------------------------
    #  Fallback
    # ------------------------------------------------------------------

    def get_fallback(self, context: AgentContext) -> dict:
        """Return skeleton tests for all testable files."""
        generated_files = context.get_artifact("generated_files") or {}
        test_files: Dict[str, str] = {}

        for filepath, content in generated_files.items():
            if filepath.endswith(".java") and self._is_testable(filepath, content):
                file_type = self._classify_source(filepath, content)
                skeleton = self._generate_skeleton(filepath, content, file_type)
                test_files[self._test_path(filepath)] = skeleton

        return {
            "test_files": test_files,
            "tests_generated": len(test_files),
            "errors": [],
            "fallback": True,
        }
