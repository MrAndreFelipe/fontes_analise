# test_oracle_sync_mini.py
"""
Script de teste REDUZIDO do oracle_sync
Testa inserção de poucos registros de TODAS as views para validação
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'src'))

import logging
from datetime import datetime
from src.data_processing.oracle_sync import OracleToPostgreSQLSync, load_config_from_env

# Configura logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_mini_sync():
    """
    Teste MINI: Sincroniza apenas 10 registros de cada tipo
    para validar se as inserções estão funcionando
    """
    
    print("=" * 80)
    print("TESTE MINI - ORACLE SYNC")
    print("Sincronizando apenas 10 registros de cada view para validação")
    print("=" * 80)
    
    # Carrega configurações
    oracle_config, postgres_config = load_config_from_env()
    
    try:
        # Inicializa sincronizador
        sync = OracleToPostgreSQLSync(oracle_config, postgres_config)
        
        # Conecta aos bancos
        if not sync.connect_databases():
            print("ERRO: Falha ao conectar aos bancos")
            return False
        
        print("Conexoes estabelecidas\n")
        
        # Estatísticas
        results = {
            'vendas_textual': {'success': False, 'errors': 0},
            'vendas_resumos': {'success': False, 'errors': 0},
            'cp_textual': {'success': False, 'errors': 0},
            'cp_resumos': {'success': False, 'errors': 0},
            'cr_textual': {'success': False, 'errors': 0},
            'cr_resumos': {'success': False, 'errors': 0}
        }
        
        # ========================================
        # 1. VENDAS - Dados Textuais (10 registros, 7 dias)
        # ========================================
        print("\n[1/6] Testando: VENDAS - Dados Textuais")
        print("-" * 80)
        inicio = datetime.now()
        
        try:
            success = sync.sync_textual_data_for_embeddings(
                days_back=7,        # Apenas últimos 7 dias
                max_records=10      # Apenas 10 registros
            )
            results['vendas_textual']['success'] = success
            results['vendas_textual']['errors'] = len([e for e in sync.sync_stats['errors'] if 'oracle_sync' in str(e)])
            
            duracao = (datetime.now() - inicio).total_seconds()
            if success:
                print(f"SUCESSO em {duracao:.1f}s - Processados: {sync.sync_stats['records_processed']}, Erros: {results['vendas_textual']['errors']}")
            else:
                print(f"FALHA em {duracao:.1f}s")
        except Exception as e:
            print(f"ERRO: {e}")
            results['vendas_textual']['errors'] = 999
        
        # ========================================
        # 2. VENDAS - Resumos Agregados
        # ========================================
        print("\n[2/6] Testando: VENDAS - Resumos Agregados")
        print("-" * 80)
        inicio = datetime.now()
        
        try:
            success = sync.sync_aggregated_summaries(
                period_months=3     # Apenas últimos 3 meses
            )
            results['vendas_resumos']['success'] = success
            results['vendas_resumos']['errors'] = len([e for e in sync.sync_stats['errors'] if 'oracle_agregado' in str(e)])
            
            duracao = (datetime.now() - inicio).total_seconds()
            if success:
                print(f"SUCESSO em {duracao:.1f}s - Erros: {results['vendas_resumos']['errors']}")
            else:
                print(f"FALHA em {duracao:.1f}s")
        except Exception as e:
            print(f"ERRO: {e}")
            results['vendas_resumos']['errors'] = 999
        
        # ========================================
        # 3. CONTAS A PAGAR - Dados Textuais (10 registros)
        # ========================================
        print("\n[3/6] Testando: CONTAS A PAGAR - Dados Textuais")
        print("-" * 80)
        inicio = datetime.now()
        
        try:
            success = sync.sync_contas_pagar(
                days_back=7,
                max_records=10
            )
            results['cp_textual']['success'] = success
            results['cp_textual']['errors'] = len([e for e in sync.sync_stats['errors'] if 'cp_' in str(e) and 'resumo' not in str(e)])
            
            duracao = (datetime.now() - inicio).total_seconds()
            if success:
                print(f"SUCESSO em {duracao:.1f}s - Erros: {results['cp_textual']['errors']}")
            else:
                print(f"FALHA em {duracao:.1f}s")
        except Exception as e:
            print(f"ERRO: {e}")
            results['cp_textual']['errors'] = 999
        
        # ========================================
        # 4. CONTAS A PAGAR - Resumos Agregados
        # ========================================
        print("\n[4/6] Testando: CONTAS A PAGAR - Resumos")
        print("-" * 80)
        inicio = datetime.now()
        
        try:
            success = sync.sync_cp_resumos_agregados(
                period_months=3
            )
            results['cp_resumos']['success'] = success
            results['cp_resumos']['errors'] = len([e for e in sync.sync_stats['errors'] if 'cp_resumo' in str(e)])
            
            duracao = (datetime.now() - inicio).total_seconds()
            if success:
                print(f"SUCESSO em {duracao:.1f}s - Erros: {results['cp_resumos']['errors']}")
            else:
                print(f"FALHA em {duracao:.1f}s")
        except Exception as e:
            print(f"ERRO: {e}")
            results['cp_resumos']['errors'] = 999
        
        # ========================================
        # 5. CONTAS A RECEBER - Dados Textuais (10 registros)
        # ========================================
        print("\n[5/6] Testando: CONTAS A RECEBER - Dados Textuais")
        print("-" * 80)
        inicio = datetime.now()
        
        try:
            success = sync.sync_contas_receber(
                days_back=7,
                max_records=10
            )
            results['cr_textual']['success'] = success
            results['cr_textual']['errors'] = len([e for e in sync.sync_stats['errors'] if 'cr_' in str(e) and 'resumo' not in str(e)])
            
            duracao = (datetime.now() - inicio).total_seconds()
            if success:
                print(f"SUCESSO em {duracao:.1f}s - Erros: {results['cr_textual']['errors']}")
            else:
                print(f"FALHA em {duracao:.1f}s")
        except Exception as e:
            print(f"ERRO: {e}")
            results['cr_textual']['errors'] = 999
        
        # ========================================
        # 6. CONTAS A RECEBER - Resumos Agregados
        # ========================================
        print("\n[6/6] Testando: CONTAS A RECEBER - Resumos")
        print("-" * 80)
        inicio = datetime.now()
        
        try:
            success = sync.sync_cr_resumos_agregados(
                period_months=3
            )
            results['cr_resumos']['success'] = success
            results['cr_resumos']['errors'] = len([e for e in sync.sync_stats['errors'] if 'cr_resumo' in str(e)])
            
            duracao = (datetime.now() - inicio).total_seconds()
            if success:
                print(f"SUCESSO em {duracao:.1f}s - Erros: {results['cr_resumos']['errors']}")
            else:
                print(f"FALHA em {duracao:.1f}s")
        except Exception as e:
            print(f"ERRO: {e}")
            results['cr_resumos']['errors'] = 999
        
        # ========================================
        # RELATÓRIO FINAL
        # ========================================
        print("\n" + "=" * 80)
        print("RELATÓRIO FINAL DO TESTE")
        print("=" * 80)
        
        total_sucesso = sum(1 for r in results.values() if r['success'])
        total_testes = len(results)
        
        print(f"\nResumo: {total_sucesso}/{total_testes} testes passaram\n")
        
        for nome, resultado in results.items():
            status = "PASSOU" if resultado['success'] else "FALHOU"
            erros = resultado['errors']
            print(f"  {nome:30s} {status:15s} Erros: {erros}")
        
        # Estatísticas finais
        print("\n" + "-" * 80)
        print(f"Total de registros processados: {sync.sync_stats['records_processed']}")
        print(f"Total de embeddings gerados: {sync.sync_stats['embeddings_generated']}")
        print(f"Total de erros: {len(sync.sync_stats['errors'])}")
        
        # Mostra primeiros 10 erros
        if sync.sync_stats['errors']:
            print("\nPrimeiros erros:")
            for i, erro in enumerate(sync.sync_stats['errors'][:10], 1):
                print(f"   {i}. {erro}")
            
            if len(sync.sync_stats['errors']) > 10:
                print(f"   ... e mais {len(sync.sync_stats['errors']) - 10} erros")
        
        print("=" * 80)
        
        # Desconecta
        sync.disconnect()
        
        return total_sucesso == total_testes
        
    except Exception as e:
        logger.error(f"Erro geral no teste: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nINICIANDO TESTE MINI DO ORACLE SYNC\n")
    
    sucesso = test_mini_sync()
    
    if sucesso:
        print("\nTODOS OS TESTES PASSARAM!")
        sys.exit(0)
    else:
        print("\nALGUNS TESTES FALHARAM - Verifique os logs acima")
        sys.exit(1)
