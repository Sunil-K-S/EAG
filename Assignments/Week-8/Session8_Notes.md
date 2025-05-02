# Session 8: From Reasoning Loop to Real-World Agent

## Overview

Until now, your agent could:
- **Perceive:** Understand instructions (Perception Layer)
- **Remember:** Store facts (Memory Layer)
- **Plan:** Decide next steps (Decision Layer)
- **Act:** Execute internal tools (Action Layer via MCP)

**Limitation:**  
It lived in a sandbox—no real-world data, no external actions.

**This session:**  
You set the agent loose (carefully!) by giving it:
- Access to real-world data (HTML, PDFs)
- Power to run secure code (Python, SQL, shell)
- The ability to parse, summarize, and act on external inputs

---

## RAG vs HyDE

- **RAG (Retrieval-Augmented Generation):**  
  Retrieves relevant documents and uses them for LLM reasoning.
- **HyDE (Hypothetical Document Embeddings):**  
  Converts the query into a hypothetical answer, then searches for similar content.
- **Your approach:**  
  Improved queries before embedding/search, but did not generate hypothetical answers.

---

## APIs: The Language of the Internet

- **API = Waiter Analogy:**  
  Client (you) orders, API (waiter) delivers to server (kitchen), brings back response (food).
- **Core Concepts:**
  - **Endpoints:** URLs for specific functions/data
  - **Methods:** Actions (GET, POST, PUT, PATCH, DELETE)
  - **Request/Response:** Structured (JSON/XML)
  - **Headers:** Metadata (auth, content-type)
  - **Payload:** Data sent in POST/PUT
  - **Status Codes:** 200 (OK), 201 (Created), 400 (Bad Request), 401/403 (Auth), 404 (Not Found), 500 (Server Error)
- **Authentication:**  
  API keys, OAuth2, JWT—never expose open APIs!

---

## Using External Tools Responsibly

- **Old tools:** Local, stateless, predictable (e.g., add, sqrt)
- **New tools:**  
  - Can access files, run code, make network calls, connect to 3rd-party APIs
  - **Risks:**  
    - Malicious commands (e.g., `rm -rf /`)
    - Infinite loops (`while True: pass`)
    - Data exfiltration (fetching private emails)
    - Downloading malware

**MCP (Modular Control Protocol) helps by:**
- Explicit tool registration
- Pydantic schemas for input/output validation
- Well-defined transport layers (stdio, sse)

---

## MCP Transport Layers

| Feature         | stdio (local) | sse (remote) |
|-----------------|--------------|--------------|
| Communication   | Process      | HTTP/SSE     |
| Security        | Sandbox      | Needs auth   |
| Performance     | Fast         | Slightly slower |
| Streaming       | Manual       | Native       |
| Use Case        | Local dev    | Cloud/prod   |

---

## Tool Safety Principles

- **Validate inputs** (Pydantic)
- **Timeouts** for long-running tools
- **Code execution:** Only allow safe math, no `import os`
- **Shell commands:** Only read-only (ls, cat)
- **File access:** Explicitly scoped
- **Logging:** All tool calls and outputs

---

## Scaling to Thousands of Tools

- **Problem:**  
  As tools grow (Gmail, Drive, Telegram, Notion, etc.), how does the agent know what exists and which to use?
- **Solution:**
  1. **Tool Summary Layer:**  
     Show human-friendly summaries, not raw schemas.
  2. **Hint-Based/Semantic Filtering:**  
     Filter tools by keyword, tag, or semantic similarity.
  3. **Distributed Discovery:**  
     Query multiple MCP servers for tool summaries, then fetch full schemas as needed.

---

## Webpage Parsing: MarkItDown & Trafilatura

- **Why not raw HTML?**  
  - Messy, unstructured, full of ads/scripts
  - Not LLM-friendly

- **MarkItDown:**  
  - Converts HTML → Markdown
  - Extracts images, tables, headings, paragraphs
  - Strips UI noise
  - Good for full-page structure, legal docs, embedding

- **Trafilatura:**  
  - Extracts just the main article/content
  - Reader-view style, concise
  - Best for news/blog summarization

| Feature         | MarkItDown         | Trafilatura         |
|-----------------|--------------------|---------------------|
| Focus           | HTML→Markdown      | Main content only   |
| Output          | Full doc, layout   | Clean, concise      |
| Table/Image     | Yes                | Table: Yes, Image: No|
| Links           | Preserved          | Optional/stripped   |
| Use Case        | RAG, legal docs    | Summarization       |

---

## PDF Summarization & Semantic Chunking

- **PDFs are hard:**  
  - Dense, inconsistent, images, tables, footnotes, scanned pages

- **Naive chunking fails:**  
  - Splitting by N tokens or newlines can break context, split tables/captions

### Rohan's Semantic Chunking Strategy

**V1:**
- Split into sentences
- Ask LLM: Should these two chunks go together?
- Merge related chunks for topical cohesion

**V2:**
- Slice into 512-word blocks
- Ask LLM: Is there a second topic? If so, split and roll over
- Efficient, accurate, minimal wasted tokens

