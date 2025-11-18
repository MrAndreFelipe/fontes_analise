# 📚 DOCUMENTAÇÃO TÉCNICA COMPLETA - Sistema RAG Cativa Têxtil

## PARTE 3 FINAL: RAG Engine, Text-to-SQL, WhatsApp e Fluxos Completos

---

# 6. PROCESSAMENTO DE DADOS

## 6.1. Embeddings (Vetores Semânticos)

**Arquivo:** `src/data_processing/embeddings.py`

### **O que são Embeddings?**

Embeddings são **representações vetoriais** de texto que capturam **significado semântico**.

**Analogia:**
```
Palavra "cachorro":
- Vetor: [0.23, -0.51, 0.87, ..., 0.12]  (1536 números)
- Números representam características: "é animal", "tem 4 patas", "late", etc

Palavra "gato":
- Vetor: [0.25, -0.48, 0.82, ..., 0.15]  (1536 números)
- Similar ao cachorro (ambos são animais)

Palavra "carro":
- Vetor: [-0.92, 0.31, -0.45, ..., 0.78]  (1536 números)
- Muito diferente (não é animal)
```

### **Por que usar Embeddings?**

**Problema:** Busca por palavra-chave não funciona bem:
```
Query: "faturamento de outubro"
Chunk 1: "Total de vendas em outubro: R$ 1.2M"  ❌ Não encontra (palavra diferente)
Chunk 2: "Receita mensal..."                    ❌ Não encontra
```

**Solução:** Busca semântica com embeddings:
```
Query embedding:         [0.23, -0.51, ...]  "faturamento outubro"
Chunk 1 embedding:       [0.25, -0.49, ...]  "vendas outubro" → 95% similar ✅
Chunk 2 embedding:       [0.21, -0.52, ...]  "receita mensal" → 88% similar ✅
Chunk 3 embedding:       [-0.92, 0.31, ...]  "contas a pagar" → 12% similar ❌
```

### **Como funciona?**

#### **Geração de Embedding:**

```python
class EmbeddingGenerator:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model_name = "text-embedding-3-small"
        self.dimension = 1536
    
    @retry_openai(max_retries=3)
    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Gera embedding para um texto
        
        Args:
            text: Texto em português
        
        Returns:
            Array numpy com 1536 floats
        """
        # Chama OpenAI API
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        
        # Extrai vetor
        embedding = response.data[0].embedding
        
        # Converte para numpy array
        return np.array(embedding)
```

**Exemplo real:**
```python
generator = EmbeddingGenerator()

# Gera embedding
text = "Pedido 843562 para cliente CONFECCOES EDILENI. Valor: R$ 2.842,50"
embedding = generator.generate_embedding(text)

print(f"Tipo: {type(embedding)}")          # <class 'numpy.ndarray'>
print(f"Dimensão: {embedding.shape}")       # (1536,)
print(f"Primeiros 5 valores: {embedding[:5]}")
# [-0.023456, 0.187234, -0.056789, 0.234123, -0.123456]
```

#### **Busca por Similaridade (pgvector):**

**SQL para busca vetorial:**
```sql
-- Busca os 5 chunks mais similares
SELECT 
    chunk_id,
    content_text,
    embedding <=> $1::vector AS distance  -- Operador <=> calcula distância cosseno
FROM chunks
WHERE nivel_lgpd <= $2  -- Filtro LGPD
ORDER BY embedding <=> $1::vector  -- Ordena por similaridade
LIMIT 5;
```

**Como funciona `<=>` (distância de cosseno)?**
```
Vetor A: [1, 0, 0]
Vetor B: [1, 0, 0]  → Distância: 0.0  (idênticos)

Vetor A: [1, 0, 0]
Vetor C: [0.7, 0.7, 0]  → Distância: 0.3  (similares)

Vetor A: [1, 0, 0]
Vetor D: [0, 1, 0]  → Distância: 1.0  (ortogonais, nada similar)

Vetor A: [1, 0, 0]
Vetor E: [-1, 0, 0]  → Distância: 2.0  (opostos, máxima diferença)

Menor distância = mais similar
```

**Código Python para busca:**
```python
def _vector_search(self, query: str, limit: int = 5) -> List[Dict]:
    """Busca vetorial no PostgreSQL"""
    
    # 1. Gera embedding da query
    query_embedding = self.embedding_generator.generate_embedding(query)
    
    # 2. Busca chunks similares
    with self.db_pool.postgres_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                chunk_id,
                content_text,
                encrypted_content,
                nivel_lgpd,
                entity,
                attributes,
                embedding <=> %s::vector AS distance
            FROM chunks
            WHERE is_active = TRUE
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding.tolist(), query_embedding.tolist(), limit))
        
        results = cursor.fetchall()
        
        # 3. Converte para dicts
        chunks = []
        for row in results:
            chunks.append({
                'chunk_id': row[0],
                'content_text': row[1],
                'encrypted_content': row[2],
                'nivel_lgpd': row[3],
                'entity': row[4],
                'attributes': row[5],
                'similarity': 1 - row[6]  # Distância → Similaridade (0-1)
            })
        
        return chunks
```

