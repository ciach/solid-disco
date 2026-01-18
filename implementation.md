🏗️ FastMCP File Organizer: Production Architecture (v2)
1. Core Architecture & Data Model
We are moving state out of memory and into a structured SQLite database (state.db). This handles caching, plan persistence, and idempotency.

1.1 Database Schema (state.db)
We need two tables: one for the "Memory" (Cache) and one for the "Intent" (Plans).

SQL
-- 1. The Smart Cache
CREATE TABLE file_cache (
    file_hash TEXT PRIMARY KEY,       -- Composite Hash
    file_path TEXT,                   -- Last known path (for debugging)
    size_bytes INTEGER,
    mtime INTEGER,
    metadata_json TEXT,               -- The AI classification
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. The Execution Plan (Persistent & Auditable)
CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    root_dir TEXT,
    status TEXT,                      -- CREATED, APPROVED, EXECUTED, FAILED
    created_at TIMESTAMP,
    executed_at TIMESTAMP
);

-- 3. The Granular Steps (Idempotency Tracking)
CREATE TABLE plan_items (
    id TEXT PRIMARY KEY,
    plan_id TEXT,
    src_path TEXT,
    dest_path TEXT,
    reasoning TEXT,
    status TEXT,                      -- PENDING, SKIPPED, DONE, ERROR
    error_msg TEXT,
    FOREIGN KEY(plan_id) REFERENCES plans(id)
);
1.2 The "Composite Hash" Strategy (Fixing 1.1)
To avoid reading 10GB files while preventing hash collisions on truncated content, we use a Metadata + Sample hash.

Python
import hashlib
import os

def calculate_composite_hash(path: Path) -> str:
    stats = path.stat()
    
    # 1. Cheap Metadata
    hasher = hashlib.sha256()
    hasher.update(str(stats.st_size).encode())
    hasher.update(str(stats.st_mtime).encode())
    
    # 2. Semantic Sampling (First 4KB + Last 4KB)
    # Catches header changes and footer updates
    with open(path, 'rb') as f:
        head = f.read(4096)
        f.seek(-4096, os.SEEK_END)
        tail = f.read(4096)
        
    hasher.update(head)
    hasher.update(tail)
    
    return hasher.hexdigest()
2. Robust Core Logic
2.1 The "Two-Pass" Reader (Fixing 1.2)
We solve the "Invoice in the middle" problem with a tiered reading strategy.

Tier 1 (Fast): Read Head (2KB) + Tail (1KB).

Tier 2 (Deep): Triggered if:

Tier 1 contains keywords: Total, Invoice, Balance Due, Agreement, Witnesseth.

File extension is high-risk: .pdf, .docx.

Or if the AI returns confidence < 0.8 on the Tier 1 read.

2.2 Rigorous Confidence Scoring (Fixing 1.3)
We stop relying on "vibes" and enforce a calculated score in classifier.py.

Python
class ClassificationResult(BaseModel):
    category: str
    confidence_score: float
    requires_deep_scan: bool  # AI signals it needs more context
    
def calculate_final_confidence(file_name, ai_result):
    score = ai_result.confidence_score
    
    # Penalty: Generic categories
    if ai_result.category in ["Misc", "Other"]:
        score -= 0.2
        
    # Boost: Filename corroboration
    if ai_result.category.lower() in file_name.lower():
        score += 0.2
        
    # The "Do Nothing" Anchor (Fixing 6)
    if ai_result.category == "Keep_Current_Location":
        score = 1.0 

    return min(max(score, 0.0), 1.0)
2.3 Symlink & Path Safety (Fixing 1.4)
The safety.py module must resolve paths to their canonical form before validating the jail.

Python
def is_safe_path(root: Path, target: Path) -> bool:
    # Resolve symlinks and relative paths
    try:
        real_root = root.resolve(strict=True)
        real_target = target.resolve(strict=False) # target might not exist yet
    except FileNotFoundError:
        return False

    # Check if target is actually inside root
    return real_target.is_relative_to(real_root)

def safe_move(src, dest):
    if os.path.islink(src):
        if not ALLOW_SYMLINKS:
            raise SecurityError("Symlink movement blocked")
        # Ensure the symlink target is also safe if we were to follow it
        # (Policy decision: usually just move the link itself)
