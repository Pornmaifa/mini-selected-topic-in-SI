# 🤖 Local Coding Assistant (Hybrid RAG)

ผู้ช่วยตอบคำถามเกี่ยวกับ codebase ที่รันบนเครื่องตัวเองทั้งหมด ไม่ต้องใช้ API key และไม่ส่งโค้ดออกไปนอกเครื่อง

ระบบจะสแกนโค้ด Python (รองรับโปรเจกต์ Django) แล้วเก็บไว้ 2 แบบ:

- **Vector DB (FAISS)** สำหรับคำถามเชิงความหมาย เช่น "ระบบ login ทำงานยังไง"
- **Graph DB (Kuzu)** สำหรับคำถามเชิงความสัมพันธ์ เช่น "view ไหนใช้ model Place บ้าง" หรือ "หน้า /location/5/ ใช้ view อะไร"

Router จะเลือกให้อัตโนมัติว่าคำถามไหนควรค้นแบบไหน แล้วส่ง context ให้ LLM (Ollama) ตอบ ถามได้ทั้งภาษาไทยและภาษาอังกฤษ

## สิ่งที่ต้องมี

| โปรแกรม | ใช้ทำอะไร | ดาวน์โหลด |
|---|---|---|
| Git | clone โปรเจกต์ | https://git-scm.com |
| uv | จัดการ Python และ package | https://docs.astral.sh/uv |
| Ollama | รัน LLM บนเครื่อง | https://ollama.com |

ไม่ต้องติดตั้ง Python เอง เพราะ uv จะโหลด Python 3.12 ให้อัตโนมัติ

แนะนำ RAM อย่างน้อย 8 GB (ถ้าจะใช้ model 7b ควรมี 16 GB)

## วิธีติดตั้ง

คำสั่งด้านล่างใช้ **Windows PowerShell** (macOS/Linux ใช้ได้เหมือนกัน ยกเว้นขั้นที่ 1)

### 1. ติดตั้ง uv (ถ้ายังไม่มี)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

ติดตั้งเสร็จแล้วให้ปิด terminal แล้วเปิดใหม่ จากนั้นตรวจด้วย `uv --version`

### 2. Clone โปรเจกต์

```powershell
git clone https://github.com/Pornmaifa/mini-selected-topic-in-SI.git
cd mini-selected-topic-in-SI
```

### 3. ติดตั้ง package

```powershell
uv sync
```

คำสั่งนี้จะสร้าง `.venv` และติดตั้งทุกอย่างตาม `uv.lock` ให้ ไม่ต้อง activate venv เอง เพราะคำสั่งต่อจากนี้ใช้ `uv run` นำหน้า

### 4. ดาวน์โหลด AI model

เปิดแอป Ollama ก่อน (หรือรัน `ollama serve` ใน terminal อีกหน้าต่าง) แล้วรัน:

```powershell
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text
```

### 5. สร้าง database จากโค้ด

```powershell
uv run python setup.py
```

คำสั่งนี้จะสแกนโค้ดในโฟลเดอร์ `my_dataset/` แล้วสร้าง `vector_db/` และ `graph_db` ถ้าโค้ดเยอะอาจใช้เวลาหลายนาที เมื่อสำเร็จจะขึ้น:

```
✅ Vector DB (FAISS) สำเร็จ
✅ Graph DB (Kuzu) สำเร็จ: ... functions/classes, ... calls, ... uses, ... foreign keys, ... urls
```

### 6. เปิดหน้าเว็บ

```powershell
uv run streamlit run app.py
```

browser จะเปิดขึ้นมาเอง ถ้าไม่เปิด ให้เข้า http://localhost:8501

## การใช้งานครั้งถัดไป

```powershell
cd mini-selected-topic-in-SI
uv run streamlit run app.py
```

ต้องเปิด Ollama ค้างไว้ทุกครั้งที่ใช้งาน

## ใช้กับโค้ดของตัวเอง

1. เอาโฟลเดอร์โค้ด Python ไปวางใน `my_dataset/` (ถ้าเป็น Django ให้วางทั้งโปรเจกต์ที่มี `manage.py`)
2. ปิดหน้าเว็บด้วย `Ctrl + C`
3. สร้าง database ใหม่แล้วเปิดหน้าเว็บ:

```powershell
uv run python setup.py
uv run streamlit run app.py
```