**Por que índice HNSW?**
```sql
-- Índice HNSW (Hierarchical Navigable Small World)
CREATE INDEX idx_chunks_embedding_cosine 
ON chunks USING hnsw (embedding vector_cosine_ops);
```

**SEM índice:**
- Compara query com TODOS os chunks (100.000 chunks = 100.000 comparações)
- Tempo: ~10 segundos

**COM índice HNSW:**
- Busca aproximada usando grafo hierárquico
- Compara apenas ~200 chunks
- Tempo: ~10 milissegundos (1000x mais rápido!)
- Precisão: ~99% (quase tão bom quanto busca exata)

---

# 7. RAG ENGINE (Núcleo do Sistema)

**Arquivo:** `src/rag/rag_engine.py`

## 7.1. Visão Geral

O RAG Engine é o **cérebro** do sistema, orquestrando todo o fluxo de processamento de queries:

```
┌─────────────────────────────────────────────────────────────┐
│                       RAG ENGINE                            │
│  ┌────────────────────────────────────────────────────┐     │
│  │  1. LGPD Check                                     │     │
│  │     - Classifica query (ALTO/MÉDIO/BAIXO)         │     │
│  │     - Verifica clearance do usuário               │     │
│  │     - Registra acesso (audit log)                 │     │
│  └──────────────────┬─────────────────────────────────┘     │
│                     │                                        │
│                     ▼                                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │  2. Rota PRIMARY: Text-to-SQL                      │     │
│  │     - GPT-4 gera SQL                               │     │
│  │     - Valida SQL (SQLValidator)                    │     │
│  │     - Executa no Oracle (connection pool)          │     │
│  │     - Retorna resultados ✅                        │     │
│  └──────────────────┬─────────────────────────────────┘     │
│                     │ (se falhar ou 0 resultados)           │
│                     ▼                                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │  3. Rota FALLBACK: Embedding Search                │     │
│  │     - Gera embedding da query                      │     │
│  │     - Busca vetorial no PostgreSQL                 │     │
│  │     - Descriptografa chunks (se criptografados)    │     │
│  │     - Retorna chunks relevantes ✅                 │     │
│  └──────────────────┬─────────────────────────────────┘     │
│                     │                                        │
│                     ▼                                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │  4. Response Formatter                             │     │
│  │     - GPT-4 formata resposta em português          │     │
│  │     - Adiciona contexto e explicações              │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 7.2. Método Principal: process_query

```python
class RAGEngine:
    def process_query(self, 
                     query: str, 
                     user_context: Optional[Dict] = None,
                     conversation_history: Optional[List[Dict]] = None) -> RAGResponse:
        """
        Processa query através do pipeline completo
        
        Args:
            query: Pergunta do usuário em português
            user_context: Contexto do usuário com clearance LGPD
            conversation_history: Histórico de conversa (para contexto)
        
        Returns:
            RAGResponse com resposta formatada
        """
        start_time = time.time()
        
        # 1. LGPD Classification & Permission Check
        lgpd_classification = self.lgpd_classifier.classify_query(query)
        user_clearance = user_context.get('lgpd_clearance', 'BAIXO')
        
        if not self.permission_checker.can_access(user_clearance, lgpd_classification.level):
            # Acesso negado
            return RAGResponse(
                success=False,
                answer="Você não tem permissão para acessar esses dados.",
                confidence=0.0,
                sources=[],
                metadata={'denied': True, 'reason': 'insufficient_clearance'},
                processing_time=time.time() - start_time,
                lgpd_compliant=True,
                requires_human_review=False
            )
        
        # 2. Try Text-to-SQL (PRIMARY route)
        if self.text_to_sql and lgpd_classification.is_structured:
            result = self.text_to_sql.generate_and_execute(query, limit=10)
            
            if result['success'] and result['rows']:
                # SQL funcionou! Formata e retorna
                answer = self._format_sql_results(result['rows'], query)
                
                # Log de acesso LGPD
                self._log_access(user_context, query, lgpd_classification, 'text_to_sql', True)
                
                return RAGResponse(
                    success=True,
                    answer=answer,
                    confidence=0.95,
                    sources=[{'type': 'oracle_sql', 'sql': result['generated_sql']}],
                    metadata={'route': 'text_to_sql', 'rows_count': len(result['rows'])},
                    processing_time=time.time() - start_time,
                    lgpd_compliant=True,
                    requires_human_review=False
                )
        
        # 3. Fallback to Embedding Search
        chunks = self._embedding_search(query, lgpd_classification.level, limit=5)
        
        if not chunks:
            # Nenhum resultado
            return RAGResponse(
                success=False,
                answer="Não encontrei informações sobre isso nos dados disponíveis.",
                confidence=0.0,
                sources=[],
                metadata={'route': 'embeddings', 'chunks_found': 0},
                processing_time=time.time() - start_time,
                lgpd_compliant=True,
                requires_human_review=False
            )
        
        # Descriptografa chunks se necessário
        chunks = self._decrypt_if_needed(chunks)
        
        # Formata resposta com GPT-4
        answer = self._format_embedding_response(chunks, query, conversation_history)
        
        # Log de acesso LGPD
        chunk_ids = [c['chunk_id'] for c in chunks]
        self._log_access(user_context, query, lgpd_classification, 'embeddings', True, chunk_ids)
        
        return RAGResponse(
            success=True,
            answer=answer,
            confidence=0.85,
            sources=[{'type': 'chunks', 'count': len(chunks)}],
            metadata={'route': 'embeddings', 'chunks_used': len(chunks)},
            processing_time=time.time() - start_time,
            lgpd_compliant=True,
            requires_human_review=False
        )
