# 📚 DOCUMENTAÇÃO TÉCNICA COMPLETA - Sistema RAG Cativa Têxtil

## PARTE 2: Módulos Core, Segurança LGPD e Processamento de Dados

---

# 4. MÓDULOS CORE

Os módulos core são a **fundação** do sistema, fornecendo funcionalidades essenciais que todos os outros componentes utilizam.

---

## 4.1. Config (Configuração Centralizada)

**Arquivo:** `src/core/config.py`

### **O que faz?**
- Carrega variáveis de ambiente do `.env`
- Centraliza todas as configurações do sistema
- Usa padrão Singleton (uma instância compartilhada)
- Valida configurações obrigatórias

### **Como funciona?**

```python
# 1. Carrega .env automaticamente ao importar
from dotenv import load_dotenv
load_dotenv()  # Carrega .env → os.environ

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
        """Carrega do os.environ"""
        return cls(
            host=os.getenv('ORACLE_HOST', 'localhost'),
            port=int(os.getenv('ORACLE_PORT', '1521')),
            # ... demais campos
        )

# 3. Classe Config (singleton)
class Config:
    _oracle_config = None  # Cache (singleton)
    
    @classmethod
    def oracle(cls) -> OracleConfig:
        """Retorna config Oracle (cached)"""
        if cls._oracle_config is None:
            cls._oracle_config = OracleConfig.from_env()
        return cls._oracle_config
```

### **Por que Singleton?**
- **Carrega variáveis UMA VEZ** na inicialização
- **Reutiliza mesma instância** em todo o código
- **Evita ler `.env` múltiplas vezes** (performance)
- **Garante consistência** das configs

### **Uso no código:**

```python
from core.config import Config

# Acessar Oracle
oracle = Config.oracle()
print(f"Host: {oracle.host}:{oracle.port}")
print(f"User: {oracle.user}")

# Acessar PostgreSQL
postgres = Config.postgres()
conn_string = f"postgresql://{postgres.user}:{postgres.password}@{postgres.host}:{postgres.port}/{postgres.database}"

# Acessar OpenAI
openai = Config.openai()
client = OpenAI(api_key=openai.api_key)

# Acessar Evolution API (WhatsApp)
evolution = Config.evolution()
webhook_url = f"{evolution.webhook_public_url}/webhook"
```

### **Configurações Fixas (Constantes):**

```python
class Config:
    # Chunking
    MAX_CHUNK_TOKENS = 800       # Máximo tokens por chunk
    OVERLAP_TOKENS = 100         # Sobreposição entre chunks
    MIN_CHUNK_TOKENS = 120       # Mínimo (menores são consolidados)
    
    # Embeddings
    EMBEDDING_DIMENSION = 1536   # text-embedding-3-small
    
    # LGPD
    LGPD_LEVELS = ["BAIXO", "MÉDIO", "ALTO"]
    
    # Processamento
    BATCH_SIZE = 1000            # Registros por lote
```

**Por que essas constantes?**
- **MAX_CHUNK_TOKENS = 800:** Limite do contexto GPT-4 (4096 tokens) dividido em ~5 chunks
- **OVERLAP_TOKENS = 100:** Evita perda de contexto entre chunks (overlap semântico)
- **EMBEDDING_DIMENSION = 1536:** Dimensão fixa do modelo OpenAI `text-embedding-3-small`

---

## 4.2. Connection Pool (Gerenciamento de Conexões)

**Arquivo:** `src/core/connection_pool.py`

### **O que faz?**
Gerencia **pools de conexões** para PostgreSQL e Oracle, permitindo:
- Reutilização de conexões (performance)
- Limite de conexões simultâneas (evita esgotar recursos)
- Gerenciamento automático do ciclo de vida
- Thread-safe (múltiplas threads podem usar simultaneamente)

### **Por que Connection Pool?**

**SEM Pool (❌ Ruim):**
```python
# Cada consulta abre/fecha conexão
for i in range(1000):
    conn = psycopg2.connect(...)  # ❌ Lento (TCP handshake)
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    conn.close()                  # ❌ Desperdiça recurso
```
- **Problema:** Abrir/fechar conexão é LENTO (~50-100ms por conexão)
- **Problema:** Esgota recursos do banco (limite de conexões)

