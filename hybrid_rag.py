"""
hybrid_rag.py — Backend: Question Router + Hybrid RAG (FAISS + Kuzu + Ollama)
ใช้โดย app.py (หน้าเว็บ) และ setup.py (ใช้ค่า config ร่วมกัน)

ทดสอบใน terminal:
    uv run python hybrid_rag.py "view ไหนใช้ model Place บ้าง"
"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings

try:
    import kuzu
except ImportError:  # ไม่มี kuzu ก็ยังใช้ได้ แต่เหลือแค่ vector mode
    kuzu = None

# ─── config (setup.py ก็ใช้ค่าชุดนี้) ─────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
MODEL_LLM = "qwen2.5-coder:3b"       # ถ้าเครื่องไหวเปลี่ยนเป็น qwen2.5-coder:7b
MODEL_EMBED = "nomic-embed-text"
NUM_CTX = 8192                        # context window ของ Ollama (ค่า default เล็กเกินไป)
VECTOR_DB_PATH = BASE_DIR / "vector_db"
GRAPH_DB_PATH = BASE_DIR / "graph_db"

URL_FRAG = re.compile(r"(?:^|\s)(/[\w\-<>:/]*)")
URL_WORDS = re.compile(r"\b(urls?|routes?|endpoints?|paths?)\b|ลิงก์|เส้นทาง|หน้าเว็บ", re.I)


# =============================================================================
# Question Router — คำถามเชิงความสัมพันธ์/โครงสร้างไป graph, ที่เหลือไป vector
# =============================================================================
class QuestionRouter:
    GRAPH_EN = re.compile(
        r"\b(call|calls|called|caller|callers|callee|callees|depend|depends|"
        r"dependency|dependencies|impact|impacts|affect|affects|uses|used|"
        r"urls?|routes?|endpoints?|models?|foreign\s*keys?|fk|relations?|"
        r"relationships?|related)\b", re.I)
    GRAPH_TH = ("เรียก", "กระทบ", "ขึ้นกับ", "ขึ้นอยู่กับ", "ถูกใช้", "ที่ใช้", "ใช้ model",
                "ความสัมพันธ์", "เชื่อม", "ลิงก์", "เส้นทาง")

    def classify(self, question: str) -> str:
        if (self.GRAPH_EN.search(question) or URL_FRAG.search(question)
                or any(k in question for k in self.GRAPH_TH)):
            return "graph"
        return "vector"


# =============================================================================
# Hybrid RAG
# =============================================================================
_STOPWORDS = {"who", "what", "which", "does", "do", "the", "a", "is", "how", "it",
              "call", "calls", "called", "function", "functions", "and", "or", "of",
              "to", "in", "by", "on", "model", "view", "form", "url"}

# (ชื่อที่แสดง, cypher) — {n} คือชื่อที่ถามถึง, คืน name, file, line ของอีกฝั่ง
_RELATIONS = [
    ("calls",                 "MATCH (a:Code)-[:CALLS]->(b:Code) WHERE a.name = $n RETURN DISTINCT b.qualname, b.file, b.line"),
    ("called by",             "MATCH (a:Code)-[:CALLS]->(b:Code) WHERE b.name = $n RETURN DISTINCT a.qualname, a.file, a.line"),
    ("uses",                  "MATCH (a:Code)-[:USES]->(b:Code) WHERE a.name = $n RETURN DISTINCT b.qualname, b.file, b.line"),
    ("used by",               "MATCH (a:Code)-[:USES]->(b:Code) WHERE b.name = $n RETURN DISTINCT a.qualname, a.file, a.line"),
    ("foreign key to",        "MATCH (a:Code)-[:FOREIGN_KEY]->(b:Code) WHERE a.name = $n RETURN DISTINCT b.qualname, b.file, b.line"),
    ("referenced by FK from", "MATCH (a:Code)-[:FOREIGN_KEY]->(b:Code) WHERE b.name = $n RETURN DISTINCT a.qualname, a.file, a.line"),
]

_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a coding assistant for a local codebase. Answer using only the "
     "context below. If the context is not enough, say you cannot find it in the "
     "codebase. Reply in the same language as the question.\n\n{context}"),
    ("human", "{question}"),
])


def _route_regex(path: str) -> str:
    """แปลง /location/<int:pk>/ เป็น regex ที่จับ /location/5 ได้"""
    parts = re.split(r"(<[^>]+>)", path.rstrip("/"))
    return "".join("[^/]+" if p.startswith("<") else re.escape(p) for p in parts)


class HybridRAG:
    def __init__(self):
        if not VECTOR_DB_PATH.exists():
            raise FileNotFoundError(
                f"ไม่พบ {VECTOR_DB_PATH.name}/ — รัน: uv run python setup.py <folder โค้ด>")
        self.vectorstore = FAISS.load_local(
            str(VECTOR_DB_PATH), OllamaEmbeddings(model=MODEL_EMBED),
            allow_dangerous_deserialization=True)   # โอเคเพราะเป็น index ที่เราสร้างเอง
        self.chain = _PROMPT | ChatOllama(model=MODEL_LLM, temperature=0, num_ctx=NUM_CTX)
        self.router = QuestionRouter()

        self.conn = None
        self.known_names: set[str] = set()
        self.routes: list = []   # [(path, url_name, view_name, file, line)]
        if kuzu is not None and GRAPH_DB_PATH.exists():
            self._db = kuzu.Database(str(GRAPH_DB_PATH), read_only=True)
            self.conn = kuzu.Connection(self._db)
            self.known_names = {r[0] for r in self._rows("MATCH (c:Code) RETURN DISTINCT c.name")}
            self.routes = self._rows(
                "MATCH (r:Route)-[:ROUTES_TO]->(c:Code) RETURN r.path, r.url_name, c.name, c.file, c.line")

    @property
    def has_graph(self) -> bool:
        return self.conn is not None

    def _rows(self, query: str, params: dict | None = None) -> list:
        res = self.conn.execute(query, params or {})
        rows = []
        while res.has_next():
            rows.append(tuple(res.get_next()))
        return rows

    # ─── retrieval ───────────────────────────────────────────────────────────
    def _vector_context(self, question: str, k: int):
        docs = self.vectorstore.similarity_search(question, k=k)
        return "\n\n".join(d.page_content for d in docs), [dict(d.metadata) for d in docs]

    def _url_context(self, question: str, tokens: list[str]):
        """หา URL ที่ถามถึง (จาก path เช่น /location/5/ หรือจากชื่อ url เช่น location_detail)"""
        hits = []
        for frag in URL_FRAG.findall(question):
            path = frag.rstrip("/")
            hits += [r for r in self.routes if re.fullmatch(_route_regex(r[0]), path)]
        hits += [r for r in self.routes if r[1] and r[1] in tokens]
        lines = [f"URL {p} (name='{u}') -> view {v} ({f}:{l})" for p, u, v, f, l in dict.fromkeys(hits)]
        return lines, [r[2] for r in hits]

    def _graph_context(self, question: str):
        tokens = list(dict.fromkeys(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", question)))
        url_lines, url_views = self._url_context(question, tokens)
        names = list(dict.fromkeys(
            url_views + [t for t in tokens if t in self.known_names and t.lower() not in _STOPWORDS]))[:3]

        parts, sources = [], []
        if url_lines:
            parts.append("URL routes:\n" + "\n".join(url_lines))
        elif not names and URL_WORDS.search(question) and self.routes:
            # ถามรวม ๆ เช่น "มี url อะไรบ้าง" -> แสดงทุก route
            parts.append("All URL routes:\n" + "\n".join(
                f"{p} (name='{u}') -> {v} ({f}:{l})" for p, u, v, f, l in self.routes[:100]))

        for n in names:
            defs = self._rows("MATCH (c:Code) WHERE c.name = $n "
                              "RETURN c.kind, c.qualname, c.file, c.line, c.code LIMIT 2", {"n": n})
            block = [f"### {kind} {q} ({f}:{l})\n{code}" for kind, q, f, l, code in defs]
            sources += [{"name": q, "file": f, "line": l} for _, q, f, l, _ in defs]
            rels = []
            for label, cypher in _RELATIONS:
                rows = self._rows(cypher + " LIMIT 30", {"n": n})
                if rows:
                    rels.append(f"  {label}: " + ", ".join(f"{r[0]} ({r[1]}:{r[2]})" for r in rows))
                    sources += [{"name": r[0], "file": r[1], "line": r[2]} for r in rows]
            urls = self._rows("MATCH (r:Route)-[:ROUTES_TO]->(c:Code) WHERE c.name = $n "
                              "RETURN r.path, r.url_name", {"n": n})
            if urls:
                rels.append("  served at URL: " + ", ".join(f"{p} (name='{u}')" for p, u in urls))
            block.append(f"Relationships of `{n}`:\n" + ("\n".join(rels) or "  (none found)"))
            parts.append("\n".join(block))
        return "\n\n".join(parts), sources

    def retrieve(self, question: str, k: int = 5) -> dict:
        """คืน route, context, sources — graph ไม่เจอข้อมูลจะ fallback ไป vector"""
        if self.router.classify(question) == "graph" and self.has_graph:
            g_ctx, g_src = self._graph_context(question)
            if g_ctx:
                v_ctx, v_src = self._vector_context(question, k=2)   # แนบโค้ดประกอบ
                return {"route": "graph", "context": g_ctx + "\n\n" + v_ctx,
                        "sources": _dedupe(g_src + v_src)}
        ctx, src = self._vector_context(question, k)
        return {"route": "vector", "context": ctx, "sources": _dedupe(src)}

    # ─── generation ──────────────────────────────────────────────────────────
    def stream_answer(self, question: str, context: str):
        for chunk in self.chain.stream({"context": context, "question": question}):
            yield chunk.content

    def query(self, question: str) -> dict:
        result = self.retrieve(question)
        result["answer"] = "".join(self.stream_answer(question, result["context"]))
        return result


def _dedupe(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sources:
        key = (s.get("file"), s.get("line"))
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):   # ภาษาไทยบน Windows terminal
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    question = " ".join(sys.argv[1:]) or "Who calls mean?"
    r = HybridRAG().query(question)
    print(f"\n[{r['route']}] {r['answer']}\n")
    for s in r["sources"]:
        print(f"  - {s['name']}  {s['file']}:{s['line']}")