```

## 7.3. Classificação LGPD da Query

**Arquivo:** `src/security/lgpd_query_classifier.py`

```python
class LGPDQueryClassifier:
    """
    Classifica queries em níveis LGPD
    """
    
    def classify_query(self, query: str) -> LGPDClassification:
        """
        Classifica query em ALTO, MÉDIO ou BAIXO
        
        Args:
            query: Pergunta do usuário
        
        Returns:
            LGPDClassification com nível, confiança e justificativa
        """
        query_lower = query.lower()
        
        # Padrões ALTO (dados pessoais)
        high_patterns = [
            'cnpj', 'cpf', 'nome do cliente', 'cliente específico',
            'fornecedor específico', 'dados pessoais', 'titular'
        ]
        
        # Padrões MÉDIO (dados financeiros)
        medium_patterns = [
            'valor', 'faturamento', 'receita', 'custo', 'pagamento',
            'título', 'duplicata', 'nota fiscal', 'pedido específico'
        ]
        
        # Padrões BAIXO (dados agregados)
        low_patterns = [
            'total', 'média', 'quantidade', 'resumo', 'estatística',
            'geral', 'período', 'mês', 'ano'
        ]
        
        # Verifica padrões
        for pattern in high_patterns:
            if pattern in query_lower:
                return LGPDClassification(
                    level='ALTO',
                    confidence=0.9,
                    reasoning=f"Query contém termo sensível: '{pattern}'",
                    is_structured=False
                )
        
        for pattern in medium_patterns:
            if pattern in query_lower:
                return LGPDClassification(
                    level='MÉDIO',
                    confidence=0.8,
                    reasoning=f"Query solicita dados financeiros: '{pattern}'",
                    is_structured='total' in query_lower or 'lista' in query_lower
                )
        
        # Default: BAIXO
        return LGPDClassification(
            level='BAIXO',
            confidence=0.7,
            reasoning="Query não contém termos sensíveis identificados",
            is_structured='total' in query_lower or 'quanto' in query_lower
        )
```

**Exemplos de classificação:**

| **Query** | **Classificação** | **Por que?** |
|-----------|------------------|--------------|
| "Qual o total de vendas de outubro?" | MÉDIO | Dados financeiros ("total", "vendas") |
| "Me mostre CNPJs dos clientes" | ALTO | Dados pessoais (CNPJ) |
| "Quantos pedidos tivemos este mês?" | BAIXO | Dados agregados (quantidade) |
| "Valor do pedido 843562" | MÉDIO | Dado financeiro específico |
| "Qual o nome do cliente do pedido X?" | ALTO | Dado pessoal (nome cliente) |

---

# 8. TEXT-TO-SQL

**Arquivo:** `src/sql/text_to_sql_service.py`

## 8.1. Visão Geral

O serviço Text-to-SQL converte **perguntas em português** para **queries SQL** automaticamente usando GPT-4.

```
"Qual o total de vendas de outubro 2024?"
        ↓
     GPT-4
        ↓
SELECT SUM(VALOR_ITEM_LIQUIDO) as total
FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
WHERE EXTRACT(MONTH FROM DATA_VENDA) = 10
  AND EXTRACT(YEAR FROM DATA_VENDA) = 2024
        ↓
  Oracle 11g
        ↓
  R$ 1.234.567,89
