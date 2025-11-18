# 📘 DOCUMENTAÇÃO COMPLETA DOS ARQUIVOS PYTHON

## Sistema RAG Cativa Têxtil - Guia Detalhado de Cada Arquivo

---

# 📂 **ESTRUTURA DO PROJETO**

```
fontes/
├── whatsapp_bot.py                    # 🚀 Script principal do bot WhatsApp
├── manage_whatsapp_users.py           # 👥 CLI para gerenciar usuários
│
├── src/
│   ├── core/                          # 🔧 Núcleo do sistema
│   │   ├── config.py                  # ⚙️  Configurações centralizadas
│   │   ├── connection_pool.py         # 🏊 Pool de conexões (PostgreSQL + Oracle)
│   │   ├── database_adapter.py        # 🔌 Adaptadores de banco de dados
│   │   ├── logging_config.py          # 📝 Configuração de logs
│   │   ├── rate_limiter.py            # 🚦 Controle de taxa de requisições
│   │   └── retry_handler.py           # 🔄 Lógica de retry com backoff
│   │
│   ├── security/                      # 🔒 Segurança e LGPD
│   │   ├── encryption.py              # 🔐 Criptografia AES-256-GCM
│   │   ├── lgpd_audit.py              # 📋 Auditoria LGPD (logs de acesso)
│   │   └── lgpd_query_classifier.py   # 🏷️  Classificador de queries LGPD
│   │
│   ├── data_processing/               # 🔄 Processamento de dados
│   │   ├── chunking.py                # ✂️  Chunking de textos
│   │   ├── data_processor.py          # 🔨 Processador geral de dados
│   │   ├── embeddings.py              # 🧬 Geração de embeddings
│   │   ├── lgpd_classifier.py         # 🏷️  Classificação LGPD de chunks
│   │   ├── lgpd_data_classifier.py    # 🏷️  Classificação LGPD de dados
│   │   └── oracle_sync.py             # 🔄 Sincronização Oracle→PostgreSQL
│   │
│   ├── sql/                           # 🗄️ Text-to-SQL
│   │   ├── schema_introspector.py     # 🔍 Introspecção do schema Oracle
│   │   ├── sql_validator.py           # ✅ Validação de SQL gerado
│   │   ├── text_to_sql_generator.py   # 🤖 Geração de SQL via GPT-4
│   │   └── text_to_sql_service.py     # 🎯 Serviço Text-to-SQL completo
│   │
│   ├── rag/                           # 🧠 RAG Engine (núcleo)
│   │   └── rag_engine.py              # 🎯 Motor RAG principal
│   │
│   ├── integrations/whatsapp/         # 📱 Integração WhatsApp
│   │   ├── authorization.py           # 🔐 Sistema de autorizações
│   │   ├── evolution_client.py        # 📡 Cliente Evolution API
│   │   ├── message_handler.py         # 💬 Processador de mensagens
│   │   ├── response_formatter.py      # 📝 Formatação de respostas
│   │   └── webhook_server.py          # 🌐 Servidor webhook Flask
│   │
│   ├── ai/                            # 🤖 IA e OpenAI
│   │   ├── openai_client.py           # 🔌 Cliente OpenAI
│   │   └── query_processor.py         # 🔍 Processamento de queries
│   │
│   └── analytics/                     # 📊 Analytics
│       ├── advanced_analytics.py      # 📈 Analytics avançado
│       ├── intelligent_cache.py       # 💾 Cache inteligente
│       └── response_templates.py      # 📄 Templates de resposta
│
└── scripts/                           # 🛠️ Scripts utilitários
    ├── cleanup_lgpd.py                # 🧹 Limpeza de dados LGPD
    └── generate_encryption_key.py     # 🔑 Geração de chave de criptografia
```

---

# 🚀 **1. ARQUIVOS PRINCIPAIS (RAIZ)**

## 1.1. `whatsapp_bot.py`

### **O que faz?**
Script principal que inicializa e executa o bot WhatsApp RAG.

### **Como funciona?**

```python
main()
  ├── 1. Valida configurações (.env)
  ├── 2. Inicializa Evolution API Client
  ├── 3. Inicializa RAG Engine
  ├── 4. Inicializa Message Handler
  ├── 5. Inicia Webhook Server (Waitress WSGI)
  ├── 6. Configura webhook na Evolution API
  ├── 7. Aguarda mensagens (loop infinito)
  └── 8. Graceful shutdown (Ctrl+C)
```

### **Onde é usado?**
- **Produção:** Executado como serviço principal do bot
- **Desenvolvimento:** `python whatsapp_bot.py`

### **Tecnologias:**
- **Waitress:** Servidor WSGI para produção
- **Threading:** Webhook roda em thread separada
- **Signal Handling:** Captura Ctrl+C para shutdown gracioso

### **Exemplo de uso:**

```bash
# Produção
python whatsapp_bot.py

# Com nohup (background)
nohup python whatsapp_bot.py > logs/bot.log 2>&1 &

# Logs
tail -f logs/bot.log
```

### **Fluxo de mensagem:**

```
WhatsApp → Evolution API → Webhook → Message Handler → RAG Engine → Response → WhatsApp
```

### **Variáveis de ambiente necessárias:**

```bash
# Evolution API (WhatsApp)
EVOLUTION_API_URL=http://10.1.200.22:8081
EVOLUTION_API_KEY=your_key
EVOLUTION_INSTANCE=cativa_rag

# Webhook
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_PUBLIC_URL=https://abc123.ngrok.io  # Opcional

# Banco de dados
ORACLE_HOST=10.1.200.43
ORACLE_PORT=1521
ORACLE_USER=user
ORACLE_PASSWORD=pass
ORACLE_SID=ORCL

PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=cativa_rag_db
PG_USER=cativa_user
PG_PASSWORD=pass

# OpenAI
OPENAI_API_KEY=sk-...
```

### **Graceful Shutdown:**

```python
class GracefulShutdown:
    """
    Gerencia shutdown gracioso:
    1. Captura SIGINT (Ctrl+C) e SIGTERM
    2. Fecha connection pools
    3. Aguarda thread do webhook
    4. Finaliza logs
    """
    
    def _handle_signal(self, signum, frame):
        # Sinaliza shutdown
        self.shutdown_requested = True
```

**Por que é importante?**
- Evita perda de mensagens em processamento
- Fecha conexões de banco corretamente
- Evita corrupção de dados

---

## 1.2. `manage_whatsapp_users.py`

### **O que faz?**
CLI (Command Line Interface) para gerenciar permissões de usuários WhatsApp.

### **Como funciona?**

```python
manage_whatsapp_users.py
  ├── add      # Adiciona/atualiza usuário
  ├── remove   # Remove usuário
  ├── disable  # Desabilita usuário
  ├── enable   # Reabilita usuário
  ├── list     # Lista todos os usuários
  ├── check    # Verifica permissões de usuário
  └── reload   # Recarrega permissões do arquivo
```

### **Onde é usado?**
- **Administração:** Gerenciar usuários do bot
- **Onboarding:** Adicionar novos usuários
- **Segurança:** Revogar acessos

### **Níveis de clearance LGPD:**

| **Nível** | **Acesso** |
|-----------|-----------|
| **BAIXO** | Dados agregados (totais, médias) |
| **MÉDIO** | Números de pedidos e valores |
| **ALTO** | Dados pessoais (CNPJs, nomes de clientes) |

### **Exemplos de uso:**

```bash
# Adicionar usuário com clearance ALTO
python manage_whatsapp_users.py add 5547999887766 "João Silva" --clearance ALTO --department TI

# Adicionar admin
python manage_whatsapp_users.py add 5547888888888 "Admin User" --clearance ALTO --admin

# Listar todos os usuários
python manage_whatsapp_users.py list

# Listar em JSON
python manage_whatsapp_users.py list --format json

# Desabilitar usuário
python manage_whatsapp_users.py disable 5547999887766

# Verificar permissões
python manage_whatsapp_users.py check 5547999887766
```

### **Saída do comando `list`:**

```
Phone                               Name                 Clearance  Dept            Enabled  Admin
--------------------------------------------------------------------------------------------------------------
5547999887766@s.whatsapp.net       João Silva           ALTO       TI              Yes      No
5547888888888@s.whatsapp.net       Admin User           ALTO       ADMIN           Yes      Yes
5547777777777@s.whatsapp.net       Maria Santos         MEDIO      VENDAS          Yes      No

Total: 3 users
```

### **Arquivo de permissões:**

Gera/atualiza: `config/whatsapp_users.json`

```json
{
  "users": {
    "5547999887766@s.whatsapp.net": {
      "name": "João Silva",
      "clearance": "ALTO",
      "department": "TI",
      "enabled": true,
      "is_admin": false,
      "created_at": "2025-01-01T10:00:00"
    }
  }
}
```

---

# 🔧 **2. CORE (NÚCLEO DO SISTEMA)**

## 2.1. `src/core/config.py`

### **O que faz?**
Gerencia todas as configurações do sistema de forma centralizada.

### **Como funciona?**

```python
Config
  ├── Carrega .env automaticamente
  ├── Fornece configs tipadas (dataclasses)
  ├── Valida configurações obrigatórias
  └── Singleton para cada tipo de config
```

### **Onde é usado?**
- **TODOS os módulos** que precisam de configuração
- `whatsapp_bot.py` para inicializar sistema
- RAG Engine para conectar aos bancos

### **Configurações disponíveis:**

```python
# Oracle
oracle = Config.oracle()
print(oracle.host)  # 10.1.200.43
print(oracle.port)  # 1521

# PostgreSQL
postgres = Config.postgres()
print(postgres.database)  # cativa_rag_db

# Evolution API
evolution = Config.evolution()
print(evolution.api_url)  # http://10.1.200.22:8081

# OpenAI
openai = Config.openai()
print(openai.model)  # gpt-4
```

### **Validação automática:**

```python
if not Config.validate():
    print("Configuração inválida!")
    # Mostra quais variáveis faltam
    sys.exit(1)
```

**Variáveis validadas:**
- ✅ ORACLE_PASSWORD
- ✅ ORACLE_SERVICE_NAME ou ORACLE_SID
- ✅ PG_PASSWORD
- ✅ OPENAI_API_KEY

### **Constantes do sistema:**

```python
Config.MAX_CHUNK_TOKENS      # 800
Config.OVERLAP_TOKENS         # 100
Config.EMBEDDING_DIMENSION    # 1536
Config.LGPD_LEVELS           # ["BAIXO", "MÉDIO", "ALTO"]
Config.PROJECT_ROOT          # Path do projeto
Config.DATA_DIR              # /fontes/data
Config.LOGS_DIR              # /fontes/logs
```

### **Exemplo de carregamento manual de .env:**

```python
from core.config import load_env_file

# Carrega .env de outro local
load_env_file('/path/to/custom.env')
```

---

## 2.2. `src/core/connection_pool.py`

### **O que faz?**
Gerencia pools de conexão para PostgreSQL e Oracle, garantindo performance e estabilidade.

### **Por que usar pool?**

**SEM pool:**
```python
# Para cada query, abre e fecha conexão
conn = psycopg2.connect(...)  # ⏱️ 100ms
cursor.execute("SELECT ...")   # ⏱️ 10ms
conn.close()                   # ⏱️ 50ms
# Total: 160ms por query
```

**COM pool:**
```python
# Conexões já estão abertas no pool
conn = pool.getconn()          # ⏱️ 1ms (pega do pool)
cursor.execute("SELECT ...")   # ⏱️ 10ms
pool.putconn(conn)             # ⏱️ 1ms (devolve ao pool)
# Total: 12ms por query (13x mais rápido!)
```

### **Como funciona?**

```python
pool = DatabaseConnectionPool(
    postgres_config={'host': 'localhost', ...},
    oracle_config={'host': '10.1.200.43', ...},
    min_connections=2,   # Sempre mantém 2 conexões abertas
    max_connections=10   # Nunca ultrapassa 10
)

# Context manager (recomendado)
with pool.postgres_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chunks LIMIT 5")
    results = cursor.fetchall()
# Conexão é automaticamente devolvida ao pool
```