**COM Pool (✅ Bom):**
```python
# Pool mantém 2-10 conexões abertas
pool = DatabaseConnectionPool(min=2, max=10)

for i in range(1000):
    conn = pool.get_connection()  # ✅ Rápido (conexão já aberta)
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    pool.return_connection(conn)  # ✅ Reutiliza
```
- **Benefício:** Conexões já estão abertas (< 1ms)
- **Benefício:** Reutiliza até 10 conexões simultâneas
- **Benefício:** Limite controlado (não esgota banco)

### **Como funciona?**

#### **Inicialização:**

```python
class DatabaseConnectionPool:
    def __init__(self, 
                 postgres_config: Dict,
                 oracle_config: Dict,
                 min_connections: int = 2,
                 max_connections: int = 10):
        
        # PostgreSQL Pool (psycopg2.pool.ThreadedConnectionPool)
        if postgres_config:
            self.postgres_pool = pool.ThreadedConnectionPool(
                minconn=min_connections,   # Mantém 2 conexões sempre abertas
                maxconn=max_connections,   # Máximo de 10 conexões simultâneas
                host=postgres_config['host'],
                port=postgres_config['port'],
                database=postgres_config['database'],
                user=postgres_config['user'],
                password=postgres_config['password']
            )
        
        # Oracle Pool (cx_Oracle.SessionPool)
        if oracle_config:
            dsn = cx_Oracle.makedsn(
                oracle_config['host'],
                oracle_config['port'],
                service_name=oracle_config['service_name']
            )
            
            self.oracle_pool = cx_Oracle.SessionPool(
                user=oracle_config['user'],
                password=oracle_config['password'],
                dsn=dsn,
                min=min_connections,       # Mínimo 2 sessões
                max=max_connections,       # Máximo 10 sessões
                increment=1,               # Incrementa de 1 em 1
                threaded=True,             # Thread-safe
                getmode=cx_Oracle.SPOOL_ATTRVAL_NOWAIT  # Retorna erro se pool cheio
            )
```

**Por que `ThreadedConnectionPool`?**
- Permite múltiplas threads usarem o pool simultaneamente
- Cada thread obtém sua própria conexão do pool
- Thread-safe via locks internos

**Por que `SPOOL_ATTRVAL_NOWAIT`?**
- Se pool estiver cheio (10 conexões em uso), **retorna erro** imediatamente
- Alternativa seria esperar (bloquear thread)
- Erro é melhor: permite retry com backoff

#### **Uso do Pool:**

**Método 1: Manual (get/return)**
```python
pool = DatabaseConnectionPool(...)

# Obter conexão
conn = pool.get_postgres_connection()

try:
    # Usar conexão
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chunks LIMIT 10")
    results = cursor.fetchall()
finally:
    # SEMPRE retornar ao pool
    pool.return_postgres_connection(conn)
```

**Método 2: Context Manager (recomendado)**
```python
pool = DatabaseConnectionPool(...)

# Context manager garante retorno automático
with pool.postgres_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chunks LIMIT 10")
    results = cursor.fetchall()
# Conexão retorna automaticamente ao pool aqui
```

**Por que Context Manager é melhor?**
- Garante retorno **mesmo se exception ocorrer**
- Código mais limpo (sem try/finally)
- Padrão Python (Pythonic)

#### **Retry Automático:**

```python
@retry_database(max_retries=3)
def get_postgres_connection(self):
    """Obtém conexão COM RETRY automático"""
    conn = self.postgres_pool.getconn()
    return conn
```

**O que o decorator `@retry_database` faz?**
- Se falhar (timeout, connection error), **tenta novamente** até 3 vezes
- Usa **exponential backoff**: 0.5s → 1s → 2s
- Log de cada tentativa
- Só falha após esgotar retries

---

## 4.3. Retry Handler (Lógica de Retry)

**Arquivo:** `src/core/retry_handler.py`

### **O que faz?**
Implementa **lógica de retry** com exponential backoff para operações que podem falhar temporariamente:
- Conexões de banco (timeouts, deadlocks)
- Chamadas API OpenAI (rate limits, erros 5xx)
- Requisições HTTP (network errors)

### **Por que Retry?**

**Problema:** Erros temporários são comuns:
- Oracle timeout (banco ocupado)
- OpenAI rate limit (quota excedida)
- Network glitch (packet loss)

