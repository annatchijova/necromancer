# NECROMANCER

**Resurrect the investigation. Not the assumptions.**

[English](#english) · [Español](#español)

---

## English

### The problem

You open a project you abandoned eight months ago. Four hundred files, contradictory notes, tests that no longer run, three documents claiming everything is finished. What were you trying to do? What did you actually prove? What is still pending? Which claims can no longer be trusted?

NECROMANCER rebuilds the history of a project from its digital remains. It is not a chatbot that summarizes a repository. It is an archaeologist for projects.

### What it does

1. **Repository autopsy.** It reads the Git history, documentation and tests without modifying anything, and rebuilds a timeline where every event links back to its file and commit.
2. **Reconstruction of intentions.** It proposes competing hypotheses about abandoned goals and decisions. Every hypothesis keeps its origin and its uncertainty. It never presents a single invented story as the story.
3. **False-conclusion detector.** It finds claims such as "implemented", "fixed" or "verified" and checks them against the available evidence.
4. **Resurrection plan.** It produces a path to resume the project: what to check first, what knowledge is missing, which risks are still open, and which next steps are reversible.

This is the difference it aims for:

> The README states the vulnerability was fixed on June 14. The associated commit modifies the validator, but no corresponding regression test was found. Status: fix documented, verification not demonstrated.

### The promise

- No model-generated inference silently becomes a verified historical fact.
- Missing evidence is never treated as proof that something did not happen.
- Everything it states points to the evidence it came from.
- It would rather say "not determinable" than invent certainty.

### Status

NECROMANCER is built in levels toward its full destination. Each level is complete and usable on its own; nothing is a throwaway prototype. The current level, what works today and what is still missing are listed honestly in the release notes of each level. Known limits are documented, not hidden.

### Quick start

```bash
pip install -e .
necromancer excavate /path/to/abandoned-repo --out report.json --markdown report.md
```

The target repository is only read. Its code is never executed.

### Run the workbench locally

First time only, from the repository root:

```bash
cd necromancer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd frontend
npm install
cd ..
```

Every time you want to use it, open two terminals.

Terminal 1, the API (from the repository root, virtualenv active):

```bash
source .venv/bin/activate
uvicorn necromancer.api:app --port 8000
```

Terminal 2, the interface:

```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser and investigate.

If port 8000 or 5173 is already taken on your machine, use free ones
instead and tell the interface where the API went. Terminal 1:
`uvicorn necromancer.api:app --port 8765`. Terminal 2:
`VITE_API_BASE=http://127.0.0.1:8765 npm run dev -- --port 5174`.
Then open http://localhost:5174.

To stop it, press Ctrl+C in both terminals.

As an MCP server, for external clients that do their own reasoning:

```bash
necromancer-mcp
```

Language models are optional and interchangeable (offline mode,
OpenAI-compatible APIs, local Ollama). None is required, and none can
change a verdict. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### License

Apache-2.0. See [LICENSE](LICENSE).

---

## Español

### El problema

Abrís un proyecto que abandonaste hace ocho meses. Cuatrocientos archivos, notas contradictorias, tests que ya no corren, tres documentos que afirman que todo está terminado. ¿Qué estabas intentando hacer? ¿Qué llegaste a demostrar de verdad? ¿Qué quedó pendiente? ¿Qué afirmaciones ya no son confiables?

NECROMANCER reconstruye la historia de un proyecto a partir de sus restos digitales. No es un chatbot que resume un repositorio. Es un arqueólogo de proyectos.

### Qué hace

1. **Autopsia del repositorio.** Lee el historial Git, la documentación y las pruebas sin modificar nada, y reconstruye una cronología donde cada evento enlaza con su archivo y su commit.
2. **Reconstrucción de intenciones.** Propone hipótesis en competencia sobre objetivos y decisiones abandonados. Cada hipótesis conserva su procedencia y su incertidumbre. Nunca presenta una única historia inventada como si fuera la historia.
3. **Detector de falsas conclusiones.** Encuentra afirmaciones como «implementado», «corregido» o «verificado» y las contrasta con la evidencia disponible.
4. **Plan de resurrección.** Produce una ruta para retomar el proyecto: qué comprobar primero, qué conocimiento falta recuperar, qué riesgos siguen abiertos y cuáles son las próximas acciones reversibles.

Esta es la diferencia que busca:

> El README afirma que la vulnerabilidad fue corregida el 14 de junio. El commit asociado modifica el validador, pero no se encontró una prueba de regresión correspondiente. Estado: corrección documentada, verificación no demostrada.

### La promesa

- Ninguna inferencia generada por un modelo se convierte en silencio en un hecho histórico verificado.
- La ausencia de evidencia nunca se trata como prueba de que algo no ocurrió.
- Todo lo que afirma apunta a la evidencia de la que salió.
- Prefiere decir «no determinable» antes que inventar certeza.

### Estado

NECROMANCER se construye por niveles hacia su destino completo. Cada nivel es completo y utilizable por sí mismo; nada es un prototipo descartable. El nivel actual, lo que funciona hoy y lo que todavía falta se listan con honestidad en las notas de cada nivel. Los límites conocidos se documentan, no se esconden.

### Inicio rápido

```bash
pip install -e .
necromancer excavate /ruta/al-repo-abandonado --out report.json --markdown report.md
```

El repositorio analizado solo se lee. Su código nunca se ejecuta.

### Levantar el workbench en tu máquina

Solo la primera vez, desde la raíz del repositorio:

```bash
cd necromancer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd frontend
npm install
cd ..
```

Cada vez que quieras usarlo, abrí dos terminales.

Terminal 1, la API (desde la raíz del repositorio, con el entorno activo):

```bash
source .venv/bin/activate
uvicorn necromancer.api:app --port 8000
```

Terminal 2, la interfaz:

```bash
cd frontend
npm run dev
```

Después abrí http://localhost:5173 en tu navegador e investigá.

Si el puerto 8000 o el 5173 ya están ocupados en tu máquina, usá puertos
libres y avisale a la interfaz dónde quedó la API. Terminal 1:
`uvicorn necromancer.api:app --port 8765`. Terminal 2:
`VITE_API_BASE=http://127.0.0.1:8765 npm run dev -- --port 5174`.
Y abrí http://localhost:5174.

Para apagarlo, Ctrl+C en las dos terminales.

Como servidor MCP, para clientes externos que razonan por su cuenta:

```bash
necromancer-mcp
```

Los modelos de lenguaje son opcionales e intercambiables (modo offline,
APIs compatibles con OpenAI, Ollama local). Ninguno es obligatorio y
ninguno puede cambiar un veredicto. Arquitectura: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Licencia

Apache-2.0. Ver [LICENSE](LICENSE).