### **Onde é usado?**
- **RAG Engine:** Para buscar chunks no PostgreSQL
- **Text-to-SQL:** Para executar SQL no Oracle
- **Oracle Sync:** Para sincronizar dados
- **LGPD Audit:** Para registrar acessos

### **Tecnologias:**

**PostgreSQL:**
- `psycopg2.pool.ThreadedConnectionPool`
- Thread-safe (múltiplas threads podem usar)

**Oracle:**
- `cx_Oracle.SessionPool`
- Suporta SERVICE_NAME e SID

### **Retry automático:**

```python
@retry_database(max_retries=3)
def get_postgres_connection(self):
    """
    Se falhar:
    1. Aguarda 1s
    2. Tenta novamente
    3. Até 3 tentativas
    """
    return self.postgres_pool.getconn()
```

### **Graceful shutdown:**

```python
pool.close_all()
# Fecha todas as conexões de ambos os pools
```

---

## 2.3. `src/core/database_adapter.py`

### **O que faz?**
Abstração para acessar PostgreSQL e Oracle de forma uniforme (Design Pattern: Adapter).

### **Por que usar adapter?**

**Problema:** PostgreSQL e Oracle têm APIs diferentes:

```python
# PostgreSQL
import psycopg2
conn = psycopg2.connect(...)
cursor = conn.cursor()
cursor.execute("SELECT * FROM chunks WHERE embedding <=> %s", [embedding])

# Oracle
import cx_Oracle
conn = cx_Oracle.connect(...)
cursor = conn.cursor()
cursor.execute("SELECT * FROM dual WHERE ROWNUM <= :limit", {'limit': 10})
```

**Solução:** Interface unificada:

```python
# Mesma API para ambos
adapter = DatabaseAdapterFactory.create_adapter(config)
adapter.connect()

# Mesmos métodos
results = adapter.search_exact_entities({'pedido': ['843562']})
results = adapter.search_vector_similarity(embedding, threshold=0.7)
summary = adapter.get_chunks_summary()
```

### **Como funciona?**

```
DatabaseAdapter (Interface Abstrata)
  ├── search_exact_entities()
  ├── search_vector_similarity()
  ├── get_chunks_summary()
  ├── insert_chunk()
  └── execute_query()
          ↑
          |
    ┌─────┴────────┐
    │              │
PostgreSQLAdapter  OracleAdapter
  (pgvector)      (Oracle 11g)
```

### **PostgreSQLAdapter:**

```python
adapter = PostgreSQLAdapter(config)
adapter.connect()

# Busca vetorial com pgvector
results = adapter.search_vector_similarity(
    embedding=[0.1, 0.2, ...],  # 1536 floats
    similarity_threshold=0.7,
    max_results=5
)

# Resultado
for result in results:
    print(result.chunk_id)
    print(result.content_text)
    print(result.similarity)  # 0.92
    print(result.nivel_lgpd)  # MÉDIO
```

**SQL gerado (pgvector):**

```sql
SELECT 
    chunk_id, 
    content_text, 
    1 - (embedding <=> $1::vector) as similarity,
    entity, 
    nivel_lgpd
FROM chunks
WHERE 1 - (embedding <=> $1::vector) >= 0.7
ORDER BY embedding <=> $1::vector 
LIMIT 5
```

### **OracleAdapter:**

```python
adapter = OracleAdapter(config)
adapter.connect()

# Busca estruturada por pedido
results = adapter.search_exact_entities({
    'pedido': ['843562']
})

# Resultado
for result in results:
    print(result.metadata)
    # {
    #   'numero_pedido': 843562,
    #   'nome_cliente': 'CONFECCOES EDILENI LTDA',
    #   'valor_liquido': 2842.50,
    #   'regiao': 'Sul',
    #   'match_type': 'exact_pedido'
    # }
```

**SQL executado:**

```sql
SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO,
       DESCRICAO_REGIAO, DATA_VENDA
FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
WHERE NUMERO_PEDIDO = :pedido
```

### **Onde é usado?**
- **RAG Engine:** Para alternar entre PostgreSQL (embeddings) e Oracle (SQL)
- **Query Processor:** Para buscar dados estruturados
- **Oracle Sync:** Para ler dados do Oracle

### **Factory Pattern:**

```python
# Cria adapter automaticamente baseado em config
adapter = DatabaseAdapterFactory.create_adapter(config)

# Ou a partir de dicionário
adapter = DatabaseAdapterFactory.from_dict({
    'host': 'localhost',
    'port': 5432,
    'database': 'cativa_rag_db',
    'user': 'user',
    'password': 'pass',
    'db_type': 'postgresql'  # ou 'oracle'
})
```

---

## 2.4. `src/core/logging_config.py`

### **O que faz?**
Configura sistema de logs estruturado para produção com rotação automática.

### **Como funciona?**

```python
setup_production_logging(
    app_name='whatsapp_rag_bot',
    log_level='INFO',
    console_output=True
)

logger = logging.getLogger(__name__)
logger.info("Mensagem processada", extra={
    'user_id': '5547999887766',
    'query': 'qual total de vendas?',
    'processing_time_ms': 3421
})
```

### **Onde é usado?**
- **whatsapp_bot.py:** Logs do bot
- **Todos os módulos:** Rastreamento de operações
- **Debugging:** Identificar problemas

### **Estrutura dos logs:**

```json
{
  "timestamp": "2025-01-04T14:32:15.123Z",
  "level": "INFO",
  "logger": "rag.rag_engine",
  "message": "Query processada com sucesso",
  "app": "whatsapp_rag_bot",
  "user_id": "5547999887766",
  "query": "qual total de vendas de outubro?",
  "route": "text_to_sql",
  "processing_time_ms": 3421,
  "success": true
}
```

### **Rotação de logs:**

```python
# Configuração automática
logs/
  ├── whatsapp_rag_bot.log         # Log atual
  ├── whatsapp_rag_bot.log.1       # Ontem
  ├── whatsapp_rag_bot.log.2       # Anteontem
  └── whatsapp_rag_bot.log.3       # 3 dias atrás
  
# Rotação:
# - Máximo 10MB por arquivo
# - Mantém últimos 7 arquivos
# - Arquivos antigos são deletados automaticamente
```

### **Níveis de log:**

```python
logger.debug("Detalhes técnicos")      # Desenvolvimento
logger.info("Operação normal")         # Produção
logger.warning("Algo suspeito")        # Atenção
logger.error("Erro recuperável")       # Problema
logger.critical("Erro fatal")          # Sistema falhou
```

---

## 2.5. `src/core/rate_limiter.py`

### **O que faz?**
Controla taxa de mensagens por usuário para prevenir abuso/spam.

### **Como funciona?**

```python
rate_limiter = RateLimiter(
    max_requests=5,     # Máximo 5 mensagens
    window_seconds=60   # Por minuto
)

# Verifica se usuário pode enviar mensagem
if rate_limiter.is_allowed(user_id):
    # Processa mensagem
    process_message(msg)
else:
    # Bloqueia usuário
    send_message(user_id, "Limite atingido. Aguarde 1 minuto.")
```

### **Onde é usado?**
- **Message Handler:** Antes de processar cada mensagem WhatsApp
- **Webhook Server:** Proteção contra bots maliciosos

### **Algoritmo: Sliding Window**

```
Tempo (segundos): 0    10    20    30    40    50    60
Mensagens:        |  1  |  2  |  3  |  4  |  5  |  ❌  |  ✅

Regra: Máximo 5 mensagens em janela móvel de 60s

Segunda 60: Primeira mensagem (segundo 0) saiu da janela → usuário pode enviar
```

### **Implementação:**

```python
class RateLimiter:
    def __init__(self, max_requests=5, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {user_id: [timestamp1, timestamp2, ...]}
    
    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        
        # Remove timestamps antigos (fora da janela)
        if user_id in self.requests:
            self.requests[user_id] = [
                ts for ts in self.requests[user_id]
                if now - ts < self.window_seconds
            ]
        
        # Verifica se está dentro do limite
        request_count = len(self.requests.get(user_id, []))
        if request_count < self.max_requests:
            # Registra nova requisição
            if user_id not in self.requests:
                self.requests[user_id] = []
            self.requests[user_id].append(now)
            return True
        
        return False  # Limite excedido
```

### **Configuração por ambiente:**

```python
# Desenvolvimento (mais permissivo)
if Config.ENVIRONMENT == 'development':
    rate_limiter = RateLimiter(max_requests=20, window_seconds=60)

# Produção (mais restritivo)
else:
    rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
```

---

## 2.6. `src/core/retry_handler.py`

### **O que faz?**
Implementa retry automático com backoff exponencial para operações que podem falhar temporariamente.

### **Por que usar retry?**

**Problema:** Falhas temporárias são comuns:
- Timeout de rede
- Banco de dados ocupado
- API temporariamente indisponível
- Erro 429 (Rate Limit) da OpenAI

**Solução:** Tentar novamente automaticamente com espera crescente.

### **Como funciona?**

```python
@retry_database(max_retries=3)
def get_database_connection():
    """
    Se falhar:
    Tentativa 1: Falha → Aguarda 1s → Tenta novamente
    Tentativa 2: Falha → Aguarda 2s → Tenta novamente
    Tentativa 3: Falha → Aguarda 4s → Tenta novamente
    Tentativa 4: ERRO FINAL (após 3 retries)
    """
    return pool.getconn()
```

### **Decorators disponíveis:**

```python
# Retry para banco de dados
@retry_database(max_retries=3)
def execute_query(sql):
    return cursor.execute(sql)

# Retry para API OpenAI
@retry_openai(max_retries=3)
def generate_embedding(text):
    return openai.embeddings.create(...)

# Retry para API Evolution (WhatsApp)
@retry_api_call(max_retries=3)
def send_whatsapp_message(phone, text):
    return evolution_api.send_text_message(phone, text)
```

### **Backoff Exponencial:**

```
Tentativa  Tempo de espera
    1           1s
    2           2s
    3           4s
    4           8s
    5          16s
```

**Fórmula:** `espera = 2^(tentativa-1) segundos`

### **Implementação:**

```python
def retry_database(max_retries=3):
    """Decorator para retry com backoff exponencial"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        # Última tentativa falhou
                        logger.error(f"Failed after {max_retries} retries: {e}")
                        raise
                    
                    # Calcula tempo de espera
                    wait_time = 2 ** attempt
                    logger.warning(f"Attempt {attempt+1} failed. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        return wrapper
    return decorator
```

### **Onde é usado?**
- **Connection Pool:** Obtenção de conexões
- **OpenAI Client:** Geração de embeddings e SQL
- **Evolution Client:** Envio de mensagens WhatsApp
- **Oracle Sync:** Sincronização de dados

---

# 🔒 **3. SECURITY (SEGURANÇA E LGPD)**

## 3.1. `src/security/encryption.py`

### **O que faz?**
Criptografa dados sensíveis usando AES-256-GCM antes de armazenar no PostgreSQL.

### **Por que criptografar?**

**LGPD (Lei Geral de Proteção de Dados):**
- Art. 46: Dados sensíveis devem ser protegidos com técnicas de criptografia
- Art. 48: Incidentes de segurança devem ser notificados
- **Dados sensíveis:** CNPJs, CPFs, nomes de clientes

**Se banco for comprometido:**
- ✅ Com criptografia: Atacante vê apenas dados cifrados
- ❌ Sem criptografia: Atacante vê todos os dados em texto plano

### **Como funciona?**

```python
encryptor = DataEncryptor()

# Criptografa
texto_original = "CNPJ: 12.345.678/0001-90"
texto_cifrado = encryptor.encrypt(texto_original)
# b'gAAAAABl...' (bytes cifrados)

# Descriptografa
texto_recuperado = encryptor.decrypt(texto_cifrado)
# "CNPJ: 12.345.678/0001-90"
```

### **Algoritmo: AES-256-GCM**

- **AES:** Advanced Encryption Standard (padrão militar)
- **256:** Tamanho da chave (256 bits = 2^256 combinações possíveis)
- **GCM:** Galois/Counter Mode (modo de operação com autenticação)