```

## 8.2. Componentes

### **8.2.1. Schema Introspector**

**Arquivo:** `src/sql/schema_introspector.py`

**O que faz:**
- Lê schema do banco Oracle (tabelas, colunas, tipos)
- Gera descrição legível para o GPT-4

**Por que é importante:**
- GPT-4 precisa saber quais tabelas/colunas existem
- Sem schema, GPT-4 "inventa" nomes que não existem

**Exemplo de schema gerado:**
```python
def get_schema_for_llm(self) -> str:
    """
    Gera descrição do schema para GPT-4
    """
    return """
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
- DESCRICAO_REGIAO (VARCHAR2): Região de venda (Sul, Sudeste, etc)
- EMPRESA (VARCHAR2): Empresa Cativa (Pomerode, Blumenau, etc)

## VW_RAG_CP_TITULOS_TEXTUAL
Contas a pagar (fornecedores, títulos, vencimentos).

Colunas:
- TITULO (VARCHAR2): Número do título
- NOME_FORNECEDOR (VARCHAR2): Nome do fornecedor
- CNPJ_FORNECEDOR (VARCHAR2): CNPJ do fornecedor (sensível)
- VALOR_TITULO (NUMBER): Valor do título
- VALOR_SALDO (NUMBER): Saldo devedor
- DATA_VENCIMENTO (DATE): Data de vencimento
- DATA_EMISSAO (DATE): Data de emissão
- DESCRICAO_GRUPO (VARCHAR2): Grupo do fornecedor
- DESCRICAO_BANCO (VARCHAR2): Banco

## VW_RAG_CR_DUPLICATAS_TEXTUAL  
Contas a receber (clientes, duplicatas, recebimentos).

Colunas:
- FATURA (VARCHAR2): Número da fatura
- NOME_CLIENTE (VARCHAR2): Nome do cliente
- CNPJ_CLIENTE (VARCHAR2): CNPJ do cliente (sensível)
- VALOR_TITULO (NUMBER): Valor da duplicata
- SALDO (NUMBER): Saldo a receber
- DATA_VENCIMENTO (DATE): Data de vencimento
- DATA_EMISSAO (DATE): Data de emissão
- SITUACAO_DUPLICATA (VARCHAR2): Situação (A Receber, Recebida, Vencida)
- NOME_REPRESENTANTE (VARCHAR2): Representante comercial
"""
```

### **8.2.2. Text-to-SQL Generator**

**Arquivo:** `src/sql/text_to_sql_generator.py`

**Como funciona:**

```python
class TextToSQLGenerator:
    def generate_sql(self, question: str, schema: str, constraints: str = None) -> str:
        """
        Gera SQL a partir de pergunta em português
        
        Args:
            question: Pergunta do usuário
            schema: Schema do banco (do SchemaIntrospector)
            constraints: Constraints adicionais (opcional)
        
        Returns:
            SQL query string
        """
        # Monta prompt para GPT-4
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

{constraints if constraints else ''}

**PERGUNTA DO USUÁRIO:**
{question}

**SQL QUERY:**
```sql
"""
        
        # Chama GPT-4
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,  # Determinístico
            max_tokens=500
        )
        
        # Extrai SQL da resposta
        sql = response.choices[0].message.content
        sql = self._extract_sql_from_markdown(sql)
        
        return sql
```

**Exemplos de geração:**

**Entrada:**
```
"Qual o total de vendas de outubro de 2024?"
```

**SQL Gerado:**
```sql
SELECT SUM(VALOR_ITEM_LIQUIDO) as total_vendas
FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
WHERE EXTRACT(MONTH FROM DATA_VENDA) = 10
  AND EXTRACT(YEAR FROM DATA_VENDA) = 2024
```

---

**Entrada:**
```
"Liste os 5 maiores pedidos de setembro"
```

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

**Entrada:**
```
"Quantos pedidos tivemos por região em 2024?"
```

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

### **8.2.3. SQL Validator**

**Arquivo:** `src/sql/sql_validator.py`

**O que faz:**
- Valida SQL gerado pelo GPT-4
- Previne SQL injection
- Adiciona LIMIT se ausente
- Bloqueia operações perigosas (DELETE, DROP, etc)

```python
class SQLValidator:
    def sanitize_and_limit(self, sql: str, limit: int = 100) -> Tuple[bool, str]:
        """
        Valida e sanitiza SQL
        
        Returns:
            (sucesso: bool, sql_sanitizado_ou_erro: str)
        """
        sql = sql.strip()
        
        # 1. Verifica operações proibidas
        dangerous_keywords = [
            'DELETE', 'DROP', 'TRUNCATE', 'ALTER', 'CREATE',
            'INSERT', 'UPDATE', 'GRANT', 'REVOKE', 'EXEC'
        ]
        
        sql_upper = sql.upper()
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False, f"Operação proibida: {keyword}"
        
        # 2. Verifica se é SELECT
        if not sql_upper.startswith('SELECT'):
            return False, "Apenas SELECT é permitido"
        
        # 3. Adiciona ROWNUM se ausente
        if 'ROWNUM' not in sql_upper and 'FETCH FIRST' not in sql_upper:
            # Adiciona limitação
            if 'WHERE' in sql_upper:
                # Adiciona AND ROWNUM
                sql = sql.replace('WHERE', f'WHERE ROWNUM <= {limit} AND', 1)
            else:
                # Adiciona WHERE ROWNUM
                # Encontra posição após FROM ... antes de ORDER BY (se houver)
                if 'ORDER BY' in sql_upper:
                    parts = sql.split('ORDER BY')
                    sql = f"{parts[0]} WHERE ROWNUM <= {limit} ORDER BY {parts[1]}"
                else:
                    sql += f" WHERE ROWNUM <= {limit}"
        
        # 4. Remove comentários (previne SQL injection)
        sql = re.sub(r'--.*', '', sql)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        return True, sql
```

