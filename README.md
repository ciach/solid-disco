# FastMCP File Organizer (solid-disco)

A production-ready, intelligent file organizer built with Python, FastMCP, and Local AI. This tool scans directories, classifies files using heuristics and LLMs (Ollama/OpenAI), and generates idempotent execution plans to organize your chaotic folders.

## Key Features

-   **Two-Pass Architecture**:
    -   *Scan Phase*: Non-destructive analysis using composite hashing (SHA-256 partials) to detect duplicates and changes.
    -   *Plan Phase*: Generates a safe, reviewable execution plan before moving a single file.
-   **Intelligent Classification**:
    -   **Hybrid Approach**: Fast heuristics for obvious types + LLM for ambiguous content.
    -   **Local AI Support**: Seamlessly integrates with **Ollama** (Llama 3, Phi-3, etc.) for privacy-first classification.
    -   **Cloud Fallback**: Supports OpenAI GPT-4o for higher accuracy.
-   **Observability First**:
    -   **Langfuse Integration**: Full tracing of every scan, classification, and prompt.
    -   **Managed Prompts**: Update classification rules dynamically via Langfuse without redeploying code.
    -   **POML Support**: Local "Prompt Object Markup Language" file for structured prompt management if cloud is unreachable.
-   **User Feedback Loop**: CLI command to rate AI accuracy and improve future results.

## Prerequisites

-   Python 3.10+
-   `uv` (Universal Python Package Manager) recommended
-   [Ollama](https://ollama.com/) (optional, for local AI)
-   [Langfuse](https://langfuse.com/) Account (optional, for tracing)

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/ciach/solid-disco.git
    cd solid-disco
    ```

2.  **Install dependencies**:
    ```bash
    uv sync
    ```

3.  **Configuration**:
    Copy `.env.example` to `.env` and configure your preferences:
    ```bash
    cp .env.example .env
    ```

    **Key Environment Variables**:
    *   `LLM_PROVIDER`: `ollama` or `openai`
    *   `OLLAMA_BASE_URL`: e.g., `http://localhost:11434/v1`
    *   `MODEL_NAME`: e.g., `llama3.2:3b` or `gpt-4o`
    *   `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`: For observability.

## Usage

The tool is accessed via the `fastmcp-organizer` CLI.

### 1. Start the Server (Optional)
If running as an MCP server for Claude Desktop or other clients:
```bash
uv run fastmcp-organizer server
```

### 2. Scan a Directory
Analyzes files and generates an organization plan.
```bash
uv run fastmcp-organizer scan /path/to/your/folder
```
*   **Output**: Returns a `Plan ID` (e.g., `123e4567-e89b...`).
*   **Note**: This does NOT move files yet.

### 3. View a Plan
Inspect the proposed changes before execution.
```bash
uv run fastmcp-organizer show <PLAN_ID>
```

### 4. Execute a Plan
Apply the changes (move/rename files) safely.
```bash
uv run fastmcp-organizer execute <PLAN_ID>
```

### 5. Provide Feedback
Help improve the AI by rating the classification quality.
```bash
uv run fastmcp-organizer feedback <PLAN_ID>
```

## Advanced: Prompt Engineering & POML

The system uses a **Prompt Object Markup Language (POML)** file located at `fastmcp_organizer/prompts/classifier.poml`. This ensures:
1.  **Strict JSON Output**: Guarantees the LLM returns parsable data.
2.  **Version Control**: Your prompts are code.
3.  **Fallback**: If Langfuse Managed Prompts fail, the local POML is used.

## Architecture

Built with SOLID principles:
-   **Core**: Pure python logic (Scanner, Classifier).
-   **Server**: Context-aware injection layer.
-   **CLI**: Rich-text interface using `click` and `rich`.
-   **Database**: SQLite for storing state and history.

## Contributing

1.  Fork the repo
2.  Create your feature branch (`git checkout -b feature/amazing-feature`)
3.  Commit your changes (`git commit -m 'Add some amazing feature'`)
4.  Push to the branch (`git push origin feature/amazing-feature`)
5.  Open a Pull Request
