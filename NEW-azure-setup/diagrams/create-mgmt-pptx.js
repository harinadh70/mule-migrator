const pptxgen = require("pptxgenjs");

const pptx = new pptxgen();

// ─── Brand Colors ───
const NAVY = "0F1B2D";
const AZURE_BLUE = "0078D4";
const AZURE_CYAN = "50E6FF";
const LIGHT_BG = "F3F2F1";
const WHITE = "FFFFFF";
const DARK_TEXT = "1B1B1B";
const SUBTLE_TEXT = "605E5C";
const SUCCESS_GREEN = "107C10";
const WARN_ORANGE = "FF8C00";
const DANGER_RED = "D13438";

// ─── Presentation Setup ───
pptx.author = "Mule Migrator Team";
pptx.company = "Mule Migrator";
pptx.subject = "Management Overview";
pptx.title = "Mule Migrator - AI-Powered Application Modernization";
pptx.layout = "LAYOUT_WIDE"; // 13.33 x 7.5

// ─── Helper Functions ───

function addDarkSlide(pptx) {
  const slide = pptx.addSlide();
  slide.background = { color: NAVY };
  return slide;
}

function addLightSlide(pptx) {
  const slide = pptx.addSlide();
  slide.background = { color: LIGHT_BG };
  return slide;
}

// Accent line at bottom
function addBottomAccent(slide, isDark = false) {
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 7.15, w: 13.33, h: 0.08,
    fill: { type: "solid", color: AZURE_BLUE },
  });
}

// Top-right tag
function addSlideNumber(slide, num, isDark = true) {
  slide.addText(`${num} / 10`, {
    x: 11.5, y: 0.25, w: 1.5, h: 0.3,
    fontSize: 9, fontFace: "Calibri",
    color: isDark ? "4A5568" : SUBTLE_TEXT,
    align: "right",
  });
}

// Section header bar
function addSectionHeader(slide, title, isDark = false) {
  // thin accent bar
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0.7, y: 0.55, w: 0.35, h: 0.04,
    fill: { type: "solid", color: AZURE_CYAN },
  });
  slide.addText(title, {
    x: 0.7, y: 0.65, w: 10, h: 0.55,
    fontSize: 28, fontFace: "Calibri Light", bold: true,
    color: isDark ? WHITE : DARK_TEXT,
  });
}

// Card shape helper
function addCard(slide, x, y, w, h, opts = {}) {
  const { fill = WHITE, shadow = true, radius = 0.08 } = opts;
  const shapeOpts = {
    x, y, w, h,
    fill: { type: "solid", color: fill },
    rectRadius: radius,
    line: { color: "E1DFDD", width: 0.5 },
  };
  if (shadow) {
    shapeOpts.shadow = { type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.12 };
  }
  slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, shapeOpts);
}

// Stat callout card
function addStatCard(slide, x, y, w, h, value, label, color = AZURE_BLUE, bgColor = WHITE) {
  addCard(slide, x, y, w, h, { fill: bgColor });
  slide.addText(value, {
    x, y: y + h * 0.12, w, h: h * 0.48,
    fontSize: 32, fontFace: "Calibri", bold: true,
    color: color, align: "center", valign: "bottom",
  });
  slide.addText(label, {
    x: x + 0.1, y: y + h * 0.58, w: w - 0.2, h: h * 0.32,
    fontSize: 11, fontFace: "Calibri",
    color: SUBTLE_TEXT, align: "center", valign: "top",
    wrap: true,
  });
}

// Icon circle
function addIconCircle(slide, x, y, size, bgColor, symbol, symbolColor = WHITE) {
  slide.addShape(pptx.shapes.OVAL, {
    x, y, w: size, h: size,
    fill: { type: "solid", color: bgColor },
  });
  slide.addText(symbol, {
    x, y, w: size, h: size,
    fontSize: Math.round(size * 22), fontFace: "Calibri",
    color: symbolColor, align: "center", valign: "middle", bold: true,
  });
}

// ═══════════════════════════════════════════════════════════
// SLIDE 1: TITLE
// ═══════════════════════════════════════════════════════════
function createSlide1(pptx) {
  const slide = addDarkSlide(pptx);

  // Subtle gradient overlay bar at top
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.33, h: 0.06,
    fill: { type: "solid", color: AZURE_BLUE },
  });

  // Left accent line
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0.9, y: 2.0, w: 0.06, h: 2.8,
    fill: { type: "solid", color: AZURE_CYAN },
  });

  // Main title
  slide.addText("Mule Migrator", {
    x: 1.3, y: 2.0, w: 8, h: 1.1,
    fontSize: 52, fontFace: "Calibri Light", bold: true,
    color: WHITE,
  });

  // Subtitle
  slide.addText("AI-Powered Application Modernization", {
    x: 1.3, y: 3.05, w: 8, h: 0.6,
    fontSize: 22, fontFace: "Calibri",
    color: AZURE_CYAN,
  });

  // Description
  slide.addText("Automating MuleSoft to Spring Boot Migration", {
    x: 1.3, y: 3.65, w: 8, h: 0.5,
    fontSize: 16, fontFace: "Calibri",
    color: SUBTLE_TEXT,
  });

  // Date badge
  slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 1.3, y: 4.4, w: 1.8, h: 0.4,
    fill: { type: "solid", color: "1A2940" },
    rectRadius: 0.05,
    line: { color: "2D3E56", width: 0.5 },
  });
  slide.addText("March 2026", {
    x: 1.3, y: 4.4, w: 1.8, h: 0.4,
    fontSize: 11, fontFace: "Calibri",
    color: AZURE_CYAN, align: "center", valign: "middle",
  });

  // Right decorative element - abstract geometric shapes
  slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 9.5, y: 1.5, w: 3.0, h: 3.0,
    fill: { type: "solid", color: "141F33" },
    rectRadius: 0.15,
    line: { color: "1E2D45", width: 1 },
  });
  slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 10.0, y: 2.0, w: 2.2, h: 2.2,
    fill: { type: "solid", color: "1A2940" },
    rectRadius: 0.12,
  });

  // AI text in the box
  slide.addText("AI", {
    x: 10.0, y: 2.15, w: 2.2, h: 1.2,
    fontSize: 48, fontFace: "Calibri", bold: true,
    color: AZURE_BLUE, align: "center", valign: "middle",
  });
  slide.addText("AGENTIC\nPLATFORM", {
    x: 10.0, y: 3.1, w: 2.2, h: 0.8,
    fontSize: 10, fontFace: "Calibri", bold: true,
    color: "4A5568", align: "center", valign: "top",
    lineSpacingMultiple: 1.3,
  });

  // Bottom accent
  addBottomAccent(slide, true);

  // Confidential note
  slide.addText("CONFIDENTIAL", {
    x: 0.7, y: 6.9, w: 2, h: 0.3,
    fontSize: 8, fontFace: "Calibri",
    color: "3A4A5C",
  });
}

