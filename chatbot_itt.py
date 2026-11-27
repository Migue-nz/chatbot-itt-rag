import re
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader

#region Carga de documentos (en el código del profe: #region Urls)
# El profe cargaba páginas web con WebBaseLoader.
# Nosotros leemos los PDF y TXT oficiales guardados en la carpeta docs/.
DOCS_DIR = Path("docs")

# AJUSTE 1: título descriptivo de cada documento
TITULOS = {
    "inscripcion_nuevo_ingreso_ago-dic-2026.txt": "ITT - Proceso de inscripción para aspirantes aceptados de nuevo ingreso: qué hacer después de salir aceptado (agosto-diciembre 2026)",
    "oferta_educativa.txt": "ITT - Oferta educativa: carreras, perfil de egreso, servicio social, residencia profesional e inglés",
    "Convocatoria-Reinscripción-AGOSTO-2026.pdf": "ITT - Convocatoria de reinscripción para estudiantes (agosto-diciembre 2026)",
    "ITTEPIC-AC-PO-002-01_CALENDARIO_ESCOLAR_AGOSTO_DICIEMBRE_2026.pdf": "ITT - Calendario escolar agosto-diciembre 2026: fechas de actividades",
    "TECNM Manual_de_Lineamientos_TecNM SinAnxs.pdf": "TecNM - Manual de Lineamientos Académico-Administrativos (norma general)",
}


def limpiar(texto):
    texto = texto.replace("\u200b", "")                 # quita caracteres invisibles (convocatoria exportada de Google Docs)
    texto = re.sub(r"\s*\d+(\.\d+)?\s*KB", "", texto)   # quita los tamaños de archivo "209.1 KB" de la oferta educativa
    texto = re.sub(r"\n{3,}", "\n\n", texto)            # junta saltos de línea repetidos
    return texto

docs_list = []
for ruta in sorted(DOCS_DIR.rglob("*")):
    if ruta.suffix.lower() == ".pdf":
        docs = PyPDFLoader(str(ruta)).load()             # un Document por página
    elif ruta.suffix.lower() == ".txt":
        docs = TextLoader(str(ruta), encoding="utf-8").load()
    else:
        continue                                         # ignora otros archivos (ej. FUENTES.md)
    for d in docs:
        d.page_content = limpiar(d.page_content)
        d.metadata["fuente"] = ruta.name                 # guardamos de qué archivo viene, para citarlo después
        d.metadata["titulo"] = TITULOS.get(ruta.name, ruta.name)   # AJUSTE 1
    docs_list.extend(docs)
    print(f"  {ruta.name}: {len(docs)} partes")

print("Documentos cargados:", len(docs_list))
#endregion

from langchain_text_splitters import RecursiveCharacterTextSplitter

#region División en fragmentos (igual que el código del profe)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
doc_splits = text_splitter.split_documents(docs_list)
# AJUSTE 1: cada fragmento empieza con el título de su documento
for s in doc_splits:
    s.page_content = f"[{s.metadata['titulo']}]\n{s.page_content}"
print("Fragmentos generados:", len(doc_splits))

# Muestra un fragmento de ejemplo para revisar que el texto se ve limpio
ejemplo = doc_splits[5]
print("\n--- Fragmento de ejemplo ---")
print("Fuente:", ejemplo.metadata["fuente"])
print(ejemplo.page_content[:500])
#endregion


from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

#region Embeddings y base vectorial (en el código del profe: #region Embeddings locales)
# Cambio justificado: usamos BGE-M3 servido por LM Studio en lugar de paraphrase-multilingual-mpnet.
embeddings = OpenAIEmbeddings(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",                 # LM Studio no pide clave real, pero el campo es obligatorio
    model="text-embedding-bge-m3",
    check_embedding_ctx_length=False,    # manda el texto tal cual (LM Studio no usa los tokens de OpenAI)
    chunk_size=64,                       # manda los fragmentos en lotes de 64
)

# Mejora: guardamos la base en disco para no recalcular los 662 vectores en cada arranque.
CHROMA_DIR = "chroma_itt"
if Path(CHROMA_DIR).exists():
    vectorstore = Chroma(collection_name="rag_itt", embedding_function=embeddings, persist_directory=CHROMA_DIR)
    print("Base vectorial cargada desde disco:", vectorstore._collection.count(), "vectores")
else:
    vectorstore = Chroma.from_documents(documents=doc_splits, collection_name="rag_itt",
                                        embedding=embeddings, persist_directory=CHROMA_DIR)
    print("Base vectorial creada:", vectorstore._collection.count(), "vectores")

retriever = vectorstore.as_retriever(search_kwargs={"k": 4})   # trae los 4 fragmentos más parecidos (igual que el profe)

