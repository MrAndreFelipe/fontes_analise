# test_embedding_fallback.py
"""
Teste de busca direta por embeddings (fallback)
Valida o fluxo de fallback quando Text-to-SQL falha
Atualizado para RAG Engine V2
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'src'))

from rag.rag_engine import RAGEngine
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_embedding_search():
    """Testa busca direta por embeddings via process_query"""
    
    print("=" * 80)
    print("TESTE DE BUSCA POR EMBEDDINGS (FALLBACK V2)")
    print("=" * 80)
    
    # Configuração do PostgreSQL
    postgres_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'cativa_rag_db',
        'user': 'cativa_user',
        'password': 'cativa_password_2024'
    }
    
    # Inicializa RAG Engine V2 (sem Oracle para forçar fallback)
    print("\n1. Inicializando RAG Engine V2...")
    print("   Oracle: Desabilitado (forçar fallback)")
    print("   OpenAI: Desabilitado (usar formatação simples)")
    
    rag = RAGEngine(
        oracle_config=None,  # Sem Oracle para forçar embedding fallback
        postgres_config=postgres_config,
        use_openai=False  # Sem OpenAI para geração
    )
    
    print("RAG Engine V2 inicializado")
    
    # Queries de teste
    test_queries = [
        "pedido 123456",
        "vendas do cliente ABC",
        "representante João Silva",
        "região Nordeste",
        "valor total de vendas"
    ]
    
    print("\n2. Testando buscas por embedding (fallback automático)...\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"TESTE {i}: {query}")
        print('=' * 80)
        
        # Chama process_query - deve usar embedding fallback automaticamente
        print(f"\nProcessando via RAG Engine V2...")
        try:
            # User context simulado
            user_context = {
                'user_id': 'test_user',
                'lgpd_clearance': 'ALTO'
            }
            
            response = rag.process_query(query, user_context=user_context)
            
            if response and response.success:
                route = response.metadata.get('route', 'unknown')
                print(f"\nResposta gerada!")
                print(f"   Rota: {route}")
                print(f"   Confiança: {response.confidence:.2f}")
                print(f"   Tempo: {response.processing_time:.2f}s")
                print(f"   LGPD: {response.metadata.get('lgpd_level', 'N/A')}")
                
                if route == 'embeddings':
                    print("   FALLBACK EMBEDDINGS FUNCIONOU!")
                    chunks_used = response.metadata.get('chunks_used', 'N/A')
                    print(f"   Chunks usados: {chunks_used}")
                
                print(f"\nResposta:")
                print("-" * 80)
                print(response.answer[:500])
                if len(response.answer) > 500:
                    print("...")
                print("-" * 80)
                
                if response.sources:
                    print(f"\nFontes (top 3):")
                    for j, source in enumerate(response.sources[:3], 1):
                        sim = source.get('similarity', 'N/A')
                        entity = source.get('entity', 'N/A')
                        print(f"   {j}. Similaridade: {sim} | Entidade: {entity}")
            else:
                print("Nenhuma resposta gerada ou falha")
                if response:
                    print(f"   Motivo: {response.metadata.get('reason', 'N/A')}")
                
        except Exception as e:
            print(f"Erro: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("TESTE CONCLUÍDO")
    print("=" * 80)

def test_vector_similarity_direct():
    """Testa busca vetorial direta (método interno V2)"""
    
    print("\n" + "=" * 80)
    print("TESTE DE BUSCA VETORIAL DIRETA V2")
    print("=" * 80)
    
    postgres_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'cativa_rag_db',
        'user': 'cativa_user',
        'password': 'cativa_password_2024'
    }
    
    print("\n1. Inicializando RAG Engine V2...")
    rag = RAGEngine(
        oracle_config=None,
        postgres_config=postgres_config,
        use_openai=False
    )
    
    print("RAG Engine V2 inicializado")
    
    test_queries = [
        "pedido de venda",
        "cliente",
        "representante",
        "valor"
    ]
    
    print("\n2. Testando busca vetorial interna (_search_similar_chunks)...\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"TESTE {i}: '{query}'")
        print('=' * 80)
        
        try:
            # Gera embedding da query
            query_embedding = rag.embedding_generator.generate_embedding(query)
            
            # Conecta se necessário
            if not rag.postgres_conn:
                import psycopg2
                rag.postgres_conn = psycopg2.connect(**postgres_config)
            
            # Busca chunks similares
            results = rag._search_similar_chunks(query_embedding, max_results=5)
            
            print(f"\nEncontrados {len(results)} chunks")
            
            if results:
                print("\nTop 5 resultados:")
                for j, result in enumerate(results[:5], 1):
                    print(f"\n   {j}. Similaridade: {result.similarity:.3f}")
                    print(f"      Chunk ID: {result.chunk_id[:30]}...")
                    print(f"      Entidade: {result.entity}")
                    print(f"      LGPD: {result.nivel_lgpd}")
                    print(f"      Preview: {result.content[:150]}...")
            else:
                print("Nenhum chunk encontrado (threshold 0.2)")
                
        except Exception as e:
            print(f"Erro: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("TESTE VETORIAL CONCLUÍDO")
    print("=" * 80)

def test_full_pipeline_with_fallback():
    """Testa o pipeline completo incluindo fallback automático V2"""
    
    print("\n" + "=" * 80)
    print("TESTE DO PIPELINE COMPLETO COM FALLBACK V2")
    print("=" * 80)
    
    postgres_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'cativa_rag_db',
        'user': 'cativa_user',
        'password': 'cativa_password_2024'
    }
    
    # Oracle config vazio para forçar fallback
    oracle_config = None
    
    print("\n1. Inicializando RAG Engine V2 (Text-to-SQL desabilitado)...")
    rag = RAGEngine(
        oracle_config=oracle_config,
        postgres_config=postgres_config,
        use_openai=False
    )
    
    print("RAG Engine V2 inicializado")
    
    # Queries analíticas que normalmente usariam Text-to-SQL
    analytical_queries = [
        "Qual o total de vendas hoje?",
        "Quem mais vendeu no mês?",
        "Qual o valor total do pedido 123456?",
        "Mostre as vendas da região Nordeste"
    ]
    
    print("\n2. Testando queries analíticas (devem usar fallback)...\n")
    
    for i, query in enumerate(analytical_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"QUERY {i}: {query}")
        print('=' * 80)
        
        try:
            response = rag.process_query(query)
            
            route = response.metadata.get('route', 'unknown')
            print(f"\nResposta gerada!")
            print(f"   Rota: {route}")
            print(f"   Confiança: {response.confidence:.2f}")
            print(f"   Tempo: {response.processing_time:.2f}s")
            print(f"   Revisão necessária: {response.requires_human_review}")
            print(f"   LGPD: {response.metadata.get('lgpd_level', 'N/A')}")
            
            print(f"\nResposta:")
            print("-" * 80)
            print(response.answer[:400])
            if len(response.answer) > 400:
                print("...")
            print("-" * 80)
            
            # Verifica se usou fallback (V2 usa 'embeddings' não 'embedding_fallback')
            if route == 'embeddings':
                print("\nFALLBACK POR EMBEDDINGS FUNCIONOU!")
                chunks_used = response.metadata.get('chunks_used', 'N/A')
                print(f"   Chunks usados: {chunks_used}")
            elif route == 'text_to_sql':
                print("\nUsou Text-to-SQL (não esperado neste teste)")
            else:
                print(f"\nRota desconhecida: {route}")
                
        except Exception as e:
            print(f"Erro: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("TESTE DO PIPELINE CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Testes de busca por embeddings')
    parser.add_argument('--test', choices=['embedding', 'vector', 'pipeline', 'all'], 
                       default='all', help='Tipo de teste a executar')
    
    args = parser.parse_args()
    
    try:
        if args.test == 'embedding' or args.test == 'all':
            test_embedding_search()
        
        if args.test == 'vector' or args.test == 'all':
            test_vector_similarity_direct()
        
        if args.test == 'pipeline' or args.test == 'all':
            test_full_pipeline_with_fallback()
            
    except KeyboardInterrupt:
        print("\n\nTeste interrompido pelo usuário")
    except Exception as e:
        print(f"\nErro fatal: {e}")
        import traceback
        traceback.print_exc()