// ═══════════════════════════════════════════════════════════
// SLIDE 2: THE CHALLENGE
// ═══════════════════════════════════════════════════════════
function createSlide2(pptx) {
  const slide = addLightSlide(pptx);
  addSlideNumber(slide, 2, false);
  addSectionHeader(slide, "The Challenge");

  // Subtitle
  slide.addText("Manual migration is slow, expensive, and error-prone", {
    x: 0.7, y: 1.2, w: 10, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: SUBTLE_TEXT,
  });

  // Pain points with bullet icons
  const pains = [
    { icon: "\u23F1", text: "Manual migration takes 2\u20134 weeks per application", color: WARN_ORANGE },
    { icon: "\u26A0", text: "Requires specialized MuleSoft + Spring Boot expertise (scarce talent)", color: DANGER_RED },
    { icon: "\u2716", text: "Error-prone: manual code translation leads to bugs and rework", color: DANGER_RED },
    { icon: "\uD83D\uDCB0", text: "Cost: $10,000\u2013$50,000 per application migration", color: WARN_ORANGE },
  ];

  pains.forEach((p, i) => {
    const yPos = 1.85 + i * 0.55;
    // Icon circle
    slide.addShape(pptx.shapes.OVAL, {
      x: 0.9, y: yPos + 0.05, w: 0.36, h: 0.36,
      fill: { type: "solid", color: p.color },
    });
    slide.addText(p.icon, {
      x: 0.9, y: yPos + 0.05, w: 0.36, h: 0.36,
      fontSize: 13, fontFace: "Calibri",
      color: WHITE, align: "center", valign: "middle",
    });
    // Text
    slide.addText(p.text, {
      x: 1.5, y: yPos, w: 7, h: 0.45,
      fontSize: 14, fontFace: "Calibri",
      color: DARK_TEXT, valign: "middle",
    });
  });

  // Divider line
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0.7, y: 4.35, w: 11.9, h: 0.01,
    fill: { type: "solid", color: "D2D0CE" },
  });

  // 3 stat callouts
  const stats = [
    { value: "2\u20134 Weeks", label: "Average Migration\nDuration", color: WARN_ORANGE },
    { value: "$10K\u2013$50K", label: "Cost Per\nApplication", color: DANGER_RED },
    { value: "40%", label: "Manual Migration\nError Rate", color: DANGER_RED },
  ];

  const cardW = 3.4;
  const gap = 0.55;
  const startX = (13.33 - (cardW * 3 + gap * 2)) / 2;

  stats.forEach((s, i) => {
    const x = startX + i * (cardW + gap);
    addCard(slide, x, 4.7, cardW, 2.0);

    // Colored top bar on card
    slide.addShape(pptx.shapes.RECTANGLE, {
      x: x + 0.15, y: 4.85, w: cardW - 0.3, h: 0.05,
      fill: { type: "solid", color: s.color },
    });

    slide.addText(s.value, {
      x, y: 5.05, w: cardW, h: 0.75,
      fontSize: 36, fontFace: "Calibri", bold: true,
      color: s.color, align: "center", valign: "bottom",
    });
    slide.addText(s.label, {
      x, y: 5.85, w: cardW, h: 0.6,
      fontSize: 12, fontFace: "Calibri",
      color: SUBTLE_TEXT, align: "center", valign: "top",
      lineSpacingMultiple: 1.2,
    });
  });

  addBottomAccent(slide);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 3: OUR SOLUTION