หรือจะชี้ไปที่โฟลเดอร์อื่นโดยไม่ต้องย้ายไฟล์ก็ได้:

```powershell
uv run python setup.py D:\path\to\your-code
```

ระบบจะข้าม `settings.py`, `migrations/`, `static/`, `media/` และ `.venv/` ให้อัตโนมัติ จึงไม่ส่งรหัสลับใน settings ให้ LLM

## โครงสร้างโปรเจกต์

```
mini-selected-topic-in-SI/
├── setup.py          # สแกนโค้ดด้วย AST แล้วสร้าง vector_db และ graph_db
├── hybrid_rag.py     # Question Router + Hybrid RAG + ค่า config (ชื่อ model, path)
├── app.py            # หน้าเว็บ Streamlit
├── my_dataset/       # โค้ดที่ต้องการให้ AI วิเคราะห์
│   └── booking_system/   # ตัวอย่าง: ระบบจองสถานที่ (Django)
├── pyproject.toml    # รายชื่อ package
└── uv.lock           # เวอร์ชัน package ที่ล็อกไว้
```

`vector_db/` และ `graph_db` ไม่ได้อยู่ใน repo ต้องสร้างเองด้วยขั้นที่ 5

## ตัวอย่างคำถาม (กับ booking_system)

| คำถาม | โหมด |
|---|---|
| ระบบ login ทำงานยังไง | 🔍 Vector |
| Place model มี field อะไรบ้าง | 🔗 Graph |
| view ไหนใช้ model Place บ้าง | 🔗 Graph |
| model ไหนมี foreign key ไปที่ Place | 🔗 Graph |
| มี url อะไรบ้าง | 🔗 Graph |
| หน้า /location/5/ ใช้ view อะไร | 🔗 Graph |
| view ไหนที่ใช้ admin_required บ้าง | 🔗 Graph |
| ระบบมีการชำระเงินไหม | ควรตอบว่าไม่พบในโค้ด |

กด **📎 Sources** ใต้คำตอบเพื่อดูว่า AI อ้างอิงไฟล์และบรรทัดไหน

## ตั้งค่า

แก้ได้ที่ส่วนบนของ `hybrid_rag.py`:

```python
MODEL_LLM = "qwen2.5-coder:3b"   # เปลี่ยนเป็น "qwen2.5-coder:7b" ถ้าเครื่องไหว จะตอบแม่นขึ้น
MODEL_EMBED = "nomic-embed-text"
NUM_CTX = 8192
```

ถ้าเปลี่ยน model ต้อง `ollama pull <ชื่อ model>` ก่อน และถ้าเปลี่ยน `MODEL_EMBED` ต้องรัน `setup.py` ใหม่

## แก้ปัญหาที่พบบ่อย
# 🤖 Local Coding Assistant (Hybrid RAG)

ผู้ช่วยตอบคำถามเกี่ยวกับ codebase ที่รันบนเครื่องตัวเองทั้งหมด ไม่ต้องใช้ API key และไม่ส่งโค้ดออกไปนอกเครื่อง

ระบบจะสแกนโค้ด Python (รองรับโปรเจกต์ Django) แล้วเก็บไว้ 2 แบบ:

- **Vector DB (FAISS)** สำหรับคำถามเชิงความหมาย เช่น "ระบบ login ทำงานยังไง"
- **Graph DB (Kuzu)** สำหรับคำถามเชิงความสัมพันธ์ เช่น "view ไหนใช้ model Place บ้าง" หรือ "หน้า /location/5/ ใช้ view อะไร"

Router จะเลือกให้อัตโนมัติว่าคำถามไหนควรค้นแบบไหน แล้วส่ง context ให้ LLM (Ollama) ตอบ ถามได้ทั้งภาษาไทยและภาษาอังกฤษ

## สิ่งที่ต้องมี

| โปรแกรม | ใช้ทำอะไร | ดาวน์โหลด |
|---|---|---|
| Git | clone โปรเจกต์ | https://git-scm.com |
| uv | จัดการ Python และ package | https://docs.astral.sh/uv |
| Ollama | รัน LLM บนเครื่อง | https://ollama.com |

ไม่ต้องติดตั้ง Python เอง เพราะ uv จะโหลด Python 3.12 ให้อัตโนมัติ

แนะนำ RAM อย่างน้อย 8 GB (ถ้าจะใช้ model 7b ควรมี 16 GB)