**Por que GCM?**
- **Confidencialidade:** Dados são cifrados
- **Integridade:** Detecta se dados foram adulterados
- **Autenticidade:** Garante que dados vieram da fonte correta

### **Geração de chave:**

```bash
# Script para gerar chave segura
python scripts/generate_encryption_key.py

# Saída:
# ENCRYPTION_KEY=gAAAAABl7X2j...
# 
# Adicione ao .env:
# ENCRYPTION_KEY=gAAAAABl7X2j...
```

**IMPORTANTE:** Chave deve ter 44 caracteres (Fernet format)

### **Exemplo no PostgreSQL:**

```python
# Salva chunk criptografado
chunk = {
    'chunk_id': 'chunk_12345',
    'content_text': None,  # Não salva texto plano
    'encrypted_content': encryptor.encrypt("Pedido 843562, Cliente: CONFECCOES EDILENI, CNPJ: 12.345.678/0001-90"),
    'nivel_lgpd': 'ALTO'
}

# Ao recuperar, descriptografa
encrypted_content = row['encrypted_content']
content_text = encryptor.decrypt(encrypted_content)
```

### **Quando criptografar?**

```python
# Classificação LGPD
if chunk.nivel_lgpd == 'ALTO':
    # Criptografa (contém dados pessoais)
    chunk.encrypted_content = encryptor.encrypt(chunk.content_text)
    chunk.content_text = None
elif chunk.nivel_lgpd == 'MÉDIO':
    # Criptografa parcialmente (valores financeiros)
    chunk.encrypted_content = encryptor.encrypt(chunk.content_text)
else:
    # BAIXO: Não criptografa (dados agregados)
    pass
```

### **Onde é usado?**
- **Data Processor:** Ao salvar chunks no PostgreSQL
- **RAG Engine:** Ao recuperar chunks criptografados
- **Oracle Sync:** Ao sincronizar dados sensíveis

---

## 3.2. `src/security/lgpd_audit.py`

### **O que faz?**
Registra todos os acessos a dados pessoais para compliance LGPD (Art. 37).

### **Por que auditar?**

**LGPD Art. 37:** Controlador deve manter registro de operações de tratamento de dados.

**Obrigatório registrar:**
- Quem acessou (user_id, user_name)
- O que acessou (chunks_accessed)
- Quando acessou (accessed_at)
- Qual clearance tinha (user_clearance)
- Se teve sucesso (success)
- Motivo de negação (denied_reason)

### **Como funciona?**

```python
audit_logger = LGPDAuditLogger(postgres_conn)

# Registra acesso bem-sucedido
audit_logger.log_access(
    user_id='5547999887766',
    user_name='João Silva',
    user_clearance='ALTO',
    query_text='Me mostre dados do cliente CONFECCOES EDILENI',
    query_classification='ALTO',
    route_used='embeddings',
    chunks_accessed=['chunk_12345', 'chunk_12346'],
    success=True,
    processing_time_ms=1234
)

# Registra acesso negado
audit_logger.log_access(
    user_id='5547777777777',
    user_name='Maria Santos',
    user_clearance='BAIXO',
    query_text='Me mostre CNPJs dos clientes',
    query_classification='ALTO',
    route_used='error',
    chunks_accessed=[],
    success=False,
    denied_reason='Insufficient clearance: BAIXO < ALTO'
)
```

### **Tabela `access_log` (PostgreSQL):**

```sql
CREATE TABLE access_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    user_name TEXT,
    user_clearance TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_classification TEXT NOT NULL,
    route_used TEXT NOT NULL,  -- 'text_to_sql', 'embeddings', 'cache', 'error'
    chunks_accessed TEXT[],
    success BOOLEAN NOT NULL DEFAULT FALSE,
    denied_reason TEXT,
    processing_time_ms INTEGER,
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### **Consultas úteis:**

```sql
-- Acessos nas últimas 24h
SELECT * FROM access_log 
WHERE accessed_at >= NOW() - INTERVAL '24 hours'
ORDER BY accessed_at DESC;

-- Acessos negados (violações)
SELECT user_name, query_text, denied_reason, accessed_at
FROM access_log 
WHERE success = FALSE
ORDER BY accessed_at DESC;

-- Top usuários por volume de queries
SELECT user_name, COUNT(*) as total_queries
FROM access_log
GROUP BY user_name
ORDER BY total_queries DESC;

-- Chunks mais acessados
SELECT UNNEST(chunks_accessed) as chunk_id, COUNT(*) as access_count
FROM access_log
WHERE chunks_accessed IS NOT NULL
GROUP BY chunk_id
ORDER BY access_count DESC
LIMIT 10;
```

### **Política de retenção:**

```python
# Limpa logs antigos (LGPD: dados devem ser excluídos após finalidade)
audit_logger.cleanup_old_logs(days=365)
# Mantém últimos 365 dias (1 ano)
```

### **Relatório de compliance:**

```python
report = audit_logger.generate_compliance_report(
    start_date='2025-01-01',
    end_date='2025-01-31'
)

print(f"Total de acessos: {report['total_accesses']}")
print(f"Acessos negados: {report['denied_accesses']}")
print(f"Taxa de sucesso: {report['success_rate']}%")
print(f"Usuários únicos: {report['unique_users']}")
```

### **Onde é usado?**
- **RAG Engine:** Após processar cada query
- **Message Handler:** Ao processar mensagens WhatsApp
- **Text-to-SQL:** Ao executar SQL no Oracle

---

## 3.3. `src/security/lgpd_query_classifier.py`

### **O que faz?**
Classifica queries em tempo real em níveis LGPD (ALTO, MÉDIO, BAIXO) antes de processar.

### **Por que classificar queries?**

**Exemplo:**
- Query: "Me mostre CNPJs dos clientes"
- Classificação: **ALTO** (contém dados pessoais)
- Usuário tem clearance: **BAIXO**
- Resultado: ❌ **ACESSO NEGADO**

**Proteção em tempo real:**
- Impede acesso não autorizado ANTES de buscar dados
- Registra tentativas de acesso indevido
- Garante compliance LGPD Art. 7º (consentimento)

### **Como funciona?**

```python
classifier = LGPDQueryClassifier()

result = classifier.classify_query("Qual o total de vendas de outubro?")

print(result.level)       # MÉDIO
print(result.confidence)  # 0.8
print(result.reasoning)   # "Query solicita dados financeiros: 'total'"
print(result.is_structured)  # True (pode usar Text-to-SQL)
```

### **Padrões de classificação:**

```python
# ALTO - Dados pessoais
high_patterns = [
    'cnpj', 'cpf', 'nome do cliente', 'cliente específico',
    'fornecedor específico', 'dados pessoais', 'titular'
]

# MÉDIO - Dados financeiros
medium_patterns = [
    'valor', 'faturamento', 'receita', 'custo', 'pagamento',
    'título', 'duplicata', 'nota fiscal', 'pedido específico'
]

# BAIXO - Dados agregados
low_patterns = [
    'total', 'média', 'quantidade', 'resumo', 'estatística',
    'geral', 'período', 'mês', 'ano'
]
```

### **Exemplos de classificação:**

| **Query** | **Classificação** | **Reasoning** |
|-----------|------------------|---------------|
| "Qual o total de vendas de outubro?" | MÉDIO | Dados financeiros ("total", "vendas") |
| "Me mostre CNPJs dos clientes" | ALTO | Dados pessoais (CNPJ) |
| "Quantos pedidos tivemos este mês?" | BAIXO | Dados agregados (quantidade) |
| "Valor do pedido 843562" | MÉDIO | Dado financeiro específico |
| "Qual o nome do cliente do pedido X?" | ALTO | Dado pessoal (nome cliente) |
| "Média de vendas por região" | BAIXO | Dados agregados (média) |

### **Estrutura do resultado:**

```python
@dataclass
class LGPDClassification:
    level: str            # "ALTO", "MÉDIO", "BAIXO"
    confidence: float     # 0.0 - 1.0
    reasoning: str        # Justificativa da classificação
    is_structured: bool   # True se pode usar Text-to-SQL
```

### **Integração com permissões:**

```python
# 1. Classifica query
classification = classifier.classify_query(query)

# 2. Obtém clearance do usuário
user_context = authorization.get_user_context(user_id)
user_clearance = user_context['lgpd_clearance']  # BAIXO, MÉDIO, ALTO

# 3. Verifica permissão
if not can_access(user_clearance, classification.level):
    return "Você não tem permissão para acessar esses dados."
```

### **Lógica de permissão:**

```python
def can_access(user_clearance: str, data_level: str) -> bool:
    """
    Regra: Usuário só pode acessar dados de nível igual ou inferior
    
    Hierarquia: BAIXO < MÉDIO < ALTO
    """
    levels = {'BAIXO': 0, 'MÉDIO': 1, 'ALTO': 2}
    return levels[user_clearance] >= levels[data_level]
```

**Tabela de permissões:**

| **User Clearance** | **Pode acessar BAIXO?** | **Pode acessar MÉDIO?** | **Pode acessar ALTO?** |
|--------------------|------------------------|------------------------|----------------------|
| BAIXO              | ✅                     | ❌                     | ❌                   |
| MÉDIO              | ✅                     | ✅                     | ❌                   |
| ALTO               | ✅                     | ✅                     | ✅                   |

### **Onde é usado?**
- **RAG Engine:** Primeira etapa do `process_query()`
- **Message Handler:** Antes de processar mensagens WhatsApp
- **LGPD Audit:** Para registrar classificação da query

---

# 🔄 **4. DATA PROCESSING (PROCESSAMENTO DE DADOS)**

## 4.1. `src/data_processing/chunking.py`

### **O que faz?**
Divide documentos grandes em pedaços (chunks) menores para processamento eficiente.

### **Por que fazer chunking?**

**Problema:**
- Embeddings têm limite de tokens (8191 para `text-embedding-3-small`)
- LLMs têm contexto limitado (GPT-4: 8192 tokens)
- Documentos grandes não cabem no modelo

**Solução:**
```
Documento grande (10.000 tokens)
         ↓
    Chunking
         ↓
Chunk 1 (800 tokens) + Chunk 2 (800 tokens) + ... + Chunk 13 (800 tokens)
```

### **Como funciona?**

```python
chunker = IntelligentChunker(
    max_tokens=800,      # Máximo por chunk
    overlap_tokens=100,  # Sobreposição entre chunks
    min_tokens=120       # Mínimo (menores são consolidados)
)

text = """
Pedido 843562 para cliente CONFECCOES EDILENI LTDA.
Valor total: R$ 2.842,50.
Região: Sul.
Data: 15/10/2024.
"""

chunks = chunker.chunk_text(text)
# [
#   Chunk(text="Pedido 843562...", tokens=150, chunk_id="chunk_1"),
#   ...
# ]
```

### **Estratégias de chunking:**

**1. Chunking Simples (por tokens):**
```
Texto: "A B C D E F G H I J K L M N O P"
Chunk size: 5 tokens
Overlap: 2 tokens

Chunk 1: A B C D E
Chunk 2:     D E F G H
Chunk 3:         G H I J K
Chunk 4:             J K L M N
Chunk 5:                 M N O P
```

**2. Chunking Inteligente (respeita estrutura):**
```
Texto:
  "Pedido 843562.\n"
  "Cliente: CONFECCOES EDILENI.\n"
  "Valor: R$ 2.842,50.\n"
  "Região: Sul.\n"

Chunk 1: "Pedido 843562. Cliente: CONFECCOES EDILENI."
Chunk 2: "Cliente: CONFECCOES EDILENI. Valor: R$ 2.842,50. Região: Sul."
         ↑ Overlap preserva contexto
```

### **Por que usar overlap?**

**Sem overlap:**
```
Chunk 1: "Pedido 843562 para cliente CONFECCOES"
Chunk 2: "EDILENI LTDA. Valor: R$ 2.842,50"

Query: "Qual o valor do pedido 843562 da CONFECCOES EDILENI?"
❌ Chunk 1 tem pedido e parte do nome
❌ Chunk 2 tem valor e resto do nome
→ Nenhum chunk tem TUDO junto!
```

**Com overlap:**
```
Chunk 1: "Pedido 843562 para cliente CONFECCOES EDILENI"
Chunk 2: "CONFECCOES EDILENI LTDA. Valor: R$ 2.842,50"
              ↑ Overlap

