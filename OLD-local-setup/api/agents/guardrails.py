"""
AgentGuardrails — post-generation validation layer for LLM-produced code.

Catches common problems *before* the code reaches the user:
  - Unbalanced braces / malformed Java
  - Missing Spring annotations
  - Hardcoded secrets and SQL injection vectors
  - Invalid import packages
  - Hallucinated classes / APIs
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from api.agents.context import AgentContext

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
#  Known-good import prefixes (not exhaustive — just the common ones)
# ---------------------------------------------------------------------------
VALID_IMPORT_PREFIXES = frozenset({
    "java.", "javax.", "jakarta.",
    "org.springframework.", "org.spring.",
    "com.fasterxml.jackson.", "com.google.",
    "org.apache.", "org.slf4j.", "org.junit.",
    "org.mockito.", "org.assertj.", "org.hamcrest.",
    "io.micrometer.", "io.swagger.", "io.springfox.",
    "lombok.", "org.projectlombok.",
    "com.zaxxer.", "org.hibernate.", "org.flywaydb.",
    "org.liquibase.", "net.sf.", "org.json.",
    "io.netty.", "reactor.",
})

# ---------------------------------------------------------------------------
#  Secret / injection patterns
# ---------------------------------------------------------------------------
SECRET_PATTERNS = [
    re.compile(r'(?:password|secret|apiKey|api_key|token)\s*=\s*"[^"]{8,}"', re.IGNORECASE),
    re.compile(r'(?:password|secret|apiKey|api_key|token)\s*=\s*\'[^\']{8,}\'', re.IGNORECASE),
    re.compile(r'Bearer\s+[A-Za-z0-9\-_]{20,}'),
    re.compile(r'(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}'),  # AWS access key
    re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'),
]

SQL_INJECTION_PATTERNS = [
    re.compile(r'"SELECT\s.*"\s*\+\s*\w+', re.IGNORECASE),
    re.compile(r'String\.format\(\s*"(?:SELECT|INSERT|UPDATE|DELETE)\s', re.IGNORECASE),
    re.compile(r'createQuery\(\s*"[^"]*"\s*\+', re.IGNORECASE),
    re.compile(r'executeQuery\(\s*"[^"]*"\s*\+', re.IGNORECASE),
]

# ---------------------------------------------------------------------------
#  Spring Boot annotation sets
# ---------------------------------------------------------------------------
CONTROLLER_ANNOTATIONS = {
    "@RestController", "@Controller",
}
SERVICE_ANNOTATIONS = {
    "@Service", "@Component",
}
REPOSITORY_ANNOTATIONS = {
    "@Repository",
}
CONFIG_ANNOTATIONS = {
    "@Configuration", "@ConfigurationProperties",
}


class AgentGuardrails:
    """Stateless validation utilities for LLM-generated Java / Spring Boot code."""

    # ------------------------------------------------------------------
    #  Java syntax
    # ------------------------------------------------------------------

    @staticmethod
    def validate_java_syntax(code: str) -> Tuple[bool, List[str]]:
        """Basic Java syntax validation.

        Checks:
          - Balanced braces ``{}``, parentheses ``()``, and brackets ``[]``
          - At least one import or class/interface declaration
          - No obviously broken statements (``;;``, ``{}``, etc.)

        Returns:
            ``(is_valid, list_of_issues)``
        """
        issues: List[str] = []

        # Balanced delimiters
        for open_ch, close_ch, label in [("{", "}", "braces"), ("(", ")", "parentheses"), ("[", "]", "brackets")]:
            depth = 0
            for ch in code:
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                if depth < 0:
                    issues.append(f"Unbalanced {label}: extra closing '{close_ch}'")
                    break
            if depth > 0:
                issues.append(f"Unbalanced {label}: {depth} unclosed '{open_ch}'")

        # Must contain a class, interface, enum, or record declaration (or at least an import)
        has_structure = bool(
            re.search(r'\b(?:class|interface|enum|record)\s+\w+', code)
            or re.search(r'^import\s+', code, re.MULTILINE)
        )
        if not has_structure and len(code) > 100:
            issues.append("No class/interface/enum declaration or import found")

        # Double semicolons (common LLM glitch)
        if ";;" in code:
            issues.append("Double semicolon ';;' detected — likely a generation artifact")

        return (len(issues) == 0, issues)

    # ------------------------------------------------------------------
    #  Spring annotations
    # ------------------------------------------------------------------

    @staticmethod
    def validate_spring_annotations(code: str) -> Tuple[bool, List[str]]:
        """Check that generated Spring Boot code contains expected annotations.

        Returns ``(has_annotations, list_of_missing_hints)``.
        """
        issues: List[str] = []

        # Determine file type heuristically
        is_controller = bool(re.search(r'Mapping\(|@RequestMapping', code))
        is_service = bool(re.search(r'@Transactional|@Async', code))
        is_repository = bool(re.search(r'JpaRepository|CrudRepository|MongoRepository', code))
        is_config = bool(re.search(r'@Bean\b|@Value\(', code))

        if is_controller:
            if not any(ann in code for ann in CONTROLLER_ANNOTATIONS):
                issues.append("Controller-like code missing @RestController or @Controller")

        if is_service:
            if not any(ann in code for ann in SERVICE_ANNOTATIONS):
                issues.append("Service-like code missing @Service or @Component")

        if is_repository:
            if not any(ann in code for ann in REPOSITORY_ANNOTATIONS):
                issues.append("Repository-like code missing @Repository")

        if is_config:
            if not any(ann in code for ann in CONFIG_ANNOTATIONS):
                issues.append("Configuration-like code missing @Configuration")

        # Generic: all class files should have package declaration
        if re.search(r'\bclass\s+\w+', code) and not re.search(r'^package\s+', code, re.MULTILINE):
            issues.append("Class declaration without package statement")

        return (len(issues) == 0, issues)

    # ------------------------------------------------------------------
    #  Security issues
    # ------------------------------------------------------------------

    @staticmethod
    def detect_security_issues(code: str) -> List[str]:
        """Scan for hardcoded secrets and SQL injection patterns."""
        findings: List[str] = []

        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(code):
                snippet = match.group(0)[:60]
                findings.append(f"Possible hardcoded secret: {snippet}...")

        for pattern in SQL_INJECTION_PATTERNS:
            for match in pattern.finditer(code):
                snippet = match.group(0)[:60]
                findings.append(f"Possible SQL injection via string concatenation: {snippet}...")

        return findings

    # ------------------------------------------------------------------
    #  Import validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_imports(code: str) -> List[str]:
        """Check that import statements use known valid package prefixes."""
        issues: List[str] = []
        import_re = re.compile(r'^import\s+(?:static\s+)?([a-zA-Z0-9_.]+)', re.MULTILINE)

        for m in import_re.finditer(code):
            fqn = m.group(1)
            if not any(fqn.startswith(prefix) for prefix in VALID_IMPORT_PREFIXES):
                issues.append(f"Unrecognised import package: {fqn}")

        return issues

    # ------------------------------------------------------------------
    #  Hallucination detection
    # ------------------------------------------------------------------

    @staticmethod
    def check_hallucination(response: str, context: Dict[str, Any]) -> bool:
        """Basic hallucination detection.

        Returns ``True`` if the response likely contains hallucinated content.

        Heuristics:
          - References classes that were never mentioned in context
          - Mentions non-existent Spring Boot starter names
          - Invents MuleSoft element names not in the original XML
        """
        known_elements = set()
        xml_input = context.get("xml_input", "")
        if xml_input:
            known_elements = set(re.findall(r'<([\w:-]+)', xml_input))

        # Check if response references MuleSoft elements not in the input
        referenced_elements = set(re.findall(r'mule:(\w+)|mulesoft:(\w+)', response, re.IGNORECASE))
        referenced_flat = {e for pair in referenced_elements for e in pair if e}

        if referenced_flat and known_elements:
            hallucinated = referenced_flat - known_elements
            if len(hallucinated) > 2:
                logger.warning(
                    "guardrails.hallucination_detected",
                    hallucinated=list(hallucinated)[:5],
                )
                return True

        # Check for fake Spring starters
        fake_starter_pattern = re.compile(r'spring-boot-starter-(?!web|data|security|test|actuator|mail|thymeleaf|validation|cache|aop|batch|integration|amqp|websocket|graphql|quartz|oauth2|logging|jdbc|jpa|mongodb|redis|artemis)\w+')
        fake_starters = fake_starter_pattern.findall(response)
        if len(fake_starters) > 1:
            logger.warning(
                "guardrails.fake_starters_detected",
                starters=fake_starters[:5],
            )
            return True

        return False

    # ------------------------------------------------------------------
    #  Combined validation
    # ------------------------------------------------------------------

    @classmethod
    def validate(
        cls,
        response: str,
        context: "AgentContext",
        *,
        fix_issues: bool = True,
    ) -> str:
        """Run all validations on the response.

        If *fix_issues* is True, attempts to auto-fix trivial problems
        (e.g. strip trailing ``;;``, add missing package declaration).

        Returns the (potentially cleaned) response string.
        """
        all_issues: List[str] = []

        # 1. Java syntax
        is_valid_syntax, syntax_issues = cls.validate_java_syntax(response)
        all_issues.extend(syntax_issues)

        # 2. Spring annotations
        _, annotation_issues = cls.validate_spring_annotations(response)
        all_issues.extend(annotation_issues)

        # 3. Security
        security_issues = cls.detect_security_issues(response)
        all_issues.extend(security_issues)

        # 4. Imports
        import_issues = cls.validate_imports(response)
        all_issues.extend(import_issues)

        # 5. Hallucination
        ctx_dict: Dict[str, Any] = {}
        if hasattr(context, "artifacts"):
            ctx_dict = context.artifacts

        is_hallucinated = cls.check_hallucination(response, ctx_dict)
        if is_hallucinated:
            all_issues.append("Response may contain hallucinated content")

        # Log all issues
        if all_issues:
            logger.warning(
                "guardrails.issues_found",
                count=len(all_issues),
                issues=all_issues[:10],
            )

        # Auto-fix trivial issues
        cleaned = response
        if fix_issues:
            # Remove double semicolons
            cleaned = cleaned.replace(";;", ";")

            # Remove trailing whitespace on each line
            cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))

        return cleaned
