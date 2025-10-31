# test_chunks_search.py
"""
Script de Teste - Pesquisa de Chunks no PostgreSQL
Testa a busca vetorial de embeddings e o fallback do RAG Engine
"""

import sys
import os
from pathlib import Path

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent / 'src'))

import logging
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

from data_processing.embeddings import EmbeddingGenerator

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChunkSearchTester:
    """Classe para testar pesquisa de chunks"""
    
    def __init__(self):
        """Inicializa o testador"""
        self.postgres_config = {
            'host': os.getenv('PG_HOST', 'localhost'),
            'port': int(os.getenv('PG_PORT', '5432')),
            'database': os.getenv('PG_DATABASE', 'cativa_rag_db'),
            'user': os.getenv('PG_USER', 'cativa_user'),
            'password': os.getenv('PG_PASSWORD', 'cativa_password_2024')
        }
        self.connection = None
        self.embedding_generator = None
    
    def connect(self) -> bool:
        """Conecta ao PostgreSQL"""
        try:
            self.connection = psycopg2.connect(**self.postgres_config)
            logger.info("Conectado ao PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar: {e}")
            return False
    
    def disconnect(self):
        """Desconecta do PostgreSQL"""
        if self.connection:
            self.connection.close()
            logger.info("Desconectado do PostgreSQL")
    
    def check_chunks_stats(self) -> Dict[str, Any]:
        """Verifica estatísticas dos chunks no banco"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            # Total de chunks
            cursor.execute("SELECT COUNT(*) as total FROM chunks")
            total = cursor.fetchone()['total']
            
            # Chunks por entidade
            cursor.execute("""
                SELECT entity, COUNT(*) as count
                FROM chunks
                GROUP BY entity
                ORDER BY count DESC
            """)
            by_entity = cursor.fetchall()
            
            # Chunks com embeddings
            cursor.execute("SELECT COUNT(*) as total FROM chunks WHERE embedding IS NOT NULL")
            with_embeddings = cursor.fetchone()['total']
            
            # Chunks por LGPD
            cursor.execute("""
                SELECT nivel_lgpd, COUNT(*) as count
                FROM chunks
                GROUP BY nivel_lgpd
                ORDER BY count DESC
            """)
            by_lgpd = cursor.fetchall()
            
            return {
                'total_chunks': total,
                'with_embeddings': with_embeddings,
                'by_entity': by_entity,
                'by_lgpd': by_lgpd
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar estatísticas: {e}")
            return {}
    
    def display_stats(self):
        """Exibe estatísticas dos chunks"""
        print("\n" + "=" * 80)
        print("ESTATÍSTICAS DOS CHUNKS NO POSTGRESQL")
        print("=" * 80)
        
        stats = self.check_chunks_stats()
        
        if not stats:
            print("Não foi possível obter estatísticas")
            return
        
        print(f"\nTotal de Chunks: {stats['total_chunks']:,}")
        print(f"Chunks com Embeddings: {stats['with_embeddings']:,}")
        
        if stats['total_chunks'] == 0:
            print("\nAVISO: Não há chunks no banco!")
            print("Execute primeiro: python -m src.data_processing.oracle_sync")
            return
        
        print(f"\nChunks por Entidade:")
        for row in stats['by_entity']:
            print(f"   {row['entity']:<25} {row['count']:>6,} chunks")
        
        print(f"\nChunks por Nível LGPD:")
        for row in stats['by_lgpd']:
            print(f"   {row['nivel_lgpd']:<10} {row['count']:>6,} chunks")
        
        print("\n" + "=" * 80)
    
    def search_chunks_by_text(self, search_text: str, limit: int = 5) -> List[Dict]:
        """Busca chunks por texto (sem embeddings)"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT chunk_id, entity, nivel_lgpd,
                       LEFT(content_text, 200) as preview,
                       attributes
                FROM chunks
                WHERE content_text ILIKE %s
                ORDER BY created_at DESC
                LIMIT %s
            """
            
            cursor.execute(query, (f'%{search_text}%', limit))
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Erro na busca por texto: {e}")
            return []
    
    def search_chunks_by_embedding(self, query: str, limit: int = 5, threshold: float = 0.3) -> List[Dict]:
        """Busca chunks por similaridade de embedding"""
        try:
            # Inicializa gerador de embeddings se necessário
            if not self.embedding_generator:
                self.embedding_generator = EmbeddingGenerator()
            
            # Gera embedding da query
            logger.info(f"Gerando embedding para: '{query}'")
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            # Busca no PostgreSQL
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            sql = """
                SELECT 
                    chunk_id,
                    entity,
                    nivel_lgpd,
                    LEFT(content_text, 200) as preview,
                    1 - (embedding <=> %s::vector) as similarity,
                    attributes,
                    periodo,
                    source_file
                FROM chunks
                WHERE embedding IS NOT NULL
                AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            
            embedding_list = query_embedding.tolist()
            cursor.execute(sql, (embedding_list, embedding_list, threshold, embedding_list, limit))
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Erro na busca por embedding: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def display_search_results(self, results: List[Dict], search_type: str):
        """Exibe resultados da busca"""
        print(f"\n{'=' * 80}")
        print(f"RESULTADOS DA BUSCA ({search_type})")
        print(f"{'=' * 80}")
        
        if not results:
            print("\nNenhum resultado encontrado")
            return
        
        print(f"\n{len(results)} resultado(s) encontrado(s):\n")
        
        for i, row in enumerate(results, 1):
            print(f"{i}. Chunk ID: {row['chunk_id']}")
            print(f"   Entidade: {row['entity']}")
            print(f"   LGPD: {row['nivel_lgpd']}")
            
            if 'similarity' in row:
                similarity_pct = row['similarity'] * 100
                print(f"   Similaridade: {similarity_pct:.1f}%")
            
            if 'periodo' in row and row['periodo']:
                print(f"   Período: {row['periodo']}")
            
            print(f"   Preview: {row['preview']}...")
            print()
    
    def test_rag_engine_search(self, query: str):
        """Testa busca usando o RAG Engine completo"""
        try:
            from rag.rag_engine import RAGEngine
            
            print(f"\n{'=' * 80}")
            print("TESTE DO RAG ENGINE COMPLETO")
            print(f"{'=' * 80}")
            print(f"\nQuery: '{query}'")
            
            # Inicializa RAG Engine
            rag = RAGEngine(
                postgres_config=self.postgres_config,
                use_openai=False  # Desabilita OpenAI para teste rápido
            )
            
            # Processa query
            logger.info("Processando query via RAG Engine...")
            response = rag.process_query(query)
            
            # Exibe resultado
            print(f"\nResposta gerada:")
            print(f"   Sucesso: {response.success}")
            print(f"   Confiança: {response.confidence:.2%}")
            print(f"   LGPD Compliant: {response.lgpd_compliant}")
            print(f"   Requer Revisão: {response.requires_human_review}")
            print(f"   Tempo de Processamento: {response.processing_time:.2f}s")
            
            print(f"\nResposta:")
            print(f"   {response.answer[:500]}...")
            
            if response.sources:
                print(f"\nFontes ({len(response.sources)}):")
                for source in response.sources[:3]:
                    print(f"   - {source}")
            
            print(f"\nMetadata:")
            for key, value in response.metadata.items():
                print(f"   {key}: {value}")
            
            rag.close()
            
        except Exception as e:
            logger.error(f"Erro no teste do RAG Engine: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Menu interativo de testes"""
    print("\n" + "=" * 80)
    print("TESTE DE PESQUISA DE CHUNKS - SISTEMA RAG CATIVA TÊXTIL")
    print("=" * 80)
    
    tester = ChunkSearchTester()
    
    # Conecta ao PostgreSQL
    if not tester.connect():
        print("\nNão foi possível conectar ao PostgreSQL")
        print("Verifique as variáveis de ambiente:")
        print("  - PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD")
        return
    
    # Menu interativo
    while True:
        print("\n" + "=" * 80)
        print("MENU DE TESTES")
        print("=" * 80)
        print("1. Ver estatísticas dos chunks")
        print("2. Buscar por texto (ILIKE)")
        print("3. Buscar por embedding (similaridade vetorial)")
        print("4. Testar RAG Engine completo")
        print("5. Teste rápido (exemplos pré-definidos)")
        print("0. Sair")
        print()
        
        choice = input("Escolha uma opção: ").strip()
        
        if choice == '0':
            print("\nEncerrando...")
            break
        
        elif choice == '1':
            tester.display_stats()
        
        elif choice == '2':
            search_text = input("\nDigite o texto para buscar: ").strip()
            if search_text:
                results = tester.search_chunks_by_text(search_text)
                tester.display_search_results(results, "Busca por Texto")
        
        elif choice == '3':
            query = input("\nDigite a pergunta: ").strip()
            if query:
                results = tester.search_chunks_by_embedding(query, limit=5, threshold=0.2)
                tester.display_search_results(results, "Busca por Embedding")
        
        elif choice == '4':
            query = input("\nDigite a pergunta: ").strip()
            if query:
                tester.test_rag_engine_search(query)
        
        elif choice == '5':
            print("\nExecutando testes rápidos...\n")
            
            # Teste 1: Estatísticas
            print("1/4 - Verificando estatísticas...")
            tester.display_stats()
            
            # Teste 2: Busca por texto
            print("\n2/4 - Busca por texto (exemplo: 'cliente')...")
            results = tester.search_chunks_by_text('cliente', limit=3)
            tester.display_search_results(results, "Busca por Texto")
            
            # Teste 3: Busca por embedding - vendas
            print("\n3/4 - Busca por embedding (exemplo: 'vendas do mês')...")
            results = tester.search_chunks_by_embedding('vendas do mês', limit=3)
            tester.display_search_results(results, "Busca por Embedding")
            
            # Teste 4: Busca por embedding - contas
            print("\n4/4 - Busca por embedding (exemplo: 'contas a pagar')...")
            results = tester.search_chunks_by_embedding('contas a pagar', limit=3)
            tester.display_search_results(results, "Busca por Embedding")
            
            print("\nTestes rápidos concluídos!")
        
        else:
            print("\nOpção inválida!")
    
    # Desconecta
    tester.disconnect()
    print("\nTestes finalizados!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTeste interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        import traceback
        traceback.print_exc()