Query: "Qual o valor do pedido 843562 da CONFECCOES EDILENI?"
✅ Chunk 2 tem nome completo + valor
→ Busca vetorial encontra Chunk 2 com alta similaridade!
```

### **Configuração recomendada:**

```python
# Para OpenAI text-embedding-3-small
Config.MAX_CHUNK_TOKENS = 800       # Máximo
Config.OVERLAP_TOKENS = 100         # 12.5% de overlap
Config.MIN_CHUNK_TOKENS = 120       # Evita chunks muito pequenos
```

### **Onde é usado?**
- **Oracle Sync:** Ao sincronizar dados do Oracle para PostgreSQL
- **Data Processor:** Ao processar CSVs ou documentos
- **RAG Engine:** Ao preparar contexto para LLM

---

## 4.2. `src/data_processing/embeddings.py`

### **O que faz?**
Gera embeddings (vetores semânticos) para textos usando OpenAI API.

### **O que são embeddings?**

**Conceito:** Representação numérica de significado.

```
Texto: "cachorro"
  ↓ OpenAI Embedding
Vetor: [0.23, -0.51, 0.87, ..., 0.12]  (1536 números)
```

**Similaridade semântica:**
```
"cachorro"     → [0.23, -0.51, ..., 0.12]
"cão"          → [0.25, -0.49, ..., 0.15]  ← Muito similar!
"gato"         → [0.20, -0.45, ..., 0.10]  ← Similar (ambos animais)
"carro"        → [-0.92, 0.31, ..., 0.78]  ← Muito diferente
```

**Cálculo de similaridade:**
```python
import numpy as np

def cosine_similarity(vec1, vec2):
    """Calcula similaridade entre dois vetores (0-1)"""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

sim_cachorro_cao = cosine_similarity(
    embedding_cachorro,
    embedding_cao
)  # 0.95 (muito similar)

sim_cachorro_carro = cosine_similarity(
    embedding_cachorro,
    embedding_carro
)  # 0.12 (não similar)
```

### **Como funciona?**

```python
generator = EmbeddingGenerator()

# Gera embedding para texto
text = "Pedido 843562 para cliente CONFECCOES EDILENI. Valor: R$ 2.842,50"
embedding = generator.generate_embedding(text)

print(type(embedding))         # <class 'numpy.ndarray'>
print(embedding.shape)          # (1536,)
print(embedding[:5])            # [-0.023456, 0.187234, -0.056789, ...]
```

### **Modelo usado:**

```python
model = "text-embedding-3-small"
# - Dimensão: 1536 floats
# - Custo: $0.020 por 1M tokens
# - Performance: Alta qualidade para português
```

### **Batch processing:**

```python
# Processa múltiplos textos de uma vez (mais eficiente)
texts = [
    "Pedido 843562...",
    "Pedido 843587...",
    "Pedido 843601..."
]

embeddings = generator.generate_embeddings_batch(texts, batch_size=100)
# [[0.23, -0.51, ...], [0.25, -0.49, ...], ...]
```

### **Retry automático:**

```python
@retry_openai(max_retries=3)
def generate_embedding(self, text: str) -> np.ndarray:
    """
    Se OpenAI API falhar:
    - Aguarda 1s, 2s, 4s entre tentativas
    - Até 3 retries
    """
    response = self.openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return np.array(response.data[0].embedding)
```

### **Onde é usado?**
- **Oracle Sync:** Gera embeddings para chunks ao sincronizar
- **RAG Engine:** Gera embedding da query do usuário para busca vetorial
- **Data Processor:** Processa novos documentos

### **Custo estimado:**

```
1 embedding = ~200 tokens (média)
1M tokens = $0.020

Para 10.000 chunks:
10.000 chunks × 200 tokens = 2M tokens
2M tokens × $0.020 = $0.040 (4 centavos de dólar)
```

---

## 4.3. `src/data_processing/lgpd_classifier.py`

### **O que faz?**
Classifica chunks de dados em níveis LGPD (ALTO, MÉDIO, BAIXO) com base no conteúdo.

### **Diferença entre `lgpd_classifier.py` e `lgpd_query_classifier.py`:**

| **lgpd_classifier.py** | **lgpd_query_classifier.py** |
|------------------------|------------------------------|
| Classifica **chunks de dados** | Classifica **queries do usuário** |
| Executa durante **sincronização** | Executa em **tempo real** |
| Resultado salvo no **PostgreSQL** | Resultado usado para **controle de acesso** |

### **Como funciona?**

```python
classifier = LGPDDataClassifier()

chunk_text = "Pedido 843562 para cliente CONFECCOES EDILENI LTDA, CNPJ 12.345.678/0001-90, Valor: R$ 2.842,50"

classification = classifier.classify_chunk(chunk_text)

print(classification.level)        # ALTO
print(classification.confidence)   # 0.95
print(classification.detected_fields)
# {'cnpj': ['12.345.678/0001-90'], 'nome_cliente': ['CONFECCOES EDILENI LTDA']}
```

### **Padrões de detecção:**

```python
# ALTO - Dados pessoais (LGPD Art. 5º)
ALTO_PATTERNS = {
    'cnpj': r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}',
    'cpf': r'\d{3}\.\d{3}\.\d{3}-\d{2}',
    'nome_cliente': r'Cliente:\s*([A-Z\s]+)',
    'email': r'[\w\.-]+@[\w\.-]+\.\w+',
    'telefone': r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}'
}

# MÉDIO - Dados financeiros
MÉDIO_PATTERNS = {
    'valor': r'R\$\s*[\d.,]+',
    'pedido_numero': r'Pedido\s+(\d+)',
    'nota_fiscal': r'NF-e\s+(\d+)',
    'duplicata': r'Duplicata\s+(\d+)'
}

# BAIXO - Dados agregados
BAIXO_PATTERNS = {
    'total': r'Total:\s*R\$',
    'média': r'Média:\s*R\$',
    'quantidade': r'Quantidade:\s*\d+',
    'período': r'\d{2}/\d{4}'
}
```

### **Lógica de classificação:**

```python
def classify_chunk(self, text: str) -> Classification:
    detected = {}
    
    # 1. Verifica padrões ALTO
    for field, pattern in ALTO_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            detected[field] = matches
            return Classification(
                level='ALTO',
                confidence=0.95,
                detected_fields=detected
            )
    
    # 2. Verifica padrões MÉDIO
    for field, pattern in MÉDIO_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            detected[field] = matches
            return Classification(
                level='MÉDIO',
                confidence=0.85,
                detected_fields=detected
            )
    
    # 3. Default: BAIXO
    return Classification(
        level='BAIXO',
        confidence=0.7,
        detected_fields={}
    )
```

### **Aplicação no PostgreSQL:**

```python
# Durante sincronização
chunk = {
    'chunk_id': 'chunk_12345',
    'content_text': "Pedido 843562, Cliente: CONFECCOES EDILENI LTDA, CNPJ: 12.345.678/0001-90",
    'nivel_lgpd': None  # Será preenchido
}

# Classifica
classification = classifier.classify_chunk(chunk['content_text'])
chunk['nivel_lgpd'] = classification.level  # ALTO

# Criptografa se necessário
if chunk['nivel_lgpd'] == 'ALTO':
    chunk['encrypted_content'] = encryptor.encrypt(chunk['content_text'])
    chunk['content_text'] = None  # Remove texto plano

# Salva no PostgreSQL
save_chunk(chunk)
```

### **Estatísticas de classificação:**

```sql
-- Chunks por nível LGPD
SELECT nivel_lgpd, COUNT(*) as quantidade
FROM chunks
GROUP BY nivel_lgpd
ORDER BY nivel_lgpd;

-- Resultado:
-- nivel_lgpd | quantidade
-- ALTO       |      1.250
-- MÉDIO      |      5.830
-- BAIXO      |      2.920
```

### **Onde é usado?**
- **Oracle Sync:** Ao sincronizar dados do Oracle para PostgreSQL
- **Data Processor:** Ao processar novos documentos
- **LGPD Audit:** Para registrar níveis de classificação

---

## 4.4. `src/data_processing/oracle_sync.py`

### **O que faz?**
Sincroniza dados do Oracle (banco de produção) para PostgreSQL (banco RAG) periodicamente.

### **Por que sincronizar?**

**Problema:**
- Oracle contém dados de produção (pedidos, clientes, vendas)
- RAG precisa desses dados para responder queries
- Oracle não tem busca vetorial (pgvector)

**Solução:**
```
Oracle (Produção)  →  Sincronização  →  PostgreSQL (RAG + pgvector)
```

### **Como funciona?**

```
1. Oracle → Busca dados novos
   ↓
2. Chunking → Divide em pedaços
   ↓
3. LGPD Classification → Classifica nível
   ↓
4. Encryption → Criptografa se necessário
   ↓
5. Embeddings → Gera vetores
   ↓
6. PostgreSQL → Salva chunks
```

### **Execução:**

```bash
# Sincroniza últimos 30 dias (máximo 5000 registros)
python -m src.data_processing.oracle_sync --days 30 --max 5000

# Sincroniza período específico
python -m src.data_processing.oracle_sync --start 2024-10-01 --end 2024-10-31

# Sincroniza tudo (CUIDADO: pode levar horas)
python -m src.data_processing.oracle_sync --all
```

### **Código simplificado:**

```python
class OracleSync:
    def sync(self, days=30, max_records=5000):
        # 1. Conecta aos bancos
        oracle_conn = self.oracle_pool.get_connection()
        postgres_conn = self.postgres_pool.get_connection()
        
        # 2. Busca dados do Oracle
        data_inicio = datetime.now() - timedelta(days=days)
        rows = oracle_conn.execute("""
            SELECT REGISTRO_ID, TEXTO_COMPLETO, DATA_VENDA, VALOR
            FROM INDUSTRIAL.VW_RAG_VENDAS_TEXTUAL
            WHERE DATA_VENDA >= :data_inicio
            AND ROWNUM <= :max_rows
            ORDER BY DATA_VENDA DESC
        """, {'data_inicio': data_inicio, 'max_rows': max_records})
        
        # 3. Processa cada registro
        for row in rows:
            # 3.1. Chunking
            chunks = self.chunker.chunk_text(row['texto_completo'])
            
            for chunk in chunks:
                # 3.2. LGPD Classification
                classification = self.lgpd_classifier.classify_chunk(chunk.text)
                
                # 3.3. Encryption (se necessário)
                if classification.level == 'ALTO':
                    encrypted = self.encryptor.encrypt(chunk.text)
                    chunk_data = {
                        'content_text': None,
                        'encrypted_content': encrypted
                    }
                else:
                    chunk_data = {
                        'content_text': chunk.text,
                        'encrypted_content': None
                    }
                
                # 3.4. Embeddings
                embedding = self.embedding_generator.generate_embedding(chunk.text)
                
                # 3.5. Salva no PostgreSQL
                chunk_data.update({
                    'chunk_id': f"oracle_{row['registro_id']}_{chunk.index}",
                    'entity': 'PEDIDO_VENDA',
                    'nivel_lgpd': classification.level,
                    'embedding': embedding,
                    'data_origem': row['data_venda'],
                    'source_file': 'oracle_vw_vendas_textual'
                })
                
                postgres_conn.insert_chunk(chunk_data)
        
        # 4. Commit
        postgres_conn.commit()
        print(f"✓ Sincronizados {len(rows)} registros")
```

### **Progressão visual:**

```
[Oracle Sync] Iniciando sincronização...
[1/5000] Processando registro 12345... ✓
[2/5000] Processando registro 12346... ✓
[3/5000] Processando registro 12347... ✓
...
[5000/5000] Processando registro 17345... ✓

Estatísticas:
  - Registros processados: 5000
  - Chunks criados: 12.450
  - Embeddings gerados: 12.450
  - LGPD ALTO: 1.250 (criptografados)
  - LGPD MÉDIO: 5.830
  - LGPD BAIXO: 5.370
  - Tempo total: 45min 23s
  - Throughput: 110 registros/segundo