## วิธีติดตั้ง

คำสั่งด้านล่างใช้ **Windows PowerShell** (macOS/Linux ใช้ได้เหมือนกัน ยกเว้นขั้นที่ 1)

### 1. ติดตั้ง uv (ถ้ายังไม่มี)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

ติดตั้งเสร็จแล้วให้ปิด terminal แล้วเปิดใหม่ จากนั้นตรวจด้วย `uv --version`

### 2. Clone โปรเจกต์

```powershell
git clone https://github.com/Pornmaifa/mini-selected-topic-in-SI.git
cd mini-selected-topic-in-SI
```

### 3. ติดตั้ง package

```powershell
uv sync
```

คำสั่งนี้จะสร้าง `.venv` และติดตั้งทุกอย่างตาม `uv.lock` ให้ ไม่ต้อง activate venv เอง เพราะคำสั่งต่อจากนี้ใช้ `uv run` นำหน้า

### 4. ดาวน์โหลด AI model

เปิดแอป Ollama ก่อน (หรือรัน `ollama serve` ใน terminal อีกหน้าต่าง) แล้วรัน:

```powershell
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text
```

### 5. สร้าง database จากโค้ด

```powershell
uv run python setup.py
```

คำสั่งนี้จะสแกนโค้ดในโฟลเดอร์ `my_dataset/` แล้วสร้าง `vector_db/` และ `graph_db` ถ้าโค้ดเยอะอาจใช้เวลาหลายนาที เมื่อสำเร็จจะขึ้น:

```
✅ Vector DB (FAISS) สำเร็จ
✅ Graph DB (Kuzu) สำเร็จ: ... functions/classes, ... calls, ... uses, ... foreign keys, ... urls
```

### 6. เปิดหน้าเว็บ

```powershell
uv run streamlit run app.py
```

browser จะเปิดขึ้นมาเอง ถ้าไม่เปิด ให้เข้า http://localhost:8501

## การใช้งานครั้งถัดไป

```powershell
cd mini-selected-topic-in-SI
uv run streamlit run app.py
```

ต้องเปิด Ollama ค้างไว้ทุกครั้งที่ใช้งาน

## ใช้กับโค้ดของตัวเอง

1. เอาโฟลเดอร์โค้ด Python ไปวางใน `my_dataset/` (ถ้าเป็น Django ให้วางทั้งโปรเจกต์ที่มี `manage.py`)
2. ปิดหน้าเว็บด้วย `Ctrl + C`
3. สร้าง database ใหม่แล้วเปิดหน้าเว็บ:

```powershell
uv run python setup.py
uv run streamlit run app.py
```

หรือจะชี้ไปที่โฟลเดอร์อื่นโดยไม่ต้องย้ายไฟล์ก็ได้:

```powershell
uv run python setup.py D:\path\to\your-code
```

ระบบจะข้าม `settings.py`, `migrations/`, `static/`, `media/` และ `.venv/` ให้อัตโนมัติ จึงไม่ส่งรหัสลับใน settings ให้ LLM

## โครงสร้างโปรเจกต์

```
mini-selected-topic-in-SI/
├── setup.py          # สแกนโค้ดด้วย AST แล้วสร้าง vector_db และ graph_db
├── hybrid_rag.py     # Question Router + Hybrid RAG + ค่า config (ชื่อ model, path)
├── app.py            # หน้าเว็บ Streamlit
├── my_dataset/       # โค้ดที่ต้องการให้ AI วิเคราะห์
│   └── booking_system/   # ตัวอย่าง: ระบบจองสถานที่ (Django)
├── pyproject.toml    # รายชื่อ package
└── uv.lock           # เวอร์ชัน package ที่ล็อกไว้
```

`vector_db/` และ `graph_db` ไม่ได้อยู่ใน repo ต้องสร้างเองด้วยขั้นที่ 5

## ตัวอย่างคำถาม (กับ booking_system)

| คำถาม | โหมด |
|---|---|
| ระบบ login ทำงานยังไง | 🔍 Vector |
| Place model มี field อะไรบ้าง | 🔗 Graph |
| view ไหนใช้ model Place บ้าง | 🔗 Graph |
| model ไหนมี foreign key ไปที่ Place | 🔗 Graph |
| มี url อะไรบ้าง | 🔗 Graph |
| หน้า /location/5/ ใช้ view อะไร | 🔗 Graph |
| view ไหนที่ใช้ admin_required บ้าง | 🔗 Graph |
| ระบบมีการชำระเงินไหม | ควรตอบว่าไม่พบในโค้ด |