**Solução:** Retry com backoff exponencial:
```
Tentativa 1: Falha → Aguarda 0.5s
Tentativa 2: Falha → Aguarda 1.0s (2x)
Tentativa 3: Falha → Aguarda 2.0s (2x)
Tentativa 4: Sucesso ✅
```

### **Como funciona?**

#### **Decorator Básico:**

```python
def retry_with_backoff(max_retries=3,
                      initial_delay=0.5,
                      backoff_factor=2.0,
                      exceptions=(Exception,)):
    """
    Decorator para retry com exponential backoff
    
    Args:
        max_retries: Máximo de tentativas (além da primeira)
        initial_delay: Delay inicial em segundos
        backoff_factor: Fator de multiplicação do delay
        exceptions: Tupla de exceções a tratar
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"{func.__name__} succeeded after {attempt + 1} attempts")
                    
                    return result
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor  # Exponential backoff
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
            
            raise last_exception
        
        return wrapper
    return decorator
```

#### **Uso:**

```python
# Retry para banco de dados
@retry_database(max_retries=3)
def get_oracle_connection():
    return cx_Oracle.connect(...)

# Retry para OpenAI
@retry_openai(max_retries=3)
def generate_embedding(text):
    return openai.embeddings.create(...)

# Retry para HTTP
@retry_api_call(max_retries=3)
def send_whatsapp_message(phone, message):
    return requests.post(...)
```

#### **Strategies Pré-definidas:**

**`retry_database` (PostgreSQL + Oracle):**
```python
def retry_database(max_retries=3):
    """
    Retry para operações de banco
    
    Trata:
    - Timeouts
    - Connection errors
    - Deadlocks
    """
    import psycopg2
    import cx_Oracle
    
    db_exceptions = (
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
        cx_Oracle.DatabaseError,
        ConnectionError,
        TimeoutError
    )
    
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=0.5,         # Começa com 0.5s
        backoff_factor=2.0,        # Dobra a cada tentativa
        exceptions=db_exceptions
    )
```

**`retry_openai` (OpenAI API):**
```python
def retry_openai(max_retries=3):
    """
    Retry para OpenAI API
    
    Trata:
    - Rate limits (429)
    - API errors (5xx)
    - Timeouts
    """
    from openai import (
        APIError,
        APIConnectionError,
        RateLimitError,
        APITimeoutError
    )
    
    openai_exceptions = (
        APIError,
        APIConnectionError,
        RateLimitError,
        APITimeoutError,
        TimeoutError,
        ConnectionError
    )
    
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=2.0,         # OpenAI precisa delay maior
        backoff_factor=3.0,        # Backoff mais agressivo (2s → 6s → 18s)
        exceptions=openai_exceptions
    )
```

**Por que delays diferentes?**
- **Banco:** Timeout geralmente é rápido (< 1s) → delay menor
- **OpenAI:** Rate limit pode durar vários segundos → delay maior

---

## 4.4. Rate Limiter (Controle de Taxa)

**Arquivo:** `src/core/rate_limiter.py`

### **O que faz?**
Previne **abuso** do sistema limitando número de requisições por usuário:
- Máximo X mensagens por minuto
- Máximo Y mensagens por hora
- Bloqueia temporariamente se exceder

### **Por que Rate Limiter?**

**Problema sem rate limit:**
- Usuário envia 1000 mensagens em 1 minuto
- Sistema fica sobrecarregado
- Banco de dados esgota conexões
- OpenAI API quota esgotada
- Custo alto (cada query = $$$)

**Solução com rate limit:**
- Máximo 10 mensagens/minuto
- Máximo 100 mensagens/hora
- Bloqueia usuário por 1 hora se exceder

### **Como funciona?**

```python
class RateLimiter:
    """
    Rate limiter baseado em sliding window
    """
    
    def __init__(self,
                 max_requests_per_minute: int = 10,
                 max_requests_per_hour: int = 100):
        self.max_per_minute = max_requests_per_minute
        self.max_per_hour = max_requests_per_hour
        
        # Armazena timestamps das requisições por usuário
        # {user_id: [timestamp1, timestamp2, ...]}
        self.user_requests = {}
    
    def is_allowed(self, user_id: str) -> bool:
        """
        Verifica se usuário pode fazer requisição
        
        Returns:
            True se permitido, False se bloqueado
        """
        now = time.time()
        
        # Inicializa lista se primeira requisição
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # Remove timestamps antigos (> 1 hora)
        user_timestamps = self.user_requests[user_id]
        user_timestamps = [ts for ts in user_timestamps if now - ts < 3600]
        self.user_requests[user_id] = user_timestamps
        
        # Conta requisições no último minuto
        last_minute = [ts for ts in user_timestamps if now - ts < 60]
        
        # Verifica limites
        if len(last_minute) >= self.max_per_minute:
            logger.warning(f"User {user_id} exceeded per-minute limit ({self.max_per_minute})")
            return False
        
        if len(user_timestamps) >= self.max_per_hour:
            logger.warning(f"User {user_id} exceeded per-hour limit ({self.max_per_hour})")
            return False
        
        # Adiciona timestamp atual
        user_timestamps.append(now)
        return True
```

**Por que Sliding Window?**
- Mais justo que fixed window
- Evita burst no início da janela

**Exemplo:**
```
Fixed Window (ruim):
00:00 - 01:00: 100 requests ✅
01:00 - 02:00: 100 requests ✅
Total em 1 minuto (00:59 - 01:00): 200 requests ❌ Burst!

Sliding Window (bom):
Qualquer janela de 1 hora: máximo 100 requests
```

### **Uso no Message Handler:**

```python
class MessageHandler:
    def __init__(self):
        self.rate_limiter = RateLimiter(
            max_requests_per_minute=10,
            max_requests_per_hour=100
        )
    
    def handle_webhook_payload(self, payload):
        user_id = payload['from']
        
        # Verifica rate limit
        if not self.rate_limiter.is_allowed(user_id):
            return {
                'error': 'Rate limit exceeded',
                'message': 'Você excedeu o limite de requisições. Tente novamente mais tarde.'
            }
        
        # Processa mensagem normalmente
        return self.process_message(payload)
```

---

# 5. SEGURANÇA E LGPD

## 5.1. Criptografia AES-256-GCM

**Arquivo:** `src/security/encryption.py`

### **O que faz?**
Implementa **criptografia AES-256-GCM** para proteger dados sensíveis (CNPJ, CPF, nomes) em conformidade com **LGPD Art. 46**.

### **Por que AES-256-GCM?**

| **Aspecto** | **AES-256-GCM** | **Por que é importante?** |
|------------|-----------------|--------------------------|
| **AES-256** | Algoritmo de criptografia com chave de 256 bits | Padrão NIST (governo EUA), inquebrável com tecnologia atual |
| **GCM Mode** | Galois/Counter Mode | Autenticação integrada (detecta adulteração) |
| **Tag de Autenticação** | 16 bytes | Garante integridade (se alterado, falha na descriptografia) |
| **IV único** | 12 bytes gerados aleatoriamente | Mesmo texto criptografado 2x gera resultados diferentes |

### **Como funciona?**

#### **Estrutura do Dado Criptografado:**

```
┌──────────┬─────────────────┬──────────────┐
│ IV (12B) │ Ciphertext (nB) │ Tag (16B)    │
└──────────┴─────────────────┴──────────────┘

IV (Initialization Vector):
- 12 bytes aleatórios
- Único para cada operação
- Necessário para descriptografar

Ciphertext:
- Tamanho variável (depende do texto)
- Texto original criptografado

Tag:
- 16 bytes de autenticação
- Gerado automaticamente pelo GCM
- Valida integridade dos dados
```

#### **Geração da Chave:**

```python
# scripts/generate_encryption_key.py

import secrets
import base64

# Gera 32 bytes aleatórios (256 bits)
key = secrets.token_bytes(32)

# Codifica em base64 para facilitar armazenamento
key_b64 = base64.b64encode(key).decode('ascii')

print(f"ENCRYPTION_KEY={key_b64}")
# Output: ENCRYPTION_KEY=j3Oa2LhtM3BkYzFm4R2V... (44 caracteres)
```

**Por que 32 bytes = 256 bits?**
- AES-256 requer chave de exatamente 256 bits
- 1 byte = 8 bits → 32 bytes × 8 = 256 bits