```

### **Agendamento automático (cron):**

```bash
# crontab -e

# Sincroniza todo dia às 2h da manhã
0 2 * * * cd /path/to/fontes && python -m src.data_processing.oracle_sync --days 1 >> logs/sync.log 2>&1
```

### **Onde é usado?**
- **Produção:** Executado periodicamente (diariamente)
- **Inicial:** Primeira carga de dados (sincroniza últimos 6 meses)

---

# 🗄️ **5. SQL (TEXT-TO-SQL)**

## 5.1. `src/sql/schema_introspector.py`

### **O que faz?**
Lê e descreve o schema do banco Oracle para o GPT-4 poder gerar SQL correto.

### **Por que o GPT-4 precisa do schema?**

**Problema:** GPT-4 não sabe quais tabelas/colunas existem no seu banco.

```
User: "Qual o total de vendas de outubro?"
GPT-4 (SEM schema): 
  SELECT SUM(total_sales) FROM sales WHERE month = 10
  ❌ Tabela "sales" não existe!
  ❌ Coluna "total_sales" não existe!
```

**Solução:** Fornecer schema para o GPT-4.

```
User: "Qual o total de vendas de outubro?"
GPT-4 (COM schema):
  SELECT SUM(VALOR_ITEM_LIQUIDO) 
  FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA 
  WHERE EXTRACT(MONTH FROM DATA_VENDA) = 10
  ✅ Tabela correta!
  ✅ Colunas corretas!
```

### **Como funciona?**

```python
introspector = SchemaIntrospector(oracle_conn)

# Obtém schema legível para GPT-4
schema = introspector.get_schema_for_llm()

print(schema)
```

**Saída:**

```markdown
# SCHEMA ORACLE - INDUSTRIAL

## VW_RAG_VENDAS_ESTRUTURADA
Vendas da empresa (pedidos, clientes, valores).

Colunas:
- NUMERO_PEDIDO (NUMBER): Número do pedido
- DATA_VENDA (DATE): Data da venda
- NOME_CLIENTE (VARCHAR2): Nome do cliente
- CNPJ_CLIENTE (VARCHAR2): CNPJ do cliente (sensível)
- VALOR_ITEM_BRUTO (NUMBER): Valor bruto do item
- VALOR_ITEM_LIQUIDO (NUMBER): Valor líquido (após descontos)
- DESCRICAO_REGIAO (VARCHAR2): Região de venda
- EMPRESA (VARCHAR2): Empresa Cativa

## VW_RAG_CP_TITULOS_TEXTUAL
Contas a pagar (fornecedores, títulos, vencimentos).

Colunas:
- TITULO (VARCHAR2): Número do título
- NOME_FORNECEDOR (VARCHAR2): Nome do fornecedor
- VALOR_TITULO (NUMBER): Valor do título
- DATA_VENCIMENTO (DATE): Data de vencimento
...
```

### **Onde é usado?**
- **Text-to-SQL Generator:** Para montar prompt do GPT-4
- **SQL Validator:** Para validar nomes de tabelas/colunas

### **Cache automático:**

```python
# Schema é cacheado (não precisa ler do banco toda vez)
introspector = SchemaIntrospector(oracle_conn, cache_ttl=3600)
# Cache válido por 1 hora
```

---

## 5.2. `src/sql/sql_validator.py`

### **O que faz?**
Valida e sanitiza SQL gerado pelo GPT-4 antes de executar no Oracle.

### **Por que validar?**

**Problema:** GPT-4 pode gerar SQL perigoso ou inválido.

```sql
-- SQL injection
SELECT * FROM vendas WHERE cliente = 'ABC'; DROP TABLE clientes; --

-- Operações perigosas
DELETE FROM vendas WHERE data < '2024-01-01'

-- SQL infinito (sem LIMIT)
SELECT * FROM vendas  -- Pode retornar milhões de linhas!
```

**Solução:** Validar ANTES de executar.

### **Como funciona?**

```python
validator = SQLValidator()

sql = "SELECT * FROM vendas"
is_valid, sanitized_sql = validator.sanitize_and_limit(sql, limit=100)

if is_valid:
    print(sanitized_sql)
    # SELECT * FROM vendas WHERE ROWNUM <= 100
else:
    print(f"SQL inválido: {sanitized_sql}")
```

### **Validações aplicadas:**

**1. Bloqueia operações perigosas:**

```python
DANGEROUS_KEYWORDS = [
    'DELETE', 'DROP', 'TRUNCATE', 'ALTER', 'CREATE',
    'INSERT', 'UPDATE', 'GRANT', 'REVOKE', 'EXEC'
]

if any(keyword in sql.upper() for keyword in DANGEROUS_KEYWORDS):
    return False, f"Operação proibida: {keyword}"
```

**2. Verifica se é SELECT:**

```python
if not sql.upper().strip().startswith('SELECT'):
    return False, "Apenas SELECT é permitido"
```

**3. Adiciona LIMIT (ROWNUM no Oracle):**

```python
# Original
SELECT * FROM vendas

# Sanitizado
SELECT * FROM vendas WHERE ROWNUM <= 100
```

**4. Remove comentários (previne SQL injection):**

```python
# Original
SELECT * FROM vendas -- DROP TABLE clientes

# Sanitizado
SELECT * FROM vendas
```

### **Exemplos:**

| **SQL Original** | **Resultado** | **SQL Sanitizado** |
|-----------------|--------------|-------------------|
| `SELECT * FROM vendas` | ✅ OK | `SELECT * FROM vendas WHERE ROWNUM <= 100` |
| `DELETE FROM vendas` | ❌ BLOQUEIA | "Operação proibida: DELETE" |
| `SELECT * FROM vendas; DROP TABLE clientes;` | ❌ BLOQUEIA | "Operação proibida: DROP" |
| `SELECT * FROM vendas -- comment` | ✅ OK | `SELECT * FROM vendas WHERE ROWNUM <= 100` |

### **Onde é usado?**
- **Text-to-SQL Service:** Após GPT-4 gerar SQL, valida antes de executar

---

## 5.3. `src/sql/text_to_sql_generator.py`

### **O que faz?**
Gera SQL automaticamente a partir de perguntas em português usando GPT-4.

### **Como funciona?**

```python
generator = TextToSQLGenerator(openai_client, schema)

question = "Qual o total de vendas de outubro de 2024?"

sql = generator.generate_sql(question)

print(sql)
# SELECT SUM(VALOR_ITEM_LIQUIDO) as total
# FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
# WHERE EXTRACT(MONTH FROM DATA_VENDA) = 10
#   AND EXTRACT(YEAR FROM DATA_VENDA) = 2024
```

### **Prompt para GPT-4:**

```python
prompt = f"""
Você é um especialista em SQL para Oracle 11g.

Dada a pergunta do usuário, gere uma query SQL válida para Oracle.

**SCHEMA DISPONÍVEL:**
{schema}

**REGRAS:**
1. Use APENAS tabelas e colunas do schema acima
2. Sempre adicione ROWNUM <= 100 para limitar resultados
3. Use funções Oracle: EXTRACT, TO_CHAR, TRUNC, etc
4. Para datas, use TRUNC ou EXTRACT conforme necessário
5. NÃO use LIMIT (use ROWNUM <= N)
6. NÃO retorne dados sensíveis (CNPJ, CPF) a menos que explicitamente solicitado
7. Use aliases descritivos para colunas

**PERGUNTA DO USUÁRIO:**
{question}

**SQL QUERY:**
```sql
"""

response = openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.0  # Determinístico
)

sql = extract_sql_from_response(response.choices[0].message.content)
```

### **Exemplos de geração:**

**Entrada:** "Qual o total de vendas de outubro de 2024?"

**SQL Gerado:**
```sql
SELECT SUM(VALOR_ITEM_LIQUIDO) as total_vendas
FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
WHERE EXTRACT(MONTH FROM DATA_VENDA) = 10
  AND EXTRACT(YEAR FROM DATA_VENDA) = 2024
```

---

**Entrada:** "Liste os 5 maiores pedidos de setembro"

**SQL Gerado:**
```sql
SELECT * FROM (
    SELECT 
        NUMERO_PEDIDO,
        NOME_CLIENTE,
        VALOR_ITEM_LIQUIDO,
        DATA_VENDA
    FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
    WHERE EXTRACT(MONTH FROM DATA_VENDA) = 9
    ORDER BY VALOR_ITEM_LIQUIDO DESC
)
WHERE ROWNUM <= 5
```

---

**Entrada:** "Quantos pedidos tivemos por região em 2024?"

**SQL Gerado:**
```sql
SELECT 
    DESCRICAO_REGIAO as regiao,
    COUNT(*) as quantidade_pedidos,
    SUM(VALOR_ITEM_LIQUIDO) as valor_total
FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
WHERE EXTRACT(YEAR FROM DATA_VENDA) = 2024
GROUP BY DESCRICAO_REGIAO
ORDER BY COUNT(*) DESC
```

### **Onde é usado?**
- **Text-to-SQL Service:** Componente principal da rota PRIMARY do RAG

---

## 5.4. `src/sql/text_to_sql_service.py`

### **O que faz?**
Serviço completo que orquestra todo o fluxo Text-to-SQL: geração → validação → execução.

### **Como funciona?**

```
User Query
  ↓
Schema Introspector → Obtém schema
  ↓
Text-to-SQL Generator → GPT-4 gera SQL
  ↓
SQL Validator → Valida e sanitiza
  ↓
Oracle Connection Pool → Executa SQL
  ↓
Results → Retorna dados
```

### **Código:**

```python
service = TextToSQLService(oracle_pool, openai_client)

result = service.generate_and_execute(
    "Qual o total de vendas de outubro?",
    limit=10
)

if result['success']:
    print(f"SQL: {result['generated_sql']}")
    print(f"Rows: {result['rows']}")
    # [{'total_vendas': 1234567.89}]
else:
    print(f"Erro: {result['error']}")
    print(f"Fallback: {result['needs_fallback']}")
```

### **Exemplo completo:**

```python
# 1. Gera SQL
result = service.generate_and_execute("Qual o total de vendas de outubro?")

# 2. Resultado
print(result)
{
    'success': True,
    'generated_sql': 'SELECT SUM(VALOR_ITEM_LIQUIDO) as total ...',
    'rows': [{'total': 1234567.89}],
    'row_count': 1,
    'execution_time_ms': 234,
    'needs_fallback': False,
    'error': None
}
```

### **Tratamento de erros:**

```python
# Query muito genérica
result = service.generate_and_execute("Me fale sobre vendas")

{
    'success': False,
    'generated_sql': None,
    'rows': [],
    'needs_fallback': True,  # ← Sinaliza para usar embedding search
    'error': 'Query too generic for SQL generation'
}
```

### **Onde é usado?**
- **RAG Engine:** Rota PRIMARY (tenta Text-to-SQL primeiro)

---

# 🧠 **6. RAG ENGINE (MOTOR PRINCIPAL)**

## 6.1. `src/rag/rag_engine.py`

### **O que faz?**
Motor RAG (Retrieval-Augmented Generation) - cérebro do sistema que orquestra todo o processamento de queries.

### **Como funciona?**

```
Query do usuário
  ↓
1. Check Cache (se já foi consultado antes)
  ↓
2. LGPD Classification & Permission Check
  ├─ Classifica query (ALTO/MÉDIO/BAIXO)
  └─ Verifica se usuário tem permissão
  ↓
3. Rota PRIMARY: Text-to-SQL (Oracle)
  ├─ Gera SQL com GPT-4
  ├─ Valida SQL
  ├─ Executa no Oracle
  └─ Retorna resultados ✅
  ↓ (se falhar ou 0 resultados)
4. Rota FALLBACK: Embedding Search (PostgreSQL)
  ├─ Gera embedding da query
  ├─ Busca vetorial no PostgreSQL
  ├─ Descriptografa chunks
  └─ Formata resposta ✅
  ↓