กด **📎 Sources** ใต้คำตอบเพื่อดูว่า AI อ้างอิงไฟล์และบรรทัดไหน

## ตั้งค่า

แก้ได้ที่ส่วนบนของ `hybrid_rag.py`:

```python
MODEL_LLM = "qwen2.5-coder:3b"   # เปลี่ยนเป็น "qwen2.5-coder:7b" ถ้าเครื่องไหว จะตอบแม่นขึ้น
MODEL_EMBED = "nomic-embed-text"
NUM_CTX = 8192
```

ถ้าเปลี่ยน model ต้อง `ollama pull <ชื่อ model>` ก่อน และถ้าเปลี่ยน `MODEL_EMBED` ต้องรัน `setup.py` ใหม่

## แก้ปัญหาที่พบบ่อย

| อาการ | วิธีแก้ |
|---|---|
| `can't open file ... setup.py` | ยังไม่ได้ `cd` เข้าโฟลเดอร์โปรเจกต์ |
| หน้าเว็บขึ้น `ไม่พบ vector_db/` | ยังไม่ได้รัน `uv run python setup.py` |
| `❌ เรียก Ollama ไม่สำเร็จ` หรือ `Connection refused` | เปิดแอป Ollama หรือรัน `ollama serve` |
| `model "..." not found` | รัน `ollama pull` ตามขั้นที่ 4 |
| `ModuleNotFoundError` | รัน `uv sync` ใหม่ |
| รัน `setup.py` แล้วลบ `graph_db` ไม่ได้ | ปิด Streamlit (`Ctrl + C`) ก่อน เพราะหน้าเว็บเปิดไฟล์ค้างไว้ |
| ภาษาไทยใน terminal เป็นตัวแปลก ๆ | รัน `chcp 65001` ก่อน |
| Sidebar ขึ้น `Graph DB: ⚠️ ไม่มี` | รัน `setup.py` ใหม่ ระบบจะยังตอบได้แต่ใช้แค่ Vector |

## หมายเหตุ

`my_dataset/booking_system` เป็นโค้ดตัวอย่างสำหรับให้ AI วิเคราะห์เท่านั้น รันเป็นเว็บ Django โดยตรงไม่ได้ เพราะเอาค่าลับอย่าง `SECRET_KEY` และ Google OAuth ออกแล้ว

## เทคโนโลยีที่ใช้

LangChain · Ollama · FAISS · Kuzu · Streamlit · Python AST · uv
| อาการ | วิธีแก้ |
|---|---|
| `can't open file ... setup.py` | ยังไม่ได้ `cd` เข้าโฟลเดอร์โปรเจกต์ |
| หน้าเว็บขึ้น `ไม่พบ vector_db/` | ยังไม่ได้รัน `uv run python setup.py` |
| `❌ เรียก Ollama ไม่สำเร็จ` หรือ `Connection refused` | เปิดแอป Ollama หรือรัน `ollama serve` |
| `model "..." not found` | รัน `ollama pull` ตามขั้นที่ 4 |
| `ModuleNotFoundError` | รัน `uv sync` ใหม่ |
| รัน `setup.py` แล้วลบ `graph_db` ไม่ได้ | ปิด Streamlit (`Ctrl + C`) ก่อน เพราะหน้าเว็บเปิดไฟล์ค้างไว้ |
| ภาษาไทยใน terminal เป็นตัวแปลก ๆ | รัน `chcp 65001` ก่อน |
| Sidebar ขึ้น `Graph DB: ⚠️ ไม่มี` | รัน `setup.py` ใหม่ ระบบจะยังตอบได้แต่ใช้แค่ Vector |

## หมายเหตุ

`my_dataset/booking_system` เป็นโค้ดตัวอย่างสำหรับให้ AI วิเคราะห์เท่านั้น รันเป็นเว็บ Django โดยตรงไม่ได้ เพราะเอาค่าลับอย่าง `SECRET_KEY` และ Google OAuth ออกแล้ว

## เทคโนโลยีที่ใช้

LangChain · Ollama · FAISS · Kuzu · Streamlit · Python AST · uv