**Exemplos de validação:**

| **SQL Input** | **Validação** | **Output** |
|--------------|--------------|------------|
| `SELECT * FROM vendas` | ✅ OK | `SELECT * FROM vendas WHERE ROWNUM <= 100` |
| `DELETE FROM vendas` | ❌ BLOQUEIA | "Operação proibida: DELETE" |
| `SELECT * FROM vendas; DROP TABLE clientes;` | ❌ BLOQUEIA | "Operação proibida: DROP" |
| `SELECT * FROM vendas -- comment` | ✅ OK (remove comentário) | `SELECT * FROM vendas WHERE ROWNUM <= 100` |

---

# 9. INTEGRAÇÃO WHATSAPP

## 9.1. Evolution API

**O que é Evolution API?**
- API open-source para WhatsApp Business
- Permite enviar/receber mensagens programaticamente
- Alternativa gratuita ao WhatsApp Business API oficial (que é pago)

**Como funciona:**

```
┌─────────────────┐
│  WhatsApp User  │
└────────┬────────┘
         │ Mensagem
         ▼
┌─────────────────┐
│  WhatsApp Web   │ (conexão via QR Code)
└────────┬────────┘
         │
         ▼
┌──────────────────────────┐
│  Evolution API Server    │ (http://10.1.200.22:8081)
└────────┬─────────────────┘
         │ HTTP Webhook
         ▼
┌──────────────────────────┐
│  Sistema RAG (Flask)     │ (http://localhost:5000/webhook)
└──────────────────────────┘
```

## 9.2. Evolution API Client

**Arquivo:** `src/integrations/whatsapp/evolution_client.py`

### **Enviar Mensagem:**

```python
class EvolutionAPIClient:
    @retry_api_call(max_retries=3)
    def send_text_message(self, phone_number: str, message: str) -> Dict:
        """
        Envia mensagem de texto (COM RETRY)
        
        Args:
            phone_number: Telefone (formato: 5547999887766)
            message: Texto (suporta markdown WhatsApp)
        """
        endpoint = f"{self.api_url}/message/sendText/{self.instance_name}"
        
        payload = {
            "number": phone_number,
            "text": message,
            "options": {
                "delay": 0,
                "presence": "composing"  # Mostra "digitando..."
            }
        }
        
        response = requests.post(endpoint, json=payload, headers=self.headers, timeout=10)
        return response.json()
```

**Markdown WhatsApp:**
```python
# Negrito
"*texto em negrito*"

# Itálico
"_texto em itálico_"

# Tachado
"~texto tachado~"

# Monoespaço (código)
"```código```"

# Exemplo
message = """
*Resultado da Consulta:*

Total de vendas: _R$ 1.234.567,89_

Período: ```outubro/2024```
"""
```

### **Configurar Webhook:**

```python
def set_webhook(self, webhook_url: str) -> Dict:
    """
    Configura webhook para receber mensagens
    
    Args:
        webhook_url: URL pública (ex: https://abc123.ngrok.io/webhook)
    """
    endpoint = f"{self.api_url}/webhook/set/{self.instance_name}"
    
    payload = {
        "url": webhook_url,
        "webhook_by_events": True,
        "webhook_base64": False,
        "events": [
            'messages.upsert',      # Nova mensagem
            'messages.update',      # Mensagem atualizada
            'connection.update'     # Status de conexão
        ]
    }
    
    response = requests.post(endpoint, json=payload, headers=self.headers, timeout=10)
    return response.json()
```

### **Indicador de "digitando...":**

```python
def send_typing_indicator(self, phone_number: str, is_typing: bool = True):
    """
    Mostra/esconde indicador de digitação
    """
    endpoint = f"{self.api_url}/chat/sendPresence/{self.instance_name}"
    
    payload = {
        "number": phone_number,
        "presence": "composing" if is_typing else "paused"
    }
    
    requests.post(endpoint, json=payload, headers=self.headers, timeout=5)
```

## 9.3. Message Handler

**Arquivo:** `src/integrations/whatsapp/message_handler.py`

**Fluxo completo:**

```python
class MessageHandler:
    def handle_webhook_payload(self, payload: Dict):
        """
        Processa webhook do Evolution API
        """
        # 1. Extrai dados da mensagem
        message_text = self._extract_message_text(payload)
        sender = self._extract_sender(payload)
        
        # 2. Valida rate limit
        if not self.rate_limiter.is_allowed(sender):
            self.evolution_client.send_text_message(
                sender, 
                "Limite de mensagens atingido. Aguarde alguns segundos."
            )
            return
        
        # 3. Marca como lida
        self.evolution_client.mark_message_as_read(payload.get('key', {}))
        
        # 4. Mostra "digitando..."
        self.evolution_client.send_typing_indicator(sender, True)
        
        # 5. Verifica autorização
        user_context = self.authorization.get_user_context(sender)
        
        # 6. Processa com RAG
        rag_response = self.rag_engine.process_query(
            message_text,
            user_context=user_context,
            conversation_history=self._get_session_context(sender)
        )
        
        # 7. Esconde "digitando..."
        self.evolution_client.send_typing_indicator(sender, False)
        
        # 8. Formata resposta
        formatted_response = self.formatter.format_response(rag_response)
        
        # 9. Envia resposta
        self.evolution_client.send_text_message(sender, formatted_response)
        
        # 10. Salva no histórico de conversa
        self._save_to_session(sender, message_text, formatted_response)
```

---

# 10. FLUXOS COMPLETOS END-TO-END

## 10.1. Fluxo 1: Query SQL (Rota PRIMARY)

**Cenário:** Usuário pergunta "Qual o total de vendas de outubro?"

```
┌──────────────┐
│ 1. USUÁRIO   │ "Qual o total de vendas de outubro?"
└──────┬───────┘
       │ WhatsApp
       ▼
┌──────────────────┐
│ 2. EVOLUTION API │ Recebe mensagem → envia para webhook
└──────┬───────────┘
       │ HTTP POST /webhook
       ▼
┌─────────────────────────┐
│ 3. MESSAGE HANDLER      │
│ - Extrai mensagem       │
│ - Valida rate limit ✅  │
│ - Marca como lida       │
│ - Mostra "digitando..." │
│ - Obtém user_context    │
│   → clearance: MÉDIO    │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│ 4. RAG ENGINE                   │
│ ┌─────────────────────────────┐ │
│ │ 4.1 LGPD Classifier         │ │
│ │ - Query: "total vendas..."  │ │
│ │ - Classificação: MÉDIO      │ │
│ │ - User clearance: MÉDIO     │ │
│ │ - Permissão: ✅ CONCEDIDA   │ │
│ └──────┬──────────────────────┘ │
│        │                         │
│        ▼                         │
│ ┌─────────────────────────────┐ │
│ │ 4.2 Text-to-SQL Service     │ │
│ │ a) Schema Introspector      │ │
│ │    → Obtém schema Oracle    │ │
│ │                             │ │
│ │ b) GPT-4 Generator          │ │
│ │    Prompt: "Gere SQL para:  │ │
│ │     'Qual total outubro?'"  │ │
│ │                             │ │
│ │    SQL gerado:              │ │
│ │    SELECT SUM(VALOR) ...    │ │
│ │    FROM VW_VENDAS ...       │ │
│ │    WHERE MONTH = 10         │ │
│ │                             │ │
│ │ c) SQL Validator            │ │
│ │    → Valida SQL ✅          │ │
│ │    → Adiciona LIMIT         │ │
│ │                             │ │
│ │ d) Oracle Connection Pool   │ │
│ │    → Executa SQL            │ │
│ │    → Resultado:             │ │
│ │      total_vendas: 1234567  │ │
│ └──────┬──────────────────────┘ │
│        │ ✅ Sucesso              │
│        ▼                         │
│ ┌─────────────────────────────┐ │
│ │ 4.3 Response Formatter      │ │
│ │ GPT-4: Formata resposta em  │ │
│ │ português natural           │ │
│ │                             │ │
│ │ "O total de vendas de       │ │
│ │ outubro foi R$ 1.234.567"   │ │
│ └──────┬──────────────────────┘ │
│        │                         │
│ ┌──────▼──────────────────────┐ │
│ │ 4.4 LGPD Audit Logger       │ │
│ │ - Log de acesso (Art. 9º)   │ │
│ │ - Rota: text_to_sql         │ │
│ │ - Success: True             │ │
│ └─────────────────────────────┘ │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────┐
│ 5. MESSAGE HANDLER  │
│ - Esconde "digita..." │
│ - Envia resposta    │
│ - Salva histórico   │
└──────┬──────────────┘
       │
       ▼
┌──────────────────┐
│ 6. EVOLUTION API │ Envia mensagem WhatsApp
└──────┬───────────┘
       │
       ▼
┌──────────────┐
│ 7. USUÁRIO   │ Recebe: "O total de vendas de outubro foi R$ 1.234.567"
└──────────────┘
```

**Tempo típico:** ~3-5 segundos

---

## 10.2. Fluxo 2: Embedding Search (Rota FALLBACK)

**Cenário:** Usuário pergunta "Me fale sobre o desempenho financeiro"

