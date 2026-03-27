const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
  TableOfContents, Bookmark, InternalHyperlink
} = require("docx");

// ─── Constants ───
const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1080; // 0.75" margins
const CONTENT_W = PAGE_W - 2 * MARGIN; // 10080
const ACCENT = "1A56DB";
const ACCENT2 = "2563EB";
const DARK = "111827";
const GRAY = "6B7280";
const LIGHT_BG = "F0F4FF";
const LIGHT_GRAY = "F9FAFB";
const WHITE = "FFFFFF";

const border = { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: WHITE };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

// ─── Helpers ───
const h1 = (text, bookmark) => {
  const children = bookmark
    ? [new Bookmark({ id: bookmark, children: [new TextRun({ text, bold: true, size: 36, font: "Arial", color: DARK })] })]
    : [new TextRun({ text, bold: true, size: 36, font: "Arial", color: DARK })];
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 }, children });
};

const h2 = (text, bookmark) => {
  const children = bookmark
    ? [new Bookmark({ id: bookmark, children: [new TextRun({ text, bold: true, size: 30, font: "Arial", color: ACCENT })] })]
    : [new TextRun({ text, bold: true, size: 30, font: "Arial", color: ACCENT })];
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 150 }, children });
};

const h3 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 },
  children: [new TextRun({ text, bold: true, size: 26, font: "Arial", color: DARK })]
});

const p = (text, opts = {}) => new Paragraph({
  spacing: { after: opts.after || 120, before: opts.before || 0 },
  alignment: opts.align || AlignmentType.LEFT,
  children: [new TextRun({ text, size: opts.size || 22, font: "Arial", color: opts.color || "374151", bold: opts.bold, italics: opts.italics })]
});

const bold_p = (label, text) => new Paragraph({
  spacing: { after: 120 },
  children: [
    new TextRun({ text: label, bold: true, size: 22, font: "Arial", color: DARK }),
    new TextRun({ text, size: 22, font: "Arial", color: "374151" })
  ]
});

const code = (text) => new Paragraph({
  spacing: { before: 60, after: 60 },
  indent: { left: 360 },
  children: [new TextRun({ text, size: 18, font: "Courier New", color: "1F2937" })]
});

const codeBlock = (lines) => lines.map(l => code(l));

const spacer = () => new Paragraph({ spacing: { after: 60 }, children: [] });

// Table helper
const makeTable = (headers, rows, colWidths) => {
  const totalW = colWidths.reduce((a, b) => a + b, 0);
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => new TableCell({
      borders, width: { size: colWidths[i], type: WidthType.DXA },
      shading: { fill: ACCENT, type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, size: 20, font: "Arial", color: WHITE })] })]
    }))
  });
  const dataRows = rows.map((row, ri) => new TableRow({
    children: row.map((cell, ci) => new TableCell({
      borders, width: { size: colWidths[ci], type: WidthType.DXA },
      shading: { fill: ri % 2 === 0 ? LIGHT_GRAY : WHITE, type: ShadingType.CLEAR },
      margins: { top: 50, bottom: 50, left: 100, right: 100 },
      children: [new Paragraph({ children: [new TextRun({ text: String(cell), size: 19, font: "Arial", color: "374151" })] })]
    }))
  }));
  return new Table({ width: { size: totalW, type: WidthType.DXA }, columnWidths: colWidths, rows: [headerRow, ...dataRows] });
};

// Bullet list
const bullet = (text) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  spacing: { after: 60 },
  children: [new TextRun({ text, size: 21, font: "Arial", color: "374151" })]
});

const bulletBold = (label, text) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  spacing: { after: 60 },
  children: [
    new TextRun({ text: label, bold: true, size: 21, font: "Arial", color: DARK }),
    new TextRun({ text, size: 21, font: "Arial", color: "374151" })
  ]
});

const numbered = (text, ref = "numbers") => new Paragraph({
  numbering: { reference: ref, level: 0 },
  spacing: { after: 80 },
  children: [new TextRun({ text, size: 21, font: "Arial", color: "374151" })]
});

// Info box
const infoBox = (title, text) => new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: [CONTENT_W],
  rows: [new TableRow({
    children: [new TableCell({
      borders: { top: { style: BorderStyle.SINGLE, size: 3, color: ACCENT }, bottom: noBorder, left: { style: BorderStyle.SINGLE, size: 3, color: ACCENT }, right: noBorder },
      shading: { fill: LIGHT_BG, type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 200, right: 200 },
      children: [
        new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 22, font: "Arial", color: ACCENT })] }),
        new Paragraph({ spacing: { before: 60 }, children: [new TextRun({ text, size: 20, font: "Arial", color: "374151" })] })
      ]
    })]
  })]
});

// ─────────────────────────────────────────────────────────────────────
// DOCUMENT CONTENT
// ─────────────────────────────────────────────────────────────────────

const sections = [];

// ══════════ COVER PAGE ══════════
sections.push({
  properties: {
    page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } }
  },
  children: [
    spacer(), spacer(), spacer(), spacer(), spacer(), spacer(), spacer(),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "AGENTIC AI MIGRATION PLATFORM", bold: true, size: 52, font: "Arial", color: ACCENT })] }),
    spacer(),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Complete Technical Documentation", size: 32, font: "Arial", color: GRAY })] }),
    spacer(),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "MuleSoft to Spring Boot  |  Self-Hosted RAG  |  Multi-Agent Orchestration", size: 22, font: "Arial", color: GRAY })] }),
    spacer(), spacer(), spacer(), spacer(), spacer(), spacer(),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, border: { top: { style: BorderStyle.SINGLE, size: 2, color: ACCENT } }, children: [] }),
    spacer(),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Version 2.0  |  Enterprise Production Grade", size: 24, font: "Arial", color: DARK, bold: true })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "March 2026", size: 22, font: "Arial", color: GRAY })] }),
    spacer(), spacer(),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Stack: FastAPI  \u00B7  React 18  \u00B7  PostgreSQL 16  \u00B7  Redis 7  \u00B7  Qdrant  \u00B7  Celery  \u00B7  sentence-transformers", size: 18, font: "Arial", color: GRAY })] }),
    spacer(), spacer(), spacer(),
    makeTable(["Component", "Technology", "Purpose"], [
      ["Backend API", "FastAPI + Uvicorn", "Async REST API + WebSocket"],
      ["Task Queue", "Celery + Redis", "Background migration & build jobs"],
      ["Database", "PostgreSQL 16", "Migration history, user data, agent traces"],
      ["Vector DB", "Qdrant (self-hosted)", "RAG knowledge base, migration memory"],
      ["Embeddings", "sentence-transformers", "Local embeddings (all-MiniLM-L6-v2)"],
      ["Cache", "Redis 7", "Embedding cache, session, pub/sub"],
      ["Frontend", "React 18 + TypeScript", "SPA with Agent Pipeline visualization"],
      ["LLM Providers", "Claude, GPT-4o, Gemini, DeepSeek, Groq, Ollama", "Multi-provider with fallback"],
      ["Deployment", "Docker Compose / Helm / Air-Gap", "Maximum portability"],
    ], [2400, 3200, 4480]),
  ]
});

