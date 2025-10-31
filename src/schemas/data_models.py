# src/schemas/data_models.py
"""
Pydantic models para validacao de dados e documentacao
Fornece type safety e geracao automatica de JSON Schema
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


# ============================================
# ENUMS
# ============================================

class LGPDLevel(str, Enum):
    """Niveis de clearance LGPD"""
    BAIXO = "BAIXO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"


class QueryRoute(str, Enum):
    """Rotas de processamento de queries"""
    TEXT_TO_SQL = "text_to_sql"
    EMBEDDINGS = "embeddings"
    CACHED = "cached"


class MessageType(str, Enum):
    """Tipos de mensagem WhatsApp"""
    CONVERSATION = "conversation"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"


# ============================================
# USER CONTEXT
# ============================================

class UserContext(BaseModel):
    """
    Contexto do usuario para controle de acesso LGPD
    
    Exemplo:
        {
            "lgpd_clearance": "ALTO",
            "user_id": "5511999999999@s.whatsapp.net",
            "user_name": "Andre Gunther",
            "department": "TI",
            "is_admin": true,
            "enabled": true
        }
    """
    lgpd_clearance: LGPDLevel = Field(
        description="Nivel de acesso LGPD do usuario"
    )
    user_id: str = Field(
        description="ID unico do usuario (WhatsApp JID)",
        min_length=1
    )
    user_name: str = Field(
        description="Nome do usuario",
        default="Usuario Desconhecido"
    )
    department: str = Field(
        description="Departamento do usuario",
        default="N/A"
    )
    is_admin: bool = Field(
        description="Se usuario tem privilegios administrativos",
        default=False
    )
    enabled: bool = Field(
        description="Se usuario esta ativo no sistema",
        default=True
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "lgpd_clearance": "ALTO",
                "user_id": "5511999999999@s.whatsapp.net",
                "user_name": "Andre Gunther",
                "department": "TI",
                "is_admin": True,
                "enabled": True
            }
        }


# ============================================
# RAG RESPONSE
# ============================================

class RAGSource(BaseModel):
    """Fonte de dados usada na resposta RAG"""
    source: str = Field(description="Tipo da fonte (oracle_text_to_sql, embeddings, etc)")
    sql: Optional[str] = Field(None, description="SQL gerado (se aplicavel)")
    chunk_id: Optional[str] = Field(None, description="ID do chunk (se embeddings)")
    similarity: Optional[float] = Field(None, description="Similaridade (se embeddings)", ge=0.0, le=1.0)


class RAGMetadata(BaseModel):
    """Metadados da resposta RAG"""
    route: QueryRoute = Field(description="Rota usada para processar query")
    lgpd_level: LGPDLevel = Field(description="Nivel LGPD da query")
    rows_returned: Optional[int] = Field(None, description="Numero de linhas retornadas (SQL)", ge=0)
    chunks_used: Optional[int] = Field(None, description="Numero de chunks usados (embeddings)", ge=0)
    error: Optional[str] = Field(None, description="Mensagem de erro (se houver)")


class RAGResponse(BaseModel):
    """
    Resposta do RAG Engine
    
    Exemplo:
        {
            "success": true,
            "answer": "Total de vendas hoje: R$ 145.327,50",
            "confidence": 0.85,
            "sources": [{"source": "oracle_text_to_sql", "sql": "SELECT ..."}],
            "metadata": {"route": "text_to_sql", "lgpd_level": "BAIXO"},
            "processing_time": 0.523,
            "lgpd_compliant": true,
            "requires_human_review": false
        }
    """
    success: bool = Field(description="Se query foi processada com sucesso")
    answer: str = Field(description="Resposta formatada para o usuario", min_length=1)
    confidence: float = Field(description="Confianca na resposta", ge=0.0, le=1.0)
    sources: List[RAGSource] = Field(description="Fontes usadas para gerar resposta", default_factory=list)
    metadata: RAGMetadata = Field(description="Metadados do processamento")
    processing_time: float = Field(description="Tempo de processamento em segundos", ge=0.0)
    lgpd_compliant: bool = Field(description="Se resposta esta em conformidade LGPD")
    requires_human_review: bool = Field(description="Se resposta requer revisao humana")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "answer": "Total de vendas hoje: R$ 145.327,50",
                "confidence": 0.85,
                "sources": [
                    {"source": "oracle_text_to_sql", "sql": "SELECT SUM(VALOR) FROM VW_RAG_VENDAS..."}
                ],
                "metadata": {
                    "route": "text_to_sql",
                    "lgpd_level": "BAIXO",
                    "rows_returned": 1
                },
                "processing_time": 0.523,
                "lgpd_compliant": True,
                "requires_human_review": False
            }
        }


# ============================================
# WEBHOOK PAYLOADS
# ============================================

class WhatsAppMessageKey(BaseModel):
    """Chave de identificacao da mensagem WhatsApp"""
    remoteJid: str = Field(description="JID do remetente")
    fromMe: bool = Field(description="Se mensagem foi enviada pelo bot")
    id: str = Field(description="ID unico da mensagem")


class WhatsAppMessageContent(BaseModel):
    """Conteudo da mensagem WhatsApp"""
    messageType: MessageType = Field(description="Tipo da mensagem")
    conversation: Optional[str] = Field(None, description="Texto da mensagem (se tipo conversation)")


class WhatsAppWebhookData(BaseModel):
    """Dados do webhook da Evolution API"""
    key: WhatsAppMessageKey = Field(description="Identificacao da mensagem")
    message: WhatsAppMessageContent = Field(description="Conteudo da mensagem")


class WhatsAppWebhookPayload(BaseModel):
    """
    Payload completo do webhook WhatsApp
    
    Exemplo:
        {
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": false,
                    "id": "message_id_123"
                },
                "message": {
                    "messageType": "conversation",
                    "conversation": "Quais foram as vendas de hoje?"
                }
            }
        }
    """
    event: str = Field(description="Tipo do evento (messages.upsert, etc)")
    data: WhatsAppWebhookData = Field(description="Dados da mensagem")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event": "messages.upsert",
                "data": {
                    "key": {
                        "remoteJid": "5511999999999@s.whatsapp.net",
                        "fromMe": False,
                        "id": "message_id_123"
                    },
                    "message": {
                        "messageType": "conversation",
                        "conversation": "Quais foram as vendas de hoje?"
                    }
                }
            }
        }


# ============================================
# CONFIGURACOES
# ============================================

class DatabaseConfig(BaseModel):
    """Configuracao de conexao com banco de dados"""
    host: str = Field(description="Host do banco de dados", min_length=1)
    port: int = Field(description="Porta do banco de dados", gt=0, lt=65536)
    user: str = Field(description="Usuario do banco", min_length=1)
    password: str = Field(description="Senha do banco", min_length=1)
    database: Optional[str] = Field(None, description="Nome do banco/SID")
    service_name: Optional[str] = Field(None, description="Service name (Oracle)")
    
    @validator('password')
    def password_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Password cannot be empty')
        return v


class OpenAIConfig(BaseModel):
    """Configuracao da OpenAI API"""
    api_key: str = Field(description="API key da OpenAI", min_length=20)
    model: str = Field(description="Modelo de chat", default="gpt-4")
    embedding_model: str = Field(description="Modelo de embeddings", default="text-embedding-3-small")
    max_tokens: int = Field(description="Maximo de tokens por request", default=1500, gt=0)
    temperature: float = Field(description="Temperature para geração", default=0.7, ge=0.0, le=2.0)


class EvolutionAPIConfig(BaseModel):
    """Configuracao da Evolution API (WhatsApp)"""
    api_url: str = Field(description="URL da Evolution API")
    api_key: str = Field(description="API key da Evolution", min_length=1)
    instance_name: str = Field(description="Nome da instancia", min_length=1)
    webhook_host: str = Field(description="Host do webhook", default="0.0.0.0")
    webhook_port: int = Field(description="Porta do webhook", default=5000, gt=0, lt=65536)
    webhook_public_url: Optional[str] = Field(None, description="URL publica do webhook")


# ============================================
# METRICAS
# ============================================

class QueryMetric(BaseModel):
    """Metrica de uma query processada"""
    timestamp: datetime = Field(description="Timestamp da query", default_factory=datetime.now)
    query_text: str = Field(description="Texto da query", max_length=500)
    lgpd_level: LGPDLevel = Field(description="Nivel LGPD")
    route_used: QueryRoute = Field(description="Rota usada")
    success: bool = Field(description="Se query foi bem-sucedida")
    latency_ms: float = Field(description="Latencia em milissegundos", ge=0.0)
    user_id: Optional[str] = Field(None, description="ID do usuario")
    error: Optional[str] = Field(None, description="Mensagem de erro")
    tokens_used: Optional[int] = Field(None, description="Tokens OpenAI usados", ge=0)


# ============================================
# UTILITARIOS
# ============================================

def generate_json_schemas():
    """Gera JSON Schemas para todos os models"""
    models = [
        UserContext,
        RAGResponse,
        WhatsAppWebhookPayload,
        DatabaseConfig,
        OpenAIConfig,
        EvolutionAPIConfig,
        QueryMetric
    ]
    
    schemas = {}
    for model in models:
        schemas[model.__name__] = model.model_json_schema()
    
    return schemas


def save_schemas_to_file(output_file: str = "docs/schemas.json"):
    """Salva schemas em arquivo JSON"""
    import json
    from pathlib import Path
    
    schemas = generate_json_schemas()
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schemas, f, indent=2, ensure_ascii=False)
    
    print(f"Schemas salvos em: {output_path}")


if __name__ == "__main__":
    # Gera documentacao dos schemas
    print("Generating JSON Schemas...")
    save_schemas_to_file()
    
    # Testa validacao
    print("\nTesting validation...")
    
    try:
        # Teste valido
        user = UserContext(
            lgpd_clearance=LGPDLevel.ALTO,
            user_id="5511999999999@s.whatsapp.net",
            user_name="Test User",
            department="TI"
        )
        print(f"Valid UserContext: {user.user_name}")
        
        # Teste invalido (deve lancar excecao)
        try:
            invalid_user = UserContext(
                lgpd_clearance="INVALID",
                user_id=""
            )
        except Exception as e:
            print(f"Validation error (expected): {e}")
        
        print("\nValidation tests passed!")
        
    except Exception as e:
        print(f"Error: {e}")