// ═══════════════════════════════════════════════════════════
function createSlide3(pptx) {
  const slide = addLightSlide(pptx);
  addSlideNumber(slide, 3, false);
  addSectionHeader(slide, "Our Solution");

  slide.addText("AI-powered automated migration \u2014 transforming weeks of work into minutes", {
    x: 0.7, y: 1.2, w: 11, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: SUBTLE_TEXT,
  });

  // 4 benefit cards
  const benefits = [
    {
      icon: "\u26A1", title: "Speed",
      stat: "10x Faster", desc: "Minutes, not weeks.\nComplete migrations in\na single session.",
      color: AZURE_BLUE, bg: "E8F4FD",
    },
    {
      icon: "\u2714", title: "Accuracy",
      stat: "99%", desc: "Compilable output.\nAI-reviewed code with\nbuilt-in best practices.",
      color: SUCCESS_GREEN, bg: "E8F5E9",
    },
    {
      icon: "\uD83D\uDCB2", title: "Cost",
      stat: "$0.04", desc: "Per migration.\n99.9% cost reduction\nvs. manual approach.",
      color: WARN_ORANGE, bg: "FFF3E0",
    },
    {
      icon: "\uD83E\uDDE0", title: "Knowledge",
      stat: "203", desc: "Migration patterns in\nRAG knowledge base.\nContinuously growing.",
      color: "6B69D6", bg: "EDE7F6",
    },
  ];

  const cardW = 2.7;
  const cardH = 3.8;
  const gap = 0.45;
  const startX = (13.33 - (cardW * 4 + gap * 3)) / 2;
  const startY = 1.9;

  benefits.forEach((b, i) => {
    const x = startX + i * (cardW + gap);

    // Card background
    addCard(slide, x, startY, cardW, cardH);

    // Colored header area
    slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: x + 0.12, y: startY + 0.12, w: cardW - 0.24, h: 1.5,
      fill: { type: "solid", color: b.bg },
      rectRadius: 0.06,
    });

    // Icon
    slide.addText(b.icon, {
      x: x, y: startY + 0.2, w: cardW, h: 0.55,
      fontSize: 28, align: "center", valign: "middle",
    });

    // Title
    slide.addText(b.title, {
      x: x, y: startY + 0.72, w: cardW, h: 0.35,
      fontSize: 13, fontFace: "Calibri", bold: true,
      color: b.color, align: "center",
    });

    // Stat
    slide.addText(b.stat, {
      x: x, y: startY + 1.0, w: cardW, h: 0.55,
      fontSize: 14, fontFace: "Calibri", bold: true,
      color: b.color, align: "center", valign: "middle",
    });

    // Description
    slide.addText(b.desc, {
      x: x + 0.2, y: startY + 1.75, w: cardW - 0.4, h: 1.8,
      fontSize: 12, fontFace: "Calibri",
      color: SUBTLE_TEXT, align: "center", valign: "top",
      lineSpacingMultiple: 1.4,
    });
  });

  addBottomAccent(slide);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 4: HOW IT WORKS