5. Cache + Audit + Return
```

### **Onde é usado?**
- **Message Handler:** Processa cada mensagem WhatsApp
- **API REST:** Endpoint para consultas programáticas (futuro)
- **CLI:** Interface de linha de comando para testes

### **Método principal: `process_query`**

```python
rag_engine = RAGEngine(
    oracle_config={'host': '10.1.200.43', ...},
    postgres_config={'host': 'localhost', ...},
    use_openai=True
)

response = rag_engine.process_query(
    query="Qual o total de vendas de outubro?",
    user_context={
        'user_id': '5547999887766',
        'lgpd_clearance': 'MÉDIO',
        'user_name': 'João Silva'
    },
    conversation_history=[
        {'user': 'Oi', 'bot': 'Olá! Como posso ajudar?'},
        {'user': 'Qual o total de vendas?', 'bot': '...'}
    ]
)

print(response.success)       # True
print(response.answer)        # "O total de vendas de outubro foi R$ 1.234.567,89"
print(response.confidence)    # 0.85
print(response.sources)       # [{'source': 'oracle_text_to_sql', 'sql': '...'}]
```

### **Estrutura da resposta:**

```python
@dataclass
class RAGResponse:
    success: bool                    # True se encontrou resposta
    answer: str                      # Resposta em português
    confidence: float                # 0.0-1.0 (confiança na resposta)
    sources: List[Dict]              # Fontes usadas
    metadata: Dict                   # Metadados (rota, LGPD, etc)
    processing_time: float           # Tempo de processamento (s)
    lgpd_compliant: bool             # True se respeitou LGPD
    requires_human_review: bool      # True se precisa validação humana
```

### **Fluxo LGPD:**

```python
# 1. Classifica query
lgpd_classification = self.lgpd_classifier.classify(query)
# level: MÉDIO
# confidence: 0.85
# reasoning: "Query solicita dados financeiros"

# 2. Verifica permissão
user_clearance = user_context['lgpd_clearance']  # BAIXO
query_level = lgpd_classification.level           # MÉDIO

if user_clearance < query_level:
    # ❌ ACESSO NEGADO
    return "Você não tem permissão para acessar dados de nível MÉDIO."
```

**Hierarquia de clearance:**
```
BAIXO (0) < MÉDIO (1) < ALTO (2)

Usuário BAIXO:  pode acessar BAIXO apenas
Usuário MÉDIO:  pode acessar BAIXO, MÉDIO
Usuário ALTO:   pode acessar BAIXO, MÉDIO, ALTO
```

### **Rota PRIMARY: Text-to-SQL**

```python
def _try_text_to_sql(self, query: str, lgpd: LGPDClassification):
    # 1. Gera SQL com GPT-4
    result = self.text_to_sql.generate_and_execute(query, limit=10)
    
    # 2. Verifica se retornou dados
    if not result or not result['rows']:
        logger.warning("Text-to-SQL returned 0 rows, triggering fallback")
        return None
    
    # 3. Formata resposta
    answer = self._format_sql_result(result)
    
    return RAGResponse(
        success=True,
        answer=answer,
        confidence=0.85,
        sources=[{'source': 'oracle_text_to_sql', 'sql': result['generated_sql']}],
        metadata={'route': 'text_to_sql', 'rows_returned': len(result['rows'])},
        ...
    )
```

**Quando usar Text-to-SQL:**
- ✅ Queries estruturadas ("total de vendas", "pedido 123")
- ✅ Dados numéricos (valores, quantidades)
- ✅ Agregações (SUM, COUNT, AVG)
- ❌ Queries genéricas ("me fale sobre vendas")
- ❌ Análises complexas

### **Rota FALLBACK: Embedding Search**

```python
def _try_embedding_search(self, query: str, lgpd: LGPDClassification):
    # 1. Gera embedding da query
    query_embedding = self.embedding_generator.generate_embedding(query)
    
    # 2. Busca chunks similares no PostgreSQL
    search_results = self._search_similar_chunks(query_embedding, max_results=10)
    
    # 3. Descriptografa chunks se necessário
    for result in search_results:
        result.content = self._decrypt_if_needed(result)
    
    # 4. Gera resposta com OpenAI (se disponível)
    context_chunks = [{'content': r.content, 'similarity': r.similarity} for r in search_results[:5]]
    answer = self._generate_answer_from_chunks(query, context_chunks)
    
    return RAGResponse(
        success=True,
        answer=answer,
        confidence=avg_similarity * 0.7,
        sources=[{'chunk_id': r.chunk_id, 'similarity': r.similarity} for r in search_results[:3]],
        metadata={'route': 'embeddings', 'chunks_used': len(search_results)},
        ...
    )
```

**SQL de busca vetorial:**

```sql
SELECT 
    chunk_id,
    content_text,
    encrypted_content,
    1 - (embedding <=> %s::vector) as similarity,  -- Distância de cosseno
    entity,
    nivel_lgpd
FROM chunks
WHERE embedding IS NOT NULL
AND 1 - (embedding <=> %s::vector) >= 0.2  -- Threshold mínimo
ORDER BY embedding <=> %s::vector
LIMIT 10;
```

### **Descriptografia de chunks:**

```python
def _decrypt_if_needed(self, chunk_row: Dict) -> str:
    """
    Descriptografa chunk se encrypted_content existir
    
    Lógica:
    1. Se encrypted_content existe → Descriptografa
    2. Senão → Usa content_text diretamente
    """
    encrypted_content = chunk_row.get('encrypted_content')
    
    if not encrypted_content:
        return chunk_row.get('content_text', '')
    
    if not self.encryptor:
        logger.warning("Chunk criptografado mas encryptor indisponível")
        return chunk_row.get('content_text', '')
    
    # Descriptografa usando AES-256-GCM
    decrypted_text = self.encryptor.decrypt(encrypted_content)
    return decrypted_text
```

**Por que descriptografar?**
- Dados ALTO (CNPJ, nomes) são salvos criptografados no PostgreSQL
- Para responder query, precisa descriptografar
- Descriptografia só acontece APÓS verificação de permissão LGPD

### **Cache em memória:**

```python
def _generate_cache_key(self, query: str, user_context: Dict) -> str:
    """Gera chave única baseada em query + user_id + clearance"""
    key_parts = [
        query.lower().strip(),
        user_context.get('user_id', ''),
        user_context.get('lgpd_clearance', '')
    ]
    key_string = '|'.join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()

# Cache de 1 hora
self.cache_ttl = 3600

# Verifica cache antes de processar
cached = self.cache.get(cache_key)
if cached and (time.time() - cached['timestamp']) < self.cache_ttl:
    return cached['response']
```

**Benefícios do cache:**
- 🚀 Resposta instantânea para queries repetidas
- 💰 Economiza tokens OpenAI
- 🔒 Cache por usuário (segurança LGPD)

### **Auditoria LGPD:**

```python
def _log_access_lgpd(self, query: str, lgpd: LGPDClassification, 
                     response: RAGResponse, user_context: Dict, start_time: float):
    """
    Log de acesso LGPD (Art. 37)
    
    Registra:
    - Quem acessou (user_id, user_name)
    - O que acessou (query, chunks)
    - Quando (timestamp)
    - Resultado (success/denied)
    """
    audit_logger.log_access(
        user_id=user_context['user_id'],
        user_name=user_context['user_name'],
        user_clearance=user_context['lgpd_clearance'],
        query_text=query,
        query_classification=lgpd.level.value,
        route_used=response.metadata['route'],
        chunks_accessed=[s['chunk_id'] for s in response.sources],
        success=response.success,
        processing_time_ms=int((time.time() - start_time) * 1000)
    )
```

### **Connection Pool:**

```python
# RAG Engine usa connection pool para produção
self.db_pool = DatabaseConnectionPool(
    postgres_config=postgres_config,
    oracle_config=oracle_config,
    min_connections=2,    # Sempre mantém 2 conexões abertas
    max_connections=10    # Nunca ultrapassa 10
)

# Context manager para buscar chunks
with self.db_pool.postgres_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chunks WHERE ...")
# Conexão automaticamente devolvida ao pool
```

### **Graceful shutdown:**

```python
def close(self):
    """Fecha connection pools ao desligar sistema"""
    if self.db_pool:
        self.db_pool.close_all()
        logger.info("Connection pools closed")
```

### **Onde é usado:**
- **whatsapp_bot.py:** Inicializa RAG Engine
- **message_handler.py:** Chama `process_query` para cada mensagem

---

# 📱 **7. WHATSAPP INTEGRATION**

## 7.1. `src/integrations/whatsapp/authorization.py`

### **O que faz?**
Gerencia permissões de usuários WhatsApp e níveis de clearance LGPD.

### **Como funciona?**

```python
auth = WhatsAppAuthorization()

# Obtém contexto do usuário
user_context = auth.get_user_context('5547999887766@s.whatsapp.net')

print(user_context)
{
    'lgpd_clearance': 'MÉDIO',
    'user_id': '5547999887766@s.whatsapp.net',
    'user_name': 'João Silva',
    'department': 'Vendas',
    'is_admin': False,
    'enabled': True
}
```

### **Arquivo de permissões:**

`src/integrations/whatsapp/whatsapp_users.json`:

```json
{
  "users": {
    "5547999887766@s.whatsapp.net": {
      "name": "João Silva",
      "clearance_level": "MÉDIO",
      "department": "Vendas",
      "enabled": true,
      "added_at": "2025-01-01T10:00:00",
      "notes": ""
    },
    "5547888888888@s.whatsapp.net": {
      "name": "Admin User",
      "clearance_level": "ALTO",
      "department": "TI",
      "enabled": true
    }
  },
  "admins": [
    "5547888888888@s.whatsapp.net"
  ]
}
```

### **Métodos principais:**

```python
# Adicionar usuário
auth.add_user(
    phone_number='5547999887766',
    name='João Silva',
    clearance_level='MÉDIO',
    department='Vendas',
    is_admin=False
)

# Verificar autorização
if auth.is_authorized('5547999887766', required_level='MÉDIO'):
    # Usuário pode acessar dados MÉDIO
    process_query()

# Desabilitar usuário (sem remover)
auth.disable_user('5547999887766')

# Listar todos os usuários
users = auth.list_users()
# [{'phone': '5547999887766', 'name': 'João Silva', 'clearance': 'MÉDIO', ...}]

# Recarregar permissões (hot-reload)
auth.reload_permissions()
```

### **Onde é usado?**
- **Message Handler:** Obtém contexto do usuário antes de processar mensagem
- **manage_whatsapp_users.py:** CLI para gerenciar usuários
- **RAG Engine:** Usa `user_context` para controle LGPD

---

## 7.2. `src/integrations/whatsapp/response_formatter.py`

### **O que faz?**
Formata respostas do RAG Engine para exibição no WhatsApp de forma natural e amigável.

### **Como funciona?**

```python
formatter = ResponseFormatter(use_llm=True)

# RAGResponse do RAG Engine
rag_response = RAGResponse(
    success=True,
    answer="Resultados (prévia):\ntotal | 1234567.89\n...",
    confidence=0.85,
    sources=[{'source': 'oracle_text_to_sql', 'sql': 'SELECT SUM(VALOR)...'}],
    metadata={'route': 'text_to_sql'},
    ...
)

# Formata para WhatsApp
formatted = formatter.format_response(rag_response)

print(formatted)
# "Claro! Encontrei o seguinte valor total:
#
# R$ 1.234.567,89
#
# Precisa de mais alguma informação?"
```

### **Formatação com LLM (GPT-4):**

```python
def _format_with_llm(self, answer: str, rag_response) -> str:
    """
    Usa GPT-4 para formatar resposta de forma natural
    """
    system_prompt = (
        "Você é um assistente prestativo do sistema da Cativa Têxtil.\n"
        "Formate os dados de forma profissional, amigável e clara.\n\n"
        "Estilo de comunicação:\n"
        "- Tom profissional-amigável: cordial, acessível mas respeitoso\n"
        "- PODE usar expressões amigáveis: 'Claro!', 'Encontrei...', 'Aqui estão...'\n"
        "- Inicie confirmando o que foi solicitado\n"
        "- Encerre de forma prestativa (ex: 'Precisa de mais alguma informação?')\n"
        "- NÃO use emojis\n"
        "- NÃO use markdown (asteriscos, sublinhados, etc)\n"
        "- NÃO seja robótico ou excessivamente formal\n"
    )
    
    user_prompt = f"Dados do Oracle:\n{answer}\n\nFormate para WhatsApp."
    
    response = self.llm_client.chat_completion(system_prompt, user_prompt)
    return response
