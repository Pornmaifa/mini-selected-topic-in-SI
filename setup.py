"""
setup.py — สแกนโค้ด Python (AST) แล้วสร้าง vector_db/ (FAISS) และ graph_db (Kuzu)
รองรับโค้ด Python ทั่วไป และโปรเจกต์ Django (models, forms, urls, views)
รันครั้งแรก และทุกครั้งที่โค้ดใน dataset เปลี่ยน (ปิด Streamlit ก่อนรัน)

    uv run python setup.py                 # ใช้โฟลเดอร์ my_dataset/
    uv run python setup.py faker-master    # หรือระบุโฟลเดอร์เอง
"""
import ast
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from hybrid_rag import BASE_DIR, GRAPH_DB_PATH, MODEL_EMBED, VECTOR_DB_PATH, kuzu

DEFAULT_DATASET = "my_dataset"
SKIP_DIRS = {"venv", "env", "node_modules", "site-packages", "build", "dist",
             "migrations", "static", "staticfiles", "media", "vector_db"}
SKIP_CHUNK_FILES = {"settings.py"}   # มี SECRET_KEY / รหัสผ่าน ไม่ส่งให้ LLM
MAX_AMBIGUOUS_TARGETS = 5            # ชื่อซ้ำเกินนี้ (เช่น get, __str__) ไม่สร้าง edge
MAX_MODULE_CHUNK = 3000
MAX_CODE_IN_GRAPH = 2500

FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
URL_FUNCS = {"path", "re_path", "url"}
REL_FIELDS = {"ForeignKey", "OneToOneField", "ManyToManyField"}


# =============================================================================
# AST helpers
# =============================================================================
def iter_py_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith((".", "__")) and d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def walk_body(node, skip):
    """เดินทุกโหนดข้างใน node แต่ไม่ลงไปในโหนดชนิด skip (เช่น function ซ้อน)"""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        if isinstance(n, skip):
            continue
        yield n
        stack.extend(ast.iter_child_nodes(n))