// ═══════════════════════════════════════════════════════════
function createSlide4(pptx) {
  const slide = addLightSlide(pptx);
  addSlideNumber(slide, 4, false);
  addSectionHeader(slide, "How It Works");

  slide.addText("A simple 4-step process from legacy code to modern application", {
    x: 0.7, y: 1.2, w: 11, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: SUBTLE_TEXT,
  });

  const steps = [
    { num: "1", title: "Upload", desc: "Upload MuleSoft\nXML files", icon: "\u2B06", color: AZURE_BLUE },
    { num: "2", title: "Analyze", desc: "AI agents analyze\n& generate code", icon: "\u2699", color: "6B69D6" },
    { num: "3", title: "Review", desc: "Review & edit code\nin the browser", icon: "\uD83D\uDD0D", color: SUCCESS_GREEN },
    { num: "4", title: "Deploy", desc: "Push to GitHub,\nbuild & deploy", icon: "\uD83D\uDE80", color: WARN_ORANGE },
  ];

  const stepW = 2.4;
  const arrowW = 0.7;
  const totalW = stepW * 4 + arrowW * 3;
  const startX = (13.33 - totalW) / 2;
  const centerY = 3.6;

  steps.forEach((s, i) => {
    const x = startX + i * (stepW + arrowW);

    // Step circle
    const circleSize = 1.3;
    const circleX = x + (stepW - circleSize) / 2;
    const circleY = centerY - circleSize / 2 - 0.5;

    // Outer ring
    slide.addShape(pptx.shapes.OVAL, {
      x: circleX - 0.08, y: circleY - 0.08, w: circleSize + 0.16, h: circleSize + 0.16,
      fill: { type: "solid", color: WHITE },
      line: { color: s.color, width: 2.5 },
      shadow: { type: "outer", blur: 8, offset: 2, color: "000000", opacity: 0.1 },
    });

    // Inner circle
    slide.addShape(pptx.shapes.OVAL, {
      x: circleX, y: circleY, w: circleSize, h: circleSize,
      fill: { type: "solid", color: s.color },
    });

    // Icon in circle
    slide.addText(s.icon, {
      x: circleX, y: circleY, w: circleSize, h: circleSize * 0.65,
      fontSize: 30, fontFace: "Calibri",
      color: WHITE, align: "center", valign: "bottom",
    });

    // Number badge
    slide.addShape(pptx.shapes.OVAL, {
      x: circleX + circleSize - 0.3, y: circleY - 0.1, w: 0.4, h: 0.4,
      fill: { type: "solid", color: NAVY },
    });
    slide.addText(s.num, {
      x: circleX + circleSize - 0.3, y: circleY - 0.1, w: 0.4, h: 0.4,
      fontSize: 12, fontFace: "Calibri", bold: true,
      color: WHITE, align: "center", valign: "middle",
    });

    // Title below circle
    slide.addText(s.title, {
      x, y: centerY + 0.55, w: stepW, h: 0.4,
      fontSize: 16, fontFace: "Calibri", bold: true,
      color: DARK_TEXT, align: "center",
    });

    // Description
    slide.addText(s.desc, {
      x, y: centerY + 0.95, w: stepW, h: 0.75,
      fontSize: 12, fontFace: "Calibri",
      color: SUBTLE_TEXT, align: "center",
      lineSpacingMultiple: 1.3,
    });

    // Arrow between steps
    if (i < 3) {
      const arrowX = x + stepW + 0.05;
      const arrowY = centerY - 0.3;
      slide.addText("\u276F", {
        x: arrowX, y: arrowY, w: arrowW - 0.1, h: 0.5,
        fontSize: 28, fontFace: "Calibri", bold: true,
        color: AZURE_BLUE, align: "center", valign: "middle",
      });
    }
  });

  // Time bar at bottom
  addCard(slide, 2.5, 5.7, 8.33, 0.7, { fill: NAVY });
  slide.addText("\u26A1  Average migration time: 5 minutes  |  Fully automated  |  No coding required", {
    x: 2.5, y: 5.7, w: 8.33, h: 0.7,
    fontSize: 13, fontFace: "Calibri", bold: true,
    color: AZURE_CYAN, align: "center", valign: "middle",
  });

  addBottomAccent(slide);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 5: AI TECHNOLOGY
// ═══════════════════════════════════════════════════════════
function createSlide5(pptx) {
  const slide = addDarkSlide(pptx);
  addSlideNumber(slide, 5, true);

  // thin top accent
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0.7, y: 0.55, w: 0.35, h: 0.04,
    fill: { type: "solid", color: AZURE_CYAN },
  });
  slide.addText("AI Technology", {
    x: 0.7, y: 0.65, w: 10, h: 0.55,
    fontSize: 28, fontFace: "Calibri Light", bold: true,
    color: WHITE,
  });

  slide.addText("Powered by Azure OpenAI GPT-4.1", {
    x: 0.7, y: 1.2, w: 10, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: AZURE_CYAN,
  });

  // RAG explanation box
  addCard(slide, 0.7, 1.85, 5.8, 1.5, { fill: "1A2940" });
  slide.addText("Retrieval-Augmented Generation (RAG)", {
    x: 0.95, y: 1.95, w: 5.3, h: 0.35,
    fontSize: 13, fontFace: "Calibri", bold: true,
    color: AZURE_CYAN,
  });
  slide.addText("Our AI doesn't just generate code \u2014 it retrieves proven migration\npatterns from a curated knowledge base of 203 documents, ensuring\naccurate, battle-tested output every time.", {
    x: 0.95, y: 2.35, w: 5.3, h: 0.85,
    fontSize: 11.5, fontFace: "Calibri",
    color: "B0BEC5", lineSpacingMultiple: 1.4,
  });

  // Cost callout
  addCard(slide, 7.0, 1.85, 5.5, 1.5, { fill: "1A2940" });
  slide.addText("Cost Per Migration", {
    x: 7.2, y: 1.95, w: 5.1, h: 0.35,
    fontSize: 13, fontFace: "Calibri", bold: true,
    color: AZURE_CYAN,
  });
  slide.addText("$0.04", {
    x: 7.2, y: 2.3, w: 2, h: 0.7,
    fontSize: 36, fontFace: "Calibri", bold: true,
    color: SUCCESS_GREEN,
  });
  slide.addText("3,972 tokens average\nper migration request", {
    x: 9.2, y: 2.35, w: 3, h: 0.6,
    fontSize: 11, fontFace: "Calibri",
    color: "B0BEC5", lineSpacingMultiple: 1.3,
  });

  // 4 Agent pipeline
  slide.addText("Four AI Agents Working Together", {
    x: 0.7, y: 3.65, w: 10, h: 0.4,
    fontSize: 16, fontFace: "Calibri", bold: true,
    color: WHITE,
  });

  const agents = [
    { name: "Planner Agent", desc: "Analyzes input and\ncreates migration strategy", icon: "\uD83D\uDCCB", color: AZURE_BLUE },
    { name: "Knowledge Agent", desc: "Retrieves relevant patterns\nfrom RAG database", icon: "\uD83D\uDCDA", color: "6B69D6" },
    { name: "Engine Agent", desc: "Orchestrates the\nmigration workflow", icon: "\u2699", color: WARN_ORANGE },
    { name: "Coder Agent", desc: "Generates Spring Boot\ncode and tests", icon: "\uD83D\uDCBB", color: SUCCESS_GREEN },
  ];

  const agentW = 2.6;
  const agentGap = 0.4;
  const totalAgentW = agentW * 4 + agentGap * 3;
  const agentStartX = (13.33 - totalAgentW) / 2;

  agents.forEach((a, i) => {
    const x = agentStartX + i * (agentW + agentGap);
    const y = 4.2;

    addCard(slide, x, y, agentW, 2.3, { fill: "1A2940" });

    // Colored top bar
    slide.addShape(pptx.shapes.RECTANGLE, {
      x: x + 0.2, y: y + 0.15, w: agentW - 0.4, h: 0.05,
      fill: { type: "solid", color: a.color },
    });

    // Icon
    slide.addText(a.icon, {
      x, y: y + 0.3, w: agentW, h: 0.6,
      fontSize: 26, align: "center", valign: "middle",
    });

    // Name
    slide.addText(a.name, {
      x, y: y + 0.9, w: agentW, h: 0.35,
      fontSize: 13, fontFace: "Calibri", bold: true,
      color: WHITE, align: "center",
    });

    // Description
    slide.addText(a.desc, {
      x: x + 0.15, y: y + 1.3, w: agentW - 0.3, h: 0.8,
      fontSize: 10.5, fontFace: "Calibri",
      color: "B0BEC5", align: "center",
      lineSpacingMultiple: 1.3,
    });

    // Arrow
    if (i < 3) {
      slide.addText("\u276F", {
        x: x + agentW + 0.02, y: y + 0.6, w: agentGap - 0.04, h: 0.5,
        fontSize: 20, fontFace: "Calibri", bold: true,
        color: AZURE_CYAN, align: "center", valign: "middle",
      });
    }
  });

  addBottomAccent(slide, true);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 6: SECURITY & COMPLIANCE