**Por que base64?**
- Base64 permite armazenar bytes como string ASCII
- Fácil de copiar/colar no `.env`
- 32 bytes → 44 caracteres base64

#### **Criptografar:**

```python
class AES256Encryptor:
    def encrypt(self, plaintext: str) -> bytes:
        """
        Criptografa texto
        
        Args:
            plaintext: Texto em português (UTF-8)
        
        Returns:
            bytes: IV + Ciphertext + Tag
        """
        # 1. Gera IV único (12 bytes aleatórios)
        iv = os.urandom(12)
        
        # 2. Converte texto para bytes UTF-8
        plaintext_bytes = plaintext.encode('utf-8')
        
        # 3. Criptografa com AES-256-GCM
        # Retorna: ciphertext + tag (tag é automaticamente incluída)
        ciphertext_and_tag = self.cipher.encrypt(iv, plaintext_bytes, None)
        
        # 4. Retorna: IV + (Ciphertext + Tag)
        return iv + ciphertext_and_tag
```

**Exemplo:**
```python
encryptor = AES256Encryptor()

plaintext = "CNPJ: 03.221.721/0001-10"  # 28 caracteres UTF-8
encrypted = encryptor.encrypt(plaintext)

# Tamanhos:
# IV:         12 bytes
# Ciphertext: 28 bytes (mesmo tamanho do texto)
# Tag:        16 bytes
# Total:      56 bytes
```

#### **Descriptografar:**

```python
def decrypt(self, encrypted_data: bytes) -> str:
    """
    Descriptografa dados
    
    Args:
        encrypted_data: IV + Ciphertext + Tag
    
    Returns:
        str: Texto original
    
    Raises:
        ValueError: Se dados inválidos ou adulterados
    """
    # 1. Separa IV (primeiros 12 bytes)
    iv = encrypted_data[:12]
    
    # 2. Pega ciphertext + tag (restante)
    ciphertext_and_tag = encrypted_data[12:]
    
    # 3. Descriptografa E valida tag
    # Se tag inválida → InvalidTag exception (dados adulterados!)
    plaintext_bytes = self.cipher.decrypt(iv, ciphertext_and_tag, None)
    
    # 4. Converte bytes → string UTF-8
    plaintext = plaintext_bytes.decode('utf-8')
    
    return plaintext
```

**Por que a tag é importante?**
- **Integridade:** Se 1 bit for alterado, tag fica inválida
- **Autenticação:** Garante que dados vieram da fonte correta
- **Segurança:** Previne ataques de modificação

**Exemplo de adulteração:**
```python
encryptor = AES256Encryptor()

# Criptografa
original = "Dados sensíveis"
encrypted = encryptor.encrypt(original)

# Adultera 1 byte
encrypted_tampered = encrypted[:-1] + b'\x00'

# Tenta descriptografar
try:
    decrypted = encryptor.decrypt(encrypted_tampered)
except ValueError:
    print("❌ Dados foram adulterados!")  # ✅ Detectado!
```

### **Uso no Sistema:**

#### **Criptografar ao sincronizar (oracle_sync.py):**

```python
class OracleToPostgreSQLSync:
    def _encrypt_if_needed(self, content: str, nivel_lgpd: str) -> Optional[bytes]:
        """
        Criptografa chunks sensíveis
        
        Política:
        - ALTO: Criptografa (CPF, CNPJ, dados pessoais)
        - MÉDIO: Criptografa (dados financeiros sensíveis)
        - BAIXO: NÃO criptografa (dados agregados/públicos)
        """
        if not self.encryptor:
            return None
        
        # Só criptografa ALTO ou MÉDIO
        if nivel_lgpd not in ['ALTO', 'MÉDIO', 'MEDIO']:
            return None
        
        try:
            encrypted_bytes = self.encryptor.encrypt(content)
            logger.debug(f"Chunk criptografado: LGPD={nivel_lgpd}, size={len(encrypted_bytes)} bytes")
            return encrypted_bytes
        except Exception as e:
            logger.error(f"Erro ao criptografar: {e}")
            return None
    
    def sync_textual_data(self):
        for row in oracle_data:
            # Classifica LGPD
            nivel_lgpd = row['nivel_lgpd']  # ALTO, MÉDIO ou BAIXO
            
            # Criptografa se necessário
            encrypted_content = self._encrypt_if_needed(row['texto_completo'], nivel_lgpd)
            
            # Insere no PostgreSQL
            chunk_data = {
                'content_text': row['texto_completo'],        # Texto original (sempre)
                'encrypted_content': encrypted_content,       # Versão criptografada (só se ALTO/MÉDIO)
                'nivel_lgpd': nivel_lgpd
            }
            self.postgres_adapter.insert_chunk(chunk_data)
```

