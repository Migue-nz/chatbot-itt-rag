# TecBot: Asistente Institucional del Instituto Tecnológico de Tepic

Chatbot que responde preguntas de **aspirantes de nuevo ingreso** y **estudiantes regulares** del Instituto Tecnológico de Tepic (ITT) usando únicamente documentos oficiales del ITT y del TecNM.

Proyecto final de la materia **Inteligencia Artificial**: un modelo de lenguaje ejecutado localmente con **LM Studio**, conectado a una interfaz web en **Python** mediante **RAG** (*Retrieval-Augmented Generation*).

## Arquitectura

```
Documentos del ITT (PDF/TXT)
   -> Limpieza y división en fragmentos (1000 caracteres, traslape 150)
   -> Embeddings con BGE-M3 (LM Studio)
   -> Base vectorial Chroma
   -> Recuperación de los 4 fragmentos más relevantes
   -> System prompt + contexto + pregunta
   -> Qwen2.5-7B-Instruct (LM Studio, temperatura 0)
   -> Interfaz web con Gradio
```

## Tecnologías

| Componente | Herramienta |
|---|---|
| Motor de inferencia local | LM Studio (servidor compatible con la API de OpenAI, puerto 1234) |
| Modelo de lenguaje | Qwen2.5-7B-Instruct, cuantización Q4_K_M |
| Modelo de embeddings | BGE-M3, cuantización Q8_0 |
| Orquestación RAG | LangChain |
| Base vectorial | Chroma |
| Interfaz | Gradio |

## Estructura del repositorio

```
chatbot_itt.py          Código principal (carga de documentos, RAG e interfaz)
requirements.txt        Dependencias de Python
docs/aspirantes/        Documentos para aspirantes (inscripción, oferta educativa)
docs/estudiantes/       Documentos para estudiantes (reinscripción, calendario, Manual de Lineamientos TecNM)
docs/FUENTES.md         Origen de cada documento
prompts/                Versiones del system prompt (v1, v2, v3) generadas durante las pruebas
```

## Casos de uso

| ID | Perfil | Caso de uso |
|---|---|---|
| CU-01 | Aspirante | Consultar el proceso de inscripción de nuevo ingreso |
| CU-02 | Aspirante | Consultar las fechas clave del ingreso |
| CU-03 | Aspirante | Conocer la oferta educativa |
| CU-04 | Estudiante | Consultar el proceso de liberación de créditos complementarios |
| CU-05 | Estudiante | Consultar los requisitos de servicio social y residencia profesional |
| CU-06 | Estudiante | Consultar el proceso de reinscripción y baja de materias |

## Cómo ejecutarlo

1. Instalar [LM Studio](https://lmstudio.ai) y descargar los modelos `Qwen2.5-7B-Instruct-GGUF` (Q4_K_M) y `bge-m3-GGUF` (Q8_0).
2. En LM Studio, cargar `qwen2.5-7b-instruct` y encender el servidor local en el puerto **1234**.
3. Crear el entorno e instalar dependencias:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   pip install pypdf
   ```
4. Ejecutar:
   ```powershell
   python chatbot_itt.py
   ```
5. Se abre en el navegador en `http://127.0.0.1:7860`, con dos pestañas:
   - **Asistente**: chat con TecBot.
   - **Comparación sin RAG vs con RAG**: muestra la misma pregunta respondida sin documentos y con documentos, junto con los fragmentos recuperados.

La primera ejecución crea la base vectorial en la carpeta `chroma_itt/` (uno o dos minutos). Si se modifican los documentos de `docs/`, hay que borrar esa carpeta para regenerarla.

## Ajustes realizados durante las pruebas

| Ajuste | Problema | Solución |
|---|---|---|
| 1 | El Manual de Lineamientos (aprox. 90% de los fragmentos) opacaba a los documentos cortos del ITT | Encabezado con el título del documento al inicio de cada fragmento |
| 2 | El asistente no citaba la fuente | System prompt v2: línea "Fuente" obligatoria |
| 3 | Fuente citada sin usar documentos y datos no priorizados | System prompt v3: excepción en la regla de fuente y reglas de respuesta directa |

## Créditos

Basado en el código de referencia proporcionado en la materia de Inteligencia Artificial del Instituto Tecnológico de Tepic, adaptado al caso institucional del ITT.

Equipo: Miguel Nuñez Peña, Monse, Josadet, Angel.