// ═══════════════════════════════════════════════════════════
function createSlide6(pptx) {
  const slide = addDarkSlide(pptx);
  addSlideNumber(slide, 6, true);

  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0.7, y: 0.55, w: 0.35, h: 0.04,
    fill: { type: "solid", color: AZURE_CYAN },
  });
  slide.addText("Security & Compliance", {
    x: 0.7, y: 0.65, w: 10, h: 0.55,
    fontSize: 28, fontFace: "Calibri Light", bold: true,
    color: WHITE,
  });

  slide.addText("Enterprise-grade security built into every layer of the platform", {
    x: 0.7, y: 1.2, w: 11, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: AZURE_CYAN,
  });

  // 5 security features
  const features = [
    { icon: "\uD83D\uDD11", title: "Azure AD", desc: "Single Sign-On (SSO)\nwith corporate identity", color: AZURE_BLUE },
    { icon: "\uD83D\uDD12", title: "Key Vault", desc: "All secrets managed\nin Azure Key Vault", color: "6B69D6" },
    { icon: "\uD83D\uDEE1", title: "SSL/TLS", desc: "End-to-end encrypted\ncommunication", color: SUCCESS_GREEN },
    { icon: "\uD83D\uDC65", title: "Role-Based Access", desc: "Granular permissions\nfor teams", color: WARN_ORANGE },
    { icon: "\uD83D\uDCDD", title: "Audit Logging", desc: "Complete activity trail\nfor compliance", color: AZURE_CYAN },
  ];

  const fW = 2.1;
  const fGap = 0.35;
  const totalFW = fW * 5 + fGap * 4;
  const fStartX = (13.33 - totalFW) / 2;

  features.forEach((f, i) => {
    const x = fStartX + i * (fW + fGap);
    const y = 2.0;

    addCard(slide, x, y, fW, 2.7, { fill: "1A2940" });

    // Icon circle
    const iconSize = 0.9;
    slide.addShape(pptx.shapes.OVAL, {
      x: x + (fW - iconSize) / 2, y: y + 0.3, w: iconSize, h: iconSize,
      fill: { type: "solid", color: f.color },
    });
    slide.addText(f.icon, {
      x: x + (fW - iconSize) / 2, y: y + 0.3, w: iconSize, h: iconSize,
      fontSize: 24, align: "center", valign: "middle",
    });

    // Title
    slide.addText(f.title, {
      x, y: y + 1.35, w: fW, h: 0.35,
      fontSize: 12, fontFace: "Calibri", bold: true,
      color: WHITE, align: "center",
    });

    // Description
    slide.addText(f.desc, {
      x: x + 0.1, y: y + 1.7, w: fW - 0.2, h: 0.7,
      fontSize: 10, fontFace: "Calibri",
      color: "B0BEC5", align: "center",
      lineSpacingMultiple: 1.3,
    });
  });

  // Zero API Keys badge
  addCard(slide, 3.5, 5.2, 6.33, 0.9, { fill: "0D2137" });
  slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 3.65, y: 5.3, w: 0.6, h: 0.35,
    fill: { type: "solid", color: SUCCESS_GREEN },
    rectRadius: 0.04,
  });
  slide.addText("\u2713", {
    x: 3.65, y: 5.3, w: 0.6, h: 0.35,
    fontSize: 14, fontFace: "Calibri", bold: true,
    color: WHITE, align: "center", valign: "middle",
  });
  slide.addText("Zero API Keys in Code", {
    x: 4.4, y: 5.25, w: 3, h: 0.3,
    fontSize: 16, fontFace: "Calibri", bold: true,
    color: WHITE,
  });
  slide.addText("All credentials managed securely through Azure Key Vault and Managed Identity", {
    x: 4.4, y: 5.55, w: 5, h: 0.3,
    fontSize: 10.5, fontFace: "Calibri",
    color: "B0BEC5",
  });

  // Compliance bar
  addCard(slide, 0.7, 6.35, 11.93, 0.55, { fill: "1A2940" });
  slide.addText("SOC 2 Ready  \u2502  GDPR Compliant Architecture  \u2502  Azure Government Compatible  \u2502  Zero Trust Security Model", {
    x: 0.7, y: 6.35, w: 11.93, h: 0.55,
    fontSize: 10.5, fontFace: "Calibri",
    color: AZURE_CYAN, align: "center", valign: "middle",
  });

  addBottomAccent(slide, true);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 7: COST COMPARISON
