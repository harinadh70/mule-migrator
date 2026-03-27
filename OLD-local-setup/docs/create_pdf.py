#!/usr/bin/env python3
"""
Generate comprehensive PDF documentation for MuleSoft to Spring Boot Migrator.
Uses ReportLab for professional PDF output.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, ListFlowable, ListItem, Flowable
)
from reportlab.lib import colors


# ════════════════════════════════════════════════════════════════
# COLOR SCHEME
# ════════════════════════════════════════════════════════════════
PRIMARY = HexColor("#1B3A5C")
PRIMARY_LIGHT = HexColor("#2C5F8A")
ACCENT = HexColor("#3B82F6")
BG_LIGHT = HexColor("#F0F4F8")
BG_CODE = HexColor("#F5F5F5")
BORDER = HexColor("#CBD5E1")
TEXT_DARK = HexColor("#1E293B")
TEXT_MED = HexColor("#475569")
TEXT_LIGHT = HexColor("#64748B")
SUCCESS = HexColor("#16A34A")
WARNING = HexColor("#D97706")
ERROR = HexColor("#DC2626")
INFO_BG = HexColor("#EFF6FF")
INFO_BORDER = HexColor("#3B82F6")
WARN_BG = HexColor("#FFFBEB")
WARN_BORDER = HexColor("#F59E0B")
TIP_BG = HexColor("#F0FDF4")
TIP_BORDER = HexColor("#22C55E")
IMP_BG = HexColor("#FEF2F2")
IMP_BORDER = HexColor("#EF4444")


# ════════════════════════════════════════════════════════════════
# CUSTOM STYLES
# ════════════════════════════════════════════════════════════════
def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'DocTitle', parent=styles['Title'],
        fontSize=28, textColor=white, alignment=TA_CENTER,
        fontName='Helvetica-Bold', spaceAfter=8, leading=34
    ))
    styles.add(ParagraphStyle(
        'DocSubTitle', parent=styles['Normal'],
        fontSize=16, textColor=HexColor("#B0C4DE"), alignment=TA_CENTER,
        fontName='Helvetica', spaceAfter=4, leading=20
    ))
    styles.add(ParagraphStyle(
        'ChapterTitle', parent=styles['Heading1'],
        fontSize=22, textColor=PRIMARY, fontName='Helvetica-Bold',
        spaceBefore=20, spaceAfter=12, leading=28,
        borderWidth=0, borderPadding=0, borderColor=PRIMARY,
    ))
    styles.add(ParagraphStyle(
        'SectionTitle', parent=styles['Heading2'],
        fontSize=15, textColor=PRIMARY_LIGHT, fontName='Helvetica-Bold',
        spaceBefore=14, spaceAfter=8, leading=20
    ))
    styles.add(ParagraphStyle(
        'SubSection', parent=styles['Heading3'],
        fontSize=12, textColor=TEXT_DARK, fontName='Helvetica-Bold',
        spaceBefore=10, spaceAfter=6, leading=16
    ))
    styles.add(ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontSize=10, textColor=TEXT_DARK, fontName='Helvetica',
        spaceBefore=3, spaceAfter=6, leading=14, alignment=TA_JUSTIFY
    ))
    styles.add(ParagraphStyle(
        'CodeBlock', parent=styles['Normal'],
        fontSize=8, textColor=HexColor("#333333"), fontName='Courier',
        spaceBefore=4, spaceAfter=4, leading=11, leftIndent=12,
        backColor=BG_CODE, borderWidth=0.5, borderColor=BORDER,
        borderPadding=6, borderRadius=2
    ))
    styles.add(ParagraphStyle(
        'BulletText', parent=styles['Normal'],
        fontSize=10, textColor=TEXT_DARK, fontName='Helvetica',
        spaceBefore=2, spaceAfter=2, leading=14, leftIndent=24,
        bulletIndent=12, bulletFontSize=10
    ))
    styles.add(ParagraphStyle(
        'TableHeader', parent=styles['Normal'],
        fontSize=9, textColor=white, fontName='Helvetica-Bold',
        alignment=TA_CENTER, leading=12
    ))
    styles.add(ParagraphStyle(
        'TableCell', parent=styles['Normal'],
        fontSize=9, textColor=TEXT_DARK, fontName='Helvetica',
        leading=12, spaceBefore=1, spaceAfter=1
    ))
    styles.add(ParagraphStyle(
        'InfoBox', parent=styles['Normal'],
        fontSize=9, textColor=TEXT_DARK, fontName='Helvetica',
        leading=13, leftIndent=8, rightIndent=8, spaceBefore=2, spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        'TOCEntry', parent=styles['Normal'],
        fontSize=11, textColor=PRIMARY, fontName='Helvetica-Bold',
        spaceBefore=6, spaceAfter=2, leading=15
    ))
    styles.add(ParagraphStyle(
        'TOCDesc', parent=styles['Normal'],
        fontSize=9, textColor=TEXT_LIGHT, fontName='Helvetica-Oblique',
        spaceBefore=0, spaceAfter=4, leading=12, leftIndent=20
    ))
    styles.add(ParagraphStyle(
        'FooterStyle', parent=styles['Normal'],
        fontSize=8, textColor=TEXT_LIGHT, fontName='Helvetica',
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        'GlossaryTerm', parent=styles['Normal'],
        fontSize=10, textColor=TEXT_DARK, fontName='Helvetica-Bold',
        spaceBefore=4, spaceAfter=1, leading=14
    ))
    styles.add(ParagraphStyle(
        'GlossaryDef', parent=styles['Normal'],
        fontSize=10, textColor=TEXT_MED, fontName='Helvetica',
        spaceBefore=0, spaceAfter=6, leading=14, leftIndent=12
    ))
    return styles


# ════════════════════════════════════════════════════════════════
# CUSTOM FLOWABLES
# ════════════════════════════════════════════════════════════════
class ColoredBox(Flowable):
    """A colored box with text inside."""
    def __init__(self, width, height, bg_color, border_color=None):
        Flowable.__init__(self)
        self.box_width = width
        self.box_height = height
        self.bg_color = bg_color
        self.border_color = border_color

    def draw(self):
        self.canv.setFillColor(self.bg_color)
        if self.border_color:
            self.canv.setStrokeColor(self.border_color)
            self.canv.setLineWidth(1)
        else:
            self.canv.setStrokeColor(self.bg_color)
        self.canv.roundRect(0, 0, self.box_width, self.box_height, 4, fill=1, stroke=1 if self.border_color else 0)

    def wrap(self, availWidth, availHeight):
        return self.box_width, self.box_height


class HLine(Flowable):
    """Horizontal line."""
    def __init__(self, width, color=BORDER, thickness=1):
        Flowable.__init__(self)
        self.line_width = width
        self.color = color
        self.thickness = thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.line_width, 0)

    def wrap(self, availWidth, availHeight):
        return self.line_width, self.thickness + 2


# ════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════
def make_table(headers, rows, col_widths=None, stripe=True):
    """Create a professionally styled table."""
    all_data = []
    # Header row
    hdr = [Paragraph(h, get_styles()['TableHeader']) for h in headers]
    all_data.append(hdr)
    # Data rows
    for row in rows:
        data_row = [Paragraph(str(cell), get_styles()['TableCell']) for cell in row]
        all_data.append(data_row)

    if col_widths:
        t = Table(all_data, colWidths=[w * inch for w in col_widths], repeatRows=1)
    else:
        t = Table(all_data, repeatRows=1)

    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    if stripe:
        for i in range(1, len(all_data)):
            if i % 2 == 0:
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), BG_LIGHT))

    t.setStyle(TableStyle(style_cmds))
    return t


def make_info_box(text, box_type="info"):
    """Create a colored info box."""
    configs = {
        "info": (INFO_BG, INFO_BORDER, "INFO"),
        "warning": (WARN_BG, WARN_BORDER, "WARNING"),
        "tip": (TIP_BG, TIP_BORDER, "TIP"),
        "important": (IMP_BG, IMP_BORDER, "IMPORTANT"),
    }
    bg, border, label = configs.get(box_type, configs["info"])
    content = f'<b>{label}:</b> {text}'
    data = [[Paragraph(content, get_styles()['InfoBox'])]]
    t = Table(data, colWidths=[6.2 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('BOX', (0, 0), (-1, -1), 1.5, border),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t


def make_code(code_text):
    """Create a code block."""
    lines = code_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    lines = lines.replace('\n', '<br/>')
    return Paragraph(lines, get_styles()['CodeBlock'])


def bullet(text):
    """Create a bullet point paragraph."""
    s = get_styles()['BulletText']
    return Paragraph(f'<bullet>&bull;</bullet> {text}', s)


def numbered_item(num, text):
    s = get_styles()['BulletText']
    return Paragraph(f'<bullet>{num}.</bullet> {text}', s)


# ════════════════════════════════════════════════════════════════
# PAGE TEMPLATES
# ════════════════════════════════════════════════════════════════
def header_footer(canvas, doc):
    """Add header and footer to each page."""
    canvas.saveState()
    page_num = doc.page

    # Header line
    if page_num > 1:
        canvas.setStrokeColor(PRIMARY)
        canvas.setLineWidth(0.5)
        canvas.line(inch, letter[1] - 0.6 * inch, letter[0] - inch, letter[1] - 0.6 * inch)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(TEXT_LIGHT)
        canvas.drawString(inch, letter[1] - 0.55 * inch, "MuleSoft to Spring Boot Migrator - Documentation")

    # Footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(inch, 0.55 * inch, letter[0] - inch, 0.55 * inch)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(TEXT_LIGHT)
    canvas.drawCentredString(letter[0] / 2, 0.4 * inch, f"Page {page_num}")
    canvas.drawRightString(letter[0] - inch, 0.4 * inch, "v1.0 - March 2026")

    canvas.restoreState()


def cover_page_template(canvas, doc):
    """Cover page with no header/footer."""
    canvas.saveState()
    canvas.restoreState()


# ════════════════════════════════════════════════════════════════
# MAIN DOCUMENT BUILD
# ════════════════════════════════════════════════════════════════
def create_pdf():
    output_dir = "/Users/harinadh/Documents/My code/mulesoft-to-springboot-migrator/docs"
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, "MuleSoft-to-SpringBoot-Migrator-Documentation.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        topMargin=0.8 * inch,
        bottomMargin=0.7 * inch,
        leftMargin=inch,
        rightMargin=inch,
        title="MuleSoft to Spring Boot Migrator - Documentation",
        author="Harinadh",
        subject="Complete Technical Documentation"
    )

    styles = get_styles()
    story = []

    # ════════════════════════════════════════════════════════════
    # COVER PAGE
    # ════════════════════════════════════════════════════════════
    story.append(Spacer(1, 2 * inch))

    # Title box
    cover_data = [[
        Paragraph('<br/>', styles['DocSubTitle']),
        Paragraph('MuleSoft to Spring Boot Migrator', styles['DocTitle']),
        Paragraph('Complete Technical Documentation', styles['DocSubTitle']),
        Paragraph('A Beginner-Friendly Guide', styles['DocSubTitle']),
        Paragraph('<br/>', styles['DocSubTitle']),
    ]]
    # Build as a simple multi-line cell
    title_content = []
    title_content.append(Spacer(1, 12))
    title_content.append(Paragraph('MuleSoft to Spring Boot Migrator', styles['DocTitle']))
    title_content.append(Spacer(1, 6))
    title_content.append(Paragraph('Complete Technical Documentation', styles['DocSubTitle']))
    title_content.append(Spacer(1, 4))
    title_content.append(Paragraph('A Beginner-Friendly Guide', styles['DocSubTitle']))
    title_content.append(Spacer(1, 12))

    title_table = Table([[title_content]], colWidths=[6.5 * inch])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0, PRIMARY),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(title_table)

    story.append(Spacer(1, 0.8 * inch))

    meta = [
        ("Version", "1.0"),
        ("Date", "March 2026"),
        ("Author", "Harinadh"),
        ("Technology Stack", "Python Flask + Spring Boot 3.2"),
    ]
    for label, value in meta:
        story.append(Paragraph(
            f'<b>{label}:</b>  {value}',
            ParagraphStyle('meta', parent=styles['BodyText2'], alignment=TA_CENTER,
                          textColor=TEXT_MED, fontSize=10)
        ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('Table of Contents', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))
    story.append(Spacer(1, 12))

    toc_items = [
        ("1.", "Introduction", "What is this tool and why does it exist?"),
        ("2.", "Key Concepts for Beginners", "Understanding MuleSoft, Spring Boot, and APIs"),
        ("3.", "System Requirements", "What you need before starting"),
        ("4.", "Installation Guide", "Step-by-step setup instructions"),
        ("5.", "Quick Start Tutorial", "Your first migration in 5 minutes"),
        ("6.", "Understanding the User Interface", "Every button and panel explained"),
        ("7.", "How the Migration Works", "The complete pipeline from XML to Java"),
        ("8.", "Supported MuleSoft Components", "Every connector, processor, and pattern"),
        ("9.", "DataWeave to Java Conversion", "How expressions are translated"),
        ("10.", "AI-Powered Code Validation", "Using LLM models to review code"),
        ("11.", "Multi-File Migration", "Working with multiple XML files"),
        ("12.", "Generated Spring Boot Project", "Understanding the output"),
        ("13.", "API Reference", "All endpoints documented"),
        ("14.", "Production Deployment", "Docker, Nginx, and cloud deployment"),
        ("15.", "Configuration Reference", "Every setting explained"),
        ("16.", "Troubleshooting Guide", "Common problems and solutions"),
        ("17.", "Glossary", "Technical terms explained simply"),
    ]

    for num, title, desc in toc_items:
        story.append(Paragraph(f'{num}  {title}', styles['TOCEntry']))
        story.append(Paragraph(desc, styles['TOCDesc']))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 1: INTRODUCTION
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('1. Introduction', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('1.1 What is This Tool?', styles['SectionTitle']))
    story.append(Paragraph(
        'The MuleSoft to Spring Boot Migrator is a web application that automatically converts '
        'MuleSoft 4 integration projects into Spring Boot 3.2 Java applications. Think of it as a '
        '"translator" that reads your MuleSoft XML configuration files and produces a complete, '
        'ready-to-run Java project.',
        styles['BodyText2']
    ))

    story.append(Paragraph('1.2 Why Would You Need This?', styles['SectionTitle']))
    story.append(Paragraph(
        'Many organizations use MuleSoft (owned by Salesforce) for building APIs and integrations. '
        'However, there are several reasons why a company might want to move to Spring Boot:',
        styles['BodyText2']
    ))
    for item in [
        '<b>Cost Reduction:</b> MuleSoft licenses can be expensive. Spring Boot is free and open-source.',
        '<b>Control:</b> With Spring Boot, you own and control your entire codebase.',
        '<b>Flexibility:</b> Spring Boot has a massive ecosystem of libraries and tools.',
        '<b>Talent Pool:</b> More developers know Java/Spring Boot than MuleSoft.',
        '<b>Performance:</b> Spring Boot applications can be highly optimized for your specific use case.',
    ]:
        story.append(bullet(item))

    story.append(Paragraph('1.3 What Does It Actually Do?', styles['SectionTitle']))
    story.append(Paragraph('Here is exactly what happens when you use this tool:', styles['BodyText2']))
    steps = [
        'You upload your MuleSoft XML files (the files that define your APIs and integrations)',
        'The tool reads and understands every element in those XML files',
        'It identifies all connectors (HTTP, Database, JMS, Kafka, etc.)',
        'It converts MuleSoft flows into Java classes with Spring Boot annotations',
        'It translates DataWeave expressions into equivalent Java code',
        'It generates a complete Maven project with all dependencies',
        'It creates configuration files (application.properties) with correct settings',
        'Optionally, an AI model reviews the generated code for quality and suggestions',
        'You download a ZIP file containing a complete, runnable Spring Boot project',
    ]
    for i, step in enumerate(steps, 1):
        story.append(numbered_item(i, step))

    story.append(Paragraph('1.4 Who Is This Documentation For?', styles['SectionTitle']))
    story.append(Paragraph(
        'This documentation is written for everyone, from complete beginners to experienced developers. '
        'Every technical term is explained. Every step includes detailed instructions. '
        'You do NOT need prior experience with MuleSoft, Spring Boot, or programming to understand this guide.',
        styles['BodyText2']
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 2: KEY CONCEPTS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('2. Key Concepts for Beginners', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    concepts = [
        ("2.1 What is MuleSoft?",
         'MuleSoft is a platform for building application programming interfaces (APIs) and integrations. '
         'It allows businesses to connect different software systems together. For example, connecting '
         'your website to a database, or connecting your payment system to your inventory system. '
         'MuleSoft uses XML configuration files to define how data flows between systems. '
         'These XML files contain "flows" which are like step-by-step instructions.'),
        ("2.2 What is Spring Boot?",
         'Spring Boot is a popular Java framework for building web applications and APIs. '
         'It is open-source (free to use) and is the most widely used Java framework in the world. '
         'Spring Boot makes it easy to create production-ready applications with minimal configuration.'),
        ("2.3 What is an API?",
         'An API (Application Programming Interface) is a way for two software programs to talk to each other. '
         'Think of it like a waiter in a restaurant: you (the client) tell the waiter (the API) what you want, '
         'the waiter goes to the kitchen (the server), and brings back your food (the response).'),
        ("2.4 What is Docker?",
         'Docker is a tool that packages your application and everything it needs into a "container." '
         'Think of a container like a shipping container: no matter what ship (computer) carries it, '
         'the contents are always the same and always work.'),
        ("2.5 What is DataWeave?",
         'DataWeave is MuleSoft\'s own programming language for transforming data. For example, if you '
         'receive customer data in one format but need to send it in a different format, DataWeave handles '
         'that transformation. Our tool converts DataWeave code into equivalent Java code.'),
        ("2.6 What is an LLM (AI Model)?",
         'LLM stands for Large Language Model. These are AI systems (like ChatGPT, Claude, Gemini) that '
         'can understand and generate text, including code. Our tool can optionally send the generated '
         'Spring Boot code to an LLM for review, getting suggestions for improvements.'),
    ]
    for title, text in concepts:
        story.append(Paragraph(title, styles['SectionTitle']))
        story.append(Paragraph(text, styles['BodyText2']))

    story.append(Spacer(1, 8))
    story.append(Paragraph('Common API Terms:', styles['SubSection']))
    story.append(make_table(
        ["Term", "What It Means", "Example"],
        [
            ["Endpoint", "A specific URL that accepts requests", "/api/customers"],
            ["GET", "A request to retrieve data", "Get list of all customers"],
            ["POST", "A request to create new data", "Create a new customer"],
            ["PUT", "A request to update existing data", "Update customer address"],
            ["DELETE", "A request to remove data", "Delete a customer record"],
            ["JSON", "A text format for sending/receiving data", '{"name": "John", "age": 30}'],
            ["XML", "Another text format (used by MuleSoft)", "&lt;name&gt;John&lt;/name&gt;"],
        ],
        col_widths=[0.9, 2.3, 3.0]
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 3: SYSTEM REQUIREMENTS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('3. System Requirements', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('3.1 Minimum Requirements', styles['SectionTitle']))
    story.append(make_table(
        ["Requirement", "Minimum", "Recommended"],
        [
            ["Operating System", "macOS 10.15+, Windows 10+, Linux", "macOS 12+ or Ubuntu 22.04+"],
            ["Python", "3.9 or higher", "3.12"],
            ["RAM", "4 GB", "8 GB or more"],
            ["Disk Space", "500 MB", "2 GB (for Docker)"],
            ["Browser", "Any modern browser", "Chrome or Firefox (latest)"],
            ["Internet", "Required for LLM validation", "Broadband connection"],
        ],
        col_widths=[1.4, 2.2, 2.6]
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph('3.2 Optional Requirements', styles['SectionTitle']))
    story.append(make_table(
        ["Component", "When Needed", "Purpose"],
        [
            ["Docker", "Production deployment", "Run the app in a container"],
            ["LLM API Key", "AI code validation", "Review generated code quality"],
            ["Java 17+", "To run generated project", "Build the Spring Boot output"],
            ["Maven 3.9+", "To build generated project", "Compile and package the Java project"],
        ],
        col_widths=[1.3, 2.0, 2.9]
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 4: INSTALLATION
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('4. Installation Guide', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('4.1 Method 1: Local Installation (Recommended for Development)', styles['SectionTitle']))

    story.append(Paragraph('Step 1: Verify Python is Installed', styles['SubSection']))
    story.append(Paragraph('Open your terminal and type:', styles['BodyText2']))
    story.append(make_code('python3 --version'))
    story.append(Paragraph(
        'You should see something like "Python 3.9.6" or higher. If you get an error, install Python from python.org.',
        styles['BodyText2']
    ))

    story.append(Paragraph('Step 2: Navigate to the Project Folder', styles['SubSection']))
    story.append(make_code('cd "/path/to/mulesoft-to-springboot-migrator/backend"'))

    story.append(Paragraph('Step 3: Install Dependencies', styles['SubSection']))
    story.append(Paragraph('This installs all the Python packages the tool needs:', styles['BodyText2']))
    story.append(make_code('pip3 install -r requirements.txt'))

    story.append(Paragraph('Step 4: Start the Server', styles['SubSection']))
    story.append(Paragraph('For development:', styles['BodyText2']))
    story.append(make_code('python3 app.py'))
    story.append(Paragraph('For production:', styles['BodyText2']))
    story.append(make_code('python3 -m gunicorn -c gunicorn.conf.py app:app'))

    story.append(Paragraph('Step 5: Open in Browser', styles['SubSection']))
    story.append(make_code('http://localhost:5000'))
    story.append(make_info_box(
        'You should see the MuleSoft to Spring Boot Migrator interface with a dark-themed UI.', "tip"
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph('4.2 Method 2: Docker Installation (Recommended for Production)', styles['SectionTitle']))
    story.append(Paragraph('Step 1: Install Docker Desktop from docker.com', styles['SubSection']))
    story.append(Paragraph('Step 2: Create Environment File', styles['SubSection']))
    story.append(make_code('cp .env.example .env\n# Edit .env with your favorite text editor'))
    story.append(Paragraph('Step 3: Start with Docker Compose', styles['SubSection']))
    story.append(make_code('# Basic start\ndocker compose up -d\n\n# With Nginx reverse proxy\ndocker compose --profile with-nginx up -d'))
    story.append(Paragraph('Step 4: Verify', styles['SubSection']))
    story.append(make_code('curl http://localhost:5000/api/health\n# {"status": "ok", "env": "production"}'))

    story.append(Spacer(1, 10))
    story.append(Paragraph('4.3 Stopping the Server', styles['SectionTitle']))
    story.append(make_table(
        ["Method", "Command"],
        [
            ["Local (Gunicorn)", "kill $(pgrep -f 'gunicorn.*app:app')"],
            ["Local (Flask dev)", "Press Ctrl+C in the terminal"],
            ["Docker", "docker compose down"],
        ],
        col_widths=[2.0, 4.2]
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 5: QUICK START
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('5. Quick Start Tutorial', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))
    story.append(Paragraph(
        'Let\'s walk through your very first migration. This tutorial takes about 5 minutes.',
        styles['BodyText2']
    ))

    qs_steps = [
        ("Step 1: Open the Application",
         'Start the server (see Chapter 4) and open http://localhost:5000 in your browser. '
         'You will see a dark-themed interface split into two panels: Input (left) and Output (right).'),
        ("Step 2: Load Sample Data",
         'Click the "Load Sample" button in the top-right corner. This fills in a sample MuleSoft XML '
         'configuration that demonstrates HTTP endpoints, database queries, and DataWeave transformations.'),
        ("Step 3: Click Migrate to Spring Boot",
         'Click the large blue "Migrate to Spring Boot" button at the bottom of the left panel. '
         'The tool will process the XML and generate a complete Spring Boot project in 1-2 seconds.'),
        ("Step 4: Explore the Output",
         'The right panel shows three tabs: Generated Files (file tree with all Java files), '
         'Summary (migration statistics), and AI Review (if LLM validation was enabled).'),
        ("Step 5: Download the Project",
         'Click "Download ZIP" to download the complete Spring Boot project. Unzip it, open in your '
         'Java IDE (IntelliJ, Eclipse, VS Code), and run it!'),
    ]
    for title, text in qs_steps:
        story.append(Paragraph(title, styles['SectionTitle']))
        story.append(Paragraph(text, styles['BodyText2']))

    story.append(make_info_box(
        'The generated project includes a Dockerfile and docker-compose.yml, so you can also run it '
        'with "docker compose up -d" without installing Java locally!', "tip"
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 6: UI
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('6. Understanding the User Interface', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('6.1 Overall Layout', styles['SectionTitle']))
    story.append(make_table(
        ["Section", "Location", "Purpose"],
        [
            ["Header Bar", "Top of page", "Logo, title, Load Sample and Clear buttons"],
            ["Input Panel", "Left side", "MuleSoft XML, DataWeave, Settings, AI Validation"],
            ["Output Panel", "Right side", "Generated code, Summary, AI Review"],
            ["Status Bar", "Bottom", "Status messages and progress"],
            ["Loading Overlay", "Center", "Animated spinner during processing"],
        ],
        col_widths=[1.2, 1.2, 3.8]
    ))

    story.append(Paragraph('6.2 Input Panel - MuleSoft XML Tab', styles['SectionTitle']))
    for item in [
        '<b>Upload Zone:</b> Drag and drop XML files or click to browse. Accepts .xml, .raml, .yaml, .yml',
        '<b>Multiple Files:</b> Upload multiple files. Each appears as a chip with filename and size',
        '<b>Code Editor:</b> Syntax-highlighted editor (CodeMirror) for pasting XML directly',
        '<b>Preview:</b> Click any uploaded file chip to preview its contents',
    ]:
        story.append(bullet(item))

    story.append(Paragraph('6.3 Input Panel - DataWeave Tab', styles['SectionTitle']))
    for item in [
        '<b>Script List:</b> Shows all DataWeave scripts as tabs',
        '<b>Add Script:</b> Click "+" to create a new named DataWeave script',
        '<b>Convert:</b> Click to see the Java equivalent of just this script',
    ]:
        story.append(bullet(item))

    story.append(Paragraph('6.4 Input Panel - Settings Tab', styles['SectionTitle']))
    story.append(make_table(
        ["Setting", "Default", "Description"],
        [
            ["Project Name", "my-spring-app", "Name for your Spring Boot project"],
            ["Group ID", "com.example", "Java package namespace"],
            ["Java Version", "17", "Target Java version (17 or 21 recommended)"],
        ],
        col_widths=[1.5, 1.5, 3.2]
    ))

    story.append(Paragraph('6.5 Input Panel - AI Validation Tab', styles['SectionTitle']))
    for item in [
        '<b>Enable/Disable Toggle:</b> Turn AI validation on or off',
        '<b>Provider Dropdown:</b> Select AI provider (Anthropic, OpenAI, Google, etc.)',
        '<b>Model Dropdown:</b> Choose a specific model',
        '<b>API Key Field:</b> Enter your API key (never stored on disk)',
        '<b>Base URL:</b> Only needed for Ollama (local AI)',
        '<b>Test Connection:</b> Verify your API key works before migrating',
    ]:
        story.append(bullet(item))

    story.append(Paragraph('6.6 Output Panel Tabs', styles['SectionTitle']))
    for item in [
        '<b>Generated Files:</b> Hierarchical file tree of all generated files. Click to view with syntax highlighting.',
        '<b>Summary:</b> Statistics - flows converted, connectors found, dependencies, warnings',
        '<b>AI Review:</b> Score (1-10), issues by severity, improvements, security issues, best practices',
    ]:
        story.append(bullet(item))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 7: PIPELINE
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('7. How the Migration Works', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))
    story.append(Paragraph(
        'The migration follows a pipeline of 6 steps. Understanding this pipeline helps you '
        'understand the output and troubleshoot any issues.',
        styles['BodyText2']
    ))

    pipeline_steps = [
        ("Step 1: Parse (parser.py)",
         'The XML parser reads each MuleSoft XML file and extracts all meaningful elements: '
         'flows, sub-flows, connectors, configurations, error handlers, DataWeave transformations, '
         'batch jobs, and more. It understands 30+ MuleSoft namespaces.'),
        ("Step 2: Merge (app.py)",
         'If multiple XML files were provided, the parsed results are merged into a single unified '
         'structure. Duplicate flows are detected and the first occurrence is kept with a warning.'),
        ("Step 3: Map Connectors (connector_mapper.py)",
         'Each detected connector is mapped to its Spring Boot equivalent. This determines Maven '
         'dependencies, Spring annotations, and configuration properties.'),
        ("Step 4: Convert Flows (flow_converter.py)",
         'Each MuleSoft flow is converted to a Java class. HTTP listeners become REST controllers, '
         'schedulers become @Scheduled methods, message listeners become JMS/Kafka/AMQP listeners.'),
        ("Step 5: Generate Project (spring_generator.py)",
         'The complete Spring Boot project is assembled: pom.xml, Application class, configuration '
         'classes, application.properties, exception classes, Dockerfile, and docker-compose.yml.'),
        ("Step 6: Validate (llm_validator.py, Optional)",
         'If AI validation is enabled, the generated code is sent to an LLM for review. The AI '
         'scores the code from 1-10 and provides actionable feedback.'),
    ]
    for title, text in pipeline_steps:
        story.append(Paragraph(title, styles['SubSection']))
        story.append(Paragraph(text, styles['BodyText2']))

    # Pipeline visual
    story.append(Spacer(1, 10))
    pipe_data = [["XML Files", "Parser", "Merger", "Converter", "Generator", "ZIP Output"]]
    pipe_colors = [
        HexColor("#E3F2FD"), HexColor("#BBDEFB"), HexColor("#90CAF9"),
        HexColor("#64B5F6"), HexColor("#42A5F5"), HexColor("#1E88E5")
    ]
    pipe_table = Table(pipe_data, colWidths=[1.08 * inch] * 6)
    pipe_style = [
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, white),
    ]
    for i, clr in enumerate(pipe_colors):
        pipe_style.append(('BACKGROUND', (i, 0), (i, 0), clr))
        if i >= 4:
            pipe_style.append(('TEXTCOLOR', (i, 0), (i, 0), white))
    pipe_table.setStyle(TableStyle(pipe_style))
    story.append(pipe_table)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 8: SUPPORTED COMPONENTS
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('8. Supported MuleSoft Components', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('8.1 Supported Connectors (30+)', styles['SectionTitle']))
    story.append(Paragraph(
        'A "connector" in MuleSoft is a pre-built module for connecting to external systems:',
        styles['BodyText2']
    ))
    story.append(make_table(
        ["MuleSoft Connector", "Purpose", "Spring Boot Equivalent"],
        [
            ["HTTP Listener", "Receives API requests", "Spring Web (@RestController)"],
            ["HTTP Request", "Sends API requests", "RestTemplate / WebClient"],
            ["Database", "MySQL, Oracle, PostgreSQL, MSSQL", "Spring Data JPA / JdbcTemplate"],
            ["JMS", "Java message queues", "JmsTemplate / @JmsListener"],
            ["AMQP", "RabbitMQ messaging", "RabbitTemplate / @RabbitListener"],
            ["Kafka", "Event streaming", "KafkaTemplate / @KafkaListener"],
            ["VM", "In-memory messaging", "Spring Events (built-in)"],
            ["File", "Local file operations", "java.nio.file.Files"],
            ["SFTP", "Secure file transfer", "Spring Integration SFTP"],
            ["FTP", "File transfer protocol", "Spring Integration FTP"],
            ["Email", "IMAP, POP3, SMTP", "Spring Mail"],
            ["SOAP/WS", "SOAP web services", "Spring Web Services"],
            ["Salesforce", "CRM integration", "RestTemplate + OAuth"],
            ["Amazon S3", "Cloud file storage", "AWS SDK v2 S3Client"],
            ["Amazon SQS", "Cloud message queue", "Spring Cloud AWS"],
            ["MongoDB", "NoSQL document DB", "Spring Data MongoDB"],
            ["Redis", "In-memory cache/store", "Spring Data Redis"],
            ["Elasticsearch", "Search engine", "Spring Data Elasticsearch"],
            ["Batch", "Batch job processing", "Spring Batch"],
            ["OAuth/Security", "Authentication", "Spring Security"],
            ["Validation", "Input validation", "Jakarta Bean Validation"],
        ],
        col_widths=[1.4, 2.0, 2.8]
    ))

    story.append(PageBreak())

    story.append(Paragraph('8.2 Supported Processors (50+)', styles['SectionTitle']))
    story.append(Paragraph('Core Logic Processors:', styles['SubSection']))
    story.append(make_table(
        ["MuleSoft Processor", "What It Does", "Java Equivalent"],
        [
            ["choice", "If/else branching", "if-else statements"],
            ["for-each", "Loop through items", "Java Stream .forEach()"],
            ["parallel-for-each", "Process in parallel", "parallelStream()"],
            ["scatter-gather", "Run tasks simultaneously", "CompletableFuture.allOf()"],
            ["try", "Handle errors", "try-catch block"],
            ["until-successful", "Retry operations", "@Retryable annotation"],
            ["async", "Background processing", "@Async annotation"],
            ["flow-ref", "Call another flow", "Service method call"],
        ],
        col_widths=[1.5, 2.0, 2.7]
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph('Connector-Specific Processors:', styles['SubSection']))
    story.append(make_table(
        ["Processor", "What It Does", "Java Equivalent"],
        [
            ["http:request", "Send HTTP request", "restTemplate.exchange()"],
            ["db:select", "Query database", "jdbcTemplate.query()"],
            ["db:insert", "Add database record", "jdbcTemplate.update()"],
            ["db:update", "Modify records", "jdbcTemplate.update()"],
            ["db:delete", "Remove records", "jdbcTemplate.update(DELETE)"],
            ["jms:publish", "Send message to queue", "jmsTemplate.convertAndSend()"],
            ["file:read", "Read a file", "Files.readString(Path)"],
            ["file:write", "Write a file", "Files.writeString(Path, content)"],
        ],
        col_widths=[1.3, 1.8, 3.1]
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph('8.3 Error Type Mapping (100+ types)', styles['SectionTitle']))
    story.append(make_table(
        ["MuleSoft Error", "Java Exception", "HTTP Status"],
        [
            ["HTTP:NOT_FOUND", "ResourceNotFoundException", "404"],
            ["HTTP:BAD_REQUEST", "BadRequestException", "400"],
            ["HTTP:UNAUTHORIZED", "UnauthorizedException", "401"],
            ["HTTP:TIMEOUT", "SocketTimeoutException", "408"],
            ["DB:CONNECTIVITY", "DataAccessResourceFailureException", "503"],
            ["VALIDATION:INVALID_*", "ConstraintViolationException", "400"],
        ],
        col_widths=[1.8, 2.8, 1.0]
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 9: DATAWEAVE
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('9. DataWeave to Java Conversion', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))
    story.append(Paragraph(
        'DataWeave is MuleSoft\'s proprietary data transformation language. This tool converts '
        'DataWeave 2.0 expressions into equivalent Java code using Java Streams.',
        styles['BodyText2']
    ))

    story.append(Paragraph('9.1 Collection Operations', styles['SectionTitle']))
    story.append(make_table(
        ["DataWeave", "What It Does", "Java Equivalent"],
        [
            ["map", "Transform each item", ".stream().map(...).collect(toList())"],
            ["filter", "Keep matching items", ".stream().filter(...).collect(toList())"],
            ["reduce", "Combine into one value", ".stream().reduce(...)"],
            ["flatMap", "Map and flatten", ".stream().flatMap(...)"],
            ["groupBy", "Group by key", ".stream().collect(groupingBy(...))"],
            ["orderBy", "Sort items", ".stream().sorted(...)"],
            ["distinctBy", "Remove duplicates", ".stream().distinct()"],
            ["sizeOf", "Count items", ".size()"],
            ["isEmpty", "Check if empty", ".isEmpty()"],
        ],
        col_widths=[1.1, 1.8, 3.3]
    ))

    story.append(Paragraph('9.2 String Operations', styles['SectionTitle']))
    story.append(make_table(
        ["DataWeave", "Java Equivalent"],
        [
            ["upper()", ".toUpperCase()"],
            ["lower()", ".toLowerCase()"],
            ["trim()", ".trim()"],
            ["contains()", ".contains()"],
            ["replace ... with ...", ".replace(old, new)"],
            ["splitBy()", ".split()"],
            ["++ (concatenation)", "+ (string concat)"],
        ],
        col_widths=[2.5, 3.7]
    ))

    story.append(Paragraph('9.3 Type Coercion', styles['SectionTitle']))
    story.append(make_table(
        ["DataWeave", "Java Equivalent"],
        [
            ["as String", "String.valueOf(x)"],
            ["as Number", "Double.parseDouble(x)"],
            ["as Boolean", "Boolean.parseBoolean(x)"],
            ["as Date", "LocalDate.parse(x)"],
            ["as DateTime", "LocalDateTime.parse(x)"],
            ['value default "fallback"', 'value != null ? value : "fallback"'],
        ],
        col_widths=[2.5, 3.7]
    ))

    story.append(Paragraph('9.4 Example Conversion', styles['SectionTitle']))
    story.append(Paragraph('DataWeave:', styles['SubSection']))
    story.append(make_code('%dw 2.0\noutput application/json\n---\npayload map (item) -&gt; {\n    fullName: item.firstName ++ " " ++ item.lastName,\n    age: item.age as Number\n}'))
    story.append(Paragraph('Generated Java:', styles['SubSection']))
    story.append(make_code('List&lt;Map&lt;String,Object&gt;&gt; result = \n  ((List&lt;Map&lt;String,Object&gt;&gt;) payload).stream()\n    .map(item -&gt; {\n        Map&lt;String,Object&gt; obj = new LinkedHashMap&lt;&gt;();\n        obj.put("fullName", item.get("firstName") + " " + \n            item.get("lastName"));\n        obj.put("age", Double.parseDouble(\n            String.valueOf(item.get("age"))));\n        return obj;\n    }).collect(Collectors.toList());'))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 10: AI VALIDATION
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('10. AI-Powered Code Validation', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('10.1 Supported AI Providers', styles['SectionTitle']))
    story.append(make_table(
        ["Provider", "Models", "Pricing", "Best For"],
        [
            ["Anthropic Claude", "Sonnet 4, 3.5 Sonnet, Opus, Haiku", "Paid", "Best code review quality"],
            ["OpenAI GPT", "GPT-4o, GPT-4 Turbo, 4o-mini, o3-mini", "Paid", "Wide availability"],
            ["Google Gemini", "2.5 Pro, 2.0 Flash, 1.5 Pro", "Free tier available", "Cost-effective"],
            ["DeepSeek", "Chat, Coder, Reasoner", "Very affordable", "Budget-friendly"],
            ["Groq", "Llama 3.3 70B, Mixtral, Llama 3.1 8B", "Free!", "Fast and free"],
            ["Ollama (Local)", "CodeLlama, Llama 3, Mistral, Qwen", "Free (local)", "Complete privacy"],
        ],
        col_widths=[1.2, 2.0, 1.2, 1.8]
    ))

    story.append(Paragraph('10.2 Setup Steps', styles['SectionTitle']))
    for i, step in enumerate([
        'Go to the "AI Validation" tab in the input panel',
        'Toggle the switch to enable AI validation',
        'Select your preferred provider from the dropdown',
        'Choose a model (speed vs quality tradeoff)',
        'Enter your API key (get from provider\'s website)',
        'Click "Test Connection" to verify',
        'Click "Migrate" - AI review is included automatically',
    ], 1):
        story.append(numbered_item(i, step))

    story.append(Paragraph('10.3 Understanding the Score', styles['SectionTitle']))
    story.append(make_table(
        ["Score", "Color", "Meaning"],
        [
            ["8-10", "Green", "Excellent - Production-ready with minor suggestions"],
            ["6-7", "Yellow", "Good - Works but has notable improvements"],
            ["4-5", "Orange", "Fair - Significant issues to address"],
            ["1-3", "Red", "Poor - Major problems need fixing"],
        ],
        col_widths=[0.8, 0.8, 4.6]
    ))

    story.append(Paragraph('10.4 Getting Free API Keys', styles['SectionTitle']))
    story.append(make_table(
        ["Provider", "How to Get", "Free Tier"],
        [
            ["Groq", "Sign up at console.groq.com", "Completely free with generous limits"],
            ["Google Gemini", "Sign up at aistudio.google.com", "Free tier with rate limits"],
            ["Ollama", "Install from ollama.com (no key needed)", "Completely free, runs locally"],
        ],
        col_widths=[1.2, 2.5, 2.5]
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 11: MULTI-FILE
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('11. Multi-File Migration', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))
    story.append(Paragraph(
        'Real MuleSoft projects typically have multiple XML files. This tool handles that seamlessly.',
        styles['BodyText2']
    ))

    story.append(Paragraph('11.1 How It Works', styles['SectionTitle']))
    for i, step in enumerate([
        'Upload multiple XML files using drag-drop or file browser',
        'Each file appears as a chip with name and size',
        'Click any chip to preview the file contents',
        'When you click "Migrate", ALL files are processed together',
        'Each file is parsed independently, then results are merged into one project',
    ], 1):
        story.append(numbered_item(i, step))

    story.append(Paragraph('11.2 Merge Rules', styles['SectionTitle']))
    story.append(make_table(
        ["Component", "Merge Rule", "On Conflict"],
        [
            ["Flows", "Combined from all files", "Duplicate names: first kept + warning"],
            ["Sub-Flows", "Combined from all files", "Duplicate names: first kept + warning"],
            ["Configurations", "Combined by name", "Duplicate names: first kept"],
            ["Properties", "Merged into single dict", "Same key: last value wins"],
            ["Connectors", "Union of all detected", "No conflicts (sets)"],
            ["Error Handlers", "All collected", "No conflicts (all kept)"],
        ],
        col_widths=[1.2, 2.2, 2.8]
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 12: GENERATED PROJECT
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('12. Generated Spring Boot Project', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('12.1 Project Structure', styles['SectionTitle']))
    story.append(make_code(
        'my-spring-app/\n'
        '+-- pom.xml                        # Maven build file\n'
        '+-- Dockerfile                     # Container image\n'
        '+-- docker-compose.yml             # Container orchestration\n'
        '+-- src/main/java/.../\n'
        '|   +-- Application.java           # Main entry point\n'
        '|   +-- controller/                # REST controllers\n'
        '|   +-- service/                   # Business logic\n'
        '|   +-- config/                    # Configuration classes\n'
        '|   +-- exception/                 # Custom exceptions\n'
        '+-- src/main/resources/\n'
        '|   +-- application.properties     # App configuration\n'
        '+-- src/test/java/.../\n'
        '    +-- ApplicationTests.java      # Unit tests'
    ))

    story.append(Paragraph('12.2 Key Generated Files', styles['SectionTitle']))
    story.append(make_table(
        ["File", "Purpose", "When Generated"],
        [
            ["pom.xml", "Maven dependencies", "Always"],
            ["Application.java", "Main class with annotations", "Always"],
            ["*Controller.java", "REST endpoints", "When HTTP flows exist"],
            ["*Service.java", "Business logic", "When flows have logic"],
            ["*Listener.java", "Message listeners", "When messaging used"],
            ["SchedulingConfig.java", "Enable scheduling", "When schedulers found"],
            ["JmsConfig.java", "JMS configuration", "When JMS used"],
            ["KafkaConfig.java", "Kafka configuration", "When Kafka used"],
            ["SecurityConfig.java", "OAuth2/JWT security", "When OAuth used"],
            ["application.properties", "All settings", "Always"],
            ["Dockerfile", "Docker build definition", "Always"],
            ["docker-compose.yml", "Services (DB, MQ, etc.)", "Always"],
        ],
        col_widths=[1.8, 2.2, 2.2]
    ))

    story.append(Paragraph('12.3 Running the Generated Project', styles['SectionTitle']))
    story.append(Paragraph('Option A: With Maven (requires Java 17+ and Maven):', styles['SubSection']))
    story.append(make_code('cd my-spring-app\nmvn spring-boot:run'))
    story.append(Paragraph('Option B: With Docker:', styles['SubSection']))
    story.append(make_code('cd my-spring-app\ndocker compose up -d'))
    story.append(make_info_box(
        'The docker-compose.yml includes all required services (MySQL, RabbitMQ, Kafka, etc.) '
        'that your migrated app needs. Just run "docker compose up" and everything starts!', "tip"
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 13: API REFERENCE
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('13. API Reference', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))
    story.append(Paragraph(
        'The migrator exposes HTTP API endpoints you can use programmatically (curl, Postman, etc.).',
        styles['BodyText2']
    ))

    endpoints = [
        ("GET /api/health", "Check server health",
         "No body needed", '{"status": "ok", "env": "production"}'),
        ("GET /api/llm/providers", "Get all available AI providers and models",
         "No body needed", '{"anthropic": {"name": "...", "models": [...]}, ...}'),
        ("POST /api/migrate", "Main migration endpoint - accepts XML, returns Spring Boot project",
         '{"muleXmlFiles": [...], "projectName": "...",\n "llmConfig": {"enabled": true, ...}}',
         '{"success": true, "files": {...},\n "summary": {...}, "llmValidation": {...}}'),
        ("POST /api/validate", "Standalone AI code review",
         '{"files": {...}, "summary": {...},\n "llmConfig": {"provider": "...", ...}}',
         '{"success": true, "validation": {"overallScore": 7, ...}}'),
        ("POST /api/migrate/download", "Download generated project as ZIP",
         '{"files": {...}, "projectName": "my-app"}', "Binary ZIP file"),
        ("POST /api/convert/dataweave", "Convert DataWeave to Java",
         '{"script": "%dw 2.0\\n..."}',
         '{"success": true, "result": {"java_code": "...", ...}}'),
    ]

    for path, desc, req, resp in endpoints:
        story.append(Paragraph(path, styles['SubSection']))
        story.append(Paragraph(desc, styles['BodyText2']))
        story.append(Paragraph('<b>Request:</b>', styles['BodyText2']))
        story.append(make_code(req))
        story.append(Paragraph('<b>Response:</b>', styles['BodyText2']))
        story.append(make_code(resp))
        story.append(Spacer(1, 6))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 14: DEPLOYMENT
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('14. Production Deployment', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('14.1 Architecture', styles['SectionTitle']))
    story.append(make_table(
        ["Layer", "Technology", "Purpose"],
        [
            ["Reverse Proxy", "Nginx", "SSL, rate limiting, caching, security headers"],
            ["App Server", "Gunicorn", "Multi-worker Python server for concurrent requests"],
            ["Application", "Flask", "The actual migrator web application and API"],
        ],
        col_widths=[1.2, 1.3, 3.7]
    ))

    story.append(Paragraph('14.2 Gunicorn Settings', styles['SectionTitle']))
    story.append(make_table(
        ["Setting", "Default", "Description"],
        [
            ["workers", "CPU cores x 2 + 1", "Worker processes for requests"],
            ["worker_class", "gthread", "Thread-based (good for LLM I/O)"],
            ["threads", "4", "Threads per worker"],
            ["timeout", "120 seconds", "Max request time (LLM calls)"],
            ["bind", "0.0.0.0:5000", "Listen address and port"],
        ],
        col_widths=[1.3, 1.8, 3.1]
    ))

    story.append(Paragraph('14.3 Nginx Features', styles['SectionTitle']))
    for item in [
        '<b>Rate Limiting:</b> 2 req/s for migrations, 10 req/s for other API endpoints',
        '<b>Gzip Compression:</b> Level 6 for text, JSON, JavaScript, SVG',
        '<b>Security Headers:</b> X-Frame-Options, CSP, X-XSS-Protection, Referrer-Policy',
        '<b>Static Caching:</b> 7-day browser cache for CSS/JS files',
        '<b>SSL/TLS:</b> HTTPS template included (requires certificates)',
        '<b>Request Limit:</b> 50 MB maximum upload size',
    ]:
        story.append(bullet(item))

    story.append(Paragraph('14.4 Docker Commands', styles['SectionTitle']))
    story.append(make_table(
        ["Command", "What It Does"],
        [
            ["docker compose up -d", "Start the application"],
            ["docker compose --profile with-nginx up -d", "Start with Nginx proxy"],
            ["docker compose logs -f app", "View real-time logs"],
            ["docker compose down", "Stop all containers"],
            ["docker compose ps", "Show container status"],
        ],
        col_widths=[3.3, 2.9]
    ))

    story.append(Paragraph('14.5 Environment Variables', styles['SectionTitle']))
    story.append(make_table(
        ["Variable", "Default", "Description"],
        [
            ["FLASK_ENV", "production", "Flask environment mode"],
            ["PORT", "5000", "Application port"],
            ["SECRET_KEY", "(must set)", "Session security key"],
            ["CORS_ORIGINS", "*", "Allowed API origins"],
            ["GUNICORN_WORKERS", "4", "Worker processes"],
            ["ANTHROPIC_API_KEY", "(empty)", "Anthropic Claude API key"],
            ["OPENAI_API_KEY", "(empty)", "OpenAI GPT API key"],
            ["GOOGLE_API_KEY", "(empty)", "Google Gemini API key"],
            ["GROQ_API_KEY", "(empty)", "Groq API key (free)"],
        ],
        col_widths=[1.8, 1.0, 3.4]
    ))

    story.append(make_info_box(
        'API keys can be set in the .env file (for Docker) or entered directly in the UI. '
        'The UI never stores API keys on disk for security.', "important"
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 15: CONFIGURATION
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('15. Configuration Reference', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('15.1 Project Files', styles['SectionTitle']))
    story.append(make_table(
        ["File", "Location", "Purpose"],
        [
            ["app.py", "backend/", "Main Flask application with routes"],
            ["gunicorn.conf.py", "backend/", "Production server configuration"],
            ["requirements.txt", "backend/", "Python package dependencies"],
            ["parser.py", "backend/migrator/", "XML parser (30+ namespaces)"],
            ["connector_mapper.py", "backend/migrator/", "Connector to Spring mapper"],
            ["flow_converter.py", "backend/migrator/", "Flow to Java converter"],
            ["spring_generator.py", "backend/migrator/", "Project generator"],
            ["dataweave_converter.py", "backend/migrator/", "DataWeave to Java converter"],
            ["llm_validator.py", "backend/migrator/", "LLM integration (6 providers)"],
            ["index.html", "backend/templates/", "Web application HTML"],
            ["app.js", "backend/static/", "Frontend JavaScript"],
            ["style.css", "backend/static/", "UI stylesheet"],
            ["Dockerfile", "project root", "Docker image definition"],
            ["docker-compose.yml", "project root", "Container orchestration"],
            ["nginx.conf", "nginx/", "Nginx configuration"],
        ],
        col_widths=[1.7, 1.4, 3.1]
    ))

    story.append(Spacer(1, 10))
    story.append(make_info_box(
        'API keys are NEVER stored in localStorage, cookies, or anywhere on disk. '
        'You must re-enter your API key each session. This is a deliberate security measure.', "important"
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 16: TROUBLESHOOTING
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('16. Troubleshooting Guide', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))

    story.append(Paragraph('16.1 Installation Issues', styles['SectionTitle']))

    problems = [
        ("pip command not found",
         "On macOS, use pip3 instead of pip:",
         "pip3 install -r requirements.txt"),
        ("gunicorn command not found",
         "Use python3 -m gunicorn instead:",
         "python3 -m gunicorn -c gunicorn.conf.py app:app"),
        ("Address already in use (port 5000)",
         "Kill the existing process:",
         "kill $(lsof -t -i :5000)"),
        ("lxml installation fails",
         "Install system libraries first:",
         "brew install libxml2 libxslt  # macOS"),
    ]
    for title, desc, solution in problems:
        story.append(Paragraph(f'<b><font color="#C62828">{title}</font></b>', styles['BodyText2']))
        story.append(Paragraph(desc, styles['BodyText2']))
        story.append(make_code(solution))
        story.append(Spacer(1, 4))

    story.append(Paragraph('16.2 Migration Issues', styles['SectionTitle']))
    story.append(make_table(
        ["Issue", "Cause", "Solution"],
        [
            ["Invalid XML error", "XML syntax errors", "Validate XML first"],
            ["Missing connectors", "Namespace not declared", "Check xmlns declarations"],
            ["Empty generated files", "No flows in XML", "Verify flow elements exist"],
            ["DataWeave warnings", "Complex patterns", "Review and adjust manually"],
            ["Duplicate flow warnings", "Same name in files", "Use unique flow names"],
        ],
        col_widths=[1.5, 1.8, 2.9]
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph('16.3 LLM Validation Issues', styles['SectionTitle']))
    story.append(make_table(
        ["Issue", "Cause", "Solution"],
        [
            ["Missing API key", "No key provided", "Enter key in AI Validation tab"],
            ["Connection failed", "Invalid key or network", "Verify key, check internet"],
            ["Takes too long", "Large project/slow model", "Use faster model (Groq, Gemini Flash)"],
            ["Module not installed", "LLM library missing", "pip3 install anthropic openai"],
        ],
        col_widths=[1.5, 1.8, 2.9]
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # CHAPTER 17: GLOSSARY
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('17. Glossary', styles['ChapterTitle']))
    story.append(HLine(6.5 * inch, PRIMARY, 2))
    story.append(Paragraph(
        'Every technical term used in this documentation, explained in plain English:',
        styles['BodyText2']
    ))
    story.append(Spacer(1, 6))

    glossary = [
        ("API", "A way for two programs to talk to each other over the internet."),
        ("API Key", "A secret password that lets your application use a service (like an AI model)."),
        ("Annotation", "In Java, a marker starting with @ that adds behavior (e.g., @GetMapping)."),
        ("Container", "A portable package containing your application and everything it needs to run."),
        ("CORS", "Cross-Origin Resource Sharing. Controls which websites can access your API."),
        ("DataWeave", "MuleSoft's proprietary language for transforming data between formats."),
        ("Dependency", "A library your project needs to work (listed in pom.xml for Java)."),
        ("Docker", "A platform for building and running containers (packaged applications)."),
        ("Docker Compose", "A tool for running multi-container applications with one command."),
        ("Endpoint", "A specific URL path in an API (e.g., /api/customers)."),
        ("Flask", "A lightweight Python web framework used to build the migrator."),
        ("Flow", "In MuleSoft, a sequence of steps triggered by an event."),
        ("Gunicorn", "A production-grade Python web server for concurrent requests."),
        ("HTTP", "The standard protocol for web communication."),
        ("JMS", "Java Message Service. Standard for sending messages between apps."),
        ("JSON", "A lightweight text format for data exchange."),
        ("Kafka", "A distributed event streaming platform for high-throughput messaging."),
        ("LLM", "Large Language Model. An AI system that understands and generates text/code."),
        ("Maven", "A build tool for Java projects that manages dependencies."),
        ("Nginx", "A high-performance web server used as a reverse proxy."),
        ("OAuth", "An authentication standard for secure access delegation."),
        ("pom.xml", "Maven build file listing all project dependencies."),
        ("REST", "A standard architecture for building web APIs."),
        ("Spring Boot", "Popular Java framework for production-ready web applications."),
        ("SSL/TLS", "Security protocols that encrypt data in transit (HTTPS)."),
        ("XML", "Extensible Markup Language. Text format used by MuleSoft."),
        ("ZIP", "Compressed file format that bundles multiple files together."),
    ]

    for term, definition in glossary:
        story.append(Paragraph(f'<b>{term}</b>', styles['GlossaryTerm']))
        story.append(Paragraph(definition, styles['GlossaryDef']))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # END PAGE
    # ════════════════════════════════════════════════════════════
    story.append(Spacer(1, 2.5 * inch))

    end_content = []
    end_content.append(Spacer(1, 12))
    end_content.append(Paragraph('End of Documentation', ParagraphStyle(
        'EndTitle', parent=styles['DocTitle'], fontSize=22
    )))
    end_content.append(Spacer(1, 6))
    end_content.append(Paragraph('MuleSoft to Spring Boot Migrator v1.0', styles['DocSubTitle']))
    end_content.append(Paragraph('March 2026', styles['DocSubTitle']))
    end_content.append(Spacer(1, 12))

    end_table = Table([[end_content]], colWidths=[6.5 * inch])
    end_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0, PRIMARY),
    ]))
    story.append(end_table)

    # ── Build the document ──
    doc.build(story, onFirstPage=cover_page_template, onLaterPages=header_footer)
    print(f"PDF document saved: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    path = create_pdf()
    print(f"\nPDF created successfully at:\n{path}")