def iter_defs(node, prefix="", in_class=False):
    """คืน (kind, qualname, node) เช่น ('method', 'Place.__str__', node)"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNC_TYPES):
            qual = prefix + child.name
            yield ("method" if in_class else "function"), qual, child
            yield from iter_defs(child, qual + ".", False)
        elif isinstance(child, ast.ClassDef):
            qual = prefix + child.name
            yield "class", qual, child
            yield from iter_defs(child, qual + ".", True)
        else:
            yield from iter_defs(child, prefix, in_class)


def segment(source, node):
    return ast.get_source_segment(source, node) or ""


def class_chunk(source, qual, node):
    """หัวคลาส + field + class Meta (ไม่รวมตัวเมธอด) — เหมาะกับ model / form"""
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    parts = [f"class {qual}({bases}):"]
    parts += ["    " + segment(source, s) for s in node.body if not isinstance(s, FUNC_TYPES)]
    methods = [s.name for s in node.body if isinstance(s, FUNC_TYPES)]
    if methods:
        parts.append("    # methods: " + ", ".join(methods))
    return "\n".join(parts)


def fk_targets(node):
    """ForeignKey / OneToOneField / ManyToManyField ชี้ไปที่ model ไหน"""
    out = set()
    for s in node.body:
        value = getattr(s, "value", None)
        if not (isinstance(s, (ast.Assign, ast.AnnAssign)) and isinstance(value, ast.Call)
                and call_name(value.func) in REL_FIELDS):
            continue
        args = list(value.args[:1]) + [k.value for k in value.keywords if k.arg == "to"]
        for a in args:
            if isinstance(a, ast.Name):
                out.add(a.id)
            elif isinstance(a, ast.Constant) and isinstance(a.value, str):
                out.add(node.name if a.value == "self" else a.value.split(".")[-1])
    return out


def list_elements(value):
    if isinstance(value, ast.List):
        return list(value.elts)
    if isinstance(value, ast.BinOp):
        return list_elements(value.left) + list_elements(value.right)
    return []


def parse_urls(tree):
    """อ่าน urlpatterns: คืน routes [(pattern, url_name, view)] และ includes [(prefix, module)]"""
    routes, includes = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "urlpatterns" for t in targets):
            continue
        for el in list_elements(node.value):
            if not (isinstance(el, ast.Call) and call_name(el.func) in URL_FUNCS and len(el.args) >= 2):
                continue
            pat, target = el.args[0], el.args[1]
            if not (isinstance(pat, ast.Constant) and isinstance(pat.value, str)):
                continue
            url_name = next((k.value.value for k in el.keywords
                             if k.arg == "name" and isinstance(k.value, ast.Constant)), "")
            if isinstance(target, ast.Call) and call_name(target.func) == "include":
                if target.args and isinstance(target.args[0], ast.Constant):
                    includes.append((pat.value, target.args[0].value))
                continue
            if isinstance(target, ast.Call) and call_name(target.func) == "as_view":
                view = call_name(target.func.value)          # MyView.as_view()
            else:
                view = call_name(target)                     # views.func / func
            if view:
                routes.append((pat.value, url_name, view))
    return routes, includes


def module_chunk(source, tree):
    """docstring + ค่าระดับโมดูล (เช่น urlpatterns)"""
    keep = [s for s in tree.body
            if isinstance(s, (ast.Assign, ast.AugAssign, ast.AnnAssign))
            or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                and isinstance(s.value.value, str))]
    return "\n".join(segment(source, s) for s in keep)[:MAX_MODULE_CHUNK]


# =============================================================================
# Parse ทั้งโปรเจกต์
# =============================================================================
def parse_project(root: Path) -> dict:
    items, modules, url_files = [], [], []
    for path in iter_py_files(root):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError, ValueError) as e:
            print(f"  ข้าม {path}: {e}")
            continue
        rel = path.relative_to(root).as_posix()
        lines = source.splitlines()

        for kind, qual, node in iter_defs(tree):
            if kind == "class" and node.name == "Meta":   # รวมอยู่ใน chunk ของคลาสแม่แล้ว
                continue
            item = {"id": f"{rel}:{node.lineno}", "name": node.name, "qualname": qual,
                    "kind": kind, "file": rel, "line": node.lineno}
            if kind == "class":
                item["code"] = class_chunk(source, qual, node)
                body = list(walk_body(node, FUNC_TYPES))       # รวม class Meta
                item["calls"] = set()
                item["fk"] = fk_targets(node)
            else:
                start = min([d.lineno for d in node.decorator_list] + [node.lineno])  # รวม @decorator
                item["code"] = "\n".join(lines[start - 1:node.end_lineno])
                body = list(walk_body(node, FUNC_TYPES + (ast.ClassDef,)))
                body += list(node.decorator_list)
                item["calls"] = {call_name(n.func) for n in body if isinstance(n, ast.Call)}
                item["calls"] |= {call_name(d) for d in node.decorator_list}   # @admin_required
                item["calls"] -= {None}
                item["fk"] = set()
            item["refs"] = {n.id for n in body if isinstance(n, ast.Name)}
            items.append(item)

        if path.name not in SKIP_CHUNK_FILES:
            text = module_chunk(source, tree)
            if text.strip():
                modules.append({"file": rel, "code": text})

        routes, includes = parse_urls(tree)
        if routes or includes:
            dotted = rel[:-3].replace("/", ".")
            url_files.append({"file": rel, "module": dotted, "routes": routes, "includes": includes})

    return {"items": items, "modules": modules, "routes": resolve_url_paths(url_files)}


def resolve_url_paths(url_files: list[dict]) -> list[tuple]:
    """ต่อ prefix จาก include() ให้เป็น path เต็ม: [(path, url_name, view, urls_file)]"""
    by_module = {u["module"]: u for u in url_files}

    def find(target):
        return next((m for m in by_module if m == target or m.endswith("." + target)), None)

    children = {find(t) for u in url_files for _, t in u["includes"]} - {None}
    result = []

    def dfs(mod, prefix, seen):
        u = by_module[mod]
        for pat, name, view in u["routes"]:
            result.append(("/" + prefix + pat, name, view, u["file"]))
        for pat, target in u["includes"]:
            child = find(target)
            if child and child not in seen:
                dfs(child, prefix + pat, seen | {child})

    for mod in sorted(m for m in by_module if m not in children):
        dfs(mod, "", {mod})
    return result


# =============================================================================
# Vector DB
# =============================================================================
def build_vector_db(project: dict) -> None:
    docs = []
    for it in project["items"]:
        if PurePosixPath(it["file"]).name in SKIP_CHUNK_FILES:
            continue
        docs.append(Document(
            page_content=f"# {it['kind']} {it['qualname']} in {it['file']}\n{it['code']}",
            metadata={"name": it["qualname"], "kind": it["kind"],
                      "file": it["file"], "line": it["line"]}))
    for m in project["modules"]:
        docs.append(Document(
            page_content=f"# module-level code in {m['file']}\n{m['code']}",
            metadata={"name": "<module>", "kind": "module", "file": m["file"], "line": 1}))

    print(f"กำลังสร้าง Vector DB จาก {len(docs)} chunks (อาจใช้เวลาหลายนาที)...")
    FAISS.from_documents(docs, OllamaEmbeddings(model=MODEL_EMBED)).save_local(str(VECTOR_DB_PATH))
    print("✅ Vector DB (FAISS) สำเร็จ")


# =============================================================================
# Graph DB
# =============================================================================
def remove_old_graph() -> None:
    # Kuzu เวอร์ชันใหม่เป็นไฟล์ (+ .wal), เวอร์ชันเก่าเป็น folder — ลบได้ทั้งสองแบบ
    for p in GRAPH_DB_PATH.parent.glob(GRAPH_DB_PATH.name + "*"):
        shutil.rmtree(p) if p.is_dir() else p.unlink()


def build_graph_db(project: dict) -> None:
    if kuzu is None:
        print("⚠️ ไม่มี kuzu — ข้าม Graph DB (ใช้ได้แค่ vector mode)")
        return
    print("กำลังสร้าง Graph DB...")
    items = project["items"]
    by_name = defaultdict(list)
    for it in items:
        by_name[it["name"]].append(it)

    def resolve(name, kinds, near_file):
        cands = [c for c in by_name.get(name, []) if c["kind"] in kinds]
        if len(cands) > 1:   # ชื่อซ้ำ: เลือกตัวที่อยู่ app/โฟลเดอร์เดียวกันก่อน
            near = PurePosixPath(near_file).parent
            same = [c for c in cands if PurePosixPath(c["file"]).parent == near]
            cands = same or cands
        return [] if len(cands) > MAX_AMBIGUOUS_TARGETS else [c["id"] for c in cands]

    edges = {"CALLS": set(), "USES": set(), "FOREIGN_KEY": set()}
    for it in items:
        for n in it["calls"]:
            edges["CALLS"].update((it["id"], t) for t in resolve(n, {"function", "method"}, it["file"]))
        for n in it["fk"]:
            edges["FOREIGN_KEY"].update((it["id"], t) for t in resolve(n, {"class"}, it["file"]))
        for n in it["refs"] - it["fk"]:
            edges["USES"].update((it["id"], t) for t in resolve(n, {"class"}, it["file"]) if t != it["id"])

    remove_old_graph()
    db = kuzu.Database(str(GRAPH_DB_PATH))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Code(id STRING, name STRING, qualname STRING, kind STRING, "
                 "file STRING, line INT64, code STRING, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE Route(path STRING, url_name STRING, PRIMARY KEY(path))")
    for rel in edges:
        conn.execute(f"CREATE REL TABLE {rel}(FROM Code TO Code)")
    conn.execute("CREATE REL TABLE ROUTES_TO(FROM Route TO Code)")

    conn.execute("BEGIN TRANSACTION")
    for it in items:
        conn.execute("CREATE (:Code {id: $id, name: $name, qualname: $q, kind: $kind, "
                     "file: $file, line: $line, code: $code})",
                     {"id": it["id"], "name": it["name"], "q": it["qualname"], "kind": it["kind"],
                      "file": it["file"], "line": it["line"],
                      "code": it["code"][:MAX_CODE_IN_GRAPH]})
    for rel, pairs in edges.items():
        for a, b in pairs:
            conn.execute(f"MATCH (a:Code {{id: $a}}), (b:Code {{id: $b}}) CREATE (a)-[:{rel}]->(b)",
                         {"a": a, "b": b})

    seen_routes, route_edges = set(), set()
    for path, url_name, view, urls_file in project["routes"]:
        if path not in seen_routes:
            conn.execute("CREATE (:Route {path: $p, url_name: $u})", {"p": path, "u": url_name})
            seen_routes.add(path)
        for t in resolve(view, {"function", "class"}, urls_file):
            if (path, t) not in route_edges:
                conn.execute("MATCH (r:Route {path: $p}), (c:Code {id: $t}) CREATE (r)-[:ROUTES_TO]->(c)",
                             {"p": path, "t": t})
                route_edges.add((path, t))
    conn.execute("COMMIT")
    conn.close()
    db.close()
    print(f"✅ Graph DB (Kuzu) สำเร็จ: {len(items)} functions/classes, "
          f"{len(edges['CALLS'])} calls, {len(edges['USES'])} uses, "
          f"{len(edges['FOREIGN_KEY'])} foreign keys, {len(seen_routes)} urls")


# =============================================================================
# Main
# =============================================================================
def resolve_root(name: str) -> Path | None:
    """หาโฟลเดอร์ทั้งจากที่รันอยู่ และจากตำแหน่งไฟล์ setup.py"""
    for c in (Path(name), BASE_DIR / name):
        if c.is_dir():
            return c.resolve()
    return None


def build_databases(dataset: str) -> None:
    root = resolve_root(dataset)
    if root is None:
        print(f"❌ ไม่พบโฟลเดอร์ '{dataset}' (รันอยู่ที่: {Path.cwd()})")
        print("   วางโฟลเดอร์โค้ดไว้ข้าง setup.py หรือใส่ path เต็ม")
        return
    print(f"กำลังสแกนโค้ดใน: {root}")
    project = parse_project(root)
    if not project["items"] and not project["modules"]:
        print("❌ ไม่พบโค้ดใน .py เลย — ตรวจว่าชี้ไปที่โฟลเดอร์โค้ดถูกต้อง")
        return
    build_vector_db(project)
    build_graph_db(project)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):   # ภาษาไทยบน Windows terminal
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build_databases(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATASET)