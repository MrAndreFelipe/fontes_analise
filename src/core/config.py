# src/core/config.py

"""
Configurações centralizadas do sistema RAG - Cativa Têxtil
Carrega configurações de variáveis de ambiente (.env) com fallbacks seguros
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


def load_env_file(env_path: Optional[str] = None):
    """
    Carrega variáveis de um arquivo .env (opcional)
    Se python-dotenv estiver instalado, usa ele. Senão, faz parsing manual.
    """
    if env_path is None:
        env_path = Path(__file__).parent.parent.parent / '.env'
    
    if not os.path.exists(env_path):
        return
    
    try:
        # Tenta usar python-dotenv se disponível
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        # Fallback: parsing manual
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and not os.getenv(key):
                        os.environ[key] = value


# Carrega .env se existir
load_env_file()


@dataclass
class OracleConfig:
    """Configuração do Oracle Database"""
    host: str
    port: int
    user: str
    password: str
    service_name: Optional[str] = None
    sid: Optional[str] = None
    
    @classmethod
    def from_env(cls):
        """Carrega configuração Oracle de variáveis de ambiente"""
        return cls(
            host=os.getenv('ORACLE_HOST', 'localhost'),
            port=int(os.getenv('ORACLE_PORT', '1521')),
            user=os.getenv('ORACLE_USER', 'user'),
            password=os.getenv('ORACLE_PASSWORD', ''),
            service_name=os.getenv('ORACLE_SERVICE_NAME'),
            sid=os.getenv('ORACLE_SID')
        )


@dataclass
class PostgresConfig:
    """Configuração do PostgreSQL"""
    host: str
    port: int
    database: str
    user: str
    password: str
    
    @classmethod
    def from_env(cls):
        """Carrega configuração PostgreSQL de variáveis de ambiente"""
        return cls(
            host=os.getenv('PG_HOST', 'localhost'),
            port=int(os.getenv('PG_PORT', '5432')),
            database=os.getenv('PG_DATABASE', 'postgres'),
            user=os.getenv('PG_USER', 'postgres'),
            password=os.getenv('PG_PASSWORD', '')
        )


@dataclass
class EvolutionAPIConfig:
    """Configuração da Evolution API (WhatsApp)"""
    api_url: str
    api_key: str
    instance_name: str
    webhook_host: str
    webhook_port: int
    webhook_public_url: str
    
    @classmethod
    def from_env(cls):
        """Carrega configuração Evolution API de variáveis de ambiente"""
        return cls(
            api_url=os.getenv('EVOLUTION_API_URL', 'http://localhost:8081'),
            api_key=os.getenv('EVOLUTION_API_KEY', ''),
            instance_name=os.getenv('EVOLUTION_INSTANCE', 'default'),
            webhook_host=os.getenv('WEBHOOK_HOST', '0.0.0.0'),
            webhook_port=int(os.getenv('WEBHOOK_PORT', '5000')),
            webhook_public_url=os.getenv('WEBHOOK_PUBLIC_URL', '')
        )


@dataclass
class OpenAIConfig:
    """Configuração da OpenAI API"""
    api_key: str
    model: str
    embedding_model: str
    max_tokens: int
    temperature: float
    
    @classmethod
    def from_env(cls):
        """Carrega configuração OpenAI de variáveis de ambiente"""
        return cls(
            api_key=os.getenv('OPENAI_API_KEY', ''),
            model=os.getenv('OPENAI_MODEL', 'gpt-4'),
            embedding_model=os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'),
            max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '1500')),
            temperature=float(os.getenv('OPENAI_TEMPERATURE', '0.7'))
        )


class Config:
    """Configurações centralizadas do sistema RAG"""
    
    # ============================================
    # CONFIGURAÇÕES FIXAS (Não dependem de .env)
    # ============================================
    
    # Diretório raiz do projeto (onde está a pasta src)
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    # Pastas importantes
    DATA_DIR = PROJECT_ROOT / "data"
    LOGS_DIR = PROJECT_ROOT / "logs"
    
    # Configurações de Chunking
    MAX_CHUNK_TOKENS = 800      # Máximo de tokens por chunk
    OVERLAP_TOKENS = 100        # Sobreposição entre chunks
    MIN_CHUNK_TOKENS = 120      # Mínimo (chunks menores são consolidados)
    
    # Configurações de Embedding
    EMBEDDING_DIMENSION = 1536  # Dimensão do text-embedding-3-small
    
    # Configurações LGPD
    LGPD_LEVELS = ["BAIXO", "MÉDIO", "ALTO"]

    BATCH_SIZE = 1000
    
    # Ambiente
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # ============================================
    # CONFIGURAÇÕES DINÂMICAS (De .env)
    # ============================================
    
    # Cache das configurações (singleton)
    _oracle_config = None
    _postgres_config = None
    _evolution_config = None
    _openai_config = None
    
    @classmethod
    def oracle(cls) -> OracleConfig:
        """Retorna configuração Oracle (singleton)"""
        if cls._oracle_config is None:
            cls._oracle_config = OracleConfig.from_env()
        return cls._oracle_config
    
    @classmethod
    def postgres(cls) -> PostgresConfig:
        """Retorna configuração PostgreSQL (singleton)"""
        if cls._postgres_config is None:
            cls._postgres_config = PostgresConfig.from_env()
        return cls._postgres_config
    
    @classmethod
    def evolution(cls) -> EvolutionAPIConfig:
        """Retorna configuração Evolution API (singleton)"""
        if cls._evolution_config is None:
            cls._evolution_config = EvolutionAPIConfig.from_env()
        return cls._evolution_config
    
    @classmethod
    def openai(cls) -> OpenAIConfig:
        """Retorna configuração OpenAI (singleton)"""
        if cls._openai_config is None:
            cls._openai_config = OpenAIConfig.from_env()
        return cls._openai_config
    
    @classmethod
    def create_directories(cls):
        """Cria os diretórios necessários se não existirem"""
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)
        print(f"Diretórios criados em: {cls.PROJECT_ROOT}")
    
    @classmethod
    def validate(cls) -> bool:
        """Valida se as configurações essenciais estão presentes"""
        errors = []
        
        # Valida Oracle
        oracle = cls.oracle()
        if not oracle.password:
            errors.append("ORACLE_PASSWORD não configurado")
        if not oracle.service_name and not oracle.sid:
            errors.append("ORACLE_SERVICE_NAME ou ORACLE_SID deve ser configurado")
        
        # Valida PostgreSQL
        postgres = cls.postgres()
        if not postgres.password:
            errors.append("PG_PASSWORD não configurado")
        
        # Valida OpenAI
        openai = cls.openai()
        if not openai.api_key:
            errors.append("OPENAI_API_KEY não configurado")
        
        if errors:
            print("WARNING: Configurações faltando:")
            for error in errors:
                print(f"   - {error}")
            return False
        
        return True
    
    @classmethod
    def print_summary(cls):
        """Imprime resumo das configurações (sem mostrar senhas)"""
        print("\n" + "=" * 60)
        print("CONFIGURAÇÃO DO SISTEMA RAG")
        print("=" * 60)
        
        print(f"\n[ENV] Ambiente: {cls.ENVIRONMENT}")
        print(f"[DEBUG] Debug: {cls.DEBUG}")
        print(f"[LOG] Log Level: {cls.LOG_LEVEL}")
        
        oracle = cls.oracle()
        print(f"\n[DB] Oracle:")
        print(f"   Host: {oracle.host}:{oracle.port}")
        print(f"   User: {oracle.user}")
        print(f"   Service: {oracle.service_name or oracle.sid}")
        print(f"   Password: {'[OK] Configurado' if oracle.password else '[FAILED] Não configurado'}")
        
        postgres = cls.postgres()
        print(f"\n[PG] PostgreSQL:")
        print(f"   Host: {postgres.host}:{postgres.port}")
        print(f"   Database: {postgres.database}")
        print(f"   User: {postgres.user}")
        print(f"   Password: {'[OK] Configurado' if postgres.password else '[FAILED] Não configurado'}")
        
        evolution = cls.evolution()
        print(f"\n[CHAT] WhatsApp (Evolution API):")
        print(f"   URL: {evolution.api_url}")
        print(f"   Instance: {evolution.instance_name}")
        print(f"   Webhook: {evolution.webhook_host}:{evolution.webhook_port}")
        print(f"   API Key: {'[OK] Configurado' if evolution.api_key else '[FAILED] Não configurado'}")
        
        openai = cls.openai()
        print(f"\n[AI] OpenAI:")
        print(f"   Model: {openai.model}")
        print(f"   Embedding Model: {openai.embedding_model}")
        print(f"   API Key: {'[OK] Configurado' if openai.api_key else '[FAILED] Não configurado'}")
        
        print("\n" + "=" * 60 + "\n")

# Teste de configuração
if __name__ == "__main__":
    Config.create_directories()
    Config.print_summary()
    
    if Config.validate():
        print("SUCCESS: Configuração válida!")
    else:
        print("ERROR: Configure as variáveis de ambiente faltantes no arquivo .env")