// ═══════════════════════════════════════════════════════════
function createSlide7(pptx) {
  const slide = addLightSlide(pptx);
  addSlideNumber(slide, 7, false);
  addSectionHeader(slide, "Cost Comparison");

  slide.addText("The business case for AI-powered migration", {
    x: 0.7, y: 1.2, w: 10, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: SUBTLE_TEXT,
  });

  // Manual column (left)
  const colW = 5.6;
  const leftX = 0.7;
  const rightX = 7.03;
  const colY = 1.85;
  const colH = 3.5;

  // Manual card
  addCard(slide, leftX, colY, colW, colH);
  // Red header
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: leftX, y: colY, w: colW, h: 0.55,
    fill: { type: "solid", color: DANGER_RED },
    rectRadius: 0.08,
  });
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: leftX, y: colY + 0.35, w: colW, h: 0.2,
    fill: { type: "solid", color: DANGER_RED },
  });
  slide.addText("\u2716  Manual Migration", {
    x: leftX, y: colY, w: colW, h: 0.55,
    fontSize: 16, fontFace: "Calibri", bold: true,
    color: WHITE, align: "center", valign: "middle",
  });

  const manualItems = [
    { label: "Cost per app", value: "$10,000 \u2013 $50,000", color: DANGER_RED },
    { label: "Time per app", value: "2 \u2013 4 weeks", color: WARN_ORANGE },
    { label: "Expertise", value: "Requires specialists", color: WARN_ORANGE },
    { label: "Quality", value: "40% error rate", color: DANGER_RED },
    { label: "Scalability", value: "Limited by headcount", color: DANGER_RED },
  ];

  manualItems.forEach((item, i) => {
    const iy = colY + 0.75 + i * 0.5;
    slide.addText(item.label, {
      x: leftX + 0.3, y: iy, w: 2.2, h: 0.4,
      fontSize: 11, fontFace: "Calibri",
      color: SUBTLE_TEXT, valign: "middle",
    });
    slide.addText(item.value, {
      x: leftX + 2.5, y: iy, w: 2.8, h: 0.4,
      fontSize: 12, fontFace: "Calibri", bold: true,
      color: item.color, align: "right", valign: "middle",
    });
  });

  // AI Migrator card
  addCard(slide, rightX, colY, colW, colH);
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: rightX, y: colY, w: colW, h: 0.55,
    fill: { type: "solid", color: SUCCESS_GREEN },
    rectRadius: 0.08,
  });
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: rightX, y: colY + 0.35, w: colW, h: 0.2,
    fill: { type: "solid", color: SUCCESS_GREEN },
  });
  slide.addText("\u2714  AI Migrator", {
    x: rightX, y: colY, w: colW, h: 0.55,
    fontSize: 16, fontFace: "Calibri", bold: true,
    color: WHITE, align: "center", valign: "middle",
  });

  const aiItems = [
    { label: "Cost per app", value: "$0.04", color: SUCCESS_GREEN },
    { label: "Time per app", value: "5 minutes", color: SUCCESS_GREEN },
    { label: "Expertise", value: "Self-service", color: SUCCESS_GREEN },
    { label: "Quality", value: "99% compilable", color: SUCCESS_GREEN },
    { label: "Scalability", value: "Unlimited", color: SUCCESS_GREEN },
  ];

  aiItems.forEach((item, i) => {
    const iy = colY + 0.75 + i * 0.5;
    slide.addText(item.label, {
      x: rightX + 0.3, y: iy, w: 2.2, h: 0.4,
      fontSize: 11, fontFace: "Calibri",
      color: SUBTLE_TEXT, valign: "middle",
    });
    slide.addText(item.value, {
      x: rightX + 2.5, y: iy, w: 2.8, h: 0.4,
      fontSize: 12, fontFace: "Calibri", bold: true,
      color: item.color, align: "right", valign: "middle",
    });
  });

  // VS divider
  slide.addShape(pptx.shapes.OVAL, {
    x: 6.15, y: 2.85, w: 1.05, h: 1.05,
    fill: { type: "solid", color: NAVY },
    shadow: { type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.2 },
  });
  slide.addText("VS", {
    x: 6.15, y: 2.85, w: 1.05, h: 1.05,
    fontSize: 16, fontFace: "Calibri", bold: true,
    color: WHITE, align: "center", valign: "middle",
  });

  // Bottom ROI section
  const roiY = 5.6;
  const roiItems = [
    { value: "$36\u2013$66/mo", label: "Azure\nInfrastructure", color: AZURE_BLUE },
    { value: "250,000%", label: "Return on\nInvestment", color: SUCCESS_GREEN },
    { value: "1 Migration", label: "Pays for 1 Year\nof Platform", color: WARN_ORANGE },
  ];

  const roiW = 3.4;
  const roiGap = 0.55;
  const roiStartX = (13.33 - (roiW * 3 + roiGap * 2)) / 2;

  roiItems.forEach((r, i) => {
    const x = roiStartX + i * (roiW + roiGap);
    addCard(slide, x, roiY, roiW, 1.3);
    slide.addText(r.value, {
      x, y: roiY + 0.1, w: roiW, h: 0.55,
      fontSize: 24, fontFace: "Calibri", bold: true,
      color: r.color, align: "center", valign: "bottom",
    });
    slide.addText(r.label, {
      x, y: roiY + 0.7, w: roiW, h: 0.45,
      fontSize: 10, fontFace: "Calibri",
      color: SUBTLE_TEXT, align: "center", valign: "top",
      lineSpacingMultiple: 1.2,
    });
  });

  addBottomAccent(slide);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 8: PLATFORM METRICS