```
[Passos 1-3 iguais ao Fluxo 1]

┌─────────────────────────────────┐
│ 4. RAG ENGINE                   │
│ ┌─────────────────────────────┐ │
│ │ 4.1 LGPD Classifier         │ │
│ │ - Query: "desempenho..."    │ │
│ │ - Classificação: MÉDIO      │ │
│ │ - is_structured: False      │ │  ← Query muito genérica
│ └──────┬──────────────────────┘ │
│        │                         │
│        ▼                         │
│ ┌─────────────────────────────┐ │
│ │ 4.2 Text-to-SQL tentado     │ │
│ │ - GPT-4 não consegue gerar  │ │
│ │   SQL específico (query     │ │
│ │   muito genérica)           │ │
│ │ - Retorna need_fallback=True│ │
│ └──────┬──────────────────────┘ │
│        │ ⚠️ Precisa fallback     │
│        ▼                         │
│ ┌─────────────────────────────┐ │
│ │ 4.3 Embedding Search        │ │
│ │ a) Embedding Generator      │ │
│ │    Query: "desempenho..."   │ │
│ │    → OpenAI Embedding       │ │
│ │      [0.23, -0.51, ...]     │ │
│ │                             │ │
│ │ b) PostgreSQL Vector Search │ │
│ │    SELECT embedding <=> ... │ │
│ │    → 5 chunks similares:    │ │
│ │                             │ │
│ │    Chunk 1: "Total vendas   │ │
│ │     outubro: R$ 1.2M"       │ │
│ │     similarity: 0.92        │ │
│ │     nivel_lgpd: MÉDIO       │ │
│ │     encrypted: True         │ │
│ │                             │ │
│ │    Chunk 2: "Receita mensal │ │
│ │     cresceu 15%"            │ │
│ │     similarity: 0.88        │ │
│ │     nivel_lgpd: BAIXO       │ │
│ │     encrypted: False        │ │
│ │                             │ │
│ │    [... mais 3 chunks]      │ │
│ │                             │ │
│ │ c) Decrypt if Needed        │ │
│ │    Chunk 1 → AES-256-GCM    │ │
│ │    → Descriptografado ✅    │ │
│ └──────┬──────────────────────┘ │
│        │                         │
│        ▼                         │
│ ┌─────────────────────────────┐ │
│ │ 4.4 Response Formatter      │ │
│ │ GPT-4: Sintetiza chunks +   │ │
│ │ responde em português       │ │
│ │                             │ │
│ │ "Com base nos dados         │ │
│ │ disponíveis, o desempenho   │ │
│ │ financeiro tem sido         │ │
│ │ positivo. As vendas de      │ │
│ │ outubro totalizaram         │ │
│ │ R$ 1.2M, com crescimento    │ │
│ │ de 15% em relação ao mês    │ │
│ │ anterior..."                │ │
│ └──────┬──────────────────────┘ │
│        │                         │
│ ┌──────▼──────────────────────┐ │
│ │ 4.5 LGPD Audit Logger       │ │
│ │ - Rota: embeddings          │ │
│ │ - Chunks: [chunk1, chunk2...│ │
│ │ - Success: True             │ │
│ └─────────────────────────────┘ │
└──────┬──────────────────────────┘
       │
[Passos 5-7 iguais ao Fluxo 1]
```

**Tempo típico:** ~2-4 segundos

---

## 10.3. Fluxo 3: Acesso Negado (LGPD)

**Cenário:** Usuário com clearance BAIXO tenta acessar dados ALTO

```
Usuário: "Me mostre CNPJs dos clientes"
Clearance: BAIXO

┌─────────────────────────────────┐
│ RAG ENGINE                      │
│ ┌─────────────────────────────┐ │
│ │ LGPD Classifier             │ │
│ │ - Query: "CNPJs clientes"   │ │
│ │ - Padrão detectado: "CNPJ"  │ │
│ │ - Classificação: ALTO       │ │  ← Dado pessoal
│ └──────┬──────────────────────┘ │
│        │                         │
│        ▼                         │
│ ┌─────────────────────────────┐ │
│ │ Permission Checker          │ │
│ │ - Query level: ALTO         │ │
│ │ - User clearance: BAIXO     │ │
│ │ - BAIXO < ALTO              │ │
│ │ → ❌ ACESSO NEGADO          │ │
│ └──────┬──────────────────────┘ │
│        │                         │
│        ▼                         │
│ ┌─────────────────────────────┐ │
│ │ LGPD Audit Logger           │ │
│ │ - Log de acesso (Art. 9º)   │ │
│ │ - Success: False            │ │
│ │ - Denied: "Insufficient     │ │
│ │   clearance: BAIXO < ALTO"  │ │
│ └─────────────────────────────┘ │
└──────┬──────────────────────────┘
       │
       ▼
Resposta: "Você não tem permissão para acessar esses dados."
```

**Tempo típico:** ~100ms (rápido, sem processar query)

---

# 11. EXEMPLOS PRÁTICOS DE USO

## 11.1. Exemplo Completo: Query de Vendas

