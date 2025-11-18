# 📚 DOCUMENTAÇÃO TÉCNICA COMPLETA - Sistema RAG Cativa Têxtil

**Trabalho de Conclusão de Curso (TCC)**  
**Sistema:** RAG (Retrieval-Augmented Generation) com WhatsApp Bot  
**Empresa:** Cativa Têxtil Ltda.  
**Versão:** 1.0.0  
**Data:** 2025-11-04

---

## 📋 ÍNDICE

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Arquitetura Geral](#2-arquitetura-geral)
3. [Infraestrutura e Setup](#3-infraestrutura-e-setup)
4. [Módulos Core](#4-módulos-core)
5. [Segurança e LGPD](#5-segurança-e-lgpd)
6. [Processamento de Dados](#6-processamento-de-dados)
7. [RAG Engine (Núcleo)](#7-rag-engine-núcleo)
8. [Text-to-SQL](#8-text-to-sql)
9. [Integração WhatsApp](#9-integração-whatsapp)
10. [Fluxos Completos End-to-End](#10-fluxos-completos-end-to-end)
11. [Deployment e Produção](#11-deployment-e-produção)

---

# 1. VISÃO GERAL DO SISTEMA

## 1.1. O que é o Sistema?

O Sistema RAG Cativa Têxtil é uma **aplicação inteligente de consulta de dados** que permite funcionários acessarem informações financeiras da empresa através de **mensagens de WhatsApp em linguagem natural**.

### 🎯 **Problema Resolvido:**
- Funcionários precisam consultar dados financeiros (vendas, contas a pagar/receber)
- Dados estão em Oracle Database 11g (ERP legado)
- Interface tradicional é complexa e requer SQL
- Difícil acesso mobile

### ✅ **Solução Implementada:**
- Bot WhatsApp que recebe perguntas em português
- Sistema converte perguntas para SQL automaticamente (Text-to-SQL)
- Consulta banco Oracle diretamente OU busca em embeddings PostgreSQL
- Responde em linguagem natural
- **100% compatível com LGPD**

---

## 1.2. Tecnologias Principais

| **Categoria** | **Tecnologia** | **Por que foi escolhida?** |
|---------------|---------------|---------------------------|
| **Linguagem** | Python 3.11+ | Ecossistema AI/ML robusto, bibliotecas maduras |
| **IA/LLM** | OpenAI GPT-4 + Embeddings | Melhor modelo para Text-to-SQL em português + geração de embeddings semânticos |
| **Banco Produção** | Oracle 11g | Banco legado da empresa (ERP existente) |
| **Banco RAG** | PostgreSQL 15 + pgvector | Suporte nativo a vetores para busca semântica |
| **WhatsApp API** | Evolution API | API open-source gratuita para WhatsApp Business |
| **Web Framework** | Flask 3.0 | Leve e eficiente para webhooks |
| **WSGI Server** | Waitress | Production-ready, thread-safe, sem dependências |
| **Criptografia** | cryptography (AES-256-GCM) | Padrão NIST, auditado, LGPD-compliant |
| **Container** | Docker + docker-compose | Portabilidade e facilidade de deploy |

---

## 1.3. Arquitetura Híbrida

O sistema usa uma **arquitetura híbrida** com duas rotas de consulta:

### 🔹 **Rota PRIMARY: Text-to-SQL (Oracle)**
- **Quando usar:** Consultas estruturadas (valores, totais, listas)
- **Como funciona:** GPT-4 converte pergunta → SQL → executa no Oracle → retorna dados
- **Vantagem:** Dados sempre atualizados em tempo real
- **Exemplo:** *"Qual o total de vendas de outubro?"*

### 🔹 **Rota FALLBACK: Embedding Search (PostgreSQL)**
- **Quando usar:** Consultas conceituais ou quando SQL falha
- **Como funciona:** Gera embedding da pergunta → busca vetorial → retorna chunks similares
- **Vantagem:** Funciona mesmo para perguntas ambíguas
- **Exemplo:** *"Me fale sobre o desempenho financeiro"*

---

## 1.4. Conformidade LGPD

Sistema **100% compatível** com Lei Geral de Proteção de Dados (LGPD):

| **Artigo LGPD** | **Implementação** |
|----------------|-------------------|
| **Art. 46º** | Criptografia AES-256-GCM para dados sensíveis (CNPJ, CPF) |
| **Art. 9º** | Log de todos os acessos com timestamp, usuário e dados acessados |
| **Art. 18º** | Log de exclusões e sistema de limpeza automática |
| **Art. 18º II** | Portabilidade de dados via export JSON |

**Níveis de classificação:**
- **ALTO:** Dados pessoais (CPF, CNPJ, nomes) → **Criptografado**
- **MÉDIO:** Dados financeiros sensíveis → **Criptografado**
- **BAIXO:** Dados agregados, públicos → **Não criptografado**

---

# 2. ARQUITETURA GERAL

## 2.1. Diagrama de Componentes

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USUÁRIO (WhatsApp)                            │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ Mensagem texto
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   EVOLUTION API (WhatsApp Gateway)                    │
│  - Recebe mensagens WhatsApp                                         │
│  - Envia para webhook configurado                                    │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ HTTP POST (webhook)
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      WEBHOOK SERVER (Flask + Waitress)               │
│  - Recebe payload Evolution API                                      │
│  - Valida e extrai mensagem                                          │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       MESSAGE HANDLER                                │
│  ├─ Authorization (verifica usuário autorizado)                      │
│  ├─ Rate Limiter (previne abuso)                                     │
│  └─ Envia query para RAG Engine                                      │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          RAG ENGINE (NÚCLEO)                         │
│  ┌────────────────────────────────────────────────────────┐          │
│  │  1. LGPD QUERY CLASSIFIER                              │          │
│  │     - Classifica nível LGPD da query                   │          │
│  │     - Verifica clearance do usuário                    │          │
│  └────────────────────────────┬───────────────────────────┘          │
│                               │                                       │
│                               ▼                                       │
│  ┌────────────────────────────────────────────────────────┐          │
│  │  2. TEXT-TO-SQL SERVICE (Rota PRIMARY)                 │          │
│  │     ├─ GPT-4: Converte query → SQL                     │          │
│  │     ├─ SQL Validator: Valida segurança do SQL          │          │
│  │     ├─ Oracle Connection Pool: Executa query           │          │
│  │     └─ Retorna resultados                              │          │
│  └────────────────────────────┬───────────────────────────┘          │
│                               │ (se falhar)                           │
│                               ▼                                       │
│  ┌────────────────────────────────────────────────────────┐          │
│  │  3. EMBEDDING SEARCH (Rota FALLBACK)                   │          │
│  │     ├─ OpenAI: Gera embedding da query                 │          │
│  │     ├─ PostgreSQL pgvector: Busca similaridade         │          │
│  │     ├─ AES-256-GCM: Descriptografa chunks sensíveis    │          │
│  │     └─ Retorna chunks relevantes                       │          │
│  └────────────────────────────┬───────────────────────────┘          │
│                               │                                       │
│                               ▼                                       │
│  ┌────────────────────────────────────────────────────────┐          │
│  │  4. RESPONSE FORMATTER                                 │          │
│  │     - GPT-4: Formata resposta em português natural     │          │
│  │     - Adiciona contexto e explicações                  │          │
│  └────────────────────────────┬───────────────────────────┘          │
│                               │                                       │
│  ┌────────────────────────────────────────────────────────┐          │
│  │  5. LGPD AUDIT LOGGER                                  │          │
│  │     - Log de acesso (Art. 9º)                          │          │
│  │     - Registro de dados acessados                      │          │
│  └────────────────────────────────────────────────────────┘          │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ Resposta formatada
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    EVOLUTION API CLIENT                              │
│  - Envia resposta de volta para WhatsApp                            │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        USUÁRIO (WhatsApp)                            │
│  Recebe resposta em linguagem natural                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2.2. Bancos de Dados

### 🔵 **Oracle 11g (Produção)**

**Por que Oracle?**
- Banco legado da empresa (ERP já existe)
- Dados de produção em tempo real
- Views pré-criadas para otimização

**O que contém:**
- Dados de vendas (pedidos, clientes, valores)
- Contas a pagar (fornecedores, títulos, vencimentos)
- Contas a receber (clientes, duplicatas, cobranças)

**Como é acessado:**
- Via `cx-Oracle` (driver Python)
- Connection Pool (2-10 conexões simultâneas)
- Queries SQL geradas dinamicamente pelo GPT-4

**Views Oracle criadas:**
```sql
-- Vendas (estruturada para SQL)
VW_RAG_VENDAS_ESTRUTURADA

-- Vendas (textual para embeddings)
VW_RAG_VENDAS_TEXTUAL

-- Resumos agregados
VW_RAG_RESUMOS_AGREGADOS

-- Contas a Pagar
VW_RAG_CP_TITULOS_TEXTUAL
VW_RAG_CP_RESUMOS_AGREGADOS

-- Contas a Receber
VW_RAG_CR_DUPLICATAS_TEXTUAL
VW_RAG_CR_RESUMOS_AGREGADOS
```

---

### 🟢 **PostgreSQL 15 + pgvector (RAG)**

**Por que PostgreSQL + pgvector?**
- Open-source e gratuito
- pgvector: extensão nativa para vetores (embeddings)
- Busca de similaridade ultra-rápida (HNSW index)
- JSON nativo (JSONB) para metadados flexíveis

**O que contém:**
- **Chunks de texto com embeddings** (sincronizados do Oracle)
- **Logs LGPD** (acessos + exclusões)
- **Usuários autorizados** WhatsApp
- **Políticas de retenção** LGPD

**Tabelas principais:**

#### **`chunks`** (Tabela principal RAG)
```sql
CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    content_text TEXT NOT NULL,              -- Texto do chunk
    encrypted_content BYTEA,                  -- Versão criptografada (se LGPD ALTO/MÉDIO)
    entity TEXT NOT NULL,                     -- Ex: "VENDAS", "CP", "CR"
    attributes JSONB NOT NULL,                -- Metadados flexíveis
    nivel_lgpd TEXT NOT NULL,                 -- "ALTO", "MÉDIO", "BAIXO"
    hash_sha256 TEXT NOT NULL UNIQUE,         -- Hash para deduplicação
    embedding vector(1536),                   -- Vetor OpenAI (1536 dimensões)
    created_at TIMESTAMP WITH TIME ZONE,
    ...
);
```

**Por que `vector(1536)`?**
- OpenAI `text-embedding-3-small` gera vetores de 1536 dimensões
- Cada dimensão é um número float representando uma característica semântica
- pgvector permite buscar chunks similares usando **similaridade de cosseno**

#### **`access_log`** (Auditoria LGPD Art. 9º)
```sql
CREATE TABLE access_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    user_clearance TEXT NOT NULL,            -- ALTO, MÉDIO, BAIXO
    query_text TEXT NOT NULL,                -- Query do usuário
    query_classification TEXT NOT NULL,      -- Classificação LGPD
    route_used TEXT NOT NULL,                -- "text_to_sql" ou "embeddings"
    chunks_accessed TEXT[],                  -- IDs dos chunks acessados
    success BOOLEAN NOT NULL,
    accessed_at TIMESTAMP WITH TIME ZONE
);
```

#### **`lgpd_deletion_log`** (Auditoria LGPD Art. 18º)
```sql
CREATE TABLE lgpd_deletion_log (
    id SERIAL PRIMARY KEY,
    deletion_type TEXT NOT NULL,             -- "retention_cleanup", "erasure_request"
    affected_table TEXT NOT NULL,
    records_deleted INTEGER NOT NULL,
    deletion_reason TEXT NOT NULL,
    criteria_used JSONB,
    executed_at TIMESTAMP WITH TIME ZONE
);
```

---

## 2.3. Sincronização Oracle → PostgreSQL

**Por que sincronizar?**
- Oracle tem dados de produção (sempre atualizados)
- PostgreSQL precisa dos dados para embedding search (fallback)
- Sincronização periódica mantém RAG atualizado

**Como funciona:**

```python
# Script: src/data_processing/oracle_sync.py

1. Conecta Oracle e PostgreSQL (via connection pools)

2. Busca dados novos do Oracle (últimos 30 dias):
   - Vendas (VW_RAG_VENDAS_TEXTUAL)
   - Contas a Pagar (VW_RAG_CP_TITULOS_TEXTUAL)
   - Contas a Receber (VW_RAG_CR_DUPLICATAS_TEXTUAL)

3. Para cada registro:
   a) Classifica nível LGPD (ALTO/MÉDIO/BAIXO)
   b) Gera embedding OpenAI (1536 dimensões)
   c) Criptografa com AES-256-GCM (se ALTO ou MÉDIO)
   d) Calcula hash SHA-256 (deduplicação)
   e) Insere no PostgreSQL (tabela chunks)

4. Log de sincronização:
   - Registros processados
   - Embeddings gerados
   - Tempo de processamento
   - Erros encontrados
```

**Executando sincronização:**
```bash
# Manual
python -m src.data_processing.oracle_sync --days 30 --max 5000

# Automático (cron job recomendado)
0 2 * * * cd /app && python -m src.data_processing.oracle_sync --days 1 --max 10000
```

**Métricas típicas:**
- ~1000 registros/minuto
- ~5000 embeddings/sincronização
- ~2-5 minutos para 30 dias de dados

---

# 3. INFRAESTRUTURA E SETUP

## 3.1. Docker Compose (PostgreSQL + pgvector)

**Arquivo:** `docker/docker-compose.yml`

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg15          # PostgreSQL 15 com pgvector pré-instalado
    container_name: cativa_rag_postgres
    environment:
      POSTGRES_DB: cativa_rag_db           # Nome do banco
      POSTGRES_USER: cativa_user           # Usuário
      POSTGRES_PASSWORD: cativa_password_2024
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - "5433:5432"                        # Porta externa:interna
    volumes:
      - postgres_data:/var/lib/postgresql/data        # Persistência de dados
      - ../sql:/docker-entrypoint-initdb.d            # Auto-executa SQLs na inicialização
      - ../database/backups:/backups                  # Pasta para backups
    restart: unless-stopped
    command: >
      postgres
      -c shared_preload_libraries=vector              # Carrega extensão pgvector
      -c log_statement=all                            # Log todas as queries (debug)
      -c max_connections=200                          # Máximo de conexões
      -c shared_buffers=256MB                         # Buffer de memória
      -c effective_cache_size=1GB                     # Cache size
      -c work_mem=64MB                                # Memória por operação
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cativa_user -d cativa_rag_db"]
      interval: 30s
      timeout: 10s
      retries: 5

  pgadmin:                                            # Interface web (opcional)
    image: dpage/pgadmin4
    container_name: cativa_rag_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@cativa.com
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "8080:80"                                     # Acesso: http://localhost:8080
    depends_on:
      - postgres
    restart: unless-stopped
    profiles:
      - tools                                         # Só inicia se: docker-compose --profile tools up

volumes:
  postgres_data:                                       # Volume persistente
```

**Por que `pgvector/pgvector:pg15`?**
- Imagem oficial do pgvector
- PostgreSQL 15 + extensão pgvector já compilada
- Pronto para uso (sem necessidade de compilar)

**Por que `shared_preload_libraries=vector`?**
- Carrega extensão pgvector na inicialização do Postgres
- Necessário para usar o tipo `vector(N)` e índices HNSW

**Por que `../sql:/docker-entrypoint-initdb.d`?**
- PostgreSQL executa automaticamente todos os `.sql` nesta pasta na **primeira inicialização**
- Scripts são executados em ordem alfabética
- Útil para criar schema inicial (`01_init_database.sql`)

---

## 3.2. Variáveis de Ambiente (.env)

**Arquivo:** `.env` (criar a partir de `.env.example`)

```env
# OpenAI API
OPENAI_API_KEY=sk-proj-xxxxx                # Chave API OpenAI (obrigatório)
OPENAI_MODEL=gpt-4                          # Modelo para Text-to-SQL
OPENAI_EMBEDDING_MODEL=text-embedding-3-small  # Modelo para embeddings

# Evolution API (WhatsApp)
EVOLUTION_API_URL=http://localhost:8081     # URL da Evolution API
EVOLUTION_API_KEY=seu_api_key               # API key Evolution
EVOLUTION_INSTANCE=cativa_bot               # Nome da instância
WEBHOOK_HOST=0.0.0.0                        # Host do webhook (0.0.0.0 = todas interfaces)
WEBHOOK_PORT=5000                           # Porta do webhook
WEBHOOK_PUBLIC_URL=https://abc123.ngrok.io  # URL pública (ngrok ou domínio real)

# Oracle Database
ORACLE_HOST=192.168.1.100                   # IP do servidor Oracle
ORACLE_PORT=1521                            # Porta Oracle (padrão)
ORACLE_SERVICE_NAME=ORCL                    # Service name OU
ORACLE_SID=dbprod                           # SID (usar um dos dois)
ORACLE_USER=system                          # Usuário Oracle
ORACLE_PASSWORD=senha_segura                # Senha Oracle

# PostgreSQL
PG_HOST=localhost                           # Host PostgreSQL (localhost se Docker local)
PG_PORT=5433                                # Porta (5433 no docker-compose)
PG_DATABASE=cativa_rag_db                   # Nome do banco
PG_USER=cativa_user                         # Usuário
PG_PASSWORD=cativa_password_2024            # Senha

# Criptografia AES-256-GCM
ENCRYPTION_KEY=abc123...                    # Chave base64 (44 caracteres)
# Gerar com: python scripts/generate_encryption_key.py

# Ambiente
ENVIRONMENT=production                       # development | production
DEBUG=false                                 # true | false
LOG_LEVEL=INFO                              # DEBUG | INFO | WARNING | ERROR
```

### **Como são carregadas as variáveis?**

**Arquivo:** `src/core/config.py`

```python
# 1. Tenta carregar .env com python-dotenv
from dotenv import load_dotenv
load_dotenv()

# 2. Define dataclasses para cada grupo de config
@dataclass
class OracleConfig:
    host: str
    port: int
    user: str
    password: str
    service_name: Optional[str] = None
    sid: Optional[str] = None
    
    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv('ORACLE_HOST', 'localhost'),
            port=int(os.getenv('ORACLE_PORT', '1521')),
            user=os.getenv('ORACLE_USER', 'user'),
            password=os.getenv('ORACLE_PASSWORD', ''),
            service_name=os.getenv('ORACLE_SERVICE_NAME'),
            sid=os.getenv('ORACLE_SID')
        )

# 3. Classe Config centralizada (singleton)
class Config:
    _oracle_config = None  # Cache
    
    @classmethod
    def oracle(cls) -> OracleConfig:
        if cls._oracle_config is None:
            cls._oracle_config = OracleConfig.from_env()
        return cls._oracle_config
```

**Por que singleton?**
- Carrega variáveis UMA VEZ no início
- Reutiliza mesma instância em todo o código
- Evita ler `.env` múltiplas vezes

---

## 3.3. Dependências Python (requirements.txt)

```txt
# Core
python-dotenv==1.0.0              # Carrega variáveis .env

# Web Framework
Flask==3.0.0                      # Webhook server
waitress==3.0.0                   # WSGI production-ready
requests==2.31.0                  # HTTP client (Evolution API)

# Bancos de Dados
psycopg2-binary==2.9.9            # Driver PostgreSQL
cx-Oracle==8.3.0                  # Driver Oracle (opcional)

# AI/ML
openai>=2.6.0                     # OpenAI API (GPT-4 + Embeddings)
numpy==1.26.3                     # Arrays para vetores

# Utilitários
python-dateutil==2.8.2            # Parsing de datas
pydantic==2.5.3                   # Validação de dados

# Segurança
cryptography==46.0.3              # AES-256-GCM (LGPD)

# Testes
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0
```

### **Por que cada biblioteca?**

**`python-dotenv`:**
- Carrega variáveis de `.env` para `os.environ`
- Facilita separar config de código

**`Flask`:**
- Micro-framework web leve
- Ideal para webhooks (recebe POST do Evolution API)
- Simples de configurar rotas

**`waitress`:**
- WSGI server production-ready
- Thread-safe (múltiplas requisições simultâneas)
- Sem dependências C (funciona no Windows)
- Alternativa: gunicorn (só Linux)

**`psycopg2-binary`:**
- Driver PostgreSQL oficial
- Versão `-binary` inclui bibliotecas compiladas (sem necessidade de gcc)

**`cx-Oracle`:**
- Driver Oracle oficial
- Lazy loading (só carrega se usar Oracle)
- Requer Oracle Instant Client instalado

**`openai`:**
- SDK oficial OpenAI
- Suporta GPT-4 (Text-to-SQL) + Embeddings (vetores)
- Retry automático em rate limits

**`numpy`:**
- Manipulação eficiente de arrays
- Usado para vetores de embeddings (1536 floats)

**`cryptography`:**
- Biblioteca auditada e segura
- Implementa AES-256-GCM (padrão NIST)
- Usado para criptografar chunks LGPD ALTO/MÉDIO

---

## 3.4. Setup Inicial (Passo a Passo)

### **1. Pré-requisitos**
```bash
# Python 3.11+
python --version

# Docker + Docker Compose
docker --version
docker-compose --version

# Git (para clonar projeto)
git --version
```

### **2. Clonar repositório**
```bash
git clone https://github.com/empresa/cativa-rag.git
cd cativa-rag
```

### **3. Criar ambiente virtual**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### **4. Instalar dependências**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### **5. Iniciar PostgreSQL (Docker)**
```bash
cd docker
docker-compose up -d postgres

# Verificar se subiu
docker ps                          # Deve aparecer cativa_rag_postgres
docker logs cativa_rag_postgres    # Ver logs
```

**O que acontece na primeira inicialização:**
1. Docker baixa imagem `pgvector/pgvector:pg15`
2. Cria volume `postgres_data` (persistência)
3. Executa scripts em `sql/`:
   - `01_init_database.sql` → Cria tabelas, índices, views
   - `02_optimize_indexes.sql` → Otimizações de performance
4. PostgreSQL fica disponível em `localhost:5433`

### **6. Gerar chave de criptografia**
```bash
python scripts/generate_encryption_key.py

# Output:
# ==================================================
# CHAVE DE CRIPTOGRAFIA AES-256-GCM GERADA
# ==================================================
#
# Chave (Base64): abc123def456...
#
# Adicione ao .env:
# ENCRYPTION_KEY=abc123def456...
```

### **7. Configurar .env**
```bash
cp .env.example .env
nano .env  # ou qualquer editor

# Preencher:
# - OPENAI_API_KEY
# - ORACLE_* (host, user, password, sid/service_name)
# - ENCRYPTION_KEY (gerada no passo 6)
# - Demais variáveis conforme necessário
```

### **8. Testar conexões**
```bash
# Testar Oracle
python tests/manual/test_oracle_connection_quick.py

# Testar PostgreSQL + pgvector
python tests/manual/test_chunks_search.py
```

### **9. Sincronizar dados Oracle → PostgreSQL**
```bash
# Primeira sincronização (últimos 30 dias)
python -m src.data_processing.oracle_sync --days 30 --max 5000

# Output:
# Conectando ao Oracle... ✓
# Conectando ao PostgreSQL... ✓
# Sincronizando vendas: 1234 registros
# Sincronizando CP: 567 registros
# Sincronizando CR: 890 registros
# Gerando embeddings: 2691/2691
# Inserindo no PostgreSQL... ✓
# Sincronização concluída em 3m 24s
```

### **10. Iniciar WhatsApp Bot**
```bash
python whatsapp_bot.py

# Output:
# ================================================================================
# WHATSAPP RAG BOT - Sistema Cativa Textil
# ================================================================================
#
# Validating system configuration... ✓
# Evolution API URL: http://localhost:8081
# Instance: cativa_bot
# Webhook Port: 5000
# OpenAI Enabled: True
#
# Instance Status: connected
# RAG Engine: Initialized
# Webhook Configured: https://abc123.ngrok.io/webhook
#
# ================================================================================
# BOT INICIADO!
# ================================================================================
#
# Aguardando mensagens do WhatsApp...
# Pressione Ctrl+C para encerrar graciosamente.
```

---

**CONTINUA NA PARTE 2 (próximo documento)...**

*Este é o Documento Parte 1 de 3*  
*Próximo: Módulos Core, Segurança LGPD, RAG Engine*