// ══════════ TABLE OF CONTENTS ══════════
sections.push({
  properties: {
    page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } }
  },
  headers: {
    default: new Header({ children: [new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" } }, children: [new TextRun({ text: "Agentic AI Migration Platform \u2014 Complete Documentation", size: 16, font: "Arial", color: GRAY, italics: true })] })] })
  },
  footers: {
    default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Page ", size: 16, font: "Arial", color: GRAY }), new TextRun({ children: [PageNumber.CURRENT], size: 16, font: "Arial", color: GRAY })] })] })
  },
  children: [
    h1("Table of Contents"),
    new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
    new Paragraph({ children: [new PageBreak()] }),

    // ══════════ 1. EXECUTIVE SUMMARY ══════════
    h1("1. Executive Summary", "exec-summary"),
    p("This document provides 100% comprehensive technical documentation for the Agentic AI Migration Platform \u2014 an enterprise-grade system that autonomously converts MuleSoft 4.x applications to Spring Boot 3.2 using a multi-agent AI pipeline backed by self-hosted RAG (Retrieval-Augmented Generation)."),
    spacer(),
    h2("1.1 What Makes This Platform Unique"),
    bulletBold("Agentic AI: ", "Five autonomous agents (Planner, Coder, Reviewer, Tester, Docs) that think, plan, act, observe, and self-correct in a loop \u2014 not just single-shot LLM calls."),
    bulletBold("Self-Hosted RAG: ", "Qdrant vector database + sentence-transformers running 100% locally. Zero data leaves your infrastructure."),
    bulletBold("Multi-Provider LLM: ", "Support for 6 providers (Claude, GPT-4o, Gemini, DeepSeek, Groq, Ollama) with automatic fallback."),
    bulletBold("Production Infrastructure: ", "FastAPI, PostgreSQL, Redis, Celery, WebSocket for enterprise-scale deployment."),
    bulletBold("Maximum Portability: ", "Docker Compose (dev), Kubernetes/Helm (enterprise), Air-Gap bundle (offline/classified)."),
    bulletBold("Multi-Tenancy: ", "Row-Level Security in PostgreSQL, tenant-scoped Redis keys, per-tenant Qdrant collections."),
    spacer(),

    h2("1.2 Platform Capabilities"),
    makeTable(["Capability", "Description", "Technology"], [
      ["MuleSoft XML Parsing", "Parses 30+ MuleSoft connector namespaces, flows, sub-flows, error handlers", "lxml + custom parser (1004 lines)"],
      ["Flow Conversion", "Converts MuleSoft flows to Spring Boot @RestController, @Service, @Scheduled", "FlowConverter (2000+ lines)"],
      ["DataWeave Conversion", "Converts DataWeave 2.0 to Java streams, lambdas, Spring code", "DataWeaveConverter (913 lines)"],
      ["Connector Mapping", "Maps 30+ MuleSoft connectors to Maven dependencies + Spring config", "ConnectorMapper (496 lines)"],
      ["Spring Boot Generation", "Generates complete project: pom.xml, controllers, services, configs, Docker", "SpringBootGenerator (50KB+)"],
      ["OpenAPI Generation", "Creates OpenAPI 3.0 specs from MuleSoft flows or RAML", "SwaggerGenerator (671 lines)"],
      ["LLM Code Review", "Multi-provider validation with scoring, security checks, best practices", "LLMValidator (637 lines)"],
      ["Agentic Pipeline", "5-agent autonomous pipeline with RAG-enhanced prompts", "PipelineOrchestrator"],
      ["RAG Knowledge Base", "800+ indexed documents on MuleSoft + Spring Boot patterns", "Qdrant + sentence-transformers"],
      ["GitHub Integration", "Push generated code to repos via Git Data API (no local git)", "PyGithub"],
      ["Build System", "JAR/WAR/Docker builds with real-time SSE streaming", "Maven wrapper + Docker"],
      ["Real-time Updates", "WebSocket for agent progress, build output streaming", "FastAPI WebSocket + Redis pub/sub"],
    ], [2200, 4400, 3480]),
    spacer(),

    h2("1.3 Architecture Overview (ASCII Diagram)"),
    ...codeBlock([
      "\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
      "\u2502                    BROWSER (React 18 + TypeScript)                \u2502",
      "\u2502  Dashboard | Migration | Swagger | Build | GitHub | Settings | RAG \u2502",
      "\u2502              AgentPipeline.tsx (real-time visualization)           \u2502",
      "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
      "                              \u2502 REST + WebSocket",
      "\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
      "\u2502                    NGINX (Reverse Proxy + TLS)                    \u2502",
      "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
      "                              \u2502",
      "\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
      "\u2502                FastAPI Backend (Uvicorn, 4 workers)               \u2502",
      "\u2502  \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510 \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510 \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510  \u2502",
      "\u2502  \u2502 REST API   \u2502 \u2502 WebSocket   \u2502 \u2502 Agent Orchestrator  \u2502  \u2502",
      "\u2502  \u2502 /api/v2/*  \u2502 \u2502 /ws/*       \u2502 \u2502 5 Specialized Agents\u2502  \u2502",
      "\u2502  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518  \u2502",
      "\u2514\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
      "      \u2502       \u2502        \u2502        \u2502        \u2502       \u2502",
      "\u250C\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2510 \u250C\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2510 \u250C\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2510 \u250C\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2510 \u250C\u2500\u2500\u2500\u2534\u2500\u2510 \u250C\u2500\u2500\u2500\u2534\u2500\u2500\u2510",
      "\u2502Postgres\u2502 \u2502 Redis \u2502 \u2502Qdrant \u2502 \u2502Celery \u2502 \u2502Celery\u2502 \u2502Celery \u2502",
      "\u2502  16   \u2502 \u2502   7   \u2502 \u2502VectorDB\u2502 \u2502Migrate\u2502 \u2502Build \u2502 \u2502Index  \u2502",
      "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2518 \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]),
    spacer(),

    // ══════════ 2. AGENTIC AI PIPELINE ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("2. Agentic AI Pipeline", "agentic-pipeline"),
    p("The core differentiator of this platform is the multi-agent orchestration system. Unlike traditional LLM integration (single call, no autonomy), our agents operate in a think-plan-act-observe-reflect loop."),
    spacer(),

    h2("2.1 What Makes It Agentic"),
    makeTable(["Property", "Non-Agentic (Traditional)", "Agentic AI (This Platform)"], [
      ["Autonomy", "Fixed pipeline, no decisions", "Agents decide what to do next based on context"],
      ["Planning", "No planning step", "Planner Agent analyzes complexity, creates strategy"],
      ["Self-Correction", "LLM scores but does not fix", "Reviewer sends feedback to Coder, iterates until quality >= 7/10"],
      ["Tool Use", "LLM generates text only", "Agents invoke tools: parse XML, validate Java, search RAG, run tests"],
      ["Memory", "Stateless per request", "Short-term (Redis) + Long-term (Qdrant) memory across migrations"],
    ], [2200, 3600, 4280]),
    spacer(),

    h2("2.2 The Agent Loop"),
    p("Every agent follows this execution pattern:"),
    ...codeBlock([
      "async def execute(self, context: AgentContext) -> AgentResult:",
      "    # 1. RETRIEVE - Semantic search from Qdrant knowledge base",
      "    rag_context = await self.retriever.search(query)",
      "",
      "    # 2. THINK - Build prompt with RAG context + agent role",
      "    prompt = self.build_prompt(context, rag_context)",
      "    self.validate_token_budget(prompt)  # Check fits budget",
      "",
      "    # 3. ACT - Call LLM with retry + timeout",
      "    response = await self.call_llm_with_retry(prompt)",
      "",
      "    # 4. VALIDATE - Guardrails check (syntax, security, hallucination)",
      "    validated = await self.guardrails.validate(response, context)",
      "",
      "    # 5. OBSERVE - Parse structured output",
      "    result = self.parse_response(validated)",
      "",
      "    # 6. REFLECT - Update memory + shared context",
      "    await self.memory.store(context, result)",
      "    context.update(self.name, result)",
      "    return result",
    ]),
    spacer(),

    h2("2.3 Pipeline Flow (Detailed)"),
    ...codeBlock([
      "User uploads MuleSoft XML",
      "    |",
      "    v",
      "[PLANNER AGENT] - Analyzes XML, queries RAG for similar migrations",
      "    | Output: MigrationPlan {complexity, connectors, risk_areas}",
      "    v",
      "[EXISTING ENGINE] - parser -> flow_converter -> connector_mapper -> spring_generator",
      "    | Output: Generated Spring Boot project files (UNCHANGED from original engine)",
      "    v",
      "[CODER AGENT] - Handles unknowns pipeline could not convert statically",
      "    | Uses RAG to find Spring Boot patterns, generates code, validates syntax",
      "    v",
      "[REVIEWER AGENT] - Reviews each file individually, scores 1-10",
      "    | If any file < 7/10 -> sends feedback to Coder Agent",
      "    v               ^",
      "    |___FIX LOOP____|  (max 2 iterations)",
      "    v",
      "[TESTER AGENT] --parallel-- [DOCS AGENT]",
      "    | JUnit tests            | README, Migration Report, Swagger",
      "    v                        v",
      "Final Output: Production-ready Spring Boot project",
      "    with tests, docs, 8+/10 quality score",
    ]),
    spacer(),

    h2("2.4 Five Specialized Agents"),
    spacer(),

    h3("2.4.1 Planner Agent"),
    bold_p("Purpose: ", "Analyzes input MuleSoft XML before migration begins. Creates a strategy."),
    bold_p("RAG Queries: ", "\"similar migrations with [connector_list]\", \"complexity patterns for [flow_count] flows\""),
    bold_p("Output: ", "MigrationPlan with complexity level, connectors detected, risk areas, estimated tokens."),
    bold_p("Key Decision: ", "If complexity=\"simple\" and all connectors have static mappings, skip Coder Agent entirely (saves tokens)."),
    p("Example output:"),
    ...codeBlock([
      "MigrationPlan {",
      "  complexity: \"moderate\",",
      "  connectors_detected: [",
      "    {name: \"http\", has_static_mapping: true, rag_pattern_found: true},",
      "    {name: \"twilio\", has_static_mapping: false, rag_pattern_found: true}",
      "  ],",
      "  risk_areas: [{flow: \"twilioSendSMS\", reason: \"Custom connector\"}],",
      "  estimated_agents_needed: [\"coder\", \"reviewer\", \"tester\"],",
      "  estimated_tokens: 12000",
      "}",
    ]),
    spacer(),

    h3("2.4.2 Coder Agent"),
    bold_p("Purpose: ", "Handles unknown elements that the static pipeline could not convert."),
    bold_p("RAG Queries: ", "\"Spring Boot equivalent for [connector_name]\", \"code example for [pattern]\""),
    bold_p("Loop: ", "For each unknown: (1) Search RAG (2) If found, use as template (3) If not, LLM generate (4) Validate syntax (5) Retry if invalid (max 2 retries)"),
    bold_p("Wraps: ", "Existing functions from backend/migrator/llm_agent.py: convert_unknown_element(), convert_unknown_dataweave(), suggest_connector_mapping()"),
    spacer(),

    h3("2.4.3 Reviewer Agent"),
    bold_p("Purpose: ", "Reviews generated code per-file with autonomous fix loop."),
    bold_p("RAG Queries: ", "\"Spring Boot anti-patterns\", \"team coding standards\", \"security best practices\""),
    bold_p("Loop: ", "(1) Review each file individually (2) Score 1-10 (3) If any < 7/10, send feedback to Coder (4) Coder fixes (5) Re-review only changed files (max 2 iterations)"),
    bold_p("Output: ", "ReviewReport { per_file_scores, overall_score, issues_found, issues_fixed, iterations }"),
    spacer(),

    h3("2.4.4 Tester Agent"),
    bold_p("Purpose: ", "Generates comprehensive JUnit 5 test suite."),
    bold_p("RAG Queries: ", "\"@WebMvcTest examples\", \"MockMvc patterns\", \"JUnit 5 assertions\""),
    bold_p("Generates: ", "@WebMvcTest for each controller, @MockBean for dependencies, happy path + error path tests, integration tests."),
    spacer(),

    h3("2.4.5 Docs Agent"),
    bold_p("Purpose: ", "Generates project documentation."),
    bold_p("Generates: ", "README.md, MIGRATION_REPORT.md (what converted vs needs manual review), CHANGELOG.md, enhanced Swagger/OpenAPI spec with examples."),
    spacer(),

    h2("2.5 Agent Error Handling & Fallbacks"),
    makeTable(["Error Type", "Handling", "Fallback"], [
      ["LLM Timeout (120s)", "Retry 3x with exponential backoff", "Use deterministic fallback (TODO comment)"],
      ["Token Budget Exceeded", "Abort agent, return partial result", "Use cached patterns from RAG"],
      ["Parse Error", "Retry with cleaner prompt", "Return raw LLM response with warning"],
      ["3 Consecutive Failures", "Circuit breaker activates", "Skip agent, use static conversion only"],
      ["Invalid Java Syntax", "Retry with error feedback in prompt", "Return code with REVIEW comment"],
      ["Hallucinated Annotation", "Guardrails detect, strip annotation", "Use standard Spring annotations"],
      ["RAG Returns No Results", "Fall back to generic LLM prompt", "Use static connector mapping"],
    ], [2400, 4000, 3680]),
    spacer(),

    h2("2.6 Agent Guardrails"),
    p("Every agent response passes through guardrails before being accepted:"),
    numbered("Java Syntax Validation: Check balanced braces, valid class structure, compilable imports"),
    numbered("Spring Annotation Verification: Confirm @RestController, @Service, @Repository etc. are real annotations"),
    numbered("Security Scan: Detect hardcoded secrets, SQL injection patterns, XSS vulnerabilities"),
    numbered("Import Verification: Check all imported packages exist in Maven Central"),
    numbered("Hallucination Detection: Verify mentioned Spring Boot features actually exist"),
    numbered("PII Detection: Flag and redact any personally identifiable information"),
    numbered("Token Limit Enforcement: Truncate context if approaching model limit"),
    spacer(),

    // ══════════ 3. RAG INFRASTRUCTURE ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("3. RAG Infrastructure (Self-Hosted)", "rag-infra"),
    p("The RAG (Retrieval-Augmented Generation) system provides agents with relevant knowledge from indexed documentation, code patterns, and past migration history. Everything runs locally \u2014 zero data leaves your infrastructure."),
    spacer(),

    h2("3.1 RAG Architecture"),
    ...codeBlock([
      "Query: \"How to convert MuleSoft HTTP listener to Spring Boot?\"",
      "  |",
      "  v",
      "[Embedding Service] - sentence-transformers (all-MiniLM-L6-v2)",
      "  | Converts query to 384-dimensional vector",
      "  v",
      "[Embedding Cache] - Redis (check if query already embedded)",
      "  |",
      "  v",
      "[Qdrant Vector DB] - Dense search (cosine similarity)",
      "  | Returns top-20 candidate chunks",
      "  v",
      "[Reciprocal Rank Fusion] - Merge dense + sparse results",
      "  |",
      "  v",
      "[Relevance Filter] - Drop results below 0.65 similarity",
      "  |",
      "  v",
      "[Context Packer] - Fit results into LLM token budget",
      "  |",
      "  v",
      "Output: 5 most relevant document chunks with metadata",
    ]),
    spacer(),

    h2("3.2 Qdrant Vector Database"),
    infoBox("Self-Hosted", "Qdrant runs as a Docker container on port 6333. All data stored locally in a Docker volume. No cloud dependencies."),
    spacer(),

    h3("3.2.1 Collections"),
    makeTable(["Collection", "Content", "Est. Documents", "Purpose"], [
      ["mulesoft_docs", "Connector XML references, DataWeave cookbook, flow patterns", "~500", "Agent context for MuleSoft understanding"],
      ["springboot_docs", "Starters, annotations, config properties, security patterns", "~300", "Agent context for Spring Boot patterns"],
      ["custom_patterns", "User-uploaded team coding standards, internal APIs", "Variable", "Team-specific code style enforcement"],
      ["migration_history", "Past successful migrations (input + output)", "Grows over time", "Learn from past migrations (RAG memory)"],
    ], [2200, 3800, 1400, 2680]),
    spacer(),

    h3("3.2.2 How to View Qdrant Data"),
    p("Qdrant provides a built-in web UI for browsing collections:"),
    numbered("Open browser: http://localhost:6333/dashboard"),
    numbered("Click on a collection name (e.g., mulesoft_docs)"),
    numbered("Browse points (documents) with their vectors and payloads"),
    numbered("Use the search tab to test semantic queries"),
    p("API endpoints for programmatic access:"),
    ...codeBlock([
      "# List all collections",
      "curl http://localhost:6333/collections",
      "",
      "# Get collection info (document count, vector size)",
      "curl http://localhost:6333/collections/mulesoft_docs",
      "",
      "# Search for similar documents",
      "curl -X POST http://localhost:6333/collections/mulesoft_docs/points/search \\",
      "  -H 'Content-Type: application/json' \\",
      "  -d '{\"vector\": [0.1, 0.2, ...], \"limit\": 5}'",
      "",
      "# Browse points with payload",
      "curl -X POST http://localhost:6333/collections/mulesoft_docs/points/scroll \\",
      "  -d '{\"limit\": 10, \"with_payload\": true}'",
    ]),
    spacer(),

    h3("3.2.3 How to View Embeddings"),
    p("Embeddings are 384-dimensional float vectors. To inspect:"),
    ...codeBlock([
      "# Python - Check embedding for a text",
      "from api.rag.embeddings import EmbeddingService",
      "svc = EmbeddingService()",
      "vec = svc.embed(\"MuleSoft HTTP listener\")",
      "print(f\"Dimension: {len(vec)}\")  # 384",
      "print(f\"Sample values: {vec[:5]}\")",
      "",
      "# Check model info",
      "print(svc.model_info())  # {name, dim, device}",
    ]),
    spacer(),

    h2("3.3 Embedding Service"),
    bold_p("Model: ", "all-MiniLM-L6-v2 (384 dimensions, 22MB, runs on CPU in ~50ms per query)"),
    bold_p("Device Auto-Detection: ", "CUDA GPU > Apple MPS (M1/M2/M3) > CPU"),
    bold_p("Singleton Pattern: ", "Model loaded once on first use, reused across all requests"),
    bold_p("Thread-Safe: ", "Uses threading.Lock to prevent concurrent model initialization"),
    bold_p("Batch Processing: ", "embed_batch() processes up to 64 texts per batch for indexing efficiency"),
    bold_p("L2 Normalization: ", "All embeddings normalized for cosine similarity search"),
    spacer(),

    h2("3.4 Knowledge Base Indexing"),
    p("The indexer processes documents through a pipeline:"),
    numbered("Read document from knowledge/ directory"),
    numbered("Detect document type (XML, Java, Markdown, text)"),
    numbered("Chunk using CodeAwareChunker (respects logical boundaries)"),
    numbered("Compute SHA256 hash for deduplication"),
    numbered("Generate embedding via EmbeddingService"),
    numbered("Upsert into Qdrant with metadata (source, type, section)"),
    spacer(),
    p("How to trigger indexing:"),
    ...codeBlock([
      "# Index all built-in knowledge (MuleSoft + Spring Boot docs)",
      "python -m api.rag.indexer --collection mulesoft_docs --path api/rag/knowledge/mulesoft/",
      "python -m api.rag.indexer --collection springboot_docs --path api/rag/knowledge/springboot/",
      "",
      "# Upload custom patterns via API",
      "curl -X POST http://localhost:8000/api/rag/upload \\",
      "  -F 'files=@my-coding-standards.md' \\",
      "  -F 'collection=custom_patterns'",
      "",
      "# Re-index a collection",
      "curl -X POST http://localhost:8000/api/rag/index \\",
      "  -d '{\"collection\": \"mulesoft_docs\", \"force\": true}'",
    ]),
    spacer(),

    h2("3.5 Chunking Strategy"),
    makeTable(["Document Type", "Chunking Method", "Chunk Size", "Overlap"], [
      ["XML (MuleSoft configs)", "Element boundaries (flow, sub-flow, connector)", "100-512 tokens", "15%"],
      ["Java (Spring Boot code)", "Class/method boundaries via regex", "100-512 tokens", "15%"],
      ["Markdown (documentation)", "Heading-based splitting (##, ###)", "100-512 tokens", "15%"],
      ["Plain text", "Sliding window with sentence boundaries", "100-512 tokens", "15%"],
    ], [2400, 3600, 1800, 2280]),
    spacer(),

    h2("3.6 RAG Cache (Redis-Backed)"),
    bold_p("Purpose: ", "Avoid recomputing embeddings for repeated queries."),
    bold_p("Cache Key: ", "SHA256(text + model_name + model_version)"),
    bold_p("TTL: ", "7 days for knowledge base embeddings, 1 hour for query embeddings"),
    bold_p("Hit Rate Tracking: ", "Prometheus metric rag_cache_hit_ratio tracks hit/miss ratio"),
    spacer(),

    h2("3.7 RAG Admin Endpoints"),
    makeTable(["Endpoint", "Method", "Description"], [
      ["/api/rag/index", "POST", "Trigger re-indexing of a knowledge base collection"],
      ["/api/rag/upload", "POST", "Upload custom documents/patterns"],
      ["/api/rag/collections", "GET", "List all Qdrant collections with document counts"],
      ["/api/rag/search", "GET", "Test semantic search interface"],
      ["/api/rag/collection/{name}", "DELETE", "Clear a collection"],
      ["/api/rag/stats", "GET", "Embedding model info, index statistics, cache hit rate"],
    ], [3000, 1200, 5880]),
    spacer(),

    // ══════════ 4. BACKEND ARCHITECTURE ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("4. Backend Architecture (FastAPI)", "backend-arch"),

    h2("4.1 Directory Structure"),
    ...codeBlock([
      "api/",
      "\u251C\u2500\u2500 main.py               # FastAPI app with lifespan context manager",
      "\u251C\u2500\u2500 config.py             # Pydantic BaseSettings (12-factor app)",
      "\u251C\u2500\u2500 database.py           # SQLAlchemy 2.0 async + asyncpg",
      "\u251C\u2500\u2500 dependencies.py       # FastAPI dependency injection",
      "\u251C\u2500\u2500 exceptions.py         # Custom exception hierarchy",
      "\u251C\u2500\u2500 middleware/",
      "\u2502   \u251C\u2500\u2500 correlation_id.py # X-Correlation-ID propagation",
      "\u2502   \u251C\u2500\u2500 request_logging.py# Structured request/response logging",
      "\u2502   \u251C\u2500\u2500 rate_limit.py     # Redis sliding window rate limiter",
      "\u2502   \u2514\u2500\u2500 error_handler.py  # Global exception -> JSON error mapping",
      "\u251C\u2500\u2500 models/               # SQLAlchemy models (PostgreSQL)",
      "\u251C\u2500\u2500 schemas/              # Pydantic request/response schemas",
      "\u251C\u2500\u2500 routers/v2/           # Versioned API (async + agents)",
      "\u251C\u2500\u2500 services/             # Business logic layer",
      "\u251C\u2500\u2500 tasks/                # Celery background tasks",
      "\u251C\u2500\u2500 websocket/            # WebSocket real-time updates",
      "\u251C\u2500\u2500 agents/               # Agentic AI framework",
      "\u2514\u2500\u2500 rag/                  # RAG infrastructure",
    ]),
    spacer(),

    h2("4.2 Configuration (12-Factor App)"),
    p("All configuration from environment variables via Pydantic BaseSettings:"),
    makeTable(["Setting", "Default", "Description"], [
      ["DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/migrator", "PostgreSQL connection string"],
      ["REDIS_URL", "redis://localhost:6379/0", "Redis connection for caching + pub/sub"],
      ["QDRANT_URL", "http://localhost:6333", "Qdrant vector DB endpoint"],
      ["CELERY_BROKER_URL", "redis://localhost:6379/1", "Celery task broker"],
      ["ANTHROPIC_API_KEY", "", "Claude API key"],
      ["OPENAI_API_KEY", "", "OpenAI API key"],
      ["GOOGLE_API_KEY", "", "Gemini API key"],
      ["EMBEDDING_MODEL", "all-MiniLM-L6-v2", "sentence-transformers model name"],
      ["ENABLE_AGENTS", "true", "Feature flag: enable/disable agent pipeline"],
      ["ENABLE_RAG", "true", "Feature flag: enable/disable RAG"],
      ["MAX_CONTENT_LENGTH", "52428800", "50MB upload limit"],
      ["CORS_ORIGINS", "[\"*\"]", "Allowed CORS origins (restrict in production)"],
      ["JWT_SECRET_KEY", "auto-generated", "JWT signing key (RS256 in production)"],
      ["AGENT_TIMEOUT", "600", "Max pipeline duration in seconds"],
    ], [2800, 2600, 4680]),
    spacer(),

    h2("4.3 Database Models (PostgreSQL)"),
    h3("4.3.1 MigrationJob"),
    ...codeBlock([
      "class MigrationJob(Base):",
      "    __tablename__ = 'migration_jobs'",
      "",
      "    id: UUID (pk, default=uuid4)",
      "    status: Enum(pending, queued, running, completed, failed, cancelled)",
      "    project_name: str",
      "    group_id: str",
      "    java_version: str = '17'",
      "",
      "    # Input (JSONB)",
      "    input_xml_files: list[dict]      # [{name, content, size}]",
      "    dataweave_scripts: dict          # {name: content}",
      "    llm_config: dict                 # {provider, model, enabled}",
      "",
      "    # Output (JSONB)",
      "    output_files: dict               # {filepath: content}",
      "    summary: dict                    # {flows, connectors, warnings}",
      "    llm_validation: dict             # {score, issues}",
      "",
      "    # Agent Tracing (JSONB)",
      "    agent_trace: dict                # {planner: {plan, duration}, coder: {...}}",
      "    total_tokens_used: int",
      "    total_cost_usd: float",
      "",
      "    # Timestamps",
      "    created_at, started_at, completed_at: datetime",
      "    duration_ms: int",
      "    user_id: FK(users.id)",
    ]),
    spacer(),

    h2("4.4 API Reference (All Endpoints)"),
    makeTable(["Endpoint", "Method", "Description", "Auth"], [
      ["/api/health", "GET", "Health check (DB, Redis, Qdrant status)", "No"],
      ["/api/v2/migrations", "POST", "Start async migration (returns 202 + job_id)", "JWT"],
      ["/api/v2/migrations/{id}", "GET", "Get migration status + results", "JWT"],
      ["/api/v2/migrations", "GET", "List all migrations (paginated)", "JWT"],
      ["/api/v2/migrations/{id}/download", "GET", "Download migration as ZIP", "JWT"],
      ["/api/v2/builds", "POST", "Start async build (JAR/WAR/Docker)", "JWT"],
      ["/api/v2/builds/{id}", "GET", "Get build status + artifact URL", "JWT"],
      ["/ws/migrations/{id}", "WS", "Real-time agent progress stream", "Token"],
      ["/ws/builds/{id}", "WS", "Real-time build output stream", "Token"],
      ["/api/swagger/from-xml", "POST", "Generate OpenAPI from MuleSoft XML", "JWT"],
      ["/api/swagger/from-raml", "POST", "Generate OpenAPI from RAML", "JWT"],
      ["/api/github/connect", "POST", "Authenticate GitHub (validate token)", "JWT"],
      ["/api/github/repos", "GET", "List user/org repositories", "JWT"],
      ["/api/github/push", "POST", "Push generated files to repository", "JWT"],
      ["/api/rag/index", "POST", "Trigger knowledge base re-indexing", "Admin"],
      ["/api/rag/upload", "POST", "Upload custom knowledge documents", "JWT"],
      ["/api/rag/search", "GET", "Test RAG semantic search", "JWT"],
      ["/api/rag/collections", "GET", "List Qdrant collections + stats", "JWT"],
      ["/api/auth/login", "POST", "Login (returns JWT access + refresh tokens)", "No"],
      ["/api/auth/register", "POST", "Register new user", "No"],
      ["/api/auth/refresh", "POST", "Refresh access token", "Refresh"],
      ["/api/v1/migrate", "POST", "Legacy sync migration (backward compat)", "No"],
    ], [2800, 900, 4200, 1080]),
    spacer(),

    h2("4.5 WebSocket Messages"),
    p("Migration WebSocket (/ws/migrations/{id}) sends typed JSON messages:"),
    makeTable(["type", "Description", "Example Data"], [
      ["agent_start", "An agent began execution", "{agent: \"planner\", timestamp: \"...\"}"],
      ["agent_progress", "Agent is working", "{agent: \"reviewer\", file: \"Controller.java\", progress: 0.6}"],
      ["agent_complete", "Agent finished", "{agent: \"reviewer\", duration_ms: 2300, tokens: 1500, score: 8.5}"],
      ["rag_query", "Agent queried RAG", "{agent: \"coder\", query: \"twilio spring boot\", results: 3}"],
      ["review_loop", "Reviewer sent feedback to Coder", "{iteration: 1, issues: 3, files_affected: 2}"],
      ["pipeline_complete", "All agents done", "{total_duration_ms: 15000, overall_score: 8.7}"],
      ["error", "Something failed", "{agent: \"tester\", error: \"LLM timeout\", fallback_used: true}"],
      ["heartbeat", "Keep-alive (every 30s)", "{timestamp: \"...\"}"],
    ], [2200, 3200, 4680]),
    spacer(),

    // ══════════ 5. EXISTING MIGRATION ENGINE ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("5. Core Migration Engine (Preserved)", "migration-engine"),
    p("The existing migration engine (8 Python modules, ~5,500 lines) is the intellectual property core. It is preserved unchanged and wrapped by the Agentic AI pipeline."),
    spacer(),

    h2("5.1 Engine Modules"),
    makeTable(["Module", "Lines", "Purpose"], [
      ["parser.py", "1004", "MuleSoft XML parser with 30+ namespace registry"],
      ["flow_converter.py", "2000+", "Converts flows to @RestController, @Service, @Scheduled"],
      ["connector_mapper.py", "496", "Maps 30+ connectors to Maven deps + Spring config"],
      ["dataweave_converter.py", "913", "Converts DataWeave 2.0 to Java streams + lambdas"],
      ["spring_generator.py", "50KB+", "Generates complete Spring Boot project structure"],
      ["swagger_generator.py", "671", "OpenAPI 3.0 generation from flows or RAML"],
      ["llm_agent.py", "333", "LLM-powered fallback for unknown elements"],
      ["llm_validator.py", "637", "Multi-provider LLM validation with 6 providers"],
    ], [3000, 1000, 6080]),
    spacer(),

    h2("5.2 Supported MuleSoft Connectors (30+)"),
    makeTable(["Connector", "Spring Boot Equivalent", "Maven Dependency"], [
      ["HTTP Listener/Request", "@RestController + RestTemplate/WebClient", "spring-boot-starter-web/webflux"],
      ["Database (MySQL/Oracle/Postgres)", "Spring Data JPA + JdbcTemplate", "spring-boot-starter-data-jpa"],
      ["JMS", "@JmsListener + JmsTemplate", "spring-boot-starter-activemq"],
      ["AMQP (RabbitMQ)", "@RabbitListener + RabbitTemplate", "spring-boot-starter-amqp"],
      ["Kafka", "@KafkaListener + KafkaTemplate", "spring-kafka"],
      ["File", "Java NIO (Path, Files)", "built-in"],
      ["SFTP", "Spring Integration SFTP", "spring-integration-sftp"],
      ["Email", "JavaMailSender", "spring-boot-starter-mail"],
      ["Salesforce", "RestTemplate + OAuth2", "spring-boot-starter-web"],
      ["AWS S3", "AmazonS3Client", "software.amazon.awssdk:s3"],
      ["AWS SQS", "SQS Listener", "spring-cloud-aws-messaging"],
      ["MongoDB", "MongoTemplate + Repository", "spring-boot-starter-data-mongodb"],
      ["Redis", "RedisTemplate + Repository", "spring-boot-starter-data-redis"],
      ["Elasticsearch", "ElasticsearchRepository", "spring-boot-starter-data-elasticsearch"],
      ["Batch", "Spring Batch Job", "spring-boot-starter-batch"],
      ["WebServices (SOAP)", "WebServiceTemplate", "spring-boot-starter-web-services"],
      ["Validation", "Bean Validation", "spring-boot-starter-validation"],
      ["OAuth/Security", "Spring Security + OAuth2", "spring-boot-starter-security"],
    ], [2600, 3800, 3680]),
    spacer(),

    h2("5.3 LLM Provider Support (6 Providers, 20+ Models)"),
    makeTable(["Provider", "Models", "API Key Env Var", "Notes"], [
      ["Anthropic Claude", "claude-sonnet-4, claude-3-5-sonnet, claude-3-opus, claude-3-5-haiku", "ANTHROPIC_API_KEY", "Best for code reasoning"],
      ["OpenAI GPT", "gpt-4o, gpt-4-turbo, gpt-4o-mini, o3-mini", "OPENAI_API_KEY", "Most widely used"],
      ["Google Gemini", "gemini-2.5-pro, gemini-2.0-flash, gemini-1.5-pro", "GOOGLE_API_KEY", "Long context window"],
      ["DeepSeek", "deepseek-chat, deepseek-coder, deepseek-reasoner", "DEEPSEEK_API_KEY", "Cost-effective"],
      ["Groq", "llama-3.3-70b, mixtral-8x7b", "GROQ_API_KEY", "Free tier, fast inference"],
      ["Ollama (Local)", "codellama, llama3, deepseek-coder-v2, mistral", "None (local)", "Air-gapped, no API keys"],
    ], [1800, 3400, 2200, 2680]),
    spacer(),

    // ══════════ 6. DEPLOYMENT ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("6. Deployment Guide", "deployment"),

    h2("6.1 Mode 1: Docker Compose (Development / Single Machine)"),
    p("Simplest deployment. One command starts everything."),
    ...codeBlock([
      "# Quick start",
      "git clone https://github.com/org/migrator-platform.git",
      "cd migrator-platform",
      "cp deploy/docker-compose/.env.example .env",
      "# Edit .env with your API keys",
      "docker compose -f deploy/docker-compose/docker-compose.yml up -d",
      "",
      "# Initialize database",
      "docker compose exec api alembic upgrade head",
      "",
      "# Seed RAG knowledge base",
      "docker compose exec api python -m api.rag.indexer",
      "",
      "# Open http://localhost:3000 (React frontend)",
      "# API at http://localhost:8000",
      "# Qdrant dashboard at http://localhost:6333/dashboard",
    ]),
    spacer(),

    h2("6.2 Mode 2: Kubernetes / Helm (Enterprise)"),
    ...codeBlock([
      "# Single-tenant deployment",
      "helm install migrator ./deploy/helm/migrator-platform \\",
      "  --namespace migrator --create-namespace \\",
      "  -f values.yaml \\",
      "  --set secrets.anthropicApiKey=$ANTHROPIC_API_KEY",
      "",
      "# Multi-tenant for specific client",
      "helm install migrator-acme ./deploy/helm/migrator-platform \\",
      "  -f values-multi-tenant.yaml \\",
      "  --set tenant.name=acme-corp \\",
      "  --set tenant.namespace=acme-corp",
    ]),
    spacer(),

    h2("6.3 Mode 3: Air-Gapped (No Internet)"),
    p("For classified or restricted environments with zero internet access:"),
    ...codeBlock([
      "# On build machine (WITH internet):",
      "./deploy/airgap/bundle.sh v1.0.0",
      "# Creates: migrator-platform-v1.0.0.tar.gz (~3GB)",
      "# Contains: Docker images, ML models, pre-indexed knowledge base",
      "",
      "# Transfer to client machine via USB/SFTP",
      "",
      "# On client machine (NO internet):",
      "tar xzf migrator-platform-v1.0.0.tar.gz",
      "cd migrator-platform-v1.0.0/",
      "./install.sh",
      "# Loads Docker images, starts all services",
      "# Open http://localhost:3000",
    ]),
    spacer(),

    h2("6.4 Docker Compose Services"),
    makeTable(["Service", "Image", "Port", "Purpose"], [
      ["api", "migrator-api:latest", "8000", "FastAPI application server (4 Uvicorn workers)"],
      ["celery-migration-worker", "migrator-api:latest", "-", "Background migration tasks (2 concurrent)"],
      ["celery-build-worker", "migrator-api:latest", "-", "Background build tasks (4 concurrent)"],
      ["celery-indexing-worker", "migrator-api:latest", "-", "RAG indexing tasks (1 worker, GPU-bound)"],
      ["celery-beat", "migrator-api:latest", "-", "Scheduled tasks (daily reindex, weekly prune)"],
      ["postgres", "postgres:16-alpine", "5432", "Primary database (migration history, users)"],
      ["redis", "redis:7-alpine", "6379", "Cache, session, pub/sub, Celery broker"],
      ["qdrant", "qdrant/qdrant:latest", "6333", "Vector DB for RAG knowledge base"],
      ["nginx", "nginx:alpine", "80/443", "Reverse proxy, TLS termination, static files"],
    ], [2800, 2200, 800, 4280]),
    spacer(),

    // ══════════ 7. MULTI-TENANCY ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("7. Multi-Tenancy Architecture", "multi-tenancy"),
    p("The platform supports both single-tenant (one instance per client) and multi-tenant (shared instance) deployment."),
    spacer(),
    makeTable(["Layer", "Isolation Method", "Implementation"], [
      ["PostgreSQL", "Row-Level Security (RLS)", "CREATE POLICY tenant_isolation USING (tenant_id = current_setting('app.tenant_id'))"],
      ["Redis", "Key prefix per tenant", "Key format: tenant:{tenant_id}:migration:{job_id}"],
      ["Qdrant", "Collection per tenant OR payload filter", "Collections: {tenant_id}_mulesoft_docs or filter by tenant_id"],
      ["Celery", "Task routing per tenant", "Enterprise tenants get dedicated workers with priority queues"],
      ["API", "Tenant context middleware", "Extract tenant_id from JWT, inject into every DB/Redis/Qdrant call"],
    ], [1800, 3000, 5280]),
    spacer(),

    // ══════════ 8. SECURITY ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("8. Security & Authentication", "security"),

    h2("8.1 Authentication"),
    bulletBold("JWT (RS256): ", "Asymmetric tokens. Public key can verify without secret. 15-min access tokens + 7-day refresh tokens."),
    bulletBold("GitHub OAuth2 SSO: ", "Login with GitHub account. Automatic user creation on first login."),
    bulletBold("API Keys: ", "Encrypted at rest in PostgreSQL using Fernet. 90-day rotation policy."),
    bulletBold("Rate Limiting: ", "Redis sliding window. 10 migrations/hour/user, 100 RAG queries/hour/user."),
    spacer(),

    h2("8.2 Secrets Management"),
    makeTable(["Secret Type", "Storage", "Rotation"], [
      ["LLM API Keys", "Environment variables (Vault in production)", "90 days"],
      ["DB Passwords", "Vault dynamic credentials (unique per pod)", "1 hour TTL"],
      ["JWT Signing Keys", "RS256 key pair in Vault", "Annually"],
      ["GitHub Tokens", "Encrypted in PostgreSQL (Fernet)", "User-managed"],
    ], [2400, 4200, 3480]),
    spacer(),

    h2("8.3 Compliance"),
    bulletBold("SOC 2 Type II: ", "All API access logged with user, timestamp, IP, action. Encryption at rest and in transit (TLS 1.3)."),
    bulletBold("GDPR: ", "No user data sent to external APIs (use Ollama). Data retention policies. Right to erasure (cascade delete). Data export API."),
    bulletBold("Air-Gapped: ", "Zero external network calls. All models bundled. Knowledge pre-indexed. Ollama with local LLM."),
    spacer(),

    // ══════════ 9. MONITORING ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("9. Monitoring & Observability", "monitoring"),

    h2("9.1 Prometheus Metrics"),
    makeTable(["Metric", "Type", "Labels", "Description"], [
      ["migration_duration_seconds", "Histogram", "complexity, agent_count", "Time to complete a migration"],
      ["agent_execution_seconds", "Histogram", "agent_name, status", "Per-agent execution time"],
      ["rag_search_latency_seconds", "Histogram", "collection", "RAG search response time"],
      ["rag_cache_hit_ratio", "Gauge", "-", "Cache hit rate (0.0-1.0)"],
      ["llm_tokens_total", "Counter", "provider, model, agent", "Total LLM tokens consumed"],
      ["llm_cost_usd_total", "Counter", "-", "Cumulative LLM API cost"],
      ["celery_queue_depth", "Gauge", "queue_name", "Tasks waiting in queue"],
      ["websocket_connections_active", "Gauge", "-", "Active WebSocket connections"],
    ], [3000, 1400, 2400, 3280]),
    spacer(),

    h2("9.2 Structured Logging"),
    p("All logs are JSON-formatted with structlog:"),
    ...codeBlock([
      "{",
      "  \"timestamp\": \"2026-03-21T10:30:00Z\",",
      "  \"level\": \"info\",",
      "  \"event\": \"agent_completed\",",
      "  \"correlation_id\": \"abc-123-def\",",
      "  \"agent\": \"reviewer\",",
      "  \"duration_ms\": 2300,",
      "  \"tokens_used\": 1500,",
      "  \"score\": 8.5,",
      "  \"migration_id\": \"uuid-here\"",
      "}",
    ]),
    spacer(),
    p("Correlation ID flows: HTTP request -> Celery task -> WebSocket message -> log entries. Enables tracing a single migration across all systems."),
    spacer(),

    h2("9.3 Grafana Dashboards"),
    bullet("Migration Pipeline: Duration P50/P95/P99, agent scores, token usage, cost per migration"),
    bullet("RAG Performance: Search latency, cache hit rate, collection sizes, indexing throughput"),
    bullet("Infrastructure: Celery queue depth, DB connections, Redis memory, Qdrant storage"),
    bullet("LLM Providers: Latency per provider, error rates, token costs, fallback frequency"),
    spacer(),

    // ══════════ 10. FRONTEND ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("10. Frontend Architecture (React)", "frontend"),

    h2("10.1 Tech Stack"),
    makeTable(["Technology", "Purpose"], [
      ["React 18", "Component framework with concurrent features"],
      ["TypeScript", "Type safety matching Pydantic backend schemas"],
      ["Vite", "Build tool with HMR and /api proxy to FastAPI"],
      ["Tailwind CSS", "Utility-first styling with dark mode support"],
      ["Monaco Editor", "VS Code-like editor for XML/Java/YAML editing"],
      ["React Flow", "Interactive architecture diagrams"],
      ["Zustand", "Lightweight state management (replaces localStorage)"],
      ["TanStack Query", "Server state caching, background refetching"],
      ["Framer Motion", "Animations and micro-interactions"],
      ["xterm.js", "Terminal emulator for build console output"],
    ], [2400, 7680]),
    spacer(),

    h2("10.2 Pages"),
    makeTable(["Page", "Route", "Key Features"], [
      ["Dashboard", "/", "Migration history (from DB), stats, quick actions"],
      ["Migration", "/migrate", "XML upload, agent pipeline visualization, file tree, code editor"],
      ["Swagger", "/swagger", "Generate OpenAPI from XML/RAML, preview, download"],
      ["Build", "/build", "JAR/WAR/Docker build, terminal output via WebSocket"],
      ["GitHub", "/github", "Connect, browse repos, push code, create repos/branches"],
      ["Settings", "/settings", "LLM config, project defaults, GitHub token, RAG settings"],
      ["RAG", "/rag", "Knowledge base management, search playground, indexing status"],
    ], [1600, 1400, 7080]),
    spacer(),

    h2("10.3 Agent Pipeline Visualization (Key Component)"),
    p("The AgentPipeline.tsx component shows real-time agent progress via WebSocket:"),
    bullet("Visual pipeline diagram: Planner -> Coder -> Reviewer -> Tester -> Docs"),
    bullet("Each agent shows: status (waiting/running/done), duration, findings, token usage"),
    bullet("Expandable detail panel: RAG context retrieved, LLM prompt sent, response received"),
    bullet("Review loop: Visual iteration counter (Reviewer <-> Coder) with diff view"),
    bullet("Token budget: Real-time cost tracking per agent and total"),
    spacer(),

    // ══════════ 11. TROUBLESHOOTING ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("11. Troubleshooting Guide", "troubleshooting"),

    makeTable(["Problem", "Cause", "Solution"], [
      ["Qdrant not starting", "Port 6333 in use", "docker compose down && docker compose up -d qdrant"],
      ["Embedding model download fails", "No internet / firewall", "Pre-download model: python -c \"from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')\""],
      ["Migration hangs", "LLM timeout", "Check AGENT_TIMEOUT setting. Increase to 900s for complex migrations."],
      ["WebSocket disconnects", "Nginx timeout", "Set proxy_read_timeout 600s in nginx.conf"],
      ["Celery tasks stuck", "Redis connection lost", "Check Redis health: redis-cli ping. Restart worker: docker compose restart celery-migration-worker"],
      ["RAG returns irrelevant results", "Knowledge base not indexed", "Run: python -m api.rag.indexer --collection mulesoft_docs"],
      ["Out of memory (Celery worker)", "Large migration + embeddings", "Increase memory limit: celery-migration-worker limits: memory: 8Gi"],
      ["Agent scores low (<5/10)", "Generic prompts, no RAG context", "Upload team coding standards to custom_patterns collection"],
      ["PostgreSQL connection refused", "DB not initialized", "Run: docker compose exec api alembic upgrade head"],
      ["JWT token expired", "Access token TTL=15min", "Client should auto-refresh via /api/auth/refresh endpoint"],
      ["Air-gap install fails", "Missing Docker images", "Re-run bundle.sh on internet machine, verify all .tar files present"],
      ["Helm install fails", "Missing secrets", "Create Kubernetes secret: kubectl create secret generic migrator-secrets ..."],
    ], [2400, 2600, 5080]),
    spacer(),

    // ══════════ 12. COMPLETE FILE INVENTORY ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("12. Complete File Inventory", "file-inventory"),
    p("Every file in the platform with its purpose:"),
    spacer(),

    h2("12.1 Backend (api/)"),
    makeTable(["File", "Lines (est.)", "Purpose"], [
      ["api/main.py", "150", "FastAPI application factory with lifespan"],
      ["api/config.py", "120", "Pydantic BaseSettings (all env vars)"],
      ["api/database.py", "80", "SQLAlchemy async engine + session"],
      ["api/dependencies.py", "60", "FastAPI dependency injection"],
      ["api/exceptions.py", "80", "Custom exception hierarchy"],
      ["api/models/migration.py", "60", "MigrationJob SQLAlchemy model"],
      ["api/models/build.py", "40", "BuildJob SQLAlchemy model"],
      ["api/models/user.py", "40", "User model with hashed password"],
      ["api/models/agent_trace.py", "35", "Per-agent execution record"],
      ["api/schemas/migration.py", "80", "Pydantic request/response schemas"],
      ["api/routers/v2/migrations.py", "120", "Migration API (async + WebSocket)"],
      ["api/routers/v2/builds.py", "80", "Build API"],
      ["api/routers/v2/rag.py", "100", "RAG admin endpoints"],
      ["api/services/migration_service.py", "100", "Migration orchestration logic"],
      ["api/tasks/celery_app.py", "40", "Celery configuration"],
      ["api/tasks/migration_tasks.py", "60", "Background migration task"],
      ["api/websocket/manager.py", "80", "WebSocket connection manager"],
      ["api/websocket/migration_ws.py", "60", "Migration progress stream"],
    ], [3200, 1200, 5680]),
    spacer(),

    h2("12.2 RAG (api/rag/)"),
    makeTable(["File", "Lines (est.)", "Purpose"], [
      ["api/rag/embeddings.py", "120", "Singleton embedding service (sentence-transformers)"],
      ["api/rag/vector_store.py", "180", "Qdrant client with retry + health check"],
      ["api/rag/chunking.py", "200", "Code-aware document chunking"],
      ["api/rag/indexer.py", "250", "Document ingestion pipeline"],
      ["api/rag/retriever.py", "200", "Hybrid search (dense + sparse + fusion)"],
      ["api/rag/cache.py", "80", "Redis-backed embedding cache"],
      ["api/rag/schemas.py", "60", "Pydantic models for RAG"],
      ["api/rag/config.py", "40", "RAG-specific settings"],
    ], [3200, 1200, 5680]),
    spacer(),

    h2("12.3 Agents (api/agents/)"),
    makeTable(["File", "Lines (est.)", "Purpose"], [
      ["api/agents/base.py", "200", "BaseAgent with lifecycle, retry, guardrails"],
      ["api/agents/context.py", "120", "Extended AgentContext with traces"],
      ["api/agents/result.py", "60", "Structured AgentResult"],
      ["api/agents/orchestrator.py", "250", "Pipeline sequencer with DAG execution"],
      ["api/agents/planner.py", "150", "Analyzes XML, creates migration plan"],
      ["api/agents/coder.py", "200", "Handles unknowns with RAG"],
      ["api/agents/reviewer.py", "180", "Per-file review with fix loop"],
      ["api/agents/tester.py", "150", "JUnit test generation"],
      ["api/agents/docs.py", "150", "Documentation generation"],
      ["api/agents/memory.py", "100", "Short-term (Redis) + Long-term (Qdrant)"],
      ["api/agents/guardrails.py", "150", "Output validation + safety checks"],
      ["api/agents/tools.py", "80", "Tool registry for agent function calling"],
    ], [3200, 1200, 5680]),
    spacer(),

    h2("12.4 Existing Engine (backend/migrator/)"),
    makeTable(["File", "Lines", "Purpose"], [
      ["backend/migrator/parser.py", "1004", "MuleSoft XML parser (30+ namespaces)"],
      ["backend/migrator/flow_converter.py", "2000+", "Flow to Spring Boot conversion"],
      ["backend/migrator/connector_mapper.py", "496", "Connector to Maven dependency mapping"],
      ["backend/migrator/dataweave_converter.py", "913", "DataWeave 2.0 to Java conversion"],
      ["backend/migrator/spring_generator.py", "50KB+", "Complete Spring Boot project generation"],
      ["backend/migrator/swagger_generator.py", "671", "OpenAPI 3.0 specification generation"],
      ["backend/migrator/llm_agent.py", "333", "LLM fallback for unknown elements"],
      ["backend/migrator/llm_validator.py", "637", "Multi-provider LLM validation"],
    ], [3800, 1000, 5280]),
    spacer(),

    // ══════════ APPENDIX ══════════
    new Paragraph({ children: [new PageBreak()] }),
    h1("Appendix A: Sample MuleSoft XML", "appendix-a"),
    p("Example MuleSoft HTTP Hello World flow (one of 6 built-in samples):"),
    ...codeBlock([
      "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
      "<mule xmlns:http=\"http://www.mulesoft.org/schema/mule/http\"",
      "      xmlns:ee=\"http://www.mulesoft.org/schema/mule/ee/core\"",
      "      xmlns=\"http://www.mulesoft.org/schema/mule/core\">",
      "",
      "  <http:listener-config name=\"HTTP_Listener_config\">",
      "    <http:listener-connection host=\"0.0.0.0\" port=\"8081\" />",
      "  </http:listener-config>",
      "",
      "  <flow name=\"helloWorldFlow\">",
      "    <http:listener config-ref=\"HTTP_Listener_config\" path=\"/hello\"",
      "                   allowedMethods=\"GET\" />",
      "    <ee:transform>",
      "      <ee:message>",
      "        <ee:set-payload><![CDATA[%dw 2.0",
      "output application/json",
      "---",
      "{message: \"Hello, World!\", timestamp: now()}]]>",
      "        </ee:set-payload>",
      "      </ee:message>",
      "    </ee:transform>",
      "    <logger level=\"INFO\" message=\"Request on /hello\" />",
      "  </flow>",
      "</mule>",
    ]),
    spacer(),

    h1("Appendix B: Generated Spring Boot Code Example", "appendix-b"),
    p("What the platform generates from the above MuleSoft XML:"),
    ...codeBlock([
      "@RestController",
      "@RequestMapping(\"/\")",
      "@Tag(name = \"HelloWorld\", description = \"Hello World operations\")",
      "public class HelloWorldController {",
      "",
      "    private static final Logger log = LoggerFactory.getLogger(",
      "        HelloWorldController.class);",
      "",
      "    @GetMapping(\"/hello\")",
      "    @Operation(summary = \"Hello World endpoint\")",
      "    @ApiResponse(responseCode = \"200\", description = \"Success\")",
      "    public ResponseEntity<Map<String, Object>> helloWorld() {",
      "        log.info(\"Request on /hello\");",
      "        Map<String, Object> response = new HashMap<>();",
      "        response.put(\"message\", \"Hello, World!\");",
      "        response.put(\"timestamp\", Instant.now());",
      "        return ResponseEntity.ok(response);",
      "    }",
      "}",
    ]),
    spacer(),

    h1("Appendix C: Quick Reference Commands", "appendix-c"),
    makeTable(["Task", "Command"], [
      ["Start all services", "docker compose -f deploy/docker-compose/docker-compose.yml up -d"],
      ["Initialize database", "docker compose exec api alembic upgrade head"],
      ["Seed RAG knowledge base", "docker compose exec api python -m api.rag.indexer"],
      ["View Qdrant dashboard", "http://localhost:6333/dashboard"],
      ["View API docs (Swagger)", "http://localhost:8000/docs"],
      ["Check service health", "curl http://localhost:8000/api/health"],
      ["View Celery queues", "docker compose exec celery-migration-worker celery -A api.tasks.celery_app inspect active"],
      ["Backup PostgreSQL", "docker compose exec postgres pg_dump -U postgres migrator > backup.sql"],
      ["Backup Qdrant", "curl -X POST http://localhost:6333/collections/mulesoft_docs/snapshots"],
      ["Upload custom patterns", "curl -X POST http://localhost:8000/api/rag/upload -F 'files=@standards.md'"],
      ["Test RAG search", "curl 'http://localhost:8000/api/rag/search?q=http+listener&collection=mulesoft_docs'"],
      ["Monitor logs (JSON)", "docker compose logs -f api --tail 100"],
      ["Scale migration workers", "docker compose up -d --scale celery-migration-worker=4"],
      ["Run Helm install", "helm install migrator ./deploy/helm/migrator-platform -f values.yaml"],
      ["Create air-gap bundle", "./deploy/airgap/bundle.sh v1.0.0"],
    ], [3200, 6880]),
    spacer(),
    spacer(),
    p("--- End of Documentation ---", { align: AlignmentType.CENTER, color: GRAY, italics: true }),
  ]
});

// ─── Build Document ───
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 300, after: 150 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ],
    characterStyles: [
      { id: "Hyperlink", name: "Hyperlink", run: { color: ACCENT, underline: {} } }
    ]
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections
});

const outPath = "/Users/harinadh/Documents/My code/mulesoft-to-springboot-migrator/docs/Agentic_AI_Platform_Complete_Documentation.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log(`Documentation generated: ${outPath}`);
  console.log(`File size: ${(buffer.length / 1024).toFixed(1)} KB`);
});