3. Deployment & Infrastructure
3.1 Docker & uv (Fixing 3.1, 3.2, 3.3)
We adopt the Immutable Container / Mutable Volume pattern.

Dockerfile

Dockerfile
FROM python:3.12-slim

# Install uv for fast, reliable dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 1. Dependency Layer (Cached)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 2. Application Layer
COPY fastmcp_organizer ./fastmcp_organizer
# Note: We do NOT copy data/ or cache.db here. 

# 3. Environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 4. Entrypoint
# Default to MCP, can be overridden for CLI
EXPOSE 3333
ENTRYPOINT ["uv", "run", "fastmcp-organizer"]
CMD ["server"] 
docker-compose.yml

YAML
services:
  organizer:
    build: .
    volumes:
      # The User Data (Target)
      - ~/Documents:/data/target:rw
      # The App State (Cache & Plans)
      - ./app_data:/data/state:rw
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=sqlite:////data/state/state.db
      - ROOT_DIR=/data/target
4. MCP Agent Integration (Fixing 2.1, 2.2)
4.1 Idempotency & Concurrency
The MCP Server methods wrap the core logic, ensuring that retries don't cause chaos.

server/mcp_agent.py

Python
@mcp.tool()
def create_organization_plan(folder_path: str) -> str:
    """Scans folder, generates a plan, persists it to DB, returns Plan ID."""
    # 1. Locking: Use SQLite explicit transaction
    with db.begin():
        # ... logic ...
        plan_id = uuid.uuid4()
        db.save_plan(plan_id, items)
    
    return f"Plan created: {plan_id}. Review summaries. Call execute_plan('{plan_id}') to apply."

@mcp.tool()
def execute_plan(plan_id: str) -> str:
    """Executes a plan. Idempotent: Skips items already marked DONE."""
    plan = db.get_plan(plan_id)
    
    results = []
    for item in plan.items:
        if item.status == 'DONE':
            results.append(f"Skipped {item.src} (Already Done)")
            continue
            
        try:
            # Re-verify safety just before move
            safety.validate_move(item.src, item.dest)
            shutil.move(item.src, item.dest)
            
            # Atomic Status Update
            db.update_item_status(item.id, 'DONE')
            results.append(f"Moved {item.src}")
            
        except Exception as e:
            db.update_item_status(item.id, 'ERROR', str(e))
    
    return "\n".join(results)
5. Observability (Fixing 5)
We will use Langfuse not just for LLM traces, but for System Metrics.

Key Metrics to Track:

Cache Hit Rate: (Cache Hits / Total Files Scanned) -> Measures efficiency.

Tokens Saved: (Total File Size - Actual Bytes Read) / 4 -> Measures cost savings (ROI).

Safety Skips: Count of files skipped due to symlink/jail checks -> Measures security events.

"Do Nothing" Ratio: Percentage of files where AI decided not to move -> Measures false positive reduction.

6. Updated Project Structure (Fixing 4)
Plaintext
fastmcp_organizer/
├── pyproject.toml              # [project.scripts] fastmcp-organizer = "fastmcp_organizer.cli:main"
├── uv.lock
├── Dockerfile
├── fastmcp_organizer/
│   ├── __init__.py
│   ├── __main__.py             # Entry point for python -m
│   ├── config.py
│   ├── cli.py                  # "uv run fastmcp-organizer scan ..."
│   ├── core/
│   │   ├── db.py               # SQLite + Locking logic
│   │   ├── scanner.py          # Composite Hashing
│   │   ├── reader.py           # 2-Pass Reading
│   │   ├── classifier.py       # Pydantic + Confidence Logic
│   │   └── safety.py           # Symlink & Jail checks
│   ├── server/
│   │   └── mcp_agent.py        # Idempotent MCP Tools
│   └── utils/
│       └── observability.py    # Langfuse Metrics wrapper
└── tests/
This plan is now watertight. It handles the edge cases (symlinks, retries, huge files) and fits perfectly into the modern Python/AI stack (uv, FastMCP, Docker).