// ═══════════════════════════════════════════════════════════
function createSlide8(pptx) {
  const slide = addLightSlide(pptx);
  addSlideNumber(slide, 8, false);
  addSectionHeader(slide, "Platform Metrics");

  slide.addText("A production-ready platform delivering measurable results", {
    x: 0.7, y: 1.2, w: 11, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: SUBTLE_TEXT,
  });

  // 4 large stat cards
  const metrics = [
    { value: "21", label: "Files Generated\nPer Migration", sub: "Complete Spring Boot project", color: AZURE_BLUE, icon: "\uD83D\uDCC4" },
    { value: "203", label: "RAG Knowledge\nDocuments", sub: "Curated migration patterns", color: "6B69D6", icon: "\uD83D\uDCDA" },
    { value: "15", label: "API\nEndpoints", sub: "Full REST API coverage", color: SUCCESS_GREEN, icon: "\uD83D\uDD17" },
    { value: "9", label: "Azure\nServices", sub: "Enterprise cloud infrastructure", color: WARN_ORANGE, icon: "\u2601" },
  ];

  const mW = 2.75;
  const mH = 3.2;
  const mGap = 0.4;
  const totalMW = mW * 4 + mGap * 3;
  const mStartX = (13.33 - totalMW) / 2;
  const mStartY = 1.9;

  metrics.forEach((m, i) => {
    const x = mStartX + i * (mW + mGap);

    addCard(slide, x, mStartY, mW, mH);

    // Icon
    slide.addText(m.icon, {
      x, y: mStartY + 0.2, w: mW, h: 0.55,
      fontSize: 26, align: "center",
    });

    // Large number
    slide.addText(m.value, {
      x, y: mStartY + 0.75, w: mW, h: 0.95,
      fontSize: 48, fontFace: "Calibri", bold: true,
      color: m.color, align: "center", valign: "middle",
    });

    // Label
    slide.addText(m.label, {
      x, y: mStartY + 1.7, w: mW, h: 0.55,
      fontSize: 13, fontFace: "Calibri", bold: true,
      color: DARK_TEXT, align: "center",
      lineSpacingMultiple: 1.2,
    });

    // Sub text
    slide.addText(m.sub, {
      x, y: mStartY + 2.3, w: mW, h: 0.4,
      fontSize: 10, fontFace: "Calibri",
      color: SUBTLE_TEXT, align: "center",
    });
  });

  // Demo URL bar
  addCard(slide, 2.0, 5.6, 9.33, 1.1, { fill: NAVY });
  slide.addText("LIVE DEMO", {
    x: 2.0, y: 5.65, w: 9.33, h: 0.4,
    fontSize: 10, fontFace: "Calibri", bold: true,
    color: AZURE_CYAN, align: "center",
  });
  slide.addText("https://nice-rock-0f9182f00.6.azurestaticapps.net", {
    x: 2.0, y: 5.95, w: 9.33, h: 0.45,
    fontSize: 14, fontFace: "Calibri",
    color: WHITE, align: "center", valign: "middle",
  });

  addBottomAccent(slide);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 9: ROADMAP
// ═══════════════════════════════════════════════════════════
function createSlide9(pptx) {
  const slide = addDarkSlide(pptx);
  addSlideNumber(slide, 9, true);

  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0.7, y: 0.55, w: 0.35, h: 0.04,
    fill: { type: "solid", color: AZURE_CYAN },
  });
  slide.addText("Roadmap", {
    x: 0.7, y: 0.65, w: 10, h: 0.55,
    fontSize: 28, fontFace: "Calibri Light", bold: true,
    color: WHITE,
  });

  slide.addText("Strategic evolution from core platform to enterprise-scale solution", {
    x: 0.7, y: 1.2, w: 11, h: 0.4,
    fontSize: 14, fontFace: "Calibri",
    color: AZURE_CYAN,
  });

  // Timeline horizontal line
  const lineY = 3.0;
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 1.0, y: lineY, w: 11.33, h: 0.04,
    fill: { type: "solid", color: AZURE_BLUE },
  });

  const phases = [
    {
      label: "NOW", title: "Core Platform", badge: "LIVE",
      items: ["Single-file migration", "Web-based editor", "GitHub integration", "Azure deployment"],
      color: SUCCESS_GREEN, badgeColor: SUCCESS_GREEN,
    },
    {
      label: "Q2 2026", title: "Collaboration", badge: "NEXT",
      items: ["Multi-file migration", "Team workspaces", "Migration history", "Advanced analytics"],
      color: AZURE_BLUE, badgeColor: AZURE_BLUE,
    },
    {
      label: "Q3 2026", title: "Enterprise", badge: "PLANNED",
      items: ["Custom patterns", "Enterprise SSO/SAML", "API marketplace", "Compliance reports"],
      color: "6B69D6", badgeColor: "6B69D6",
    },
    {
      label: "Q4 2026", title: "Scale", badge: "VISION",
      items: ["Multi-cloud support", "Batch migration", "CI/CD integration", "Partner ecosystem"],
      color: WARN_ORANGE, badgeColor: WARN_ORANGE,
    },
  ];

  const phW = 2.7;
  const phGap = 0.35;
  const totalPhW = phW * 4 + phGap * 3;
  const phStartX = (13.33 - totalPhW) / 2;

  phases.forEach((p, i) => {
    const x = phStartX + i * (phW + phGap);

    // Timeline dot
    const dotSize = 0.25;
    const dotX = x + phW / 2 - dotSize / 2;
    slide.addShape(pptx.shapes.OVAL, {
      x: dotX - 0.05, y: lineY - 0.12, w: dotSize + 0.1, h: dotSize + 0.1,
      fill: { type: "solid", color: NAVY },
      line: { color: p.color, width: 2 },
    });
    slide.addShape(pptx.shapes.OVAL, {
      x: dotX + 0.03, y: lineY - 0.04, w: dotSize - 0.06, h: dotSize - 0.06,
      fill: { type: "solid", color: p.color },
    });

    // Phase label above dot
    slide.addText(p.label, {
      x, y: lineY - 0.6, w: phW, h: 0.35,
      fontSize: 12, fontFace: "Calibri", bold: true,
      color: p.color, align: "center",
    });

    // Card below
    const cardY = lineY + 0.5;
    addCard(slide, x, cardY, phW, 3.2, { fill: "1A2940" });

    // Badge
    slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: x + (phW - 1.1) / 2, y: cardY + 0.15, w: 1.1, h: 0.3,
      fill: { type: "solid", color: p.badgeColor },
      rectRadius: 0.04,
    });
    slide.addText(p.badge, {
      x: x + (phW - 1.1) / 2, y: cardY + 0.15, w: 1.1, h: 0.3,
      fontSize: 9, fontFace: "Calibri", bold: true,
      color: WHITE, align: "center", valign: "middle",
    });

    // Title
    slide.addText(p.title, {
      x, y: cardY + 0.5, w: phW, h: 0.35,
      fontSize: 14, fontFace: "Calibri", bold: true,
      color: WHITE, align: "center",
    });

    // Items
    p.items.forEach((item, j) => {
      slide.addText(`\u2022  ${item}`, {
        x: x + 0.25, y: cardY + 1.0 + j * 0.42, w: phW - 0.4, h: 0.35,
        fontSize: 10.5, fontFace: "Calibri",
        color: "B0BEC5", valign: "middle",
      });
    });
  });

  addBottomAccent(slide, true);
}

