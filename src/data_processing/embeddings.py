# src/data_processing/embeddings.py
"""
Sistema de geração de embeddings
Suporta tanto embeddings reais via OpenAI quanto simulados
"""

import numpy as np
import hashlib
import sys
import os
import logging
from pathlib import Path
from typing import List, Optional
import time

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent.parent))
from core.config import Config
from core.retry_handler import retry_openai

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tenta importar OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI não instalada. Execute: pip install openai")

class EmbeddingGenerator:
    """
    Gerador de embeddings vetoriais para texto
    Suporta modo real (OpenAI) e simulado
    """
    
    def __init__(self, use_openai: bool = True, api_key: str = None):
        """
        Inicializa o gerador de embeddings
        
        Args:
            use_openai: Se True, usa OpenAI. Se False, usa simulado. 
                       Se None, detecta automaticamente baseado na disponibilidade da API
            api_key: Chave da API OpenAI (opcional, pode usar variável de ambiente)
        """
        self.dimension = Config.EMBEDDING_DIMENSION
        self.openai_client = None
        self.use_openai = False
        
        # Determina se deve usar OpenAI
        if use_openai is None:
            # Auto-detecta baseado na disponibilidade
            use_openai = self._should_use_openai(api_key)
        
        if use_openai and OPENAI_AVAILABLE:
            # Tenta configurar OpenAI
            success = self._setup_openai(api_key)
            if success:
                self.use_openai = True
                self.model_name = "text-embedding-3-small"
            else:
                logger.warning("Falha ao configurar OpenAI, usando modo simulado")
                self.model_name = "text-embedding-3-small-simulated"
        else:
            # Modo simulado
            self.model_name = "text-embedding-3-small-simulated"
        
        # Cache para otimização
        self.embedding_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Rate limiting para OpenAI
        self.last_api_call = 0
        self.min_api_interval = 0.1  # 100ms entre chamadas
        
        logger.info(f"EmbeddingGenerator inicializado:")
        logger.info(f"Modelo: {self.model_name}")
        logger.info(f"Dimensões: {self.dimension}")
        logger.info(f"Modo: {'OpenAI Real' if self.use_openai else 'Simulado'}")
    
    def _should_use_openai(self, api_key: str = None) -> bool:
        """Determina se deve usar OpenAI baseado na disponibilidade"""
        if not OPENAI_AVAILABLE:
            return False
        
        # Verifica se há API key disponível
        if api_key:
            return True
        
        # Tenta pegar da variável de ambiente
        env_key = os.getenv('OPENAI_API_KEY')
        if env_key:
            return True
        
        # Tenta ler do arquivo .env
        env_file = Path('.env')
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith('OPENAI_API_KEY=') and len(line.split('=', 1)[1].strip()) > 10:
                            return True
            except:
                pass
        
        return False
    
    def _setup_openai(self, api_key: str = None) -> bool:
        """Configura cliente OpenAI"""
        try:
            # Obtém API key
            if not api_key:
                api_key = os.getenv('OPENAI_API_KEY')
            
            if not api_key:
                # Tenta ler do .env
                env_file = Path('.env')
                if env_file.exists():
                    with open(env_file, 'r') as f:
                        for line in f:
                            if line.startswith('OPENAI_API_KEY='):
                                api_key = line.split('=', 1)[1].strip().strip('"\'')
                                break
            
            if not api_key:
                logger.warning("API Key OpenAI não encontrada")
                return False
            
            # Cria cliente OpenAI
            self.openai_client = OpenAI(api_key=api_key)
            
            # Testa conexão
            test_response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input="teste",
                encoding_format="float"
            )
            
            logger.info("OpenAI API configurada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao configurar OpenAI: {e}")
            return False
    
    def _rate_limit(self):
        """Implementa rate limiting para API calls"""
        if self.use_openai:
            current_time = time.time()
            time_since_last = current_time - self.last_api_call
            
            if time_since_last < self.min_api_interval:
                sleep_time = self.min_api_interval - time_since_last
                time.sleep(sleep_time)
            
            self.last_api_call = time.time()
    
    def generate_embedding(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Gera embedding para um texto
        
        Args:
            text: Texto para gerar embedding
            use_cache: Se deve usar cache
            
        Returns:
            Array numpy com o embedding (vetor de números)
        """
        if not text or not text.strip():
            # Retorna vetor zero para texto vazio
            return np.zeros(self.dimension)
        
        # Verifica cache
        if use_cache and text in self.embedding_cache:
            self.cache_hits += 1
            return self.embedding_cache[text]
        
        self.cache_misses += 1
        
        # Gera embedding
        if self.use_openai:
            logger.debug("Gerando embedding via OpenAI API")
            embedding = self._generate_openai_embedding(text)
        else:
            embedding = self._generate_simulated_embedding(text)
        
        # Armazena no cache
        if use_cache:
            self.embedding_cache[text] = embedding
        
        return embedding
    
    @retry_openai(max_retries=3)
    def _generate_openai_embedding(self, text: str) -> np.ndarray:
        """Gera embedding real usando OpenAI API (COM RETRY)"""
        self._rate_limit()
        
        try:
            # Chama API OpenAI
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text.strip(),
                encoding_format="float"
            )
            
            # Extrai embedding
            embedding_data = response.data[0].embedding
            embedding = np.array(embedding_data, dtype=np.float32)
            
            # Normaliza o vetor (importante para cálculos de similaridade)
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Erro ao gerar embedding OpenAI: {e}")
            logger.info("Usando embedding simulado como fallback")
            return self._generate_simulated_embedding(text)
    
    def _generate_simulated_embedding(self, text: str) -> np.ndarray:
        """
        Gera embedding simulado (fallback)
        Usa hash do texto para gerar embedding determinístico
        """
        # Usa hash do texto como seed para números aleatórios determinísticos
        text_hash = hashlib.md5(text.encode()).hexdigest()
        np.random.seed(int(text_hash[:8], 16))
        
        # Gera vetor aleatório com distribuição normal
        embedding = np.random.normal(0, 1, self.dimension)
        
        # Normaliza o vetor (importante para cálculos de similaridade)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.astype(np.float32)
    
    def generate_batch_embeddings(self, texts: List[str], batch_size: int = 50) -> List[np.ndarray]:
        """
        Gera embeddings para múltiplos textos
        
        Args:
            texts: Lista de textos
            batch_size: Tamanho do lote para API calls
            
        Returns:
            Lista de embeddings
        """
        embeddings = []
        
        logger.info(f"Gerando embeddings para {len(texts)} textos...")
        logger.info(f"Modo: {'OpenAI Real' if self.use_openai else 'Simulado'}")
        
        if self.use_openai:
            # Processa em lotes para OpenAI
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(texts) + batch_size - 1) // batch_size
                
                if batch_num % 10 == 1:  # Log a cada 10 lotes
                    logger.info(f"   Processando lote {batch_num}/{total_batches}")
                
                batch_embeddings = self._generate_batch_openai(batch)
                embeddings.extend(batch_embeddings)
        else:
            # Modo simulado - processa individualmente
            for i, text in enumerate(texts):
                if i % 100 == 0 and i > 0:
                    logger.info(f"   Processados: {i}/{len(texts)}")
                
                embedding = self.generate_embedding(text, use_cache=True)
                embeddings.append(embedding)
        
        logger.info(f"{len(embeddings)} embeddings gerados!")
        
        # Log estatísticas de cache
        if self.cache_hits + self.cache_misses > 0:
            hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) * 100
            logger.info(f"   Cache: {self.cache_hits} hits, {self.cache_misses} misses ({hit_rate:.1f}% hit rate)")
        
        return embeddings
    
    def _generate_batch_openai(self, texts: List[str]) -> List[np.ndarray]:
        """Gera embeddings em lote usando OpenAI"""
        try:
            self._rate_limit()
            
            # Filtra textos vazios
            valid_texts = []
            valid_indices = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_texts.append(text.strip())
                    valid_indices.append(i)
            
            if not valid_texts:
                # Todos vazios, retorna zeros
                return [np.zeros(self.dimension) for _ in texts]
            
            # Chama API
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=valid_texts,
                encoding_format="float"
            )
            
            # Processa resultados
            embeddings = []
            valid_idx = 0
            
            for i in range(len(texts)):
                if i in valid_indices:
                    # Texto válido - usa embedding da API
                    embedding_data = response.data[valid_idx].embedding
                    embedding = np.array(embedding_data, dtype=np.float32)
                    embedding = embedding / np.linalg.norm(embedding)
                    embeddings.append(embedding)
                    valid_idx += 1
                else:
                    # Texto vazio - usa zeros
                    embeddings.append(np.zeros(self.dimension))
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Erro no batch OpenAI: {e}")
            # Fallback para simulado
            return [self._generate_simulated_embedding(text) for text in texts]
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calcula similaridade de cosseno entre dois embeddings
        
        Args:
            embedding1: Primeiro embedding
            embedding2: Segundo embedding
            
        Returns:
            Similaridade entre 0 e 1 (1 = idênticos)
        """
        # Fórmula da similaridade de cosseno
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Converte de [-1, 1] para [0, 1]
        return (similarity + 1) / 2
    
    def clear_cache(self):
        """Limpa o cache de embeddings"""
        self.embedding_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info("Cache de embeddings limpo")
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do gerador"""
        return {
            'mode': 'OpenAI' if self.use_openai else 'Simulated',
            'model': self.model_name,
            'dimensions': self.dimension,
            'cache_size': len(self.embedding_cache),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%" 
                       if (self.cache_hits + self.cache_misses) > 0 else "N/A"
        }

def test_embeddings():
    """Testa o sistema de embeddings"""
    
    print("TESTANDO SISTEMA DE EMBEDDINGS")
    print("=" * 50)
    
    # Teste 1: Modo automático (detecta se tem API key)
    print("\n Teste modo automático:")
    generator_auto = EmbeddingGenerator()
    print(f"Modo: {generator_auto.model_name}")
    
    # Teste 2: Forçar modo simulado
    print("\n Teste modo simulado:")
    generator_sim = EmbeddingGenerator(use_openai=False)
    print(f"Modo: {generator_sim.model_name}")
    
    # Teste 3: Forçar modo OpenAI (se disponível)
    print("\n Teste modo OpenAI:")
    generator_openai = EmbeddingGenerator(use_openai=True)
    print(f"Modo: {generator_openai.model_name}")
    
    # Textos de teste (similares aos do CSV)
    test_texts = [
        "Pedido 843562 Cliente CONFECCOES EDINELI valor 2842.50",
        "Pedido 843563 Cliente CONFECCOES EDINELI valor 2800.00",  # Similar ao anterior
        "Pedido 999999 Cliente EMPRESA DIFERENTE valor 5000.00",   # Diferente
        "Representante MATO GROSSO região SP INTERIOR",
        "Região Santa Catarina Sul Serra produtos têxteis"
    ]
    
    print(f"\n Testando com {len(test_texts)} textos...")
    
    # Gera embeddings com o gerador principal
    embeddings = generator_auto.generate_batch_embeddings(test_texts)
    
    print(f"\n Informações dos embeddings:")
    print(f"Quantidade: {len(embeddings)}")
    print(f"Dimensões: {embeddings[0].shape}")
    print(f"Tipo: {type(embeddings[0])}")
    
    # Testa similaridades
    print(f"\n Testando similaridades:")
    
    # Textos similares (0 e 1) devem ter alta similaridade
    sim_alta = generator_auto.calculate_similarity(embeddings[0], embeddings[1])
    print(f"Textos similares (0 vs 1): {sim_alta:.3f}")
    
    # Textos diferentes (0 e 2) devem ter baixa similaridade  
    sim_baixa = generator_auto.calculate_similarity(embeddings[0], embeddings[2])
    print(f"Textos diferentes (0 vs 2): {sim_baixa:.3f}")
    
    # Texto consigo mesmo deve ser 100% similar
    sim_identica = generator_auto.calculate_similarity(embeddings[0], embeddings[0])
    print(f"Texto idêntico (0 vs 0): {sim_identica:.3f}")
     
    # Estatísticas
    print(f"\n Estatísticas:")
    stats = generator_auto.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Verificações
    print(f"\n Verificações:")
    print(f"Similaridade idêntica ≈ 1.0? {abs(sim_identica - 1.0) < 0.001}")
    print(f"Similaridade alta > baixa? {sim_alta > sim_baixa}")
    
    return embeddings

if __name__ == "__main__":
    test_embeddings()