#### **Descriptografar ao buscar (rag_engine.py):**

```python
class RAGEngine:
    def _decrypt_if_needed(self, chunks: List[Dict]) -> List[Dict]:
        """
        Descriptografa chunks que possuem encrypted_content
        """
        for chunk in chunks:
            # Se tem versão criptografada, descriptografa
            if chunk.get('encrypted_content'):
                try:
                    decrypted = self.encryptor.decrypt(chunk['encrypted_content'])
                    chunk['content_text'] = decrypted
                    logger.debug(f"Chunk {chunk['chunk_id']} descriptografado")
                except Exception as e:
                    logger.error(f"Erro ao descriptografar chunk {chunk['chunk_id']}: {e}")
                    # Mantém texto original se falhar
        
        return chunks
    
    def _embedding_search(self, query: str, limit: int = 5):
        # Busca chunks similares
        chunks = self._vector_search(query, limit)
        
        # Descriptografa se necessário
        chunks = self._decrypt_if_needed(chunks)
        
        return chunks
```

### **Boas Práticas:**

✅ **O que fazer:**
- Gerar chave com `secrets.token_bytes(32)` (criptograficamente seguro)
- Armazenar chave no `.env` (NÃO versionar!)
- Em produção: usar AWS Secrets Manager ou Azure Key Vault
- Criptografar dados **ANTES** de inserir no banco
- Descriptografar apenas quando **realmente necessário**

❌ **O que NÃO fazer:**
- Usar chave hard-coded no código
- Reutilizar IV (initialization vector)
- Armazenar chave no banco de dados
- Compartilhar chave por email/chat
- Commitar `.env` no Git

---

## 5.2. Auditoria LGPD (Logs de Acesso e Exclusão)

**Arquivo:** `src/security/lgpd_audit.py`

### **O que faz?**
Registra **logs de auditoria** para conformidade LGPD:
- **Art. 37º:** Log de todos os acessos a dados pessoais
- **Art. 18º:** Log de todas as exclusões de dados

### **Por que auditar?**
- **LGPD obriga** registro de acessos a dados pessoais
- Permite **rastreabilidade** (quem acessou o quê e quando)
- Suporta **investigações** em caso de incidente
- Evidência para **órgãos reguladores** (ANPD)

### **Como funciona?**

#### **Log de Acesso (Art. 37º):**

```python
class LGPDAuditLogger:
    def log_access(self,
                   user_id: str,                  # Telefone WhatsApp
                   user_name: Optional[str],      # Nome do usuário
                   user_clearance: str,           # ALTO, MÉDIO, BAIXO
                   query_text: str,               # Pergunta do usuário
                   query_classification: str,     # Classificação LGPD da query
                   route_used: str,               # text_to_sql, embeddings, cache
                   chunks_accessed: List[str],    # IDs dos chunks acessados
                   success: bool,                 # Se acesso foi bem-sucedido
                   denied_reason: Optional[str],  # Motivo se negado
                   processing_time_ms: int):      # Tempo de processamento
        """
        Registra acesso na tabela access_log
        """
        cursor = self.conn.cursor()
        
        query = """
            INSERT INTO access_log 
            (user_id, user_name, user_clearance, query_text, query_classification,
             route_used, chunks_accessed, success, denied_reason, processing_time_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            user_id,
            user_name,
            user_clearance,
            query_text[:1000],  # Limita tamanho
            query_classification,
            route_used,
            chunks_accessed,    # Array PostgreSQL
            success,
            denied_reason,
            processing_time_ms
        ))
        
        self.conn.commit()
```

