#!/usr/bin/env python3
"""
Generate a comprehensive line-by-line teaching PDF for the MuleSoft to Spring Boot Migrator.
"""
from fpdf import FPDF
import os

class TeachingPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "MuleSoft to Spring Boot Migrator - Complete Line-by-Line Code Guide", align="C")
        self.ln(4)
        self.set_draw_color(100, 102, 241)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(99, 102, 241)
        self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(99, 102, 241)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 41, 59)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def subsection_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(51, 65, 85)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def code_block(self, code, language=""):
        self.set_fill_color(245, 245, 250)
        self.set_font("Courier", "", 8.5)
        self.set_text_color(30, 30, 30)
        lines = code.split("\n")
        for line in lines:
            safe = line.replace("\t", "    ")
            # Truncate very long lines
            if len(safe) > 110:
                safe = safe[:107] + "..."
            self.cell(0, 4.5, f"  {safe}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)

    def explain(self, text):
        """Explanation text with a left border"""
        self.set_draw_color(99, 102, 241)
        x = self.get_x()
        y = self.get_y()
        self.set_font("Helvetica", "I", 9.5)
        self.set_text_color(71, 85, 105)
        self.set_x(x + 5)
        self.multi_cell(180, 5, text)
        # Draw left border
        self.line(x + 2, y, x + 2, self.get_y())
        self.ln(3)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 41, 59)
        x = self.get_x()
        self.cell(5, 5.5, "-")
        self.multi_cell(180, 5.5, text)
        self.ln(1)

    def key_concept(self, title, description):
        self.set_fill_color(240, 240, 255)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(99, 102, 241)
        self.cell(0, 7, f"  KEY CONCEPT: {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 5, f"  {description}")
        self.ln(3)


def generate_pdf():
    pdf = TeachingPDF()
    pdf.alias_nb_pages()
    pdf.set_title("MuleSoft to Spring Boot Migrator - Complete Code Guide")
    pdf.set_author("Migration Tool Documentation")

    # ================================================================
    # COVER PAGE
    # ================================================================
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 15, "MuleSoft to Spring Boot", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 15, "Migration Tool", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 10, "Complete Line-by-Line Code Teaching Guide", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 12)
    pdf.cell(0, 8, "From Zero Experience to Full Understanding", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(0, 7, "This guide explains every single file, every function, and every line of code", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "in the MuleSoft to Spring Boot Migrator application.", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "No prior programming experience required.", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(30)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 7, "Technology Stack: Python, Flask, Gunicorn, HTML/CSS/JS, Docker, Nginx", align="C", new_x="LMARGIN", new_y="NEXT")

    # ================================================================
    # TABLE OF CONTENTS
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("Table of Contents")
    toc = [
        ("1", "Introduction - What This Application Does"),
        ("2", "How The Application Works (Big Picture)"),
        ("3", "Project File Structure"),
        ("4", "Chapter 1: app.py - The Main Application"),
        ("5", "Chapter 2: parser.py - Reading MuleSoft XML"),
        ("6", "Chapter 3: dataweave_converter.py - DataWeave to Java"),
        ("7", "Chapter 4: connector_mapper.py - Mapping Connectors"),
        ("8", "Chapter 5: flow_converter.py - Converting Flows"),
        ("9", "Chapter 6: spring_generator.py - Building Spring Boot Project"),
        ("10", "Chapter 7: llm_validator.py - AI Code Validation"),
        ("11", "Chapter 8: gunicorn.conf.py - Production Server"),
        ("12", "Chapter 9: Frontend (HTML, CSS, JavaScript)"),
        ("13", "Chapter 10: Docker & Nginx - Deployment"),
        ("14", "How To Run The Application"),
        ("15", "Glossary of Terms"),
    ]
    for num, title in toc:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(10, 7, num)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")

    # ================================================================
    # INTRODUCTION
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("1. Introduction - What This Application Does")

    pdf.body_text(
        "MuleSoft is a popular integration platform used by big companies to connect different software systems "
        "together. It uses XML files to define how data flows between systems. Spring Boot is a Java framework "
        "used to build web applications and microservices.\n\n"
        "This tool AUTOMATICALLY converts MuleSoft XML configurations into a complete, runnable Spring Boot "
        "Java project. Think of it like a translator that converts one programming language into another."
    )

    pdf.section_title("What Problem Does It Solve?")
    pdf.body_text(
        "When a company decides to move from MuleSoft to Spring Boot, developers normally have to manually "
        "rewrite thousands of lines of code. This tool automates 80-90% of that work, saving weeks or months "
        "of development time."
    )

    pdf.section_title("What Does The Tool Do Step By Step?")
    pdf.bullet("STEP 1 - PARSE: Reads MuleSoft XML files and understands their structure (what APIs, databases, message queues are used)")
    pdf.bullet("STEP 2 - CONVERT DATAWEAVE: Translates MuleSoft's data transformation language (DataWeave) into Java code")
    pdf.bullet("STEP 3 - MAP CONNECTORS: Figures out what Spring Boot libraries (dependencies) are needed to replace each MuleSoft connector")
    pdf.bullet("STEP 4 - CONVERT FLOWS: Turns MuleSoft flow definitions into Spring Boot Java classes (Controllers, Services, etc.)")
    pdf.bullet("STEP 5 - GENERATE PROJECT: Creates a complete Spring Boot project with pom.xml, config files, Docker setup, and all Java classes")
    pdf.bullet("STEP 6 - AI VALIDATION (Optional): Sends the generated code to an AI model (like ChatGPT or Claude) for review")

    pdf.section_title("Technologies Used (Explained Simply)")
    pdf.key_concept("Python", "The programming language the tool is written in. Python is known for being easy to read and write.")
    pdf.key_concept("Flask", "A lightweight Python web framework. It lets us create a website/API with just a few lines of code. Think of it as the 'skeleton' that handles web requests.")
    pdf.key_concept("Gunicorn", "A production-grade web server for Python. Flask's built-in server is only for testing. Gunicorn can handle many users at once safely.")
    pdf.key_concept("HTML/CSS/JavaScript", "The frontend (what users see in their browser). HTML = structure, CSS = styling, JavaScript = interactivity.")
    pdf.key_concept("Docker", "A tool that packages the application into a 'container' - like a box that includes everything needed to run it on any computer.")
    pdf.key_concept("Nginx", "A reverse proxy server that sits in front of Gunicorn. It handles SSL, caching, rate limiting, and serves static files efficiently.")
    pdf.key_concept("lxml", "A Python library for parsing XML files. MuleSoft configurations are written in XML, so we need this to read them.")

    # ================================================================
    # BIG PICTURE
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("2. How The Application Works (Big Picture)")

    pdf.section_title("The Request Flow")
    pdf.body_text(
        "When a user clicks 'Migrate' in the web browser, here is exactly what happens:"
    )
    pdf.code_block(
        "User's Browser (JavaScript)\n"
        "    |\n"
        "    |-- HTTP POST /api/migrate (sends XML content as JSON)\n"
        "    |\n"
        "    v\n"
        "Nginx (if deployed with Docker)\n"
        "    |-- Rate limits the request\n"
        "    |-- Forwards to Gunicorn\n"
        "    |\n"
        "    v\n"
        "Gunicorn (Production Server)\n"
        "    |-- Picks a worker thread to handle the request\n"
        "    |\n"
        "    v\n"
        "Flask app.py -> migrate() function\n"
        "    |\n"
        "    |-- 1. MuleSoftParser.parse(xml)       -> structured data\n"
        "    |-- 2. DataWeaveConverter.convert()     -> Java code\n"
        "    |-- 3. ConnectorMapper.map_connectors() -> dependencies\n"
        "    |-- 4. FlowConverter.convert()          -> Java source files\n"
        "    |-- 5. SpringBootGenerator.generate()   -> full project\n"
        "    |-- 6. (Optional) LLM validate_code()   -> AI review\n"
        "    |\n"
        "    v\n"
        "JSON Response -> Browser renders results"
    )

    pdf.section_title("The Pipeline Pattern")
    pdf.body_text(
        "This application uses a 'pipeline' pattern - data flows through a series of processing stages, "
        "where each stage transforms the data and passes it to the next. This is a very common pattern "
        "in software engineering. Each stage is a separate Python module (file), making the code organized "
        "and easy to maintain."
    )

    # ================================================================
    # PROJECT STRUCTURE
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("3. Project File Structure")

    pdf.code_block(
        "mulesoft-to-springboot-migrator/\n"
        "|\n"
        "|-- backend/                      # All server-side code\n"
        "|   |-- app.py                    # Main Flask application (entry point)\n"
        "|   |-- gunicorn.conf.py          # Production server configuration\n"
        "|   |-- requirements.txt          # Python package dependencies\n"
        "|   |\n"
        "|   |-- migrator/                 # Core migration logic (Python package)\n"
        "|   |   |-- __init__.py           # Makes 'migrator' a package, exports classes\n"
        "|   |   |-- parser.py             # Reads & parses MuleSoft XML files\n"
        "|   |   |-- dataweave_converter.py # Converts DataWeave scripts to Java\n"
        "|   |   |-- connector_mapper.py   # Maps MuleSoft connectors to Spring deps\n"
        "|   |   |-- flow_converter.py     # Converts Mule flows to Spring Java code\n"
        "|   |   |-- spring_generator.py   # Generates complete Spring Boot project\n"
        "|   |   |-- llm_validator.py      # AI-powered code validation\n"
        "|   |\n"
        "|   |-- templates/                # HTML templates\n"
        "|   |   |-- index.html            # The single-page web interface\n"
        "|   |\n"
        "|   |-- static/                   # Static files served to browser\n"
        "|       |-- app.js                # Frontend JavaScript logic\n"
        "|       |-- style.css             # All visual styling\n"
        "|\n"
        "|-- Dockerfile                    # Instructions to build Docker image\n"
        "|-- docker-compose.yml            # Multi-container Docker setup\n"
        "|-- nginx/nginx.conf              # Nginx reverse proxy configuration\n"
        "|-- .env.example                  # Template for environment variables\n"
        "|-- .dockerignore                 # Files to exclude from Docker"
    )

    pdf.body_text(
        "The 'backend/' folder contains everything. The 'migrator/' subfolder is a Python package "
        "(indicated by __init__.py) containing the 6 core modules that do the actual migration work."
    )

    # ================================================================
    # CHAPTER 1: app.py
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("4. Chapter 1: app.py - The Main Application")

    pdf.body_text(
        "This is the ENTRY POINT of the entire application. When someone visits the website or sends an API "
        "request, this file handles it. It's like the 'front desk' of a hotel - it receives all requests and "
        "directs them to the right place."
    )

    pdf.section_title("Lines 1-12: Documentation String (Docstring)")
    pdf.code_block(
        '"""\n'
        "MuleSoft to Spring Boot Migration Tool - Main Flask Application\n"
        "\n"
        "Features:\n"
        "  - Multi-XML input: accepts multiple MuleSoft XML files...\n"
        "  - LLM-powered code validation\n"
        "  - DataWeave to Java conversion\n"
        "  - Complete Spring Boot 3.2 project generation\n"
        "\n"
        "Production:\n"
        "  gunicorn -w 4 -b 0.0.0.0:5000 app:app\n"
        '"""'
    )
    pdf.explain(
        "A docstring (triple quotes) at the top of a file explains what the file does. "
        "This is documentation for other developers. Python ignores it during execution."
    )

    pdf.section_title("Lines 13-30: Import Statements")
    pdf.code_block(
        "import os\n"
        "import json\n"
        "import logging\n"
        "import tempfile\n"
        "import zipfile\n"
        "import io\n"
        "from flask import Flask, request, jsonify, send_file, render_template\n"
        "from flask_cors import CORS\n"
        "\n"
        "from migrator.parser import MuleSoftParser\n"
        "from migrator.flow_converter import FlowConverter\n"
        "from migrator.dataweave_converter import DataWeaveConverter\n"
        "from migrator.connector_mapper import ConnectorMapper\n"
        "from migrator.spring_generator import SpringBootGenerator\n"
        "from migrator.llm_validator import (\n"
        "    get_available_providers,\n"
        "    validate_code,\n"
        ")"
    )
    pdf.explain(
        "IMPORTS bring in tools (libraries) we need:\n"
        "- os: Read environment variables (like passwords, config)\n"
        "- json: Convert Python objects to/from JSON format\n"
        "- logging: Write log messages for debugging\n"
        "- zipfile, io: Create ZIP files in memory (for downloading projects)\n"
        "- Flask, request, jsonify: The web framework and its tools\n"
        "- CORS: Allows the API to be called from different domains\n"
        "- migrator.*: Our own modules that do the actual migration work"
    )

    pdf.section_title("Lines 35-66: The App Factory Pattern")
    pdf.code_block(
        "def create_app():\n"
        '    """Application factory - returns a configured Flask app."""\n'
        '    application = Flask(__name__, static_folder="static",\n'
        '                       template_folder="templates")\n'
        "\n"
        '    env = os.environ.get("FLASK_ENV", "production")\n'
        "    application.config.update(\n"
        "        ENV=env,\n"
        '        DEBUG=(env == "development"),\n'
        '        SECRET_KEY=os.environ.get("SECRET_KEY", os.urandom(32).hex()),\n'
        "        MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50 MB\n"
        "        JSON_SORT_KEYS=False,\n"
        "    )\n"
        "\n"
        '    allowed_origins = os.environ.get("CORS_ORIGINS", "*")\n'
        '    CORS(application, origins=allowed_origins.split(","))\n'
        "\n"
        "    _register_routes(application)\n"
        "    return application"
    )
    pdf.key_concept("App Factory Pattern",
        "Instead of creating the Flask app directly as a global variable, we use a function "
        "(create_app) that builds and returns it. This is a best practice because: "
        "(1) It makes testing easier - you can create multiple apps with different configs. "
        "(2) It avoids circular import problems. "
        "(3) It's the pattern recommended by Flask's official documentation."
    )
    pdf.explain(
        "Line by line:\n"
        "- Flask(__name__): Creates a new Flask web app. __name__ tells Flask where to find files.\n"
        "- static_folder='static': Where CSS/JS files live\n"
        "- template_folder='templates': Where HTML files live\n"
        "- os.environ.get('FLASK_ENV', 'production'): Read FLASK_ENV from environment, default to 'production'\n"
        "- SECRET_KEY: A random key used to secure cookies/sessions. os.urandom(32) generates 32 random bytes.\n"
        "- MAX_CONTENT_LENGTH: Maximum upload size (50 MB)\n"
        "- CORS: Cross-Origin Resource Sharing - allows the frontend to call our API"
    )

    pdf.section_title("Lines 69-84: Route Registration")
    pdf.code_block(
        "def _register_routes(application):\n"
        '    @application.route("/")\n'
        "    def index():\n"
        '        return render_template("index.html")\n'
        "\n"
        '    @application.route("/api/health", methods=["GET"])\n'
        "    def health():\n"
        '        return jsonify({"status": "ok", "env": application.config["ENV"]})\n'
        "\n"
        '    @application.route("/api/llm/providers", methods=["GET"])\n'
        "    def llm_providers():\n"
        "        return jsonify(get_available_providers())"
    )
    pdf.explain(
        "ROUTES map URLs to functions:\n"
        "- @application.route('/'): When someone visits the homepage, show index.html\n"
        "- @application.route('/api/health'): A health check endpoint - monitoring tools use this to verify the app is running\n"
        "- @application.route('/api/llm/providers'): Returns the list of AI models available for code validation\n\n"
        "The @ symbol is a 'decorator' - it modifies the function below it. Here, it tells Flask 'when someone visits this URL, run this function.'"
    )

    pdf.section_title("Lines 87-224: The Main Migration Endpoint")
    pdf.code_block(
        '@application.route("/api/migrate", methods=["POST"])\n'
        "def migrate():\n"
        "    data = request.get_json()\n"
        "    if not data:\n"
        '        return jsonify({"error": "No data provided"}), 400\n'
        "\n"
        '    xml_files = data.get("muleXmlFiles", [])\n'
        '    single_xml = data.get("muleXml", "")\n'
        "\n"
        "    if not xml_files and single_xml.strip():\n"
        '        xml_files = [{"name": "main.xml", "content": single_xml}]'
    )
    pdf.explain(
        "This is the MOST IMPORTANT endpoint - it does the actual migration:\n"
        "- methods=['POST']: Only accepts POST requests (sending data to the server)\n"
        "- request.get_json(): Extracts JSON data from the request body\n"
        "- 400 status code: Means 'Bad Request' - the client sent invalid data\n"
        "- muleXmlFiles: An array of {name, content} objects (multi-file support)\n"
        "- muleXml: Legacy single-XML support for backward compatibility\n"
        "- The if/else converts single XML into the multi-file format"
    )

    pdf.subsection_title("The Migration Pipeline (inside migrate())")
    pdf.code_block(
        "parser = MuleSoftParser()\n"
        "parsed_list = []\n"
        "for xml_file in xml_files:\n"
        "    content = xml_file.get('content', '').strip()\n"
        "    name = xml_file.get('name', 'unknown.xml')\n"
        "    parsed_list.append(parser.parse(content))\n"
        "\n"
        "if len(parsed_list) == 1:\n"
        "    parsed = parsed_list[0]\n"
        "else:\n"
        "    parsed = _merge_parsed_results(parsed_list)\n"
        "\n"
        "dw_converter = DataWeaveConverter()\n"
        "connector_mapper = ConnectorMapper()\n"
        "connector_info = connector_mapper.map_connectors(parsed)\n"
        "\n"
        "flow_converter = FlowConverter(dw_converter, connector_mapper)\n"
        "spring_files = flow_converter.convert(parsed, converted_dw)\n"
        "\n"
        "generator = SpringBootGenerator(\n"
        "    project_name=project_name,\n"
        "    group_id=group_id,\n"
        "    java_version=java_version,\n"
        ")\n"
        "project_files = generator.generate(spring_files, connector_info, parsed)"
    )
    pdf.explain(
        "This is the pipeline in action:\n"
        "1. Create a parser and parse each XML file into structured Python dictionaries\n"
        "2. If multiple files, merge them (deduplicating by flow name)\n"
        "3. Convert any DataWeave scripts to Java\n"
        "4. Map connectors to Spring Boot dependencies\n"
        "5. Convert flows to Java source code\n"
        "6. Generate the complete project structure\n\n"
        "Each step takes the output of the previous step as input."
    )

    pdf.section_title("Lines 262-296: Download & DataWeave Endpoints")
    pdf.code_block(
        '@application.route("/api/migrate/download", methods=["POST"])\n'
        "def download_project():\n"
        "    buffer = io.BytesIO()\n"
        '    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:\n'
        "        for filepath, content in files.items():\n"
        '            zf.writestr(f"{project_name}/{filepath}", content)\n'
        "    buffer.seek(0)\n"
        '    return send_file(buffer, mimetype="application/zip",\n'
        '                     as_attachment=True, download_name=f"{project_name}.zip")'
    )
    pdf.explain(
        "This creates a ZIP file IN MEMORY (not on disk) containing all generated files:\n"
        "- io.BytesIO(): Creates a file-like object in RAM\n"
        "- zipfile.ZipFile: Opens it as a ZIP file for writing\n"
        "- ZIP_DEFLATED: Compresses the content\n"
        "- buffer.seek(0): Rewinds to the beginning so Flask can read it\n"
        "- send_file: Sends the ZIP as a downloadable file to the browser"
    )

    pdf.section_title("Lines 302-383: Helper Functions")
    pdf.code_block(
        "def _merge_parsed_results(parsed_list: list) -> dict:\n"
        "    merged = {\n"
        '        "global_configs": [], "flows": [], "sub_flows": [],\n'
        '        "connectors": set(), "warnings": [],\n'
        "    }\n"
        "    seen_flow_names = set()\n"
        "    for parsed in parsed_list:\n"
        "        for flow in parsed.get('flows', []):\n"
        "            flow_name = flow.get('name', '')\n"
        "            if flow_name not in seen_flow_names:\n"
        "                seen_flow_names.add(flow_name)\n"
        "                merged['flows'].append(flow)\n"
        "            else:\n"
        "                merged['warnings'].append(\n"
        "                    f\"Duplicate flow '{flow_name}'...\")\n"
        "    return merged"
    )
    pdf.explain(
        "When multiple XML files are uploaded, we need to merge them:\n"
        "- A Python 'set' stores unique values - perfect for tracking which flow names we've already seen\n"
        "- If two files define a flow with the same name, we keep the first one and add a warning\n"
        "- All connectors are combined using set union (automatically removes duplicates)\n"
        "- Properties are merged with later values overwriting earlier ones"
    )

    pdf.section_title("Lines 386-394: App Startup")
    pdf.code_block(
        "app = create_app()\n"
        "\n"
        'if __name__ == "__main__":\n'
        '    port = int(os.environ.get("PORT", 5000))\n'
        '    debug = os.environ.get("FLASK_ENV", "production") == "development"\n'
        "    app.run(host='0.0.0.0', port=port, debug=debug)"
    )
    pdf.explain(
        "- app = create_app(): Creates the Flask app at module level. Gunicorn needs this.\n"
        "- if __name__ == '__main__': This code only runs when you execute 'python app.py' directly.\n"
        "  When Gunicorn imports the file, __name__ is 'app', not '__main__', so this block is skipped.\n"
        "- host='0.0.0.0': Listen on ALL network interfaces (not just localhost)\n"
        "- This is the development mode fallback. In production, Gunicorn handles everything."
    )

    # ================================================================
    # CHAPTER 2: parser.py
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("5. Chapter 2: parser.py - Reading MuleSoft XML")

    pdf.body_text(
        "This is the FIRST stage of the pipeline. Its job is to read MuleSoft XML configuration files "
        "and convert them into structured Python dictionaries that the rest of the application can work with. "
        "Think of it as a translator that reads a foreign document and creates a structured summary."
    )

    pdf.section_title("Lines 1-81: Namespaces and Constants")
    pdf.code_block(
        "NAMESPACES = {\n"
        '    "mule":  "http://www.mulesoft.org/schema/mule/core",\n'
        '    "http":  "http://www.mulesoft.org/schema/mule/http",\n'
        '    "db":    "http://www.mulesoft.org/schema/mule/db",\n'
        '    "jms":   "http://www.mulesoft.org/schema/mule/jms",\n'
        '    "kafka": "http://www.mulesoft.org/schema/mule/kafka",\n'
        '    "file":  "http://www.mulesoft.org/schema/mule/file",\n'
        "    ... # 30+ namespaces total\n"
        "}"
    )
    pdf.key_concept("XML Namespaces",
        "XML namespaces are like last names for XML tags. Just as two people named 'John' can be "
        "distinguished by their last names (John Smith vs John Doe), XML tags with the same name "
        "from different systems are distinguished by namespaces. For example, <http:listener> and "
        "<file:listener> are both 'listener' but in different namespaces. The NAMESPACES dictionary "
        "maps short prefixes (like 'http') to full namespace URLs."
    )

    pdf.section_title("Lines 108-141: The Main Parse Method")
    pdf.code_block(
        "class MuleSoftParser:\n"
        "    def parse(self, xml_content: str) -> dict:\n"
        "        root = etree.fromstring(xml_content.encode('utf-8'))\n"
        "        ns_map = self._build_ns_map(root)\n"
        "        return {\n"
        '            "global_configs":    self._parse_global_configs(root, ns_map),\n'
        '            "flows":             self._parse_flows(root, ns_map),\n'
        '            "sub_flows":         self._parse_sub_flows(root, ns_map),\n'
        '            "error_handlers":    self._parse_error_handlers(root, ns_map),\n'
        '            "connectors":        self._detect_connectors(root, ns_map),\n'
        '            "batch_jobs":        self._parse_batch_jobs(root, ns_map),\n'
        "            ...\n"
        "        }"
    )
    pdf.explain(
        "- etree.fromstring(): Parses the XML string into a tree structure (like a family tree of elements)\n"
        "- The 'root' is the top-level element of the XML tree\n"
        "- _build_ns_map: Combines namespaces from the actual XML with our known defaults\n"
        "- The return dictionary has a key for each type of thing we extract from the XML\n"
        "- Each _parse_* method is responsible for extracting one type of information"
    )

    pdf.section_title("Lines 155-261: Parsing Global Configurations")
    pdf.body_text(
        "This method loops through every top-level element in the XML and identifies configuration blocks:"
    )
    pdf.code_block(
        "def _parse_global_configs(self, root, ns_map):\n"
        "    configs = []\n"
        "    for elem in root:\n"
        "        tag = self._local_tag(elem)   # e.g., 'listener-config'\n"
        "        ns = self._get_ns_prefix(elem) # e.g., 'http'\n"
        "\n"
        '        if tag == "listener-config" and ns in ("http", ""):\n'
        "            config = self._make_http_listener_config(elem)\n"
        '        elif tag == "config" and ns == "db":\n'
        "            config = self._make_db_config(elem)\n"
        "        # ... 15+ more connector types\n"
        "    return configs"
    )
    pdf.explain(
        "Pattern Recognition: For each XML element, we check its tag name AND namespace to determine what type it is.\n"
        "This is like sorting mail - you look at the label to decide which mailbox it goes into.\n"
        "Each connector type (HTTP, Database, JMS, Kafka, etc.) has its own parsing logic because they have different attributes."
    )

    pdf.section_title("Lines 362-431: Parsing Flows")
    pdf.body_text(
        "A 'flow' in MuleSoft is a sequence of processing steps. Think of it like a recipe - "
        "it has a trigger (when to start), steps (what to do), and error handling (what if something goes wrong)."
    )
    pdf.code_block(
        "def _parse_flow_element(self, flow_elem, ns_map, is_sub_flow=False):\n"
        "    flow_data = {\n"
        '        "name": flow_elem.get("name", ""),\n'
        '        "source": None,        # What triggers this flow\n'
        '        "processors": [],      # Steps to execute\n'
        '        "error_handler": None,  # Error handling\n'
        "    }\n"
        "    for child in flow_elem:\n"
        "        # First element might be a source (trigger)\n"
        "        if flow_data['source'] is None:\n"
        "            source = self._try_parse_source(child, ...)\n"
        "            if source:\n"
        "                flow_data['source'] = source\n"
        "                continue\n"
        "        # Everything else is a processor\n"
        "        flow_data['processors'].append(processor)"
    )
    pdf.explain(
        "For each flow:\n"
        "- 'source' is the first element (usually an HTTP listener or scheduler that triggers the flow)\n"
        "- 'processors' are all subsequent elements (the actual work steps)\n"
        "- 'error_handler' defines what happens when something goes wrong\n"
        "The parser identifies 15+ different source types (HTTP, JMS, Kafka, File, Email, etc.)"
    )

    # ================================================================
    # CHAPTER 3: DataWeave
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("6. Chapter 3: dataweave_converter.py - DataWeave to Java")

    pdf.body_text(
        "DataWeave is MuleSoft's proprietary data transformation language. It's used to transform data "
        "from one format to another (e.g., change field names, filter arrays, convert types). "
        "This module converts DataWeave scripts into equivalent Java code using regex-based pattern matching."
    )

    pdf.section_title("The Converter Class Structure")
    pdf.code_block(
        "class DataWeaveConverter:\n"
        "    def __init__(self):\n"
        "        self.warnings = []         # Things that couldn't be converted\n"
        "        self.imports_needed = set() # Java imports needed\n"
        "        self._vars = {}            # DataWeave variable declarations\n"
        "        self._functions = {}       # DataWeave function declarations\n"
        "\n"
        "    def convert(self, dw_script: str) -> dict:\n"
        "        header_info = self._parse_header(script)\n"
        "        body = self._strip_header(script)\n"
        "        java_code = self._convert_body(body)\n"
        '        return {"java_code": java_code, "imports": ..., "warnings": ...}'
    )
    pdf.explain(
        "A DataWeave script has two parts:\n"
        "1. HEADER: Lines before '---' that declare output type, variables, and functions\n"
        "   Example: '%dw 2.0' and 'output application/json'\n"
        "2. BODY: Lines after '---' that contain the actual transformation\n"
        "   Example: 'payload map (item) -> { name: item.firstName }'\n\n"
        "The converter processes the header first (extracting vars/functions), then converts the body."
    )

    pdf.section_title("Expression Conversion - The Heart of the Converter")
    pdf.body_text(
        "The _convert_expression method uses regular expressions (regex) to find DataWeave patterns "
        "and replace them with Java equivalents:"
    )
    pdf.code_block(
        "# DataWeave: payload.field.subField\n"
        "# Java:      ((Map)payload.get(\"field\")).get(\"subField\")\n"
        "expr = re.sub(r'\\bpayload\\.(\\w+)\\.(\\w+)',\n"
        '    lambda m: f\'((Map)payload.get("{m.group(1)}")).get("{m.group(2)}")\',\n'
        "    expr)\n"
        "\n"
        "# DataWeave: attributes.queryParams.id\n"
        "# Java:      request.getParameter(\"id\")\n"
        "expr = re.sub(r'\\battributes\\.queryParams\\.(\\w+)',\n"
        "    r'request.getParameter(\"\\1\")', expr)\n"
        "\n"
        "# DataWeave: upper(name)\n"
        "# Java:      name.toUpperCase()\n"
        "expr = re.sub(r'\\bupper\\(([^)]+)\\)', r'\\1.toUpperCase()', expr)\n"
        "\n"
        "# DataWeave: items splitBy \",\"\n"
        '# Java:      items.split(",")\n'
        "expr = re.sub(r'(\\w+)\\s+splitBy\\s+\"([^\"]+)\"',\n"
        "    r'\\1.split(\"\\2\")', expr)"
    )
    pdf.key_concept("Regular Expressions (Regex)",
        "Regex is a pattern-matching language used to find and replace text. "
        "\\b means 'word boundary', \\w+ means 'one or more word characters', "
        "([^)]+) means 'capture everything that's not a closing parenthesis'. "
        "re.sub(pattern, replacement, text) finds all matches and replaces them."
    )

    pdf.section_title("Body Conversion - Handling Complex Structures")
    pdf.code_block(
        "def _convert_body(self, script):\n"
        "    if s.startswith('{'):    return self._convert_object_mapping(s)\n"
        "    if s.startswith('['):    return self._convert_array_literal(s)\n"
        "    if 'map' in s:          return self._convert_map_operation(s)\n"
        "    if 'filter' in s:       return self._convert_filter_operation(s)\n"
        "    if 'reduce' in s:       return self._convert_reduce_operation(s)\n"
        "    if 'groupBy' in s:      return self._convert_groupby_operation(s)\n"
        "    if 'orderBy' in s:      return self._convert_orderby_operation(s)\n"
        "    if 'if' in s:           return self._convert_conditional(s)"
    )
    pdf.explain(
        "The body converter detects what kind of DataWeave operation is being used and calls the "
        "appropriate conversion method. Each operation (map, filter, reduce, etc.) has a Java Stream "
        "API equivalent:\n"
        "- DataWeave 'map' -> Java .stream().map().collect()\n"
        "- DataWeave 'filter' -> Java .stream().filter().collect()\n"
        "- DataWeave 'reduce' -> Java .stream().reduce()\n"
        "- DataWeave 'groupBy' -> Java Collectors.groupingBy()\n"
        "- DataWeave '{key: value}' -> Java Map with LinkedHashMap"
    )

    # ================================================================
    # CHAPTER 4: Connector Mapper
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("7. Chapter 4: connector_mapper.py - Mapping Connectors")

    pdf.body_text(
        "This module is essentially a lookup table that answers: 'For each MuleSoft connector, "
        "what Spring Boot libraries do I need?' It also maps HTTP methods, error types, and generates "
        "Spring configuration properties."
    )

    pdf.section_title("The Dependency Map")
    pdf.code_block(
        "CONNECTOR_DEPENDENCY_MAP = {\n"
        '    "http": [\n'
        '        {"groupId": "org.springframework.boot",\n'
        '         "artifactId": "spring-boot-starter-web"},\n'
        "    ],\n"
        '    "database": [\n'
        '        {"groupId": "org.springframework.boot",\n'
        '         "artifactId": "spring-boot-starter-data-jpa"},\n'
        "    ],\n"
        '    "kafka": [\n'
        '        {"groupId": "org.springframework.kafka",\n'
        '         "artifactId": "spring-kafka"},\n'
        "    ],\n"
        "    # ... 25+ more mappings\n"
        "}"
    )
    pdf.explain(
        "Each entry maps a MuleSoft connector name to a list of Maven dependencies needed in Spring Boot.\n"
        "Maven is Java's package manager (like pip for Python). Dependencies are identified by:\n"
        "- groupId: The organization (e.g., org.springframework.boot)\n"
        "- artifactId: The specific library (e.g., spring-boot-starter-web)\n"
        "These get added to pom.xml, which tells Maven what to download."
    )

    pdf.section_title("The Error Type Map")
    pdf.code_block(
        "ERROR_TYPE_MAP = {\n"
        '    "HTTP:NOT_FOUND":     "ResourceNotFoundException",\n'
        '    "HTTP:BAD_REQUEST":   "BadRequestException",\n'
        '    "DB:CONNECTIVITY":    "CannotGetJdbcConnectionException",\n'
        '    "JMS:TIMEOUT":        "TimeoutException",\n'
        '    "ANY":                "Exception",\n'
        "}"
    )
    pdf.explain(
        "MuleSoft has its own error naming system (like HTTP:NOT_FOUND). Spring Boot uses Java exceptions.\n"
        "This map converts between the two. For example, if a MuleSoft flow catches HTTP:NOT_FOUND errors, "
        "the converted Spring code will catch ResourceNotFoundException."
    )

    pdf.section_title("Spring Config Properties Generation")
    pdf.body_text(
        "The get_spring_config_for_connector() method generates Spring application.properties entries "
        "for each connector type:"
    )
    pdf.code_block(
        'if connector_type == "database":\n'
        '    props["spring.datasource.url"] = config["url"]\n'
        '    props["spring.datasource.driver-class-name"] = config["driver"]\n'
        '    props["spring.datasource.username"] = config["user"]\n'
        "\n"
        'elif connector_type == "kafka":\n'
        '    props["spring.kafka.bootstrap-servers"] = "localhost:9092"\n'
        '    props["spring.kafka.consumer.group-id"] = "migrated-app-group"'
    )

    # ================================================================
    # CHAPTER 5: Flow Converter
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("8. Chapter 5: flow_converter.py - Converting Flows to Java")

    pdf.body_text(
        "This is the LARGEST and most complex module (~1000 lines). It takes the parsed MuleSoft flow "
        "data and generates actual Java source code files for Spring Boot. Each MuleSoft flow becomes "
        "either a Spring @RestController (for HTTP flows) or a @Service/@Component class."
    )

    pdf.section_title("Flow Conversion Strategy")
    pdf.code_block(
        "class FlowConverter:\n"
        "    def convert(self, parsed_data, converted_dw):\n"
        "        files = {}\n"
        "        for flow in parsed_data.get('flows', []):\n"
        "            source = flow.get('source', {})\n"
        "            source_type = source.get('type', '') if source else ''\n"
        "\n"
        "            if source_type == 'http-listener':\n"
        "                files.update(self._convert_http_flow(flow, ...))\n"
        "            elif source_type == 'scheduler':\n"
        "                files.update(self._convert_scheduler_flow(flow, ...))\n"
        "            elif source_type in ('jms-listener', 'amqp-listener'):\n"
        "                files.update(self._convert_messaging_flow(flow, ...))\n"
        "            elif source_type == 'kafka-listener':\n"
        "                files.update(self._convert_kafka_flow(flow, ...))"
    )
    pdf.explain(
        "The converter looks at what TRIGGERS each flow:\n"
        "- HTTP listener -> @RestController with @GetMapping/@PostMapping\n"
        "- Scheduler -> @Scheduled method that runs periodically\n"
        "- JMS/AMQP listener -> @JmsListener/@RabbitListener for message queues\n"
        "- Kafka listener -> @KafkaListener for event streaming\n"
        "- File listener -> @Scheduled with file polling\n"
        "Each type generates different Java annotations and patterns."
    )

    pdf.section_title("HTTP Flow Conversion Example")
    pdf.code_block(
        "def _convert_http_flow(self, flow, ...):\n"
        "    # Generates a Spring @RestController like:\n"
        "    #\n"
        "    # @RestController\n"
        "    # @RequestMapping(\"/api\")\n"
        "    # public class OrderController {\n"
        "    #     @GetMapping(\"/orders\")\n"
        "    #     public ResponseEntity<?> getOrders() {\n"
        "    #         // converted processors here\n"
        "    #     }\n"
        "    # }"
    )
    pdf.explain(
        "For each HTTP flow:\n"
        "1. The flow name becomes the Java class name (e.g., 'get-orders' -> 'GetOrdersController')\n"
        "2. The HTTP method (GET/POST/PUT/DELETE) determines the Spring annotation\n"
        "3. The URL path from the listener becomes the @RequestMapping value\n"
        "4. Each processor in the flow becomes Java code inside the method body"
    )

    pdf.section_title("Processor Conversion")
    pdf.body_text(
        "Each MuleSoft processor (logger, set-payload, db:select, http:request, etc.) gets converted "
        "to its Java equivalent:"
    )
    pdf.code_block(
        "# MuleSoft logger -> SLF4J log statement\n"
        "# <logger message=\"Processing order\" level=\"INFO\"/>\n"
        "# Becomes: log.info(\"Processing order\");\n"
        "\n"
        "# MuleSoft set-variable -> Java variable\n"
        "# <set-variable variableName=\"orderId\" value=\"#[payload.id]\"/>\n"
        "# Becomes: Object orderId = payload.get(\"id\");\n"
        "\n"
        "# MuleSoft db:select -> JdbcTemplate query\n"
        "# <db:select><db:sql>SELECT * FROM orders</db:sql></db:select>\n"
        "# Becomes: jdbcTemplate.queryForList(\"SELECT * FROM orders\");\n"
        "\n"
        "# MuleSoft http:request -> WebClient call\n"
        "# Becomes: webClient.get().uri(\"/api/...\").retrieve().bodyToMono();"
    )

    # ================================================================
    # CHAPTER 6: Spring Generator
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("9. Chapter 6: spring_generator.py - Building the Project")

    pdf.body_text(
        "This module takes all the converted Java files and wraps them in a complete, runnable "
        "Spring Boot project. It generates the project configuration, build files, Docker setup, "
        "and infrastructure code that a developer would normally write by hand."
    )

    pdf.section_title("What Gets Generated")
    pdf.bullet("pom.xml - Maven build file with all dependencies")
    pdf.bullet("Main Application class with Spring Boot annotations")
    pdf.bullet("application.properties & application.yml - Configuration files")
    pdf.bullet("Profile-specific configs (dev, prod)")
    pdf.bullet("Config classes (JMS, Kafka, AMQP, Security, CORS, Cache, etc.)")
    pdf.bullet("Custom exception classes (ResourceNotFoundException, etc.)")
    pdf.bullet("JsonUtil utility class")
    pdf.bullet("Dockerfile for containerization")
    pdf.bullet("docker-compose.yml with dependent services (DB, Redis, Kafka, etc.)")
    pdf.bullet(".gitignore file")
    pdf.bullet("Test class skeleton")

    pdf.section_title("The POM.XML Generator")
    pdf.code_block(
        "def _generate_pom(self, connector_info):\n"
        "    deps = connector_info.get('dependencies', [])\n"
        "    dep_xml = ''\n"
        "    for d in deps:\n"
        "        dep_xml += f'''\n"
        "        <dependency>\n"
        "            <groupId>{d['groupId']}</groupId>\n"
        "            <artifactId>{d['artifactId']}</artifactId>\n"
        "        </dependency>'''\n"
        "    # Wraps in full POM template with Spring Boot parent"
    )
    pdf.explain(
        "pom.xml is the Maven Project Object Model - it defines:\n"
        "- Project identity (groupId, artifactId, version)\n"
        "- Parent: spring-boot-starter-parent (provides default configs)\n"
        "- Dependencies: All Spring Boot starters and libraries needed\n"
        "- Build plugins: The Spring Boot Maven plugin for packaging\n"
        "This is automatically customized based on what connectors were detected."
    )

    pdf.section_title("Smart Config Class Generation")
    pdf.code_block(
        "# Only generates configs that are actually needed:\n"
        "has_kafka = 'kafka' in connectors\n"
        "has_jms = 'jms' in connectors\n"
        "has_redis = 'redis' in connectors or 'objectstore' in connectors\n"
        "\n"
        "if has_kafka:\n"
        "    files['config/KafkaConfig.java'] = self._gen_kafka_config()\n"
        "if has_jms:\n"
        "    files['config/JmsConfig.java'] = self._gen_jms_config()\n"
        "if has_redis:\n"
        "    files['config/CacheConfig.java'] = self._gen_cache_config()"
    )
    pdf.explain(
        "The generator is SMART - it only creates config classes for connectors that were actually "
        "detected in the MuleSoft XML. No unused boilerplate. This keeps the generated project clean."
    )

    # ================================================================
    # CHAPTER 7: LLM Validator
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("10. Chapter 7: llm_validator.py - AI Code Validation")

    pdf.body_text(
        "This module sends the generated Spring Boot code to AI language models for review. "
        "It supports 6 different AI providers and 20+ models, using an Object-Oriented design pattern "
        "called the 'Strategy Pattern' to make them interchangeable."
    )

    pdf.section_title("The Provider Registry")
    pdf.code_block(
        "LLM_PROVIDERS = {\n"
        '    "anthropic": {\n'
        '        "name": "Anthropic Claude",\n'
        '        "models": [\n'
        '            {"id": "claude-sonnet-4-20250514", "tier": "premium"},\n'
        '            {"id": "claude-3-5-haiku", "tier": "standard"},\n'
        "        ],\n"
        '        "env_key": "ANTHROPIC_API_KEY",\n'
        "    },\n"
        '    "openai": { ... },  "google": { ... },\n'
        '    "deepseek": { ... }, "groq": { ... }, "ollama": { ... },\n'
        "}"
    )
    pdf.explain(
        "This dictionary defines ALL available AI providers and their models.\n"
        "The frontend reads this to populate the provider/model dropdowns.\n"
        "Each provider has: display name, available models (with tier info), the environment "
        "variable name for the API key, and documentation URL."
    )

    pdf.section_title("The Abstract Base Class Pattern")
    pdf.code_block(
        "from abc import ABC, abstractmethod\n"
        "\n"
        "class BaseLLMProvider(ABC):\n"
        "    def __init__(self, api_key='', model='', base_url=''):\n"
        "        self.api_key = api_key\n"
        "        self.model = model\n"
        "\n"
        "    @abstractmethod\n"
        "    def validate(self, files, summary) -> dict:\n"
        "        pass\n"
        "\n"
        "    def _parse_response(self, text) -> dict:\n"
        "        # Strips markdown fences, parses JSON\n"
        "        return json.loads(text)"
    )
    pdf.key_concept("Abstract Base Class (ABC)",
        "An ABC defines a 'contract' that all subclasses must follow. BaseLLMProvider says: "
        "'Every LLM provider MUST have a validate() method.' Each provider (Anthropic, OpenAI, etc.) "
        "implements this differently, but they all have the same interface. This means the rest of "
        "the code can work with ANY provider without knowing which specific one it is."
    )

    pdf.section_title("Provider Implementations")
    pdf.code_block(
        "class AnthropicProvider(BaseLLMProvider):\n"
        "    def validate(self, files, summary):\n"
        "        import anthropic\n"
        "        client = anthropic.Anthropic(api_key=self.api_key)\n"
        "        response = client.messages.create(\n"
        "            model=self.model,\n"
        "            system=VALIDATION_SYSTEM_PROMPT,\n"
        "            messages=[{'role': 'user', 'content': prompt}],\n"
        "        )\n"
        "        return self._parse_response(response.content[0].text)\n"
        "\n"
        "class DeepSeekProvider(BaseLLMProvider):\n"
        "    def validate(self, files, summary):\n"
        "        import openai  # Reuses OpenAI SDK!\n"
        "        client = openai.OpenAI(\n"
        "            api_key=self.api_key,\n"
        '            base_url="https://api.deepseek.com",  # Different URL\n'
        "        )"
    )
    pdf.explain(
        "Clever design choices:\n"
        "- Anthropic and OpenAI each use their own official Python SDK\n"
        "- DeepSeek and Groq REUSE the OpenAI SDK with a different base_url (because their APIs are compatible)\n"
        "- Ollama uses raw HTTP (urllib) to avoid requiring an extra dependency\n"
        "- Google Gemini uses the google-generativeai SDK\n"
        "- Imports are done INSIDE the method so the app doesn't crash if a library isn't installed"
    )

    pdf.section_title("The Factory Function")
    pdf.code_block(
        "PROVIDER_CLASSES = {\n"
        '    "anthropic": AnthropicProvider,\n'
        '    "openai": OpenAIProvider,\n'
        '    "google": GoogleProvider,\n'
        '    "deepseek": DeepSeekProvider,\n'
        '    "groq": GroqProvider,\n'
        '    "ollama": OllamaProvider,\n'
        "}\n"
        "\n"
        "def get_provider(provider_name, api_key, model, base_url):\n"
        "    cls = PROVIDER_CLASSES.get(provider_name)\n"
        "    return cls(api_key=api_key, model=model, base_url=base_url)"
    )
    pdf.key_concept("Factory Pattern",
        "Instead of using if/else to create the right provider, we use a dictionary that maps "
        "names to classes. The get_provider() function looks up the class and creates an instance. "
        "To add a new AI provider, you just add one entry to this dictionary and create the class."
    )

    # ================================================================
    # CHAPTER 8: Gunicorn
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("11. Chapter 8: gunicorn.conf.py - Production Server")

    pdf.body_text(
        "Flask's built-in server is NOT safe for production - it can only handle one request at a time "
        "and has no security features. Gunicorn (Green Unicorn) is a production WSGI server that can "
        "handle thousands of concurrent users."
    )

    pdf.code_block(
        "import multiprocessing\n"
        "\n"
        "bind = '0.0.0.0:5000'\n"
        "workers = multiprocessing.cpu_count() * 2 + 1  # e.g., 9 on 4-core\n"
        "worker_class = 'gthread'  # Thread-based workers\n"
        "threads = 4               # 4 threads per worker\n"
        "timeout = 120             # 2 min timeout for LLM calls\n"
        "preload_app = True        # Load app once, fork workers"
    )
    pdf.explain(
        "Key settings explained:\n"
        "- bind: Listen on all interfaces, port 5000\n"
        "- workers: Number of separate processes. Formula: 2 * CPU cores + 1\n"
        "  On a 4-core machine: 2*4+1 = 9 workers, each handling requests independently\n"
        "- worker_class='gthread': Uses threads within each worker. This is IMPORTANT for our app because\n"
        "  LLM API calls are I/O-bound (waiting for network). Threads let one worker handle multiple\n"
        "  requests while waiting for AI responses.\n"
        "- timeout=120: AI calls can take 30-60 seconds, so we set 2 minutes\n"
        "- preload_app=True: Loads the app ONCE in the master process, then forks workers.\n"
        "  This saves memory because workers share the loaded code."
    )

    # ================================================================
    # CHAPTER 9: Frontend
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("12. Chapter 9: Frontend (HTML, CSS, JavaScript)")

    pdf.section_title("index.html - The Single Page Application")
    pdf.body_text(
        "The entire UI is a single HTML page with two main panels: Input (left) and Output (right). "
        "It uses a tab-based interface to organize different sections."
    )
    pdf.code_block(
        "<div class=\"panel input-panel\">\n"
        "  <!-- Tab buttons -->\n"
        "  <button class=\"tab\" data-tab=\"mule-xml\">MuleSoft XML</button>\n"
        "  <button class=\"tab\" data-tab=\"dataweave\">DataWeave</button>\n"
        "  <button class=\"tab\" data-tab=\"settings\">Settings</button>\n"
        "  <button class=\"tab\" data-tab=\"llm-settings\">AI Validation</button>\n"
        "\n"
        "  <!-- Tab content panels -->\n"
        "  <div id=\"tab-mule-xml\">   ...textarea for XML...    </div>\n"
        "  <div id=\"tab-dataweave\">  ...DataWeave editor...    </div>\n"
        "  <div id=\"tab-settings\">   ...project settings...    </div>\n"
        "  <div id=\"tab-llm-settings\">...AI provider config... </div>\n"
        "</div>"
    )

    pdf.section_title("style.css - CSS Custom Properties (Variables)")
    pdf.code_block(
        ":root {\n"
        "    --bg-primary: #0f172a;    /* Dark navy background */\n"
        "    --bg-secondary: #1e293b;  /* Slightly lighter panels */\n"
        "    --accent: #6366f1;        /* Indigo purple for buttons */\n"
        "    --success: #22c55e;       /* Green for success states */\n"
        "    --error: #ef4444;         /* Red for errors */\n"
        "    --radius: 8px;            /* Rounded corners */\n"
        "}"
    )
    pdf.explain(
        "CSS Custom Properties (variables) are defined once and reused everywhere.\n"
        "Changing --accent from purple to blue would update EVERY button, link, and highlight\n"
        "across the entire application. This is why the UI looks consistent."
    )

    pdf.section_title("app.js - Frontend Logic")
    pdf.code_block(
        "// Multi-file upload handling\n"
        "let uploadedXmlFiles = [];  // Array of {name, content}\n"
        "\n"
        "function handleFileUpload(event) {\n"
        "    for (const file of event.target.files) {\n"
        "        const reader = new FileReader();\n"
        "        reader.onload = e => {\n"
        "            uploadedXmlFiles.push({\n"
        "                name: file.name,\n"
        "                content: e.target.result\n"
        "            });\n"
        "            renderUploadedFiles();\n"
        "        };\n"
        "        reader.readAsText(file);\n"
        "    }\n"
        "}\n"
        "\n"
        "// The main migration function\n"
        "async function migrate() {\n"
        "    const response = await fetch('/api/migrate', {\n"
        "        method: 'POST',\n"
        "        headers: {'Content-Type': 'application/json'},\n"
        "        body: JSON.stringify({\n"
        "            muleXmlFiles: uploadedXmlFiles,\n"
        "            llmConfig: getLLMConfig(),\n"
        "            projectName: document.getElementById('projectName').value,\n"
        "        }),\n"
        "    });\n"
        "    const data = await response.json();\n"
        "    renderResults(data);\n"
        "}"
    )
    pdf.explain(
        "Key JavaScript concepts:\n"
        "- FileReader: Browser API to read files uploaded by the user\n"
        "- async/await: Modern way to handle operations that take time (like API calls)\n"
        "- fetch(): Makes HTTP requests to our backend API\n"
        "- JSON.stringify(): Converts JavaScript objects to JSON text\n"
        "- The migrate() function collects all user inputs and sends them to the server"
    )

    # ================================================================
    # CHAPTER 10: Docker & Nginx
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("13. Chapter 10: Docker & Nginx - Deployment")

    pdf.section_title("Dockerfile")
    pdf.code_block(
        "FROM python:3.12-slim\n"
        "# Install system deps for lxml XML parsing\n"
        "RUN apt-get update && apt-get install -y libxml2-dev libxslt-dev\n"
        "\n"
        "# Create non-root user (security best practice)\n"
        "RUN useradd -m appuser\n"
        "WORKDIR /app\n"
        "COPY backend/requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY backend/ .\n"
        "USER appuser\n"
        "\n"
        "HEALTHCHECK CMD python -c \"import urllib.request; ...\"\n"
        "CMD [\"gunicorn\", \"-c\", \"gunicorn.conf.py\", \"app:app\"]"
    )
    pdf.explain(
        "The Dockerfile is a recipe for building a container:\n"
        "1. Start with Python 3.12 (slim = smaller image)\n"
        "2. Install C libraries needed by lxml (XML parser)\n"
        "3. Create a non-root user (SECURITY: if hacked, attacker has limited permissions)\n"
        "4. Install Python packages first (Docker caches this layer)\n"
        "5. Copy application code\n"
        "6. Switch to non-root user\n"
        "7. Health check: Docker will restart the container if this fails\n"
        "8. CMD: The command to run (Gunicorn serving our app)"
    )

    pdf.section_title("nginx.conf - Reverse Proxy")
    pdf.code_block(
        "# Rate limiting\n"
        "limit_req_zone $binary_remote_addr zone=migrate:10m rate=2r/s;\n"
        "limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;\n"
        "\n"
        "server {\n"
        "    listen 80;\n"
        "    client_max_body_size 50M;\n"
        "\n"
        "    location /api/migrate {\n"
        "        limit_req zone=migrate burst=5;\n"
        "        proxy_pass http://app:5000;\n"
        "        proxy_read_timeout 120s;  # For LLM calls\n"
        "    }\n"
        "\n"
        "    location /static/ {\n"
        "        proxy_pass http://app:5000;\n"
        "        expires 7d;  # Browser caches for 7 days\n"
        "    }\n"
        "}"
    )
    pdf.explain(
        "Nginx sits in FRONT of our application:\n"
        "- Rate limiting: Prevents abuse. /api/migrate allows 2 requests/second per IP.\n"
        "  'burst=5' means 5 requests can queue up during spikes.\n"
        "- proxy_pass: Forwards requests to our Gunicorn app server\n"
        "- proxy_read_timeout: 120 seconds for LLM validation (AI calls are slow)\n"
        "- Static file caching: CSS/JS files are cached by browsers for 7 days\n"
        "- Security headers: X-Frame-Options, Content-Security-Policy, etc."
    )

    # ================================================================
    # HOW TO RUN
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("14. How To Run The Application")

    pdf.section_title("Option 1: Run Locally (Development)")
    pdf.code_block(
        "# Navigate to the project\n"
        "cd /path/to/mulesoft-to-springboot-migrator/backend\n"
        "\n"
        "# Install Python dependencies\n"
        "pip3 install -r requirements.txt\n"
        "\n"
        "# Run with Gunicorn (production server)\n"
        "python3 -m gunicorn -c gunicorn.conf.py app:app\n"
        "\n"
        "# Or run in development mode (with auto-reload)\n"
        "FLASK_ENV=development python3 app.py\n"
        "\n"
        "# Open browser: http://localhost:5000"
    )

    pdf.section_title("Option 2: Run with Docker")
    pdf.code_block(
        "# Build and start the application\n"
        "docker compose up -d\n"
        "\n"
        "# With Nginx (rate limiting, SSL support)\n"
        "docker compose --profile with-nginx up -d\n"
        "\n"
        "# View logs\n"
        "docker compose logs -f app\n"
        "\n"
        "# Stop everything\n"
        "docker compose down"
    )

    pdf.section_title("Using the Application")
    pdf.bullet("1. Open http://localhost:5000 in your browser")
    pdf.bullet("2. Paste MuleSoft XML or upload XML files (supports multiple files)")
    pdf.bullet("3. (Optional) Add DataWeave scripts in the DataWeave tab")
    pdf.bullet("4. (Optional) Configure project name, group ID, Java version in Settings")
    pdf.bullet("5. (Optional) Enable AI Validation and select a provider/model")
    pdf.bullet("6. Click 'Migrate' - the tool generates a complete Spring Boot project")
    pdf.bullet("7. Browse generated files in the right panel, review the summary")
    pdf.bullet("8. Click 'Download ZIP' to get the complete project")

    # ================================================================
    # GLOSSARY
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("15. Glossary of Terms")

    glossary = [
        ("API", "Application Programming Interface - a way for programs to communicate with each other"),
        ("REST", "Representational State Transfer - a style for building web APIs using HTTP methods"),
        ("JSON", "JavaScript Object Notation - a text format for exchanging data, like {\"name\": \"John\"}"),
        ("XML", "Extensible Markup Language - a text format for storing structured data using tags"),
        ("Flask", "A lightweight Python web framework for building web applications and APIs"),
        ("Gunicorn", "Green Unicorn - a production-grade Python WSGI HTTP server"),
        ("WSGI", "Web Server Gateway Interface - the Python standard for web servers to talk to web apps"),
        ("Docker", "A platform for packaging apps into containers that run anywhere"),
        ("Nginx", "A high-performance web server and reverse proxy"),
        ("Maven", "Java's build tool and dependency manager (like pip for Python)"),
        ("pom.xml", "Project Object Model - Maven's configuration file listing dependencies"),
        ("Spring Boot", "A Java framework for building production-ready applications quickly"),
        ("MuleSoft", "An integration platform for connecting different applications and data sources"),
        ("DataWeave", "MuleSoft's language for transforming data between formats"),
        ("Namespace (XML)", "A way to avoid naming conflicts by grouping XML tags with unique identifiers"),
        ("Decorator (@)", "Python syntax that modifies a function, e.g., @app.route adds URL routing"),
        ("Regex", "Regular expressions - patterns for finding and replacing text"),
        ("Abstract Class", "A class that defines methods subclasses must implement"),
        ("Factory Pattern", "A design pattern where a function creates objects based on parameters"),
        ("Pipeline Pattern", "A design where data flows through sequential processing stages"),
        ("LLM", "Large Language Model - AI models like ChatGPT, Claude, Gemini"),
        ("CORS", "Cross-Origin Resource Sharing - browser security for API calls between domains"),
        ("Environment Variable", "A configuration value set outside the code (like passwords)"),
        ("Rate Limiting", "Restricting how many requests a user can make per time period"),
    ]

    for term, definition in glossary:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(45, 6, term)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 6, definition)
        pdf.ln(1)

    # ================================================================
    # CHAPTER: AI AGENT ARCHITECTURE
    # ================================================================
    pdf.add_page()
    pdf.chapter_title("Chapter 16: AI Agent Architecture")

    pdf.body_text(
        "This chapter explains the Enterprise AI Agentic Agent system that was added "
        "to the migrator. When the migrator encounters unknown MuleSoft XML elements, "
        "connectors, or DataWeave patterns that it cannot convert with its built-in rules, "
        "it now calls an LLM (AI model) in real-time to generate the equivalent Java/Spring Boot code."
    )
    pdf.ln(4)

    pdf.section_title("Why an AI Agent?")
    pdf.body_text(
        "Before the AI agent, unknown elements were either silently dropped or left as "
        "// TODO comments. This meant the user had to manually write code for anything "
        "the migrator didn't recognize. The AI agent solves this by using the same LLM "
        "provider the user configured (Claude, GPT-4, Gemini, etc.) to generate code "
        "for unknown elements during migration, not just for post-migration validation."
    )
    pdf.ln(4)

    pdf.section_title("The Triple Fallback Pattern")
    pdf.body_text(
        "Every unknown element goes through three levels of fallback:"
    )
    pdf.bullet("1. AI Conversion: If AI is enabled and the LLM is reachable, send the unknown "
               "element to the LLM with a specialized prompt. Use the generated code.")
    pdf.bullet("2. TODO Comment: If AI is disabled or the LLM call fails, insert a // TODO comment "
               "in the generated Java code so the developer knows what needs manual attention.")
    pdf.bullet("3. Warning in Summary: Add a warning to the migration summary so the user "
               "can see exactly which elements were not converted.")
    pdf.ln(4)

    pdf.section_title("AgentContext Class (llm_agent.py)")
    pdf.body_text(
        "The AgentContext is the central class that threads through the entire migration pipeline. "
        "Think of it as a shared notebook that every converter module can read from and write to."
    )
    pdf.ln(2)
    pdf.code_block(
        'class AgentContext:\n'
        '    def __init__(self, enabled=False, llm_config=None):\n'
        '        self.enabled = enabled       # Is AI turned on?\n'
        '        self.llm_config = llm_config  # Provider, API key, model\n'
        '        self.ai_conversions = []      # Successful AI conversions\n'
        '        self.ai_skipped = []          # Items skipped (AI off/failed)'
    )
    pdf.explain(
        "enabled: A boolean flag. True if the user turned on AI Validation AND provided a valid provider. "
        "llm_config: A dictionary with keys 'provider', 'apiKey', 'model', 'baseUrl'. "
        "ai_conversions: A list of dictionaries tracking every successful AI conversion. "
        "ai_skipped: A list of dictionaries tracking every item that was skipped."
    )
    pdf.ln(4)

    pdf.section_title("How the Pipeline Uses AgentContext")
    pdf.body_text(
        "The AgentContext is created once in app.py when a migration request comes in, "
        "then passed to every converter module:"
    )
    pdf.ln(2)
    pdf.code_block(
        '# In app.py /api/migrate endpoint:\n'
        'agent_context = AgentContext(\n'
        '    enabled=llm_enabled and bool(llm_provider),\n'
        '    llm_config={...}\n'
        ')\n'
        '\n'
        '# Passed to each stage:\n'
        'parser.parse(content, agent_context=agent_context)\n'
        'dw_converter.convert(script, agent_context=agent_context)\n'
        'connector_mapper.map_connectors(parsed, agent_context=agent_context)\n'
        'flow_converter.convert(parsed, converted_dw, agent_context=agent_context)'
    )
    pdf.explain(
        "Each module checks agent_context.enabled before calling the LLM. If disabled, "
        "it records the skipped item and falls back to a TODO comment."
    )
    pdf.ln(4)

    pdf.section_title("Agent Functions")
    pdf.body_text(
        "The llm_agent.py module provides four specialized functions, each building a "
        "custom prompt for a different type of unknown element:"
    )
    pdf.ln(2)

    pdf.subsection_title("1. convert_unknown_element()")
    pdf.body_text(
        "Used by flow_converter.py when it encounters an unknown XML processor. "
        "It sends the XML element and flow context to the LLM and asks for equivalent "
        "Java code. The LLM returns a code block that gets inserted directly into the "
        "generated controller or service method."
    )
    pdf.ln(2)

    pdf.subsection_title("2. convert_unknown_dataweave()")
    pdf.body_text(
        "Used by dataweave_converter.py when a DataWeave expression cannot be parsed "
        "by the regex-based converter. The LLM receives the raw DataWeave expression "
        "and returns equivalent Java code using streams, lambdas, or Jackson."
    )
    pdf.ln(2)

    pdf.subsection_title("3. suggest_connector_mapping()")
    pdf.body_text(
        "Used by connector_mapper.py when a MuleSoft connector is not in the built-in "
        "mapping table. The LLM suggests Maven dependencies and Spring properties."
    )
    pdf.ln(2)

    pdf.subsection_title("4. convert_unknown_source()")
    pdf.body_text(
        "Used by parser.py when a message source (listener/inbound endpoint) is not "
        "recognized. The LLM determines the equivalent Spring Boot configuration."
    )
    pdf.ln(4)

    pdf.section_title("The chat() Method")
    pdf.body_text(
        "The existing llm_validator.py had a validate() method for post-migration code review. "
        "We added a new chat() method to BaseLLMProvider and all 6 subclasses. Unlike validate() "
        "which expects structured JSON output, chat() returns raw text - perfect for code generation."
    )
    pdf.ln(2)
    pdf.code_block(
        '# In BaseLLMProvider (abstract):\n'
        '@abstractmethod\n'
        'def chat(self, system_prompt, user_prompt, max_tokens=2048) -> str:\n'
        '    """Generic chat - returns raw text response."""\n'
        '    pass\n'
        '\n'
        '# Convenience function:\n'
        'def chat_with_llm(config, system_prompt, user_prompt) -> str:\n'
        '    provider = get_provider(config["provider"], ...)\n'
        '    return provider.chat(system_prompt, user_prompt)'
    )
    pdf.ln(4)

    pdf.section_title("Integration Points (19 Locations)")
    pdf.body_text(
        "The AI agent integrates at 19 specific locations across 4 modules:"
    )
    pdf.bullet("parser.py: 2 locations - unknown global configs and unknown message sources")
    pdf.bullet("dataweave_converter.py: 11 locations - one for each unparseable DW pattern "
               "(map, filter, reduce, groupBy, orderBy, distinctBy, flatMap, pluck, "
               "mapObject, filterObject, match)")
    pdf.bullet("connector_mapper.py: 1 location - unknown connector dependency mapping")
    pdf.bullet("flow_converter.py: 5 locations - main unknown processor catch-all, plus "
               "Salesforce, S3, SQS, and validation unknowns")
    pdf.ln(4)

    pdf.section_title("Frontend Display")
    pdf.body_text(
        "After migration, the Summary tab shows an AI Agent card with two stats: "
        "how many elements were successfully converted by AI, and how many were skipped. "
        "Each conversion shows the element name, a purple 'AI' badge, and a brief description. "
        "If AI is disabled but unknown elements were found, a prompt appears suggesting "
        "the user enable AI Validation."
    )
    pdf.ln(4)

    pdf.section_title("Key Takeaways")
    pdf.key_concept(
        "AgentContext Pattern",
        "A shared context object that flows through the entire pipeline, tracking AI state "
        "and results. This avoids global state and makes the system testable."
    )
    pdf.key_concept(
        "Lazy Provider Initialization",
        "The LLM provider is only created when the first AI call is made, not at startup. "
        "This means there's zero overhead when AI is disabled."
    )
    pdf.key_concept(
        "Triple Fallback",
        "AI code -> TODO comment -> warning in summary. The system degrades gracefully "
        "at every level, never throwing errors for unknown elements."
    )

    # ================================================================
    # SAVE
    # ================================================================
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "MuleSoft_to_SpringBoot_Migrator_Complete_Guide.pdf"
    )
    pdf.output(output_path)
    print(f"\nPDF generated successfully: {output_path}")
    print(f"Total pages: {pdf.page_no()}")
    return output_path


if __name__ == "__main__":
    generate_pdf()
