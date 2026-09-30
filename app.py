"""
app.py — หน้าจอ Streamlit Chat
รัน:  uv run streamlit run app.py   (ต้องรัน setup.py ก่อน)
"""
import streamlit as st

from hybrid_rag import MODEL_LLM, HybridRAG

st.set_page_config(page_title="Pornmaifa Local Coding Assistant", page_icon="🤖", layout="wide")


@st.cache_resource(show_spinner="Loading databases...")
def get_rag() -> HybridRAG:
    return HybridRAG()   # โหลด FAISS + Kuzu ครั้งเดียว ใช้ซ้ำทุก query


try:
    rag = get_rag()
except FileNotFoundError as e:
    st.error(str(e))
    st.code("uv run python setup.py my_dataset")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []


def show_meta(route: str, sources: list) -> None:
    st.caption("Mode: 🔗 Graph" if route == "graph" else "Mode: 🔍 Vector")
    if sources:
        with st.expander(f"📎 Sources ({len(sources)})"):
            for s in sources:
                st.markdown(f"- `{s.get('name', '?')}` — {s.get('file', '?')}:{s.get('line', '?')}")


with st.sidebar:
    st.title("🤖 Pornmaifa Assistant")
    st.markdown("Ask about your indexed codebase")
    st.caption(f"Model: {MODEL_LLM}")
    st.caption("Graph DB: ✅ พร้อมใช้" if rag.has_graph else "Graph DB: ⚠️ ไม่มี (vector only)")
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            show_meta(m["route"], m["sources"])

if prompt := st.chat_input("Ask about your codebase..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        route, sources = "vector", []
        try:
            with st.spinner("Searching codebase..."):
                result = rag.retrieve(prompt)
            route, sources = result["route"], result["sources"]
            answer = st.write_stream(rag.stream_answer(prompt, result["context"]))
        except Exception as e:  # ส่วนใหญ่คือ Ollama ไม่ได้รัน / ไม่มี model
            answer = f"❌ เรียก Ollama ไม่สำเร็จ (เปิด Ollama อยู่หรือเปล่า?)\n\n`{e}`"
            st.error(answer)
        show_meta(route, sources)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "route": route, "sources": sources})