```

**Antes (raw SQL result):**
```
Resultados (prévia):
total | 1234567.89
-----
(1 linha)
```

**Depois (formatado com LLM):**
```
Claro! Encontrei o seguinte valor total:

R$ 1.234.567,89

Precisa de mais alguma informação?
```

### **Formatação de valores monetários:**

```python
def _format_table_data(self, text: str) -> str:
    # Detecta valor numérico
    value = 1234567.89
    
    # Formata com separadores brasileiros
    if value >= 1000000:
        formatted = f"R$ {value:,.2f}".replace(',', '.')
        formatted = formatted.replace('.', ',', 1)
        # R$ 1.234.567,89
    elif value >= 1000:
        formatted = f"R$ {value:,.2f}".replace(',', '.')
        # R$ 1.234,56
    else:
        formatted = f"R$ {value:.2f}".replace('.', ',')
        # R$ 12,34
```

### **Remoção de markdown:**

```python
def _apply_whatsapp_formatting(self, text: str) -> str:
    """Remove formatação markdown para WhatsApp"""
    # Remove **bold**
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    
    # Remove *italic*
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)
    
    # Remove _underline_
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    return text
```

**Por que remover markdown?**
- WhatsApp renderiza markdown automaticamente
- GPT-4 tende a usar `**negrito**` e `_itálico_`
- Queremos texto limpo e legível

### **Mensagens de erro amigáveis:**

```python
error_messages = {
    "generic": "Ocorreu um erro ao processar sua solicitação. Por favor, tente novamente.",
    "timeout": "A consulta demorou mais que o esperado. Tente ser mais específico.",
    "no_results": "Não encontrei informações com esses critérios. Tente reformular a consulta.",
    "database": "No momento estou com dificuldade para acessar os dados. Tente novamente em instantes."
}
```

### **Onde é usado?**
- **Message Handler:** Formata resposta antes de enviar para WhatsApp

---

## 7.3. `src/integrations/whatsapp/webhook_server.py`

### **O que faz?**
Servidor Flask que recebe webhooks da Evolution API e processa mensagens WhatsApp.

### **Como funciona?**

```python
webhook_server = WebhookServer(host='0.0.0.0', port=5000)

# Configura handler para processar mensagens
webhook_server.set_message_handler(message_handler.handle_webhook_payload)

# Inicia servidor
webhook_server.run()
```

### **Endpoints:**

**1. POST /webhook** - Recebe mensagens

```python
@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_json()
    
    event_type = payload.get('event')  # 'messages.upsert'
    
    if event_type == 'messages.upsert':
        # Processa mensagem
        self.message_handler(payload)
    
    return jsonify({'status': 'success'}), 200
```

**2. GET /health** - Health check

```python
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'whatsapp-webhook',
        'handler_configured': True
    }), 200
```

**3. GET /** - Info do serviço

```python
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'service': 'WhatsApp RAG Bot',
        'status': 'running',
        'endpoints': {
            'webhook': '/webhook (POST)',
            'health': '/health (GET)'
        }
    }), 200
```

### **Payload da Evolution API:**

```json
{
  "event": "messages.upsert",
  "instance": "cativa_rag",
  "data": {
    "key": {
      "remoteJid": "5547999887766@s.whatsapp.net",
      "fromMe": false,
      "id": "3EB0..."
    },
    "message": {
      "conversation": "Qual o total de vendas de outubro?"
    },
    "messageType": "conversation",
    "messageTimestamp": 1704384000
  }
}
```

### **Tratamento de erros:**

```python
try:
    self.message_handler(payload)
except Exception as e:
    logger.error(f"Error in message handler: {e}")
    logger.error(traceback.format_exc())

# Sempre retorna success para Evolution API
return jsonify({'status': 'success'}), 200
```

**Por que sempre retorna success?**
- Evolution API reenvia webhook se receber erro
- Erros no processamento não devem causar reenvio
- Log do erro é suficiente para debug

### **Produção: Waitress WSGI**

```python
# whatsapp_bot.py usa Waitress ao invés de Flask dev server
from waitress import serve

serve(
    webhook_server.app,
    host='0.0.0.0',
    port=5000,
    threads=4,              # 4 threads para processar requests
    channel_timeout=30,     # Timeout de 30s
    connection_limit=100    # Máximo 100 conexões simultâneas
)
```

**Por que Waitress?**
- 🚀 Production-ready (não usar Flask dev server em produção!)
- 🔒 Thread-safe
- ⚡ Melhor performance
- 🛡️ Mais estável

### **Onde é usado?**
- **whatsapp_bot.py:** Inicia webhook server em thread separada

---

# 🤖 **8. AI / OPENAI**

## 8.1. `src/ai/openai_client.py`

### **O que faz?**
Cliente centralizado para integração com OpenAI API (embeddings e chat completions).

### **Como funciona?**

```python
from ai.openai_client import OpenAIClient

client = OpenAIClient()

# 1. Gera embedding
embedding = client.generate_embedding("Pedido 843562 para cliente CONFECCOES EDILENI")
print(embedding.shape)  # (1536,)

# 2. Gera embeddings em lote (mais eficiente)
texts = ["texto 1", "texto 2", "texto 3"]
embeddings = client.generate_batch_embeddings(texts, batch_size=50)

# 3. Gera resposta com contexto RAG
rag_response = client.generate_chat_response(
    query="Qual o total de vendas?",
    context_chunks=[
        {'content': 'Total de vendas: R$ 1.234.567', 'similarity': 0.92}
    ],
    user_context={'department': 'Vendas'},
    conversation_history=[
        {'user': 'Oi', 'bot': 'Olá! Como posso ajudar?'}
    ]
)

print(rag_response['answer'])
print(rag_response['tokens_used'])  # {'prompt': 123, 'completion': 45, 'total': 168}
```

### **Modelos utilizados:**

```python
self.embedding_model = "text-embedding-3-small"
# - Dimensões: 1536 floats
# - Custo: $0.020 por 1M tokens
# - Qualidade: Alta para português

self.chat_model = "gpt-4o-mini"
# - Modelo eficiente (mais barato que GPT-4)
# - Boa qualidade de resposta
# - Custo: ~$0.15/1M input tokens, ~$0.60/1M output tokens
```

### **Rate Limiting:**

```python
def _rate_limit(self):
    """Implementa rate limiting simples"""
    current_time = time.time()
    time_since_last = current_time - self.last_request_time
    
    if time_since_last < self.min_request_interval:
        sleep_time = self.min_request_interval - time_since_last
        time.sleep(sleep_time)
    
    self.last_request_time = time.time()

# Mínimo 100ms entre requests
self.min_request_interval = 0.1
```

**Por que rate limiting?**
- Evita erro 429 (Too Many Requests) da OpenAI
- Distribui carga uniformemente
- Previne bloqueio da API Key

### **Cache de embeddings:**

```python
# Cache em memória
self.embedding_cache = {}

def generate_embedding(self, text: str, use_cache: bool = True):
    # Verifica cache antes de chamar API
    if use_cache and text in self.embedding_cache:
        return self.embedding_cache[text]
    
    # Chama API
    embedding = self._call_openai_api(text)
    
    # Armazena no cache
    if use_cache:
        self.embedding_cache[text] = embedding
    
    return embedding
```

**Benefícios:**
- 💰 Economiza tokens (chamadas repetidas são grátis)
- 🚀 Resposta instantânea para textos já processados
- 📊 Útil para textos que se repetem (ex: nomes de clientes)

### **System Prompt (ChatGPT):**

```python
system_prompt = """
Você é um assistente inteligente da Cativa Têxtil.

=== REGRAS FUNDAMENTAIS ===

1. SAUDAÇÕES:
   - Se apenas saudação (oi, olá), responda apenas com saudação amigável
   - NÃO mostre dados ou tabelas em saudações

2. CONSULTAS DE DADOS:
   - Use SOMENTE as informações do contexto fornecido
   - Seja preciso, factual e objetivo
   - Formate valores em formato brasileiro (R$ 1.234,56)

3. FORMATAÇÃO:
   - Organize de forma clara e legível no WhatsApp
   - Limite respostas a 5-7 itens principais

4. PRIVACIDADE E LGPD:
   - Respeite o nível de permissão do usuário
   - Não exponha dados sensíveis desnecessariamente

5. QUANDO NÃO SOUBER:
   - Seja honesto: "Não encontrei informações"
   - Não invente dados
"""
```

### **Histórico de conversa:**

```python
def _build_user_prompt(self, query, context_chunks, user_context, conversation_history):
    prompt_parts = []
    
    # Histórico recente (últimas 3 mensagens)
    if conversation_history:
        prompt_parts.append("=== HISTÓRICO DA CONVERSA ===")
        for msg in conversation_history[-3:]:
            prompt_parts.append(f"Usuário: {msg['user']}")
            prompt_parts.append(f"Assistente: {msg['bot']}")
        prompt_parts.append("---")
    
    # Contexto recuperado (chunks RAG)
    if context_chunks:
        prompt_parts.append("=== CONTEXTO RELEVANTE ===")
        for i, chunk in enumerate(context_chunks[:5], 1):
            prompt_parts.append(f"{i}. [Similaridade: {chunk['similarity']:.2f}] {chunk['content']}")
    
    # Pergunta atual
    prompt_parts.append(f"=== PERGUNTA ATUAL ===")
    prompt_parts.append(query)
    
    return "\n".join(prompt_parts)
```

**Por que incluir histórico?**
- Contexto da conversa ("e o mês passado?" → sabe que falou de outubro)
- Respostas mais naturais
- Evita repetir informações já fornecidas

### **Fallback (sem API Key):**

```python
def _generate_simulated_embedding(self, text: str) -> np.ndarray:
    """Gera embedding simulado usando hash determinístico"""
    import hashlib
    
    # Hash como seed
    text_hash = hashlib.md5(text.encode()).hexdigest()
    np.random.seed(int(text_hash[:8], 16))
    
    # Vetor aleatório normalizado
    embedding = np.random.normal(0, 1, 1536)
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding
```

**Por que fallback?**
- Permite testar sistema sem API Key
- Desenvolvimento local sem custos
- Degradação graceful se API falhar

### **Onde é usado?**
- **RAG Engine:** Gera embeddings de queries e formata respostas
- **Oracle Sync:** Gera embeddings em lote ao sincronizar dados
- **Response Formatter:** Formata respostas com LLM

---

# 🛠️ **9. SCRIPTS UTILITÁRIOS**

## 9.1. `scripts/cleanup_lgpd.py`

### **O que faz?**
Script de limpeza automática de dados conforme políticas LGPD.

### **Como funciona?**

```bash
# Execução manual
python scripts/cleanup_lgpd.py

# Execução agendada (cron - Linux/Mac)
# Todo dia 1º do mês às 04:00
0 4 1 * * cd /path/to/fontes && python scripts/cleanup_lgpd.py >> logs/cleanup.log 2>&1

# Windows (Task Scheduler)
# Configurar tarefa agendada para executar mensalmente
```

### **Operações realizadas:**

**1. Limpeza de chunks expirados:**

```python
def cleanup_expired_chunks(self) -> int:
    """
    Remove chunks expirados baseado em retention_until
    
    SQL:
    UPDATE chunks
    SET is_active = FALSE,
        deleted_at = NOW()
    WHERE retention_until < NOW()
    AND is_active = TRUE
    """
    # Soft delete (não deleta permanentemente)
    # Permite recovery window de 90 dias
