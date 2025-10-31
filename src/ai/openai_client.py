# src/ai/openai_client.py
"""
OpenAI Client - Sistema RAG Cativa Têxtil
Integração completa com OpenAI API para embeddings e chat completions
"""

import sys
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import numpy as np

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent.parent))

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("OpenAI não instalado. Execute: pip install openai")

from core.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIClient:
    """
    Cliente OpenAI para Sistema RAG
    Gerencia embeddings e chat completions
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa cliente OpenAI
        
        Args:
            api_key: Chave da API OpenAI (se None, usa variável de ambiente)
        """
        
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library não encontrada. Execute: pip install openai")
        
        # Configuração da API
        self.api_key = api_key or self._get_api_key()
        self.api_key_configured = bool(self.api_key and self.api_key.strip() and not self.api_key.startswith('your-'))
        
        if not self.api_key_configured:
            logger.warning("API Key OpenAI não configurada. Usando modo simulado.")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)
        
        # Modelos utilizados
        self.embedding_model = "text-embedding-3-small"
        self.chat_model = "gpt-4o-mini"  # Modelo mais eficiente
        self.embedding_dimensions = 1536
        
        # Cache para embeddings (otimização)
        self.embedding_cache = {}
        
        # Controle de rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms entre requests
        
        logger.info(f"OpenAI Client inicializado")
        logger.info(f"Embedding Model: {self.embedding_model}")
        logger.info(f"Chat Model: {self.chat_model}")
        logger.info(f"API Key: {' Configurada' if self.api_key_configured else ' Não configurada'}")
    
    def _get_api_key(self) -> Optional[str]:
        """Obtém API key de diferentes fontes"""
        import os
        
        # Tenta variáveis de ambiente
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            return api_key
        
        # Tenta arquivo de configuração
        config_file = Path('.env')
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    for line in f:
                        if line.startswith('OPENAI_API_KEY='):
                            return line.split('=', 1)[1].strip().strip('"\'')
            except Exception as e:
                logger.warning(f"Erro ao ler .env: {e}")
        
        return None
    
    def _rate_limit(self):
        """Implementa rate limiting simples"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def generate_embedding(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Gera embedding para texto usando OpenAI API
        
        Args:
            text: Texto para gerar embedding
            use_cache: Usar cache para otimização
            
        Returns:
            Array numpy com embedding
        """
        
        if not text or not text.strip():
            return np.zeros(self.embedding_dimensions)
        
        # Verifica cache
        if use_cache and text in self.embedding_cache:
            return self.embedding_cache[text]
        
        # Se API não configurada, usa simulação
        if not self.client:
            return self._generate_simulated_embedding(text)
        
        try:
            self._rate_limit()
            
            # Chama API OpenAI
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text.strip(),
                encoding_format="float"
            )
            
            # Extrai embedding
            embedding_data = response.data[0].embedding
            embedding = np.array(embedding_data, dtype=np.float32)
            
            # Normaliza (importante para similaridade de cosseno)
            embedding = embedding / np.linalg.norm(embedding)
            
            # Armazena no cache
            if use_cache:
                self.embedding_cache[text] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
            logger.info("Usando embedding simulado como fallback")
            return self._generate_simulated_embedding(text)
    
    def generate_batch_embeddings(self, texts: List[str], batch_size: int = 50) -> List[np.ndarray]:
        """
        Gera embeddings em lote para otimizar API calls
        
        Args:
            texts: Lista de textos
            batch_size: Tamanho do lote (máximo OpenAI é ~2048)
            
        Returns:
            Lista de embeddings
        """
        
        if not self.client:
            logger.info("API não configurada, usando embeddings simulados")
            return [self._generate_simulated_embedding(text) for text in texts]
        
        embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        logger.info(f"Gerando {len(texts)} embeddings em {total_batches} lote(s)")
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            try:
                self._rate_limit()
                
                logger.info(f"   Lote {batch_num}/{total_batches}: {len(batch)} textos")
                
                # Filtra textos vazios
                valid_texts = [text.strip() for text in batch if text and text.strip()]
                
                if not valid_texts:
                    embeddings.extend([np.zeros(self.embedding_dimensions)] * len(batch))
                    continue
                
                # Chama API
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=valid_texts,
                    encoding_format="float"
                )
                
                # Processa resultados
                batch_embeddings = []
                valid_idx = 0
                
                for original_text in batch:
                    if original_text and original_text.strip():
                        embedding_data = response.data[valid_idx].embedding
                        embedding = np.array(embedding_data, dtype=np.float32)
                        embedding = embedding / np.linalg.norm(embedding)
                        batch_embeddings.append(embedding)
                        valid_idx += 1
                    else:
                        batch_embeddings.append(np.zeros(self.embedding_dimensions))
                
                embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"Erro no lote {batch_num}: {e}")
                # Fallback para embeddings simulados
                batch_embeddings = [self._generate_simulated_embedding(text) for text in batch]
                embeddings.extend(batch_embeddings)
        
        logger.info(f"{len(embeddings)} embeddings gerados")
        return embeddings
    
    def generate_chat_response(self, query: str, context_chunks: List[Dict], user_context: Dict = None, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Gera resposta usando ChatGPT com contexto RAG
        
        Args:
            query: Pergunta do usuário
            context_chunks: Chunks relevantes recuperados
            user_context: Contexto adicional do usuário
            conversation_history: Histórico recente da conversa (lista de {user, bot})
            
        Returns:
            Dicionário com resposta estruturada
        """
        
        if not self.client:
            return self._generate_simulated_chat_response(query, context_chunks)
        
        try:
            # Monta contexto para ChatGPT
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(query, context_chunks, user_context, conversation_history)
            
            self._rate_limit()
            
            # Chama ChatGPT
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000,
                temperature=0.1,  # Resposta mais factual
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            # Extrai resposta
            answer = response.choices[0].message.content.strip()
            
            # Metadados da resposta
            usage = response.usage
            
            return {
                'success': True,
                'answer': answer,
                'model': self.chat_model,
                'tokens_used': {
                    'prompt': usage.prompt_tokens,
                    'completion': usage.completion_tokens,
                    'total': usage.total_tokens
                },
                'context_chunks_used': len(context_chunks),
                'generated_at': time.time()
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar resposta ChatGPT: {e}")
            return self._generate_simulated_chat_response(query, context_chunks)
    
    def _build_system_prompt(self) -> str:
        """Constrói prompt de sistema para ChatGPT"""
        
        return """Você é um assistente inteligente da Cativa Têxtil, especializado em consultar dados corporativos de vendas, clientes e representantes.

=== REGRAS FUNDAMENTAIS ===

1. SAUDAÇÕES:
   - Se a mensagem for apenas saudação (oi, olá, bom dia, boa tarde, boa noite), responda APENAS com uma saudação amigável
   - Exemplo: "Olá! Sou o assistente virtual da Cativa Têxtil. Como posso ajudar?"
   - NÃO mostre dados ou tabelas em saudações

2. CONSULTAS DE DADOS:
   - Use SOMENTE as informações do contexto fornecido
   - Seja preciso, factual e objetivo
   - Responda em português brasileiro claro
   - Formate valores monetários em formato brasileiro (R$ 1.234,56)
   - Se não houver contexto suficiente, diga claramente

3. FORMATAÇÃO DE RESPOSTAS:
   - Para dados tabulares: organize de forma clara e legível no WhatsApp
   - Use quebras de linha e espaçamento adequado
   - Destaque informações importantes
   - Limite respostas a 5-7 itens principais (se houver muitos dados)

4. PRIVACIDADE E LGPD:
   - Respeite o nível de permissão do usuário
   - Não exponha dados sensíveis desnecessariamente
   - Mantenha confidencialidade

5. QUANDO NÃO SOUBER:
   - Seja honesto: "Não encontrei informações sobre isso"
   - Sugira reformular a pergunta se apropriado
   - Não invente dados

=== CONTEXTO DA EMPRESA ===
Cativa Têxtil: empresa têxtil com 36+ anos de tradição
Localização: Pomerode, Santa Catarina
Áreas: Produção, Comercial, Marketing e Desenvolvimento

=== TIPOS DE CONSULTAS SUPORTADAS ===
- Pedidos e faturamento
- Clientes e representantes
- Regiões geográficas
- Performance comercial
- Análises estatísticas"""
    
    def _build_user_prompt(self, query: str, context_chunks: List[Dict], user_context: Dict = None, conversation_history: List[Dict] = None) -> str:
        """Constrói prompt do usuário com contexto RAG e histórico de conversa"""
        
        prompt_parts = []
        
        # Histórico recente da conversa (NOVO)
        if conversation_history and len(conversation_history) > 0:
            prompt_parts.append("=== HISTÓRICO DA CONVERSA ===")
            for msg in conversation_history[-3:]:
                prompt_parts.append(f"Usuário: {msg['user']}")
                prompt_parts.append(f"Assistente: {msg['bot']}")
                prompt_parts.append("")
            prompt_parts.append("---")
            prompt_parts.append("")
        
        # Contexto recuperado
        if context_chunks:
            prompt_parts.append("=== CONTEXTO RELEVANTE ===")
            for i, chunk in enumerate(context_chunks[:5], 1):
                similarity = chunk.get('similarity', 0)
                content = chunk.get('content', '')
                prompt_parts.append(f"{i}. [Similaridade: {similarity:.2f}] {content}")
            
            prompt_parts.append("")
        
        # Contexto do usuário (se disponível)
        if user_context:
            department = user_context.get('department', 'Não especificado')
            prompt_parts.append(f"CONTEXTO DO USUÁRIO: Departamento {department}")
            prompt_parts.append("")
        
        # Pergunta atual
        prompt_parts.append(f"=== PERGUNTA ATUAL ===")
        prompt_parts.append(query)
        prompt_parts.append("")
        prompt_parts.append("Responda considerando o histórico da conversa e o contexto fornecido:")
        
        return "\n".join(prompt_parts)
    
    def _generate_simulated_embedding(self, text: str) -> np.ndarray:
        """Gera embedding simulado (fallback)"""
        import hashlib
        
        # Usa hash determinístico como seed
        text_hash = hashlib.md5(text.encode()).hexdigest()
        np.random.seed(int(text_hash[:8], 16))
        
        # Gera vetor aleatório normalizado
        embedding = np.random.normal(0, 1, self.embedding_dimensions)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.astype(np.float32)
    
    def _generate_simulated_chat_response(self, query: str, context_chunks: List[Dict]) -> Dict[str, Any]:
        """Gera resposta simulada (fallback)"""
        
        if context_chunks:
            best_chunk = context_chunks[0]
            answer = f"Com base nos dados encontrados: {best_chunk['content'][:200]}..."
        else:
            answer = "Não encontrei informações específicas para responder sua pergunta."
        
        return {
            'success': True,
            'answer': answer,
            'model': 'simulated',
            'tokens_used': {'total': 0},
            'context_chunks_used': len(context_chunks),
            'generated_at': time.time()
        }
    
    def test_api_connection(self) -> Dict[str, Any]:
        """Testa conexão com OpenAI API"""
        
        if not self.client:
            return {
                'connected': False,
                'error': 'API Key não configurada'
            }
        
        try:
            # Teste simples de embedding
            test_response = self.client.embeddings.create(
                model=self.embedding_model,
                input="teste de conexão",
                encoding_format="float"
            )
            
            return {
                'connected': True,
                'embedding_model': self.embedding_model,
                'chat_model': self.chat_model,
                'embedding_dimensions': len(test_response.data[0].embedding)
            }
            
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }

# Função de teste
def test_openai_integration():
    """Testa integração OpenAI completa"""
    
    print("TESTANDO INTEGRAÇÃO OPENAI")
    print("=" * 50)
    
    # Inicializa cliente
    client = OpenAIClient()
    
    # Teste de conexão
    connection_test = client.test_api_connection()
    print(f"Conexão: {connection_test}")
    
    # Teste de embedding
    print(f"\nTestando embeddings...")
    test_texts = [
        "Pedido 843562 Cliente CONFECCOES EDINELI valor 2842.50",
        "Vendas região São Paulo acima de 2000 reais",
        "Representante comercial MATO GROSSO"
    ]
    
    embeddings = client.generate_batch_embeddings(test_texts)
    print(f"Gerados {len(embeddings)} embeddings")
    print(f"Dimensões: {embeddings[0].shape if embeddings else 'N/A'}")
    
    # Teste de chat (se API configurada)
    if client.client:
        print(f"\nTestando chat completion...")
        mock_chunks = [
            {
                'content': 'Pedido número 843562. Cliente: CONFECCOES EDINELI LTDA. Valor líquido: R$ 2.842,50.',
                'similarity': 0.85
            }
        ]
        
        chat_response = client.generate_chat_response(
            "Qual o valor do pedido 843562?",
            mock_chunks
        )
        # 843562
        #"Qual o valor do pedido 111?"
        print(f"Resposta: {chat_response['answer'][:100]}...")
        print(f"Tokens: {chat_response['tokens_used']['total']}")
    
    print(f"\nTeste concluído!")

if __name__ == "__main__":
    test_openai_integration()