// ═══════════════════════════════════════════════════════════
// SLIDE 10: THANK YOU
// ═══════════════════════════════════════════════════════════
function createSlide10(pptx) {
  const slide = addDarkSlide(pptx);

  // Top accent line
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.33, h: 0.06,
    fill: { type: "solid", color: AZURE_BLUE },
  });

  // Left accent line
  slide.addShape(pptx.shapes.RECTANGLE, {
    x: 0.9, y: 2.2, w: 0.06, h: 2.4,
    fill: { type: "solid", color: AZURE_CYAN },
  });

  // "Ready to Modernize?"
  slide.addText("Ready to Modernize?", {
    x: 1.3, y: 2.2, w: 10, h: 0.9,
    fontSize: 44, fontFace: "Calibri Light", bold: true,
    color: WHITE,
  });

  // Tagline
  slide.addText("Mule Migrator \u2014 AI-Powered Application Modernization", {
    x: 1.3, y: 3.15, w: 10, h: 0.5,
    fontSize: 18, fontFace: "Calibri",
    color: AZURE_CYAN,
  });

  // URL box
  addCard(slide, 1.3, 4.0, 5.5, 0.65, { fill: "1A2940" });
  slide.addText("\uD83C\uDF10  https://nice-rock-0f9182f00.6.azurestaticapps.net", {
    x: 1.3, y: 4.0, w: 5.5, h: 0.65,
    fontSize: 12, fontFace: "Calibri",
    color: AZURE_CYAN, align: "center", valign: "middle",
  });

  // Key value props at bottom
  const props = [
    { icon: "\u26A1", text: "5 min migrations" },
    { icon: "\uD83D\uDCB2", text: "$0.04 per migration" },
    { icon: "\u2714", text: "99% compilable" },
    { icon: "\uD83D\uDEE1", text: "Enterprise secure" },
  ];

  const propW = 2.5;
  const propGap = 0.35;
  const totalPW = propW * 4 + propGap * 3;
  const pStartX = (13.33 - totalPW) / 2;

  props.forEach((p, i) => {
    const x = pStartX + i * (propW + propGap);
    addCard(slide, x, 5.3, propW, 0.6, { fill: "1A2940" });
    slide.addText(`${p.icon}  ${p.text}`, {
      x, y: 5.3, w: propW, h: 0.6,
      fontSize: 11, fontFace: "Calibri", bold: true,
      color: WHITE, align: "center", valign: "middle",
    });
  });

  // Thank you note
  slide.addText("Thank you", {
    x: 0, y: 6.3, w: 13.33, h: 0.5,
    fontSize: 14, fontFace: "Calibri",
    color: "4A5568", align: "center",
  });

  addBottomAccent(slide, true);
}

// ═══════════════════════════════════════════════════════════
// GENERATE ALL SLIDES
// ═══════════════════════════════════════════════════════════

console.log("Creating Mule Migrator Management Presentation...\n");

createSlide1(pptx);
console.log("  [1/10] Title slide");

createSlide2(pptx);
console.log("  [2/10] The Challenge");

createSlide3(pptx);
console.log("  [3/10] Our Solution");

createSlide4(pptx);
console.log("  [4/10] How It Works");

createSlide5(pptx);
console.log("  [5/10] AI Technology");

createSlide6(pptx);
console.log("  [6/10] Security & Compliance");

createSlide7(pptx);
console.log("  [7/10] Cost Comparison");

createSlide8(pptx);
console.log("  [8/10] Platform Metrics");

createSlide9(pptx);
console.log("  [9/10] Roadmap");

createSlide10(pptx);
console.log("  [10/10] Thank You");

const outputPath = "./Mule_Migrator_Management_Overview.pptx";
pptx.writeFile({ fileName: outputPath }).then(() => {
  console.log(`\n  Presentation saved: ${outputPath}`);
  console.log("  10 slides | Executive-level | Azure themed\n");
}).catch(err => {
  console.error("Error writing file:", err);
});