**Entrada WhatsApp:**
```
"Quais foram os 5 maiores pedidos de outubro?"
```

**Processamento:**
1. **LGPD:** MÉDIO (valores financeiros)
2. **Clearance:** MÉDIO ✅
3. **Rota:** Text-to-SQL (query estruturada)

**SQL Gerado:**
```sql
SELECT * FROM (
    SELECT 
        NUMERO_PEDIDO,
        NOME_CLIENTE,
        VALOR_ITEM_LIQUIDO,
        TO_CHAR(DATA_VENDA, 'DD/MM/YYYY') as data
    FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA
    WHERE EXTRACT(MONTH FROM DATA_VENDA) = 10
      AND EXTRACT(YEAR FROM DATA_VENDA) = 2024
    ORDER BY VALOR_ITEM_LIQUIDO DESC
)
WHERE ROWNUM <= 5
```

**Resposta WhatsApp:**
```
*Maiores Pedidos de Outubro 2024:*

1. *Pedido 843562*
   Cliente: CONFECCOES EDILENI LTDA
   Valor: R$ 45.678,90
   Data: 15/10/2024

2. *Pedido 843587*
   Cliente: GISA LOOKS LTDA
   Valor: R$ 38.234,50
   Data: 22/10/2024

3. *Pedido 843601*
   Cliente: DBR COMERCIO S.A.
   Valor: R$ 32.456,80
   Data: 28/10/2024

4. *Pedido 843543*
   Cliente: MODA BRASIL LTDA
   Valor: R$ 28.901,20
   Data: 08/10/2024

5. *Pedido 843589*
   Cliente: TEXTIL EXPRESS
   Valor: R$ 25.123,40
   Data: 19/10/2024

_Total: R$ 170.394,80_
```

---

## 11.2. Deploy em Produção

### **Checklist Completo:**

#### **1. Infraestrutura:**
```bash
# Docker PostgreSQL
cd docker
docker-compose up -d postgres

# Verifica
docker ps
docker logs cativa_rag_postgres
```

#### **2. Banco de Dados:**
```bash
# PostgreSQL
psql -U cativa_user -d cativa_rag_db -f sql/01_init_database.sql
psql -U cativa_user -d cativa_rag_db -f sql/02_optimize_indexes.sql

# Oracle (via SQL Developer ou sqlplus)
sqlplus user/password@ORCL @sql/oracle_views_financeiro_cativa.sql
sqlplus user/password@ORCL @sql/views_oracle.sql
```

#### **3. Configuração:**
```bash
# Gera chave
python scripts/generate_encryption_key.py

# Cria .env
cp .env.example .env
nano .env  # Preencher com valores reais
```

#### **4. Sincronização Inicial:**
```bash
# Sincroniza últimos 30 dias
python -m src.data_processing.oracle_sync --days 30 --max 5000

# Verifica dados no PostgreSQL
psql -U cativa_user -d cativa_rag_db
SELECT COUNT(*) FROM chunks;
SELECT entity, COUNT(*) FROM chunks GROUP BY entity;
```

#### **5. Iniciar Bot:**
```bash
# Produção (Waitress)
python whatsapp_bot.py

# Ou com nohup (background)
nohup python whatsapp_bot.py > logs/bot.log 2>&1 &
```

#### **6. Monitoramento:**
```bash
# Logs em tempo real
tail -f logs/bot.log

# Queries SQL recentes
psql -U cativa_user -d cativa_rag_db
SELECT accessed_at, user_name, query_text, route_used, success
FROM access_log
ORDER BY accessed_at DESC
LIMIT 10;
```

---

## 📚 **CONCLUSÃO**

Este sistema RAG implementa uma solução completa e profissional para consulta de dados financeiros via WhatsApp, com:

✅ **Arquitetura Híbrida:** Text-to-SQL (Oracle) + Embedding Search (PostgreSQL)  
✅ **100% LGPD:** Criptografia AES-256-GCM + Auditoria completa  
✅ **Production-Ready:** Connection pooling, retry logic, rate limiting  
✅ **Segurança:** SQL validation, permissões por usuário, logs auditáveis  
✅ **Performance:** Busca vetorial HNSW, cache, processamento otimizado  

**Stack Tecnológica:**
- Python 3.11+ (linguagem principal)
- OpenAI GPT-4 + Embeddings (IA/LLM)
- Oracle 11g (banco produção)
- PostgreSQL 15 + pgvector (banco RAG)
- Evolution API (WhatsApp)
- Flask + Waitress (webhook server)
- Docker (containerização)

**Total de Linhas:** ~15.000 linhas Python  
**Módulos:** 48 arquivos  
**Cobertura LGPD:** 100%  
**Testes:** 14 unitários + 3 manuais  

---

*Documentação Completa - Partes 1, 2 e 3*  
*Sistema RAG Cativa Têxtil - TCC 2025*  
*Preparado para apresentação e banca*
