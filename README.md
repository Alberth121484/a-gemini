# Agente IA Optimizado para Slack

Reemplazo de alto rendimiento del agente n8n, diseñado para soportar **13,000+ usuarios simultáneos**.

## 🚀 Mejoras vs n8n

| Aspecto | n8n Original | Versión Optimizada |
|---------|--------------|-------------------|
| **Concurrencia** | Secuencial por workflow | Async/await real |
| **Base de datos** | Sin pooling | Connection pool (10-100) |
| **Caché** | Ninguno | Redis para historial y rate limiting |
| **Overhead** | Alto (múltiples sub-workflows) | Mínimo (código directo) |
| **Escalabilidad** | ~100 usuarios | 13,000+ usuarios |
| **Latencia** | 2-5 segundos | <1 segundo |

## 📦 Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                      Slack (13,000 usuarios)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Slack Bolt (Socket Mode)                 │
│                    Rate Limiter (Redis)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     GeminiAgent                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Calculator  │  │ Web Search  │  │   Image     │        │
│  │    Tool     │  │   (Tavily)  │  │  Analysis   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Image     │  │  Document   │  │   Audio     │        │
│  │ Generation  │  │  Analysis   │  │  (Whisper)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │     Redis       │ │   Google AI     │
│  (Chat Memory)  │ │    (Cache)      │ │    (Gemini)     │
│   (Logs)        │ │ (Rate Limit)    │ │    (Imagen)     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 🛠️ Instalación

### 1. Clonar y configurar

```bash
cd agent-optimized
cp .env.example .env
# Editar .env con tus credenciales
```

### 2. Instalar dependencias

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configurar base de datos

```sql
-- Crear tabla de chat history (si no existe)
CREATE TABLE IF NOT EXISTS n8n_chat_histories_geminiv2 (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_session ON n8n_chat_histories_geminiv2(session_id, created_at DESC);

-- Crear tabla de logs
CREATE TABLE IF NOT EXISTS logsgemini (
    userid VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    correo VARCHAR(255) NOT NULL,
    peticiones INTEGER DEFAULT 0
);
```

### 4. Configurar Slack App

1. Crear una app en [api.slack.com/apps](https://api.slack.com/apps)
2. Habilitar **Socket Mode**
3. Agregar los siguientes scopes de Bot Token:
   - `chat:write`
   - `files:read`
   - `files:write`
   - `reactions:read`
   - `reactions:write`
   - `users:read`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
4. Suscribirse a eventos:
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `message.mpim`
   - `app_mention`

## 🚀 Ejecución

### Modo desarrollo

```bash
# Solo Slack bot
python main.py slack

# Solo servidor HTTP (health checks)
python main.py server

# Ambos
python main.py all
```

### Modo producción (Docker)

```bash
docker-compose up -d
```

## 🔧 Configuración

Variables de entorno principales:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SLACK_BOT_TOKEN` | Token del bot de Slack | - |
| `SLACK_APP_TOKEN` | Token de app (Socket Mode) | - |
| `GOOGLE_API_KEY` | API key de Google AI | - |
| `OPENAI_API_KEY` | API key de OpenAI (audio) | - |
| `TAVILY_API_KEY` | API key de Tavily (búsqueda) | - |
| `DATABASE_URL` | URL de PostgreSQL | - |
| `REDIS_URL` | URL de Redis | `redis://localhost:6379/0` |
| `DATABASE_POOL_MIN` | Conexiones mínimas | `10` |
| `DATABASE_POOL_MAX` | Conexiones máximas | `100` |
| `RATE_LIMIT_REQUESTS` | Límite de peticiones | `100` |
| `RATE_LIMIT_WINDOW` | Ventana en segundos | `60` |

## 📊 Endpoints

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Health check básico |
| `GET /ready` | Verifica conexiones a DB y Redis |
| `GET /metrics` | Métricas del pool de conexiones |

## 🔄 Funcionalidades

### Herramientas disponibles

1. **Calculator** - Cálculos matemáticos seguros
2. **Web Search** - Búsqueda con Tavily API
3. **Image Analysis** - Análisis con Gemini Vision
4. **Image Generation** - Generación con Imagen 4.0
5. **Document Analysis** - PDF, Excel, Word, PPT, CSV, etc.
6. **Audio Transcription** - Whisper para transcripción
7. **Audio Generation** - TTS para respuestas de voz

### Formatos de documento soportados

- PDF (`.pdf`)
- Excel (`.xlsx`, `.xls`, `.ods`)
- Word (`.docx`, `.doc`)
- PowerPoint (`.pptx`, `.ppt`)
- Texto (`.txt`, `.rtf`, `.csv`)
- Web (`.html`, `.xml`, `.json`)

## 🔒 Seguridad

- Rate limiting por usuario
- Conexiones seguras a APIs
- Sin hardcoding de credenciales
- Evaluación segura de expresiones matemáticas

## 📈 Escalabilidad

Para 13,000 usuarios simultáneos:

1. **PostgreSQL**: Pool de 100 conexiones
2. **Redis**: Caché de historial (5 min TTL)
3. **Workers**: Múltiples instancias con Uvicorn
4. **Rate Limiting**: 100 req/min por usuario

### Recomendaciones de infraestructura

```yaml
# Para 13,000 usuarios
PostgreSQL:
  - Conexiones máximas: 500
  - RAM: 8GB+
  - CPU: 4+ cores

Redis:
  - RAM: 2GB+
  - maxmemory-policy: allkeys-lru

Aplicación:
  - Instancias: 4-8
  - RAM por instancia: 2GB
  - CPU por instancia: 2 cores
```

## 🐳 Docker Compose

```yaml
version: '3.8'

services:
  agent:
    build: .
    command: python main.py all
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: agentdb
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## 📝 Licencia

Propietario - Uso interno