**Exemplo de uso:**
```python
audit_logger = LGPDAuditLogger(postgres_conn)

# Registra acesso bem-sucedido
audit_logger.log_access(
    user_id="+5547999887766",
    user_name="João Silva",
    user_clearance="MÉDIO",
    query_text="Qual o total de vendas de outubro?",
    query_classification="MÉDIO",
    route_used="text_to_sql",
    chunks_accessed=[],  # SQL direto, sem chunks
    success=True,
    denied_reason=None,
    processing_time_ms=1234
)

# Registra acesso negado
audit_logger.log_access(
    user_id="+5547999887766",
    user_name="João Silva",
    user_clearance="BAIXO",
    query_text="Me mostre CNPJs dos clientes",
    query_classification="ALTO",
    route_used="error",
    chunks_accessed=[],
    success=False,
    denied_reason="Clearance insuficiente: BAIXO < ALTO",
    processing_time_ms=12
)
```

**Consulta de logs:**
```sql
-- Acessos do último mês
SELECT 
    accessed_at,
    user_name,
    user_clearance,
    query_classification,
    route_used,
    success
FROM access_log
WHERE accessed_at >= NOW() - INTERVAL '30 days'
ORDER BY accessed_at DESC;

-- Acessos negados
SELECT 
    accessed_at,
    user_name,
    query_text,
    denied_reason
FROM access_log
WHERE success = FALSE
ORDER BY accessed_at DESC;
```

#### **Log de Exclusão (Art. 18º):**

```python
def log_deletion(self,
                deletion_type: str,              # retention_cleanup, erasure_request, manual
                affected_table: str,             # chunks, access_log, etc
                records_deleted: int,            # Quantidade deletada
                deletion_reason: str,            # Motivo
                criteria_used: Dict,             # Critérios (JSON)
                requested_by: str,               # Quem solicitou
                approved_by: Optional[str],      # Quem aprovou
                evidence_backup_location: str):  # Local do backup
    """
    Registra exclusão na tabela lgpd_deletion_log
    """
    cursor = self.conn.cursor()
    
    query = """
        INSERT INTO lgpd_deletion_log
        (deletion_type, affected_table, records_deleted, deletion_reason,
         criteria_used, requested_by, approved_by, evidence_backup_location)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    
    cursor.execute(query, (
        deletion_type,
        affected_table,
        records_deleted,
        deletion_reason,
        json.dumps(criteria_used),  # JSON
        requested_by,
        approved_by,
        evidence_backup_location
    ))
    
    log_id = cursor.fetchone()[0]
    self.conn.commit()
    
    return log_id
```

**Exemplo de uso:**
```python
# Limpeza automática por retenção
audit_logger.log_deletion(
    deletion_type="retention_cleanup",
    affected_table="chunks",
    records_deleted=1523,
    deletion_reason="Dados com mais de 5 anos (política de retenção)",
    criteria_used={
        "created_at_before": "2020-01-01",
        "nivel_lgpd": "ALTO",
        "retention_days": 1825  # 5 anos
    },
    requested_by="system",
    approved_by="auto",
    evidence_backup_location="/backups/2025-11-04_retention_cleanup.sql"
)

# Solicitação de exclusão de titular
audit_logger.log_deletion(
    deletion_type="erasure_request",
    affected_table="chunks",
    records_deleted=42,
    deletion_reason="Solicitação de exclusão do titular CNPJ 03.221.721/0001-10",
    criteria_used={
        "cnpj": "03221721000110",
        "data_category": "vendas"
    },
    requested_by="juridico@cativa.com.br",
    approved_by="dpo@cativa.com.br",
    evidence_backup_location="/backups/erasure/cnpj_03221721000110.sql"
)
```

**Consulta de exclusões:**
```sql
-- Exclusões dos últimos 90 dias
SELECT 
    executed_at,
    deletion_type,
    affected_table,
    records_deleted,
    deletion_reason
FROM lgpd_deletion_log
WHERE executed_at >= NOW() - INTERVAL '90 days'
ORDER BY executed_at DESC;

-- Total deletado por tipo
SELECT 
    deletion_type,
    COUNT(*) as total_operations,
    SUM(records_deleted) as total_records
FROM lgpd_deletion_log
GROUP BY deletion_type;
```

---

**CONTINUA NA PARTE 3...**

*Este é o Documento Parte 2 de 3*  
*Próximo: RAG Engine, Text-to-SQL, WhatsApp Integration, Fluxos End-to-End*
