# src/data_processing/chunking.py
"""
Sistema de fragmentação (chunking):
- Máximo 800 tokens por chunk
- 100 tokens de sobreposição
- Consolida chunks menores que 120 tokens
"""

from typing import List
import sys
from pathlib import Path

# Adiciona src ao path para imports funcionarem
sys.path.append(str(Path(__file__).parent.parent))
from core.config import Config

class ChunkingEngine:
    """
    Engine responsável por fragmentar texto em chunks otimizados
    """
    
    def __init__(self):
        """Inicializa com configurações do TCC"""
        self.max_tokens = Config.MAX_CHUNK_TOKENS
        self.overlap_tokens = Config.OVERLAP_TOKENS  
        self.min_tokens = Config.MIN_CHUNK_TOKENS
        
        # Estimativa aproximada: 1 token ≈ 4 caracteres em português
        self.chars_per_token = 4
        
        print(f"ChunkingEngine inicializado:")
        print(f"Máximo: {self.max_tokens} tokens ({self.max_tokens * self.chars_per_token} chars)")
        print(f"Sobreposição: {self.overlap_tokens} tokens")
        print(f"Mínimo: {self.min_tokens} tokens")
    
    def create_chunks(self, text: str) -> List[str]:
        """
        Cria chunks de texto conforme especificação
        
        Args:
            text: Texto para fragmentar
            
        Returns:
            Lista de chunks de texto
        """
        # Checa se text é vazio ou composto apenas de espaços
        if not text or not text.strip():
            return []
        
        # Converte tokens para caracteres
        max_chars = self.max_tokens * self.chars_per_token
        overlap_chars = self.overlap_tokens * self.chars_per_token
        min_chars = self.min_tokens * self.chars_per_token
        
        # Divide o texto em palavras
        words = text.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            # Testa se adicionar a próxima palavra ultrapassaria o limite
            test_chunk = f"{current_chunk} {word}".strip()
            
            if len(test_chunk) > max_chars and current_chunk:
                # Se o chunk atual atende o tamanho mínimo, adiciona à lista
                if len(current_chunk) >= min_chars:
                    chunks.append(current_chunk)
                    
                    # Cria sobreposição: pega os últimos caracteres do chunk anterior
                    overlap_start = max(0, len(current_chunk) - overlap_chars)
                    current_chunk = current_chunk[overlap_start:] + f" {word}"
                else:
                    # Chunk muito pequeno, continua adicionando
                    current_chunk = test_chunk
            else:
                current_chunk = test_chunk
        
        # Processa o último chunk
        if current_chunk.strip():
            if len(current_chunk) >= min_chars:
                chunks.append(current_chunk)
            elif chunks:
                # Consolida chunk pequeno com o anterior
                chunks[-1] += f" {current_chunk}"
            else:
                # É o único chunk, mantém mesmo sendo pequeno
                chunks.append(current_chunk)
        
        return chunks if chunks else [text]
    
    def get_chunk_stats(self, text: str) -> dict:
        """
        Retorna estatísticas sobre os chunks criados
        """
        chunks = self.create_chunks(text)
        
        if not chunks:
            return {"total_chunks": 0}
        
        chunk_sizes = [len(chunk) for chunk in chunks]
        
        return {
            "total_chunks": len(chunks),
            "min_size": min(chunk_sizes),
            "max_size": max(chunk_sizes),
            "avg_size": sum(chunk_sizes) // len(chunk_sizes),
            "total_text_length": len(text),
            "chunks": chunks[:3]  # Primeiros 3 chunks para visualização
        }

# Função de teste
def test_chunking():
    """Testa o sistema de chunking com dados similares aos do CSV"""
    
    print("Testando sistema de chunking...")
    
    # Simula texto similar ao que será gerado dos dados de venda
    test_text = """
    Pedido número 843562. Cliente: CONFECCOES EDINELI LTDA. CNPJ: 03.221.721/0001-10. 
    Representante: MATO GROSSO COMERCIO E REPRESENTACAO LTDA. Região: SP - PIRACICABA P + M + Y + E. 
    Regional: SP INTERIOR. Valor líquido: R$ 2842,50. Valor bruto: R$ 3158,50. 
    Este pedido representa uma venda importante para a empresa no estado de São Paulo, 
    especificamente na região de Piracicaba. O cliente CONFECCOES EDINELI LTDA é um 
    parceiro estratégico que tem demonstrado consistência em suas compras ao longo dos anos.
    A diferença entre valor bruto e líquido sugere aplicação de descontos comerciais 
    apropriados conforme política da empresa. O representante MATO GROSSO COMERCIO atende 
    esta região com eficiência e mantém bom relacionamento com os clientes locais.
    """ * 8  # Multiplica por 8 para ter texto maior
    
    engine = ChunkingEngine()
    stats = engine.get_chunk_stats(test_text)
    
    print("Estatísticas dos chunks:")
    for key, value in stats.items():
        if key == "chunks":
            print(f"Primeiros chunks:")
            for i, chunk in enumerate(value, 1):
                print(f"      {i}. {chunk[:100]}...")
        else:
            print(f"   {key}: {value}")
    
    return stats

if __name__ == "__main__":
    test_chunking()