```

**Política de retenção por entidade:**

| **Entidade** | **Retenção** | **Base Legal** |
|--------------|--------------|---------------|
| PEDIDO_VENDA | 5 anos | Código Civil (Art. 206) |
| CLIENTE | 5 anos | LGPD (Art. 16) |
| FINANCEIRO | 7 anos | Receita Federal |
| LOGS_ACESSO | 6 meses | LGPD (Art. 37) |

**2. Limpeza de logs de acesso:**

```python
def cleanup_old_access_logs(self, days_to_keep: int = 180):
    """
    Remove logs de acesso antigos
    
    Default: 180 dias (6 meses)
    Conforme LGPD Art. 37
    """
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    DELETE FROM access_log
    WHERE accessed_at < cutoff_date
```

**3. Hard delete de soft-deleted antigos:**

```python
def hard_delete_old_soft_deleted(self, days_to_keep: int = 90):
    """
    Remove permanentemente chunks soft-deleted há mais de 90 dias
    
    Recovery window: 90 dias
    """
    DELETE FROM chunks
    WHERE is_active = FALSE
    AND deleted_at < (NOW() - INTERVAL '90 days')
```

### **Saída do script:**

```
================================================================================
LGPD CLEANUP SERVICE - Limpeza Automática de Dados
================================================================================
Execution time: 2025-01-04 04:00:00

=== Cleaning up expired chunks ===
Found 1,234 expired chunks
Soft deleted 1,234 expired chunks

=== Cleaning up access logs older than 180 days ===
Deleted 45,678 old access logs

=== Hard deleting chunks soft-deleted > 90 days ago ===
Permanently deleted 892 soft-deleted chunks

================================================================================
CLEANUP SUMMARY
================================================================================
Chunks soft-deleted (expired): 1,234
Chunks hard-deleted (old soft-deletes): 892
Access logs deleted: 45,678
Total records cleaned: 47,804
Errors: 0
================================================================================
LGPD cleanup completed successfully
================================================================================
```

### **Auditoria automática:**

Cada exclusão é registrada em `lgpd_deletion_log`:

```sql
INSERT INTO lgpd_deletion_log (
    deletion_type,
    affected_table,
    records_deleted,
    deletion_reason,
    criteria_used,
    requested_by,
    approved_by,
    executed_at
) VALUES (
    'retention_cleanup',
    'chunks',
    1234,
    'Limpeza automática - expiração de retenção LGPD',
    '{"retention_until": "less than NOW()"}',
    'system',
    'lgpd_retention_policy',
    NOW()
);
```

### **Onde é usado?**
- **Produção:** Executado mensalmente via cron/Task Scheduler
- **Manual:** Admin pode executar quando necessário

---

## 9.2. `scripts/generate_encryption_key.py`

### **O que faz?**
Gera chave de criptografia AES-256 criptograficamente segura.

### **Como funciona?**

```bash
python scripts/generate_encryption_key.py
```

**Saída:**

```
======================================================================
 GERADOR DE CHAVE DE CRIPTOGRAFIA AES-256
 Sistema RAG Cativa Têxtil - Conformidade LGPD
======================================================================

Gerando chave criptograficamente segura...
✅ Chave gerada com sucesso!

DETALHES DA CHAVE:
----------------------------------------------------------------------
Tamanho:        32 bytes (256 bits)
Formato:        Base64 (para armazenamento)
Algoritmo:      AES-256-GCM
Padrão:         NIST FIPS 197

======================================================================
CHAVE GERADA (Base64):
======================================================================

XyZ123abc...def456GHI789jkl012MNO345pqr678STU901vwx==

======================================================================

📝 INSTRUÇÕES DE USO:
----------------------------------------------------------------------

1. ADICIONE AO ARQUIVO .env:
   ENCRYPTION_KEY=XyZ123abc...def456GHI789jkl012MNO345pqr678STU901vwx==

2. EM PRODUÇÃO:
   - Use gerenciador de secrets (AWS KMS, Azure Key Vault, etc)
   - OU variável de ambiente do sistema
   - NUNCA commite no Git

3. FAÇA BACKUP SEGURO:
   - Armazene em gerenciador de senhas
   - Guarde cópia offline em local seguro
   - Se perder a chave, dados criptografados são IRRECUPERÁVEIS

======================================================================
⚠️  AVISOS DE SEGURANÇA IMPORTANTES:
======================================================================

❌ NUNCA commite esta chave no Git
❌ NUNCA compartilhe por email/mensagem não criptografada
❌ NUNCA use a mesma chave em dev e produção
✅ SEMPRE faça backup em local seguro
✅ SEMPRE rotacione chaves periodicamente (ex: a cada 90 dias)
✅ SEMPRE use gerenciador de secrets em produção

======================================================================
🔬 TESTE RÁPIDO DA CHAVE:
======================================================================

✅ Teste passou!
   Original:        Teste de criptografia
   Criptografado:   89a7b2c3d4e5f6... (48 bytes)
   Descriptografado: Teste de criptografia

======================================================================
Chave gerada e testada com sucesso!
======================================================================
```

### **Função principal:**

```python
def generate_and_display_key():
    # 1. Gera chave segura de 32 bytes (256 bits)
    key = generate_key()  # usa os.urandom(32)
    
    # 2. Converte para Base64 (fácil de copiar/colar)
    key_b64 = key_to_base64(key)
    
    # 3. Testa a chave
    encryptor = AES256Encryptor(key=key)
    encrypted = encryptor.encrypt("Teste")
    decrypted = encryptor.decrypt(encrypted)
    assert "Teste" == decrypted
    
    # 4. Exibe instruções
    print(f"ENCRYPTION_KEY={key_b64}")
```

### **Rotação de chaves:**

**Por que rotacionar?**
- Segurança: Limita janela de exposição se chave for comprometida
- Compliance: Boas práticas de segurança
- LGPD: Medidas técnicas adequadas (Art. 46)

**Como rotacionar:**

```bash
# 1. Gera nova chave
python scripts/generate_encryption_key.py

# 2. Adiciona NOVA chave como ENCRYPTION_KEY_NEW no .env
ENCRYPTION_KEY=old_key_here
ENCRYPTION_KEY_NEW=new_key_here

# 3. Script de migração (futuro)
python scripts/rotate_encryption_key.py
# - Lê chunks com chave antiga
# - Re-criptografa com chave nova
# - Atualiza banco

# 4. Remove chave antiga do .env
ENCRYPTION_KEY=new_key_here
```

### **Onde é usado?**
- **Setup inicial:** Primeira configuração do sistema
- **Rotação:** Troca periódica de chaves (recomendado a cada 90 dias)

---

# 🎯 **CONCLUSÃO DA DOCUMENTAÇÃO**

## **Status Final:**

✅ **DOCUMENTAÇÃO COMPLETA**

**Arquivos documentados:**

1. **Arquivos principais (raiz)** - 2 arquivos
   - whatsapp_bot.py
   - manage_whatsapp_users.py

2. **Core (núcleo)** - 6 arquivos
   - config.py
   - connection_pool.py
   - database_adapter.py
   - logging_config.py
   - rate_limiter.py
   - retry_handler.py

3. **Security (LGPD)** - 3 arquivos
   - encryption.py
   - lgpd_audit.py
   - lgpd_query_classifier.py

4. **Data Processing** - 4 arquivos
   - chunking.py
   - embeddings.py
   - lgpd_classifier.py
   - oracle_sync.py

5. **SQL (Text-to-SQL)** - 4 arquivos
   - schema_introspector.py
   - sql_validator.py
   - text_to_sql_generator.py
   - text_to_sql_service.py

6. **RAG Engine** - 1 arquivo
   - rag_engine.py

7. **WhatsApp Integration** - 3 arquivos
   - authorization.py
   - response_formatter.py
   - webhook_server.py

8. **AI / OpenAI** - 1 arquivo
   - openai_client.py

9. **Scripts Utilitários** - 2 arquivos
   - cleanup_lgpd.py
   - generate_encryption_key.py

**Total:** 26 arquivos principais documentados

---

## **Resumo do Sistema**

### **Arquitetura:**

```
WhatsApp (Usuário)
    ↓
Evolution API
    ↓
Webhook Server (Flask + Waitress)
    ↓
Message Handler
    ├─ Authorization (LGPD clearance)
    ├─ Rate Limiter (anti-spam)
    └─ RAG Engine
        ├─ LGPD Classifier
        ├─ Text-to-SQL (Oracle) [PRIMARY]
        ├─ Embedding Search (PostgreSQL) [FALLBACK]
        ├─ OpenAI Client (GPT-4 + Embeddings)
        └─ Response Formatter
    ↓
Evolution API
    ↓
WhatsApp (Resposta)
```

### **Stack Tecnológica:**

- **Linguagem:** Python 3.11+
- **IA/LLM:** OpenAI GPT-4o-mini + text-embedding-3-small
- **Bancos:**
  - Oracle 11g (dados de produção)
  - PostgreSQL 15 + pgvector (RAG + busca vetorial)
- **WhatsApp:** Evolution API (open-source)
- **Web Server:** Flask + Waitress WSGI
- **Segurança:** AES-256-GCM, LGPD compliance
- **Infraestrutura:** Docker (PostgreSQL), Connection Pooling

### **Características Principais:**

✅ **Arquitetura Híbrida:** Text-to-SQL (Oracle) + Embedding Search (PostgreSQL)  
✅ **100% LGPD:** Criptografia AES-256-GCM + Auditoria completa  
✅ **Production-Ready:** Connection pooling, retry logic, rate limiting  
✅ **Segurança:** SQL validation, permissões por usuário, logs auditáveis  
✅ **Performance:** Busca vetorial HNSW, cache, processamento otimizado  
✅ **Escalabilidade:** Connection pooling, batch processing, índices otimizados

### **Conformidade LGPD:**

- ✅ **Art. 7º** - Consentimento e permissões por usuário
- ✅ **Art. 9º** - Criptografia de dados sensíveis (AES-256-GCM)
- ✅ **Art. 16º** - Política de retenção de dados
- ✅ **Art. 18º** - Direito de exclusão (soft delete + hard delete)
- ✅ **Art. 37º** - Registro de acessos (access_log)
- ✅ **Art. 46º** - Medidas técnicas de segurança
- ✅ **Art. 48º** - Notificação de incidentes (logs auditáveis)

### **Métricas do Projeto:**

- **Linhas de código:** ~15.000 linhas Python
- **Módulos:** 48 arquivos .py
- **Tabelas PostgreSQL:** 7 (chunks, access_log, lgpd_deletion_log, etc)
- **Views Oracle:** 3 (VW_RAG_VENDAS_ESTRUTURADA, VW_RAG_CP_TITULOS_TEXTUAL, etc)
- **Índices:** 15+ (HNSW vetorial, B-tree, GIN full-text)
- **Cobertura LGPD:** 100%
- **Testes:** 14 unitários + 3 manuais

### **Deployment:**

```bash
# 1. Clone repositório
git clone <repo>
cd fontes

# 2. Cria ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# 3. Instala dependências
pip install -r requirements.txt

# 4. Configura .env
cp .env.example .env
python scripts/generate_encryption_key.py
# Editar .env com credenciais

# 5. Inicia PostgreSQL (Docker)
cd docker
docker-compose up -d postgres

# 6. Cria schema PostgreSQL
psql -U cativa_user -d cativa_rag_db -f sql/01_init_database.sql

# 7. Sincroniza dados Oracle → PostgreSQL
python -m src.data_processing.oracle_sync --days 30 --max 5000

# 8. Inicia bot WhatsApp
python whatsapp_bot.py
```

---

## **Considerações Finais**

Esta documentação cobre todos os componentes principais do **Sistema RAG Cativa Têxtil**, fornecendo:

- 📖 Explicações simples e acessíveis de cada arquivo
- 🔍 Detalhes técnicos de implementação
- 🔗 Interações entre componentes
- 💡 Exemplos práticos de uso
- 🛡️ Aspectos de segurança e LGPD
- 🚀 Guias de deployment e manutenção

**Sistema desenvolvido para:**
- Cativa Têxtil Ltda.
- Trabalho de Conclusão de Curso (TCC) 2025
- Curso: [Seu Curso]
- Instituição: [Sua Instituição]

---

**Documentação elaborada por:** [Seu Nome]  
**Data:** Janeiro 2025  
**Versão:** 1.0 - Completa  

---

*Fim da Documentação Completa dos Arquivos Python*
