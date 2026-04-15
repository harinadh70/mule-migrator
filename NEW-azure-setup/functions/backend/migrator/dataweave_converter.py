"""
DataWeave to Java Converter – Comprehensive conversion of MuleSoft DataWeave 2.0
expressions, scripts, operators and functions to equivalent Java / Spring code.

Covers:
  Core operators : map, filter, reduce, pluck, mapObject, filterObject,
                   groupBy, orderBy, distinctBy, flatMap, flatten
  String ops     : upper, lower, trim, capitalize, camelize, dasherize,
                   replace, match, matches, contains, startsWith, endsWith,
                   splitBy, joinBy, substringBefore, substringAfter, wrap
  Array ops      : sizeOf, indexOf, flatten, min, max, avg, sum, first, last
  Object ops     : keys, values, entries, merge (++), remove (--), update
  Type coercion  : as String, as Number, as Boolean, as Date, as DateTime
  Null handling  : default, if/else, unless, when/otherwise, null coalescing
  Date / time    : now(), |date|, period, date arithmetic
  Conditional    : if-else, match/case (pattern matching)
  Lambdas / Vars : var, fun, do { }
  MEL compat     : #[payload], flowVars, sessionVars, message.*
"""
import re


# ═══════════════════════════════════════════════════════════════════════════════
#  Main converter
# ═══════════════════════════════════════════════════════════════════════════════
class DataWeaveConverter:
    def __init__(self):
        self.warnings = []
        self.imports_needed = set()
        self._vars = {}       # DataWeave var declarations
        self._functions = {}  # DataWeave fun declarations

    # ── public API ────────────────────────────────────────────────────────
    def convert(self, dw_script: str, agent_context=None) -> dict:
        """Convert a full DataWeave script to Java code.

        Args:
            dw_script: The DataWeave script to convert.
            agent_context: Optional AgentContext for LLM-based fallback on
                           unparseable patterns.
        """
        if not dw_script or not dw_script.strip():
            return {"java_code": "", "imports": [], "warnings": []}

        self.warnings = []
        self.imports_needed = set()
        self._vars = {}
        self._functions = {}
        self._agent_ctx = agent_context

        script = dw_script.strip()

        # Parse header (vars, funs, output type) then body
        header_info = self._parse_header(script)
        body = self._strip_header(script)

        # Simple inline expression
        if self._is_simple_expression(body):
            result = self._convert_simple_expression(body)
            result["output_type"] = header_info.get("output_type", "application/json")
            return result

        # Full body conversion
        java_code = self._convert_body(body)

        # Prepend variable declarations
        var_lines = self._emit_vars()
        fun_lines = self._emit_functions()
        if var_lines or fun_lines:
            java_code = "\n".join(var_lines + fun_lines) + "\n\n" + java_code

        return {
            "java_code": java_code,
            "imports": sorted(self.imports_needed),
            "warnings": self.warnings,
            "output_type": header_info.get("output_type", "application/json"),
        }

    def convert_inline_expression(self, expression: str) -> str:
        """Convert an inline DataWeave / MEL expression such as #[payload.name]."""
        if not expression:
            return ""
        expr = expression.strip()
        if expr.startswith("#[") and expr.endswith("]"):
            expr = expr[2:-1].strip()
        return self._convert_expression(expr)

    # ── Header parsing ────────────────────────────────────────────────────
    def _parse_header(self, script: str) -> dict:
        info = {"output_type": "application/json", "vars": {}, "functions": {}}
        for line in script.split("\n"):
            stripped = line.strip()
            # output type
            m = re.match(r"output\s+(application/\w+)", stripped)
            if m:
                info["output_type"] = m.group(1)
            # var declarations
            m = re.match(r"var\s+(\w+)\s*=\s*(.+)", stripped)
            if m:
                self._vars[m.group(1)] = m.group(2).strip()
            # fun declarations
            m = re.match(r"fun\s+(\w+)\s*\(([^)]*)\)\s*=\s*(.+)", stripped)
            if m:
                self._functions[m.group(1)] = {
                    "params": m.group(2).strip(),
                    "body": m.group(3).strip(),
                }
        return info

    def _strip_header(self, script: str) -> str:
        lines = script.split("\n")
        body_start = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith(("%dw", "output ", "input ", "import ", "var ", "fun ", "ns ", "type ")):
                body_start = i + 1
            elif s == "---":
                body_start = i + 1
                break
        return "\n".join(lines[body_start:]).strip()

    # ── Variable / function emission ──────────────────────────────────────
    def _emit_vars(self):
        lines = []
        for name, value in self._vars.items():
            java_val = self._convert_expression(value)
            lines.append(f"Object {name} = {java_val};")
        return lines

    def _emit_functions(self):
        lines = []
        for fname, fdef in self._functions.items():
            params = fdef["params"]
            body = fdef["body"]
            java_body = self._convert_expression(body)
            java_params = ", ".join(
                f"Object {p.strip()}" for p in params.split(",") if p.strip()
            ) if params else ""
            lines.append(f"// DataWeave function: {fname}")
            lines.append(f"private Object {fname}({java_params}) {{")
            lines.append(f"    return {java_body};")
            lines.append("}")
        return lines

    # ── Expression detection ──────────────────────────────────────────────
    def _is_simple_expression(self, script: str) -> bool:
        s = script.strip()
        if s.startswith("#["):
            return True
        if "\n" not in s and len(s) < 300:
            return True
        return False

    def _convert_simple_expression(self, script: str) -> dict:
        expr = script.strip()
        if expr.startswith("#[") and expr.endswith("]"):
            expr = expr[2:-1].strip()
        java_expr = self._convert_expression(expr)
        return {
            "java_code": java_expr,
            "imports": sorted(self.imports_needed),
            "warnings": self.warnings,
        }

    # ══════════════════════════════════════════════════════════════════════
    #  EXPRESSION CONVERSION  –  the heart of the converter
    # ══════════════════════════════════════════════════════════════════════
    def _convert_expression(self, expr: str) -> str:
        if not expr:
            return '""'
        expr = expr.strip()

        # ── $ (current item in lambda) ──────────────────────────────
        # $.field → item.get("field")  (DW implicit lambda variable)
        expr = re.sub(r"\$\.(\w+)", r'item.get("\1")', expr)
        expr = re.sub(r"\$\$", "index", expr)  # $$ = index in DW

        # ── p() function (MuleSoft property lookup) ──────────────────
        # p('key') → environment.getProperty("key")
        expr = re.sub(r"p\('([^']+)'\)", r'environment.getProperty("\1")', expr)
        expr = re.sub(r'p\("([^"]+)"\)', r'environment.getProperty("\1")', expr)

        # ── payload / attributes / vars references ────────────────────
        # payload."key" → ((Map<String,Object>)payload).get("key")  (DW quoted key access)
        expr = re.sub(r'\bpayload\."(\w+)"', r'((Map<String,Object>)payload).get("\1")', expr)
        # payload[N] → ((List<?>)payload).get(N)
        expr = re.sub(r"\bpayload\[(\d+)\]", r"((List<?>)payload).get(\1)", expr)
        # payload.field.subField → ((Map<String,Object>)payload.get("field")).get("subField")
        expr = re.sub(
            r"\bpayload\.(\w+)\.(\w+)",
            lambda m: f'((Map<String,Object>)payload.get("{m.group(1)}")).get("{m.group(2)}")',
            expr,
        )
        expr = re.sub(r"\bpayload\.(\w+)", r'payload.get("\1")', expr)
        expr = re.sub(r"\bpayload\b(?![\.\[\"])", "payload", expr)

        # attributes.queryParams.x → queryParams.get("x")
        expr = re.sub(r"\battributes\.queryParams\.(\w+)", r'queryParams.get("\1")', expr)
        expr = re.sub(r"\battributes\.queryParams\['([^']+)'\]", r'queryParams.get("\1")', expr)
        expr = re.sub(r'\battributes\.queryParams\["([^"]+)"\]', r'queryParams.get("\1")', expr)

        # attributes.headers → headers param
        expr = re.sub(r"\battributes\.headers\['([^']+)'\]", r'headers.get("\1")', expr)
        expr = re.sub(r'\battributes\.headers\["([^"]+)"\]', r'headers.get("\1")', expr)
        expr = re.sub(r"\battributes\.headers\.(\w+)", r'headers.get("\1")', expr)

        # attributes.uriParams.x → pathVariable
        expr = re.sub(r"\battributes\.uriParams\.(\w+)", r"\1", expr)
        expr = re.sub(r"\battributes\.requestPath\b", '"/"', expr)
        expr = re.sub(r"\battributes\.method\b", '"GET"', expr)
        expr = re.sub(r"\battributes\.statusCode\b", "200", expr)

        # flowVars / vars
        expr = re.sub(r"\bflowVars\['([^']+)'\]", r"\1", expr)
        expr = re.sub(r'\bflowVars\["([^"]+)"\]', r"\1", expr)
        expr = re.sub(r"\bflowVars\.(\w+)", r"\1", expr)
        expr = re.sub(r"\bvars\.(\w+)", r"\1", expr)

        # ── String operations ─────────────────────────────────────────
        expr = re.sub(r"\bupper\(([^)]+)\)", r"\1.toUpperCase()", expr)
        expr = re.sub(r"\blower\(([^)]+)\)", r"\1.toLowerCase()", expr)
        expr = re.sub(r"\btrim\(([^)]+)\)", r"\1.trim()", expr)
        expr = re.sub(r"\bcapitalize\(([^)]+)\)",
                       r'org.apache.commons.lang3.StringUtils.capitalize(\1)', expr)

        # splitBy → .split()
        expr = re.sub(r'(\w[\w.]*)\s+splitBy\s+"([^"]+)"', r'\1.split("\2")', expr)
        expr = re.sub(r"(\w[\w.]*)\s+splitBy\s+'([^']+)'", r'\1.split("\2")', expr)

        # joinBy → String.join()
        expr = re.sub(r'(\w[\w.]*)\s+joinBy\s+"([^"]+)"', r'String.join("\2", \1)', expr)

        # contains
        expr = re.sub(r'(\w[\w.]*)\s+contains\s+"([^"]+)"', r'\1.contains("\2")', expr)
        expr = re.sub(r"(\w[\w.]*)\s+contains\s+(\w+)", r"\1.contains(\2)", expr)

        # startsWith / endsWith
        expr = re.sub(r'(\w[\w.]*)\s+startsWith\s+"([^"]+)"', r'\1.startsWith("\2")', expr)
        expr = re.sub(r'(\w[\w.]*)\s+endsWith\s+"([^"]+)"', r'\1.endsWith("\2")', expr)

        # replace … with …
        expr = re.sub(
            r'(\w[\w.]*)\s+replace\s+"([^"]+)"\s+with\s+"([^"]+)"',
            r'\1.replace("\2", "\3")', expr,
        )
        expr = re.sub(
            r"(\w[\w.]*)\s+replace\s+/([^/]+)/\s+with\s+\"([^\"]+)\"",
            lambda m: f'{m.group(1)}.replaceAll("{m.group(2)}", "{m.group(3)}")', expr,
        )

        # match / matches (regex)
        expr = re.sub(
            r'(\w[\w.]*)\s+matches\s+/([^/]+)/',
            r'\1.matches("\2")', expr,
        )

        # String concatenation: ++ → +
        expr = re.sub(r"\s+\+\+\s+", " + ", expr)

        # substringBefore / substringAfter
        expr = re.sub(
            r'substringBefore\(([^,]+),\s*"([^"]+)"\)',
            r'\1.substring(0, \1.indexOf("\2"))', expr,
        )
        expr = re.sub(
            r'substringAfter\(([^,]+),\s*"([^"]+)"\)',
            r'\1.substring(\1.indexOf("\2") + \2.length())', expr,
        )

        # ── Array / Collection operations ─────────────────────────────
        expr = re.sub(r"\bsizeOf\(([^)]+)\)", r"\1.size()", expr)
        expr = re.sub(r"\bflatten\(([^)]+)\)",
                       r'\1.stream().flatMap(Collection::stream).collect(Collectors.toList())',
                       expr)
        if "Collectors" in expr:
            self.imports_needed.add("java.util.stream.Collectors")
            self.imports_needed.add("java.util.Collection")

        expr = re.sub(r"\bfirst\(([^)]+)\)", r"\1.get(0)", expr)
        expr = re.sub(r"\blast\(([^)]+)\)", r"\1.get(\1.size() - 1)", expr)
        expr = re.sub(r"\bindexOf\(([^,]+),\s*([^)]+)\)", r"\1.indexOf(\2)", expr)

        # min / max / sum / avg on arrays
        expr = re.sub(r"\bmin\(([^)]+)\)",
                       r'\1.stream().mapToDouble(Number::doubleValue).min().orElse(0)', expr)
        expr = re.sub(r"\bmax\(([^)]+)\)",
                       r'\1.stream().mapToDouble(Number::doubleValue).max().orElse(0)', expr)
        expr = re.sub(r"\bsum\(([^)]+)\)",
                       r'\1.stream().mapToDouble(Number::doubleValue).sum()', expr)
        expr = re.sub(r"\bavg\(([^)]+)\)",
                       r'\1.stream().mapToDouble(Number::doubleValue).average().orElse(0)', expr)

        # ── Object operations ─────────────────────────────────────────
        # keysOf / keys
        expr = re.sub(r"\bkeysOf\(([^)]+)\)", r"new ArrayList<>(\1.keySet())", expr)
        expr = re.sub(r"\bvaluesOf\(([^)]+)\)", r"new ArrayList<>(\1.values())", expr)
        expr = re.sub(r"\bentriesOf\(([^)]+)\)", r"new ArrayList<>(\1.entrySet())", expr)

        if "ArrayList" in expr:
            self.imports_needed.add("java.util.ArrayList")

        # ── Null handling ─────────────────────────────────────────────
        # value default "fallback"
        expr = re.sub(
            r'(\w[\w.()\"]*)\s+default\s+"([^"]+)"',
            r'\1 != null ? \1 : "\2"', expr,
        )
        expr = re.sub(
            r"(\w[\w.()\"]*)\s+default\s+(\w+)",
            r"\1 != null ? \1 : \2", expr,
        )

        # isEmpty
        expr = re.sub(r"\bisEmpty\(([^)]+)\)",
                       r"(\1 == null || String.valueOf(\1).isEmpty())", expr)

        # isBlank
        expr = re.sub(r"\bisBlank\(([^)]+)\)",
                       r"(\1 == null || String.valueOf(\1).isBlank())", expr)

        # ── Type coercion ─────────────────────────────────────────────
        # as String {format: "pattern"} → formatted conversion
        expr = re.sub(r'(\w[\w.()]*)\s+as\s+String\s*\{\s*format:\s*"([^"]+)"\s*\}',
                       r'DateTimeFormatter.ofPattern("\2").format(\1)', expr)
        expr = re.sub(r"(\w[\w.()]*)\s+as\s+String", r"String.valueOf(\1)", expr)
        expr = re.sub(r"(\w[\w.()]*)\s+as\s+Number", r"Double.parseDouble(String.valueOf(\1))", expr)
        expr = re.sub(r"(\w[\w.()]*)\s+as\s+Boolean", r"Boolean.parseBoolean(String.valueOf(\1))", expr)

        # as Date / DateTime / LocalDate
        expr = re.sub(r'(\w[\w.()]*)\s+as\s+Date\s*\{\s*format:\s*"([^"]+)"\s*\}',
                       r'LocalDate.parse(String.valueOf(\1), DateTimeFormatter.ofPattern("\2"))', expr)
        expr = re.sub(r"(\w[\w.()]*)\s+as\s+Date",
                       r"LocalDate.parse(String.valueOf(\1))", expr)
        expr = re.sub(r"(\w[\w.()]*)\s+as\s+DateTime",
                       r"LocalDateTime.parse(String.valueOf(\1))", expr)
        expr = re.sub(r"(\w[\w.()]*)\s+as\s+LocalDateTime",
                       r"LocalDateTime.parse(String.valueOf(\1))", expr)

        # Clean up stray {format: ...} blocks that weren't caught above
        expr = re.sub(r'\s*\{format:\s*"[^"]+"\s*\}', '', expr)

        if "LocalDate" in expr:
            self.imports_needed.add("java.time.LocalDate")
        if "LocalDateTime" in expr:
            self.imports_needed.add("java.time.LocalDateTime")
        if "DateTimeFormatter" in expr:
            self.imports_needed.add("java.time.format.DateTimeFormatter")

        # ── Date / time ───────────────────────────────────────────────
        expr = re.sub(r"\bnow\(\)", "LocalDateTime.now()", expr)
        if "LocalDateTime.now()" in expr:
            self.imports_needed.add("java.time.LocalDateTime")

        # ── Logical operators ─────────────────────────────────────────
        expr = re.sub(r"\band\b", "&&", expr)
        expr = re.sub(r"\bor\b", "||", expr)
        expr = re.sub(r"\bnot\b", "!", expr)

        # ── Equality ──────────────────────────────────────────────────
        expr = re.sub(r"\b~=\b", ".equals", expr)

        # ── Type check ────────────────────────────────────────────────
        expr = re.sub(r"(\w+)\s+is\s+String", r"\1 instanceof String", expr)
        expr = re.sub(r"(\w+)\s+is\s+Number", r"\1 instanceof Number", expr)
        expr = re.sub(r"(\w+)\s+is\s+Boolean", r"\1 instanceof Boolean", expr)
        expr = re.sub(r"(\w+)\s+is\s+Array", r"\1 instanceof List", expr)
        expr = re.sub(r"(\w+)\s+is\s+Object", r"\1 instanceof Map", expr)

        # ── MEL compatibility ─────────────────────────────────────────
        expr = re.sub(r"\bmessage\.payload\b", "payload", expr)
        expr = re.sub(r"message\.inboundProperties\['([^']+)'\]", r'request.getHeader("\1")', expr)
        expr = re.sub(r"\bsessionVars\.(\w+)", r"\1", expr)
        expr = re.sub(r"\bserver\.dateTime\b", "LocalDateTime.now()", expr)

        return expr

    # ── LLM Fallback for unparseable DataWeave ────────────────────────────
    def _dw_fallback(self, operation: str, original: str) -> str:
        """Try LLM conversion for an unparseable DataWeave pattern.

        Returns converted Java code, or a TODO comment if conversion is unavailable.
        """
        todo = f"// TODO: Convert {operation}\n// Original: {original}"
        if not self._agent_ctx:
            return todo
        from .llm_agent import convert_unknown_dataweave
        converted = convert_unknown_dataweave(
            self._agent_ctx, original,
            context_hint=f"This is a DataWeave {operation} operation")
        if converted:
            return f"// Converted from DataWeave: {operation}\n{converted}"
        return todo

    # ══════════════════════════════════════════════════════════════════════
    #  BODY CONVERSION  –  handles multi-line DataWeave bodies
    # ══════════════════════════════════════════════════════════════════════
    def _convert_body(self, script: str) -> str:
        s = script.strip()

        # Object literal: { key: value, … }
        if s.startswith("{"):
            return self._convert_object_mapping(s)

        # Array literal: [ … ]
        if s.startswith("["):
            return self._convert_array_literal(s)

        # map operation
        if re.search(r"\bmap\b", s):
            return self._convert_map_operation(s)

        # flatMap
        if re.search(r"\bflatMap\b", s):
            return self._convert_flatmap_operation(s)

        # filter
        if re.search(r"\bfilter\b", s):
            return self._convert_filter_operation(s)

        # reduce
        if re.search(r"\breduce\b", s):
            return self._convert_reduce_operation(s)

        # groupBy
        if re.search(r"\bgroupBy\b", s):
            return self._convert_groupby_operation(s)

        # orderBy
        if re.search(r"\borderBy\b", s):
            return self._convert_orderby_operation(s)

        # distinctBy
        if re.search(r"\bdistinctBy\b", s):
            return self._convert_distinctby_operation(s)

        # pluck
        if re.search(r"\bpluck\b", s):
            return self._convert_pluck_operation(s)

        # mapObject
        if re.search(r"\bmapObject\b", s):
            return self._convert_mapobject_operation(s)

        # filterObject
        if re.search(r"\bfilterObject\b", s):
            return self._convert_filterobject_operation(s)

        # if/else / when/otherwise / match
        if re.search(r"\bif\s*\(", s) or "when " in s:
            return self._convert_conditional(s)
        if re.match(r"\w+\s+match\s*\{", s, re.DOTALL):
            return self._convert_match_expression(s)

        # do { } block
        if s.startswith("do {"):
            return self._convert_do_block(s)

        # Default: line-by-line
        lines = []
        for line in s.split("\n"):
            converted = self._convert_expression(line.strip())
            if converted:
                lines.append(converted)
        return "\n".join(lines)

    # ── Object mapping  { key: value } → Map ─────────────────────────────
    def _convert_object_mapping(self, script: str) -> str:
        self.imports_needed.add("java.util.Map")
        self.imports_needed.add("java.util.LinkedHashMap")

        java_lines = ["Map<String, Object> result = new LinkedHashMap<>();"]
        content = self._extract_braces(script)
        pairs = self._split_pairs(content)

        for pair in pairs:
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            # Handle conditional keys: (key) if condition
            cond_match = re.match(r"\((.+?)\)\s+if\s+(.+)", pair)
            if cond_match:
                inner_pair = cond_match.group(1)
                condition = self._convert_expression(cond_match.group(2).strip())
                if ":" in inner_pair:
                    key, value = inner_pair.split(":", 1)
                    key = key.strip().strip('"').strip("'")
                    java_val = self._convert_expression(value.strip())
                    java_lines.append(f'if ({condition}) {{ result.put("{key}", {java_val}); }}')
                continue

            key, value = pair.split(":", 1)
            key = key.strip().strip('"').strip("'")
            value = value.strip()
            java_val = self._convert_expression(value)
            java_lines.append(f'result.put("{key}", {java_val});')

        # NOTE: Do NOT emit "return result;" here — the caller
        # (flow_converter) handles the assignment to payload/transformed.
        return "\n".join(java_lines)

    # ── Array literal [ … ] ───────────────────────────────────────────────
    def _convert_array_literal(self, script: str) -> str:
        self.imports_needed.add("java.util.List")
        self.imports_needed.add("java.util.Arrays")
        content = script.strip().strip("[]").strip()
        items = self._split_pairs(content)
        java_items = []
        for item in items:
            java_items.append(self._convert_expression(item.strip()))
        return f'List<Object> result = Arrays.asList({", ".join(java_items)});'

    # ── map ───────────────────────────────────────────────────────────────
    def _convert_map_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.List",
                                    "java.util.Map", "java.util.LinkedHashMap"])
        # source map (item, index) -> { body }
        m = re.match(r"(\w[\w.]*)\s+map\s+\((\w+)(?:,\s*(\w+))?\)\s*->\s*(.+)",
                      script, re.DOTALL)
        if not m:
            m = re.match(r"(\w[\w.]*)\s+map\s*\((\w+)\)\s*->\s*(.+)", script, re.DOTALL)
            if m:
                return self._build_stream_map(m.group(1), m.group(2), m.group(3))
            # Simplest form: source map { … }
            m = re.match(r"(\w[\w.]*)\s+map\s*\{(.+)\}", script, re.DOTALL)
            if m:
                return self._build_stream_map(m.group(1), "item", "{" + m.group(2) + "}")
            self.warnings.append("Could not fully parse map operation")
            return self._dw_fallback("map operation", script)

        source = self._convert_expression(m.group(1))
        item_var = m.group(2)
        body = (m.group(4) if m.lastindex == 4 else m.group(3)).strip()
        return self._build_stream_map(source, item_var, body)

    def _build_stream_map(self, source: str, item_var: str, body: str) -> str:
        source_java = self._convert_expression(source) if not source.startswith("((") else source
        body = body.strip()
        if body.startswith("{") and body.endswith("}"):
            # Multi-field mapping
            map_body = self._convert_object_in_lambda(body.strip("{}"), item_var)
            return (
                f"List<Map<String, Object>> result = ((List<Map<String, Object>>) {source_java}).stream()\n"
                f"    .map({item_var} -> {{\n{map_body}\n    }})\n"
                f"    .collect(Collectors.toList());"
            )
        else:
            body_java = self._convert_expression(body)
            return (
                f"List<Object> result = ((List<?>) {source_java}).stream()\n"
                f"    .map({item_var} -> {body_java})\n"
                f"    .collect(Collectors.toList());"
            )

    # ── flatMap ───────────────────────────────────────────────────────────
    def _convert_flatmap_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.List"])
        m = re.match(r"(\w[\w.]*)\s+flatMap\s+\((\w+)\)\s*->\s*(.+)", script, re.DOTALL)
        if not m:
            self.warnings.append("Could not parse flatMap operation")
            return self._dw_fallback("flatMap", script)
        source = self._convert_expression(m.group(1))
        item_var = m.group(2)
        body_java = self._convert_expression(m.group(3).strip())
        return (
            f"List<Object> result = ((List<?>) {source}).stream()\n"
            f"    .flatMap({item_var} -> ((List<?>) {body_java}).stream())\n"
            f"    .collect(Collectors.toList());"
        )

    # ── filter ────────────────────────────────────────────────────────────
    def _convert_filter_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.List"])
        m = re.match(r"(\w[\w.]*)\s+filter\s+\((\w+)(?:,\s*\w+)?\)\s*->\s*(.+)",
                      script, re.DOTALL)
        if not m:
            m = re.match(r"(\w[\w.]*)\s+filter\s+\$\s*(.+)", script, re.DOTALL)
            if m:
                source = self._convert_expression(m.group(1))
                cond = self._convert_expression(m.group(2).strip())
                return (
                    f"List<Object> result = ((List<?>) {source}).stream()\n"
                    f"    .filter(item -> {cond})\n"
                    f"    .collect(Collectors.toList());"
                )
            self.warnings.append("Could not parse filter operation")
            return self._dw_fallback("filter", script)
        source = self._convert_expression(m.group(1))
        item_var = m.group(2)
        condition = self._convert_expression(m.group(3).strip())
        return (
            f"List<Object> result = ((List<?>) {source}).stream()\n"
            f"    .filter({item_var} -> {condition})\n"
            f"    .collect(Collectors.toList());"
        )

    # ── reduce ────────────────────────────────────────────────────────────
    def _convert_reduce_operation(self, script: str) -> str:
        self.imports_needed.add("java.util.List")
        m = re.match(r"(\w[\w.]*)\s+reduce\s+\((\w+),\s*(\w+)\)\s*->\s*(.+)",
                      script, re.DOTALL)
        if not m:
            self.warnings.append("Could not parse reduce operation")
            return self._dw_fallback("reduce", script)
        source = self._convert_expression(m.group(1))
        item_var = m.group(2)
        acc_var = m.group(3)
        body = self._convert_expression(m.group(4).strip())
        return (
            f"Object result = ((List<?>) {source}).stream()\n"
            f"    .reduce(null, ({acc_var}, {item_var}) -> {body});"
        )

    # ── groupBy ───────────────────────────────────────────────────────────
    def _convert_groupby_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.List",
                                    "java.util.Map"])
        m = re.match(r"(\w[\w.]*)\s+groupBy\s+\((\w+)\)\s*->\s*(.+)", script, re.DOTALL)
        if not m:
            m = re.match(r"(\w[\w.]*)\s+groupBy\s+\$\.(\w+)", script, re.DOTALL)
            if m:
                source = self._convert_expression(m.group(1))
                field = m.group(2)
                return (
                    f'Map<Object, List<Object>> result = ((List<Map<String,Object>>) {source}).stream()\n'
                    f'    .collect(Collectors.groupingBy(item -> item.get("{field}")));'
                )
            self.warnings.append("Could not parse groupBy operation")
            return self._dw_fallback("groupBy", script)
        source = self._convert_expression(m.group(1))
        item_var = m.group(2)
        key_expr = self._convert_expression(m.group(3).strip())
        return (
            f"Map<Object, List<Object>> result = ((List<?>) {source}).stream()\n"
            f"    .collect(Collectors.groupingBy({item_var} -> {key_expr}));"
        )

    # ── orderBy ───────────────────────────────────────────────────────────
    def _convert_orderby_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.List",
                                    "java.util.Comparator"])
        m = re.match(r"(\w[\w.]*)\s+orderBy\s+\((\w+)\)\s*->\s*(.+)", script, re.DOTALL)
        if not m:
            m = re.match(r"(\w[\w.]*)\s+orderBy\s+\$\.(\w+)", script, re.DOTALL)
            if m:
                source = self._convert_expression(m.group(1))
                field = m.group(2)
                return (
                    f'List<Object> result = ((List<Map<String,Object>>) {source}).stream()\n'
                    f'    .sorted(Comparator.comparing(item -> String.valueOf(item.get("{field}"))))\n'
                    f'    .collect(Collectors.toList());'
                )
            self.warnings.append("Could not parse orderBy operation")
            return self._dw_fallback("orderBy", script)
        source = self._convert_expression(m.group(1))
        item_var = m.group(2)
        key_expr = self._convert_expression(m.group(3).strip())
        return (
            f"List<Object> result = ((List<?>) {source}).stream()\n"
            f"    .sorted(Comparator.comparing({item_var} -> {key_expr}))\n"
            f"    .collect(Collectors.toList());"
        )

    # ── distinctBy ────────────────────────────────────────────────────────
    def _convert_distinctby_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.List",
                                    "java.util.concurrent.ConcurrentHashMap"])
        m = re.match(r"(\w[\w.]*)\s+distinctBy\s+\((\w+)\)\s*->\s*(.+)", script, re.DOTALL)
        if not m:
            m = re.match(r"(\w[\w.]*)\s+distinctBy\s+\$\.(\w+)", script, re.DOTALL)
            if m:
                source = self._convert_expression(m.group(1))
                field = m.group(2)
                return (
                    f'List<Object> result = ((List<Map<String,Object>>) {source}).stream()\n'
                    f'    .filter(ConcurrentHashMap.newKeySet()::add)\n'
                    f'    .collect(Collectors.toList());\n'
                    f'// NOTE: distinctBy $.{field} — consider using a TreeSet or LinkedHashSet keyed on "{field}"'
                )
            self.warnings.append("Could not parse distinctBy operation")
            return self._dw_fallback("distinctBy", script)
        source = self._convert_expression(m.group(1))
        item_var = m.group(2)
        key_expr = self._convert_expression(m.group(3).strip())
        return (
            f"// distinctBy with key function\n"
            f"java.util.Set<Object> seen = ConcurrentHashMap.newKeySet();\n"
            f"List<Object> result = ((List<?>) {source}).stream()\n"
            f"    .filter({item_var} -> seen.add({key_expr}))\n"
            f"    .collect(Collectors.toList());"
        )

    # ── pluck  (object → array) ──────────────────────────────────────────
    def _convert_pluck_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.List",
                                    "java.util.Map"])
        m = re.match(r"(\w[\w.]*)\s+pluck\s+\((\w+),\s*(\w+)\)\s*->\s*(.+)",
                      script, re.DOTALL)
        if not m:
            self.warnings.append("Could not parse pluck operation")
            return self._dw_fallback("pluck", script)
        source = self._convert_expression(m.group(1))
        val_var = m.group(2)
        key_var = m.group(3)
        body = self._convert_expression(m.group(4).strip())
        return (
            f"List<Object> result = ((Map<String,Object>) {source}).entrySet().stream()\n"
            f"    .map(entry -> {{ Object {key_var} = entry.getKey(); Object {val_var} = entry.getValue(); return {body}; }})\n"
            f"    .collect(Collectors.toList());"
        )

    # ── mapObject ─────────────────────────────────────────────────────────
    def _convert_mapobject_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.Map",
                                    "java.util.LinkedHashMap"])
        m = re.match(r"(\w[\w.]*)\s+mapObject\s+\((\w+),\s*(\w+)\)\s*->\s*\{(.+)\}",
                      script, re.DOTALL)
        if not m:
            self.warnings.append("Could not parse mapObject operation")
            return self._dw_fallback("mapObject", script)
        source = self._convert_expression(m.group(1))
        val_var = m.group(2)
        key_var = m.group(3)
        body = m.group(4).strip()
        pairs = self._split_pairs(body)
        put_lines = []
        for pair in pairs:
            pair = pair.strip()
            if ":" not in pair:
                continue
            k, v = pair.split(":", 1)
            k_java = self._convert_expression(k.strip().strip('"'))
            v_java = self._convert_expression(v.strip())
            put_lines.append(f'        newMap.put({k_java}, {v_java});')
        return (
            f"Map<String, Object> newMap = new LinkedHashMap<>();\n"
            f"((Map<String,Object>) {source}).forEach(({key_var}, {val_var}) -> {{\n"
            + "\n".join(put_lines) + "\n"
            f"}});\n"
            f"Map<String, Object> result = newMap;"
        )

    # ── filterObject ──────────────────────────────────────────────────────
    def _convert_filterobject_operation(self, script: str) -> str:
        self.imports_needed.update(["java.util.stream.Collectors", "java.util.Map",
                                    "java.util.LinkedHashMap"])
        m = re.match(r"(\w[\w.]*)\s+filterObject\s+\((\w+),\s*(\w+)\)\s*->\s*(.+)",
                      script, re.DOTALL)
        if not m:
            self.warnings.append("Could not parse filterObject operation")
            return self._dw_fallback("filterObject", script)
        source = self._convert_expression(m.group(1))
        val_var = m.group(2)
        key_var = m.group(3)
        condition = self._convert_expression(m.group(4).strip())
        return (
            f"Map<String, Object> result = ((Map<String,Object>) {source}).entrySet().stream()\n"
            f"    .filter(entry -> {{ Object {key_var} = entry.getKey(); Object {val_var} = entry.getValue(); return {condition}; }})\n"
            f"    .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue, (a,b)->a, LinkedHashMap::new));"
        )

    # ── Conditional ───────────────────────────────────────────────────────
    def _convert_conditional(self, script: str) -> str:
        # if (cond) expr1 else expr2
        m = re.match(r"if\s*\((.+?)\)\s+(.+?)\s+else\s+(.+)", script, re.DOTALL)
        if m:
            cond = self._convert_expression(m.group(1).strip())
            then_expr = self._convert_expression(m.group(2).strip())
            else_expr = self._convert_expression(m.group(3).strip())
            return f"({cond}) ? {then_expr} : {else_expr}"
        return self._convert_expression(script)

    # ── match / case (pattern matching) ───────────────────────────────────
    def _convert_match_expression(self, script: str) -> str:
        m = re.match(r"(\w+)\s+match\s*\{(.+)\}", script, re.DOTALL)
        if not m:
            self.warnings.append("Could not parse match expression")
            return self._dw_fallback("match expression", script)
        subject = self._convert_expression(m.group(1))
        cases_str = m.group(2).strip()
        lines = [f"// Pattern matching on {subject}"]
        cases = re.split(r"\bcase\b", cases_str)
        first = True
        for case in cases:
            case = case.strip()
            if not case:
                continue
            # else / default
            if case.startswith("else"):
                body = case.replace("else", "", 1).strip().lstrip("->").strip()
                java_body = self._convert_expression(body)
                lines.append(f"}} else {{")
                lines.append(f"    result = {java_body};")
                continue
            # case pattern -> body
            cm = re.match(r"(.+?)\s*->\s*(.+)", case, re.DOTALL)
            if cm:
                pattern = cm.group(1).strip()
                body = cm.group(2).strip()
                java_cond = self._pattern_to_java(subject, pattern)
                java_body = self._convert_expression(body)
                if first:
                    lines.append(f"Object result;")
                    lines.append(f"if ({java_cond}) {{")
                    first = False
                else:
                    lines.append(f"}} else if ({java_cond}) {{")
                lines.append(f"    result = {java_body};")
        if not first:
            lines.append("}")
        return "\n".join(lines)

    def _pattern_to_java(self, subject: str, pattern: str) -> str:
        # is Type
        m = re.match(r"is\s+(\w+)", pattern)
        if m:
            java_type = {"String": "String", "Number": "Number",
                         "Boolean": "Boolean", "Array": "List",
                         "Object": "Map"}.get(m.group(1), m.group(1))
            return f"{subject} instanceof {java_type}"
        # literal match
        if pattern.startswith('"') or pattern.startswith("'"):
            return f"{subject}.equals({pattern})"
        # regex
        if pattern.startswith("/"):
            regex = pattern.strip("/")
            return f'String.valueOf({subject}).matches("{regex}")'
        return f"{subject}.equals({pattern})"

    # ── do { } block ──────────────────────────────────────────────────────
    def _convert_do_block(self, script: str) -> str:
        content = self._extract_braces(script[2:].strip())  # strip "do"
        lines = []
        for line in content.split("\n"):
            converted = self._convert_expression(line.strip())
            if converted:
                lines.append(converted)
        return "// do block\n" + "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════
    def _convert_object_in_lambda(self, body: str, item_var: str) -> str:
        lines = []
        lines.append("        Map<String, Object> obj = new LinkedHashMap<>();")
        pairs = self._split_pairs(body.strip().strip("{}"))
        for pair in pairs:
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            key, value = pair.split(":", 1)
            key = key.strip().strip('"').strip("'")
            value = value.strip()
            java_value = self._convert_expression(value)
            # If _convert_expression didn't handle item_var.field, do it now
            # But skip if already converted to .get("...") form
            if f'{item_var}.get("' not in java_value:
                java_value = re.sub(
                    rf"\b{item_var}\.(\w+)",
                    rf'{item_var}.get("\1")',
                    java_value,
                )
            lines.append(f'        obj.put("{key}", {java_value});')
        lines.append("        return obj;")
        return "\n".join(lines)

    def _extract_braces(self, script: str) -> str:
        """Extract content between the first { and matching }."""
        depth = 0
        start = None
        for i, ch in enumerate(script):
            if ch == "{":
                if depth == 0:
                    start = i + 1
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    return script[start:i]
        return script.strip().strip("{}")

    def _split_pairs(self, content: str) -> list:
        pairs = []
        depth = 0
        current = ""
        in_string = False
        string_char = ""
        for ch in content:
            if in_string:
                current += ch
                if ch == string_char:
                    in_string = False
                continue
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
                current += ch
            elif ch in ("{", "[", "("):
                depth += 1
                current += ch
            elif ch in ("}", "]", ")"):
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                pairs.append(current)
                current = ""
            else:
                current += ch
        if current.strip():
            pairs.append(current)
        return pairs


# ═══════════════════════════════════════════════════════════════════════════════
#  MEL Helper (Mule 3 compatibility)
# ═══════════════════════════════════════════════════════════════════════════════
class DataWeaveExpressionHelper:
    """Convert common Mule Expression Language patterns to Java."""

    @staticmethod
    def convert_mel_expression(expr: str) -> str:
        if not expr:
            return ""
        expr = expr.strip()
        if expr.startswith("#[") and expr.endswith("]"):
            expr = expr[2:-1].strip()

        expr = re.sub(r"\bmessage\.payload\b", "payload", expr)
        expr = re.sub(r"message\.inboundProperties\['([^']+)'\]",
                       r'request.getHeader("\1")', expr)
        expr = re.sub(r"\bsessionVars\.(\w+)", r"\1", expr)
        expr = re.sub(r"\bflowVars\.(\w+)", r"\1", expr)
        expr = re.sub(r"\bserver\.dateTime\b", "LocalDateTime.now()", expr)
        expr = re.sub(r"\bmessage\.outboundProperties\['([^']+)'\]",
                       r'response.getHeaders().get("\1")', expr)
        expr = re.sub(r"\brecordVars\.(\w+)", r"\1", expr)
        return expr