# Prueba de búsqueda
pregunta = "¿El curso de inducción es obligatorio?"
print(f"\n=== Prueba de búsqueda: {pregunta} ===")
for i, d in enumerate(retriever.invoke(pregunta)):
    print(f"\n[{i+1}] Fuente: {d.metadata['fuente']}")
    print(d.page_content[:300])
#endregion


from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

#region Modelo de lenguaje (en el código del profe: #region gemma)
llm = ChatOpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
    model="qwen2.5-7b-instruct",   # cambio: Qwen en lugar de google/gemma-4-e4b
    temperature=0                  # igual que el profe: 0 para evitar respuestas inventadas
)
#endregion

#region Prompt SIN RAG (igual que el profe, adaptado al ITT)
template_simple = """
Eres TecBot, el asistente virtual del Instituto Tecnológico de Tepic.
Explícalo en texto plano y en máximo 150 palabras.
Responde únicamente utilizando conocimiento que conozcas con certeza.
Si no conoces la respuesta responde exactamente:
"No dispongo de información suficiente para responder."
Pregunta:
{question}
Respuesta:
"""
prompt_simple = ChatPromptTemplate.from_template(template_simple)
chain_simple = ({"question": RunnablePassthrough()}
        | prompt_simple
        | llm
        | StrOutputParser()
)
#endregion

#region Prompt CON RAG (nuestro system prompt v1)
# Leemos el system prompt desde el archivo; duplicamos las llaves para que LangChain no las confunda con variables.
SYSTEM_PROMPT = Path("prompts/system_prompt_v1.md").read_text(encoding="utf-8").replace("{", "{{").replace("}", "}}")

def formatear_contexto(docs):
    # Mejora: cada fragmento lleva el nombre de su documento, para que el bot pueda citar la fuente.
    return "\n\n".join(f"[Documento: {d.metadata['fuente']}]\n{d.page_content}" for d in docs)

prompt_rag = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}")
])
chain_rag = ({"context": retriever | formatear_contexto, "question": RunnablePassthrough()}
        | prompt_rag
        | llm
        | StrOutputParser()
)
#endregion

# Prueba rápida: la misma pregunta sin RAG y con RAG
pregunta = "¿El curso de inducción es obligatorio?"
print("\n=========== SIN RAG ===========")
print(chain_simple.invoke(pregunta))
print("\n=========== CON RAG ===========")
print(chain_rag.invoke(pregunta))


#zxcvbnm

import gradio as gr

#region Funciones de la interfaz
def responder(mensaje, historial):
    # Pestaña 1: el asistente responde siempre con RAG
    return chain_rag.invoke(mensaje)

def comparar(pregunta):
    # Pestaña 2: igual que el profe, sin RAG vs con RAG y los fragmentos recuperados
    respuesta_simple = chain_simple.invoke(pregunta)
    respuesta_rag = chain_rag.invoke(pregunta)
    docs = retriever.invoke(pregunta)
    contexto = ""
    for i, d in enumerate(docs):
        contexto += f"\n\n========== Fragmento {i+1} | {d.metadata['fuente']} ==========\n"
        contexto += d.page_content[:1200]
    return (respuesta_simple, respuesta_rag, contexto)
#endregion

#region Interfaz (en el código del profe: #region Interfaz)
with gr.Blocks(title="TecBot - Asistente ITT") as demo:
    gr.Markdown("# TecBot — Asistente Institucional del Instituto Tecnológico de Tepic")

    with gr.Tab("Asistente"):
        gr.ChatInterface(
            fn=responder,
            examples=[
                "Ya salí aceptado, ¿qué tengo que hacer para inscribirme?",
                "¿Cuándo es el curso de inducción y es obligatorio ir?",
                "¿Cuántos créditos complementarios necesito?",
                "¿Con qué porcentaje de créditos puedo empezar mi servicio social?",
                "Me dijeron que el curso de inducción es opcional, ¿verdad?",
                "¿Quién eres?",
            ],
        )

    with gr.Tab("Comparación sin RAG vs con RAG"):
        gr.Markdown("### Respuesta SIN aumento de datos vs CON aumento de datos")
        pregunta = gr.Textbox(label="Pregunta", lines=2)
        boton = gr.Button("Consultar")
        salida1 = gr.Textbox(label="Qwen SIN RAG", lines=8)
        salida2 = gr.Textbox(label="Qwen CON RAG", lines=8)
        salida3 = gr.Textbox(label="Fragmentos recuperados", lines=18)
        boton.click(fn=comparar, inputs=pregunta, outputs=[salida1, salida2, salida3])

demo.launch(inbrowser=True)
#endregion