| Approach      | Classic Fixed | Strategy 1 (Pairwise) | Strategy 2 (Block+Smart) |
|---------------|--------------|-----------------------|--------------------------|
| Chunk Control | ✅           | ⚠️                   | ✅                       |
| Topic Bound.  | ❌           | ✅                   | ✅                       |
| LLM Cost      | ✅           | ❌                   | ⚖️                       |
| Accuracy      | ❌           | ✅                   | ✅                       |
| Speed         | ✅           | ❌                   | ⚡                       |
| Waste         | ✅           | ❌                   | ✅                       |

- **After chunking:**  
  - Embed with FAISS
  - Query: semantic search → top-k chunks → LLM reasoning

---

## PDF Parsing: MarkItDown vs PyMuPDF4LLM

| Feature         | MarkItDown         | PyMuPDF4LLM         |
|-----------------|--------------------|---------------------|
| Engine          | pdfminer.six       | PyMuPDF             |
| Layout          | Weak               | Strong              |
| Images          | No                 | Yes                 |
| Tables          | Inferred           | Accurate, CSV       |
| Markdown        | Basic              | GitHub-flavored     |
| Headers         | Flat               | Font-size-based     |
| Page-by-Page    | No                 | Yes                 |
| Use Case        | Basic conversion   | RAG, summarization  |

- **For image-only PDFs:**  
  - Extract images (PyMuPDF4LLM)
  - OCR with Gemma3/Ollama
  - Add OCR output as a chunk

---

## Secure Code Execution (Python, Shell, SQL)

- **Why?**  
  - Sometimes reasoning isn't enough; need to compute, query, or list files

- **Principles:**
  - Validate inputs (e.g., SELECT-only for SQL)
  - Time/memory/output limits
  - Isolated execution (subprocesses/containers)
  - No external imports

- **Tools:**
  - `run_python_sandbox`: Math-only eval
  - `run_shell_sandbox`: Read-only shell commands
  - `run_sql_query`: SELECTs on SQLite

---

## Agent Integration: Putting It All Together

**Proposed pipeline:**
1. **extract_webpage** (Trafilatura): HTML → Markdown (tables, images)
2. **extract_pdf** (PyMuPDF4LLM): PDF → Markdown + image refs
3. **Image → Caption** (Gemma3): Replace images with LLM-generated alt-text
4. **Semantic chunking:** Topic-based, not token-based
5. **Embed + store in FAISS:** For downstream RAG
6. **Other formats:** Convert to PDF for unified processing

- **Pydantic models** in `models.py`
- **Agent invokes tools** via `action.py` (no extra orchestration logic needed)

---

## Assignment Recap

- Add support for Gmail, Telegram, and Google Drive via MCP servers (at least one using SSE)
- Send a message to your agent on Telegram:  
  "Find the current point standing of F1 racers, put that in a Google Sheet, and email me the link"
- Agent should:
  1. Search online for F1 standings
  2. Create a spreadsheet in Google Drive
  3. Email the link via Gmail
  4. All triggered from a Telegram message

---

## Key Q&A and Discussions from the Session

- **Why not just dump all tool schemas to the LLM?**  
  Token explosion, decision fatigue, and latency. Use summaries and filtering.
- **How to handle tool safety?**  
  Validate, restrict, and log everything. Never allow arbitrary code or shell execution.
- **How to chunk documents for RAG?**  
  Use semantic chunking, not just fixed-size or newline splits.
- **How to handle images in PDFs/webpages?**  
  Extract, caption (with VLM), and embed for retrieval.
- **How to scale to thousands of tools?**  
  Use distributed discovery, summaries, and hint-based filtering.
- **How to handle multi-modal (text+image) documents?**  
  Extract all modalities, caption images, and chunk semantically.

---

## Important Resources & Tools

- [MarkItDown](https://github.com/markitdown/markitdown) – HTML to Markdown conversion
- [Trafilatura](https://github.com/adbar/trafilatura) – Main content extraction from web pages
- [PyMuPDF4LLM](https://github.com/llm-tools/pymupdf4llm) – PDF parsing for LLMs
- [FAISS](https://github.com/facebookresearch/faiss) – Vector search for RAG
- [Ollama](https://ollama.com/) – Local LLMs (Gemma, etc.)
- [Gemma3](https://ollama.com/library/gemma) – Vision model for image captioning/OCR
- [Pydantic](https://docs.pydantic.dev/) – Data validation for tool schemas
- [FastAPI](https://fastapi.tiangolo.com/) – For building HTTP MCP servers
- [MCP Protocol](https://github.com/stanford-oval/mcp) – Modular Control Protocol for agent-tool communication

---

## Takeaways

- **Agents must be safe, robust, and scalable**
- **Tool discovery and selection is a major challenge as you scale**
- **Web and PDF parsing is non-trivial—choose the right tool for the job**
- **Semantic chunking and multi-modal reasoning are essential for high-quality RAG**
- **Secure code execution is a must for agentic systems**
- **Design for extensibility: new tools, new transports, new data types**

---

*For diagrams, see the original slides or code snippets referenced in the transcript.* 