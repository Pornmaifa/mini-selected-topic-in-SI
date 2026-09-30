# 🤖 Local Coding Assistant (Hybrid RAG)
ระบบจะสแกนโค้ด Python (รองรับโปรเจกต์ Django) แล้วเก็บไว้ 2 แบบ:

- **Vector DB (FAISS)** สำหรับคำถามเชิงความหมาย เช่น "ระบบ login ทำงานยังไง"
- **Graph DB (Kuzu)** สำหรับคำถามเชิงความสัมพันธ์ เช่น "view ไหนใช้ model Place บ้าง" หรือ "หน้า /location/5/ ใช้ view อะไร"

Router จะเลือกให้อัตโนมัติว่าคำถามไหนควรค้นแบบไหน แล้วส่ง context ให้ LLM (Ollama) ตอบ ถามได้ทั้งภาษาไทยและภาษาอังกฤษ
วิธีการรัน

cd D:\olama\LLM\project
uv run streamlit run app.py

uv run python setup.py
