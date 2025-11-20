#!/usr/bin/env python
# generate_metrics_report.py
"""
Script para gerar relatório de métricas para o TCC
Analisa os dados coletados e gera estatísticas formatadas
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from monitoring import get_metrics_collector, print_metrics_summary


def calculate_percentages(routes: dict) -> dict:
    """Calcula percentuais de uso por rota"""
    total = sum(routes.values())
    if total == 0:
        return {}
    
    return {
        route: {
            'count': count,
            'percentage': (count / total) * 100
        }
        for route, count in routes.items()
    }


def generate_detailed_report():
    """Gera relatório detalhado para o TCC"""
    collector = get_metrics_collector()
    summary = collector.get_summary()
    
    print("\n" + "=" * 80)
    print("RELATÓRIO DE MÉTRICAS - TCC SISTEMA RAG CATIVA TÊXTIL")
    print("=" * 80)
    print(f"Data do Relatório: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 80)
    
    if 'message' in summary:
        print(f"\n⚠️  {summary['message']}")
        print("\nPara começar a coletar métricas:")
        print("1. Execute o bot: python whatsapp_bot.py")
        print("2. Envie consultas via WhatsApp")
        print("3. Execute este script novamente\n")
        return
    
    total_queries = summary['total_queries']
    
    # SEÇÃO 1: DESEMPENHO GERAL
    print("\n📊 1. DESEMPENHO GERAL")
    print("-" * 80)
    print(f"Total de Consultas Processadas: {total_queries}")
    print(f"Taxa de Sucesso: {summary['success_rate']}")
    print(f"Latência Média: {summary['average_latency_ms']}ms")
    
    # Calcula latência em segundos
    avg_latency_seconds = float(summary['average_latency_ms'].replace('ms', '')) / 1000
    print(f"Latência Média (segundos): {avg_latency_seconds:.2f}s")
    
    # SEÇÃO 2: DISTRIBUIÇÃO POR ROTA
    print("\n📈 2. DISTRIBUIÇÃO POR ROTA (Text-to-SQL vs Embeddings)")
    print("-" * 80)
    
    routes_with_pct = calculate_percentages(summary['routes'])
    
    for route, data in routes_with_pct.items():
        print(f"{route.upper():20} : {data['count']:4} consultas ({data['percentage']:5.1f}%)")
    
    # SEÇÃO 3: DISTRIBUIÇÃO LGPD
    print("\n🔒 3. DISTRIBUIÇÃO POR NÍVEL LGPD")
    print("-" * 80)
    
    lgpd_with_pct = calculate_percentages(summary['lgpd_distribution'])
    
    for level, data in lgpd_with_pct.items():
        print(f"{level:10} : {data['count']:4} consultas ({data['percentage']:5.1f}%)")
    
    # SEÇÃO 4: CUSTOS OPENAI
    print("\n💰 4. CONSUMO DE TOKENS (OpenAI)")
    print("-" * 80)
    print(f"Total de Tokens Utilizados: {summary['total_tokens_used']:,}")
    
    if total_queries > 0:
        avg_tokens = summary['total_tokens_used'] / total_queries
        print(f"Média de Tokens por Consulta: {avg_tokens:.1f}")
    
    # SEÇÃO 5: ERROS
    print("\n❌ 5. ANÁLISE DE ERROS")
    print("-" * 80)
    print(f"Total de Erros: {summary['error_count']}")
    
    if summary['error_count'] > 0:
        error_rate = (summary['error_count'] / total_queries) * 100
        print(f"Taxa de Erro: {error_rate:.1f}%")
    
    # SEÇÃO 6: INFORMAÇÕES ADICIONAIS
    print("\n📅 6. PERÍODO DE COLETA")
    print("-" * 80)
    print(f"Início da Coleta: {summary['last_reset']}")
    print(f"Arquivo de Métricas: logs/metrics.json")
    
    # SEÇÃO 7: RESUMO PARA TCC
    print("\n" + "=" * 80)
    print("📝 RESUMO PARA INCLUSÃO NO TCC")
    print("=" * 80)
    
    print(f"\n✓ Tempo médio de resposta: {avg_latency_seconds:.1f} segundos")
    print(f"✓ Taxa de sucesso: {summary['success_rate']}")
    
    # Calcula percentuais das rotas
    if 'text_to_sql' in summary['routes'] and 'embeddings' in summary['routes']:
        text_to_sql_pct = routes_with_pct.get('text_to_sql', {}).get('percentage', 0)
        embeddings_pct = routes_with_pct.get('embeddings', {}).get('percentage', 0)
        
        print(f"✓ Distribuição de rotas:")
        print(f"  - Text-to-SQL: {text_to_sql_pct:.0f}%")
        print(f"  - Embeddings (fallback): {embeddings_pct:.0f}%")
    
    print(f"✓ Total de consultas analisadas: {total_queries}")
    
    # Calcula disponibilidade (baseado na taxa de sucesso)
    success_rate_value = float(summary['success_rate'].replace('%', ''))
    print(f"✓ Disponibilidade estimada: {success_rate_value:.1f}%")
    
    print("\n" + "=" * 80)
    print("💡 OBSERVAÇÕES:")
    print("=" * 80)
    print("• Estes dados são baseados em consultas reais processadas pelo sistema")
    print("• Para aumentar a amostra, continue usando o bot e colete mais dados")
    print("• O arquivo logs/metrics.json é atualizado automaticamente")
    print("• Use 'python generate_metrics_report.py --reset' para zerar métricas")
    print("=" * 80 + "\n")


def export_to_json(output_file: str = "metrics_report.json"):
    """Exporta métricas para JSON formatado"""
    collector = get_metrics_collector()
    summary = collector.get_summary()
    
    output_path = Path(output_file)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Métricas exportadas para: {output_path}")


def reset_metrics():
    """Reseta métricas para novo período de coleta"""
    collector = get_metrics_collector()
    
    response = input("⚠️  Tem certeza que deseja resetar todas as métricas? (sim/não): ")
    
    if response.lower() in ['sim', 's', 'yes', 'y']:
        collector.reset_metrics()
        print("✓ Métricas resetadas com sucesso!")
        print("  Novo período de coleta iniciado.")
    else:
        print("✗ Operação cancelada.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Gerador de Relatório de Métricas - TCC Sistema RAG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  # Gerar relatório completo
  python generate_metrics_report.py
  
  # Exportar para JSON
  python generate_metrics_report.py --export
  
  # Resetar métricas (novo período)
  python generate_metrics_report.py --reset
  
  # Visualização simples
  python generate_metrics_report.py --simple
        """
    )
    
    parser.add_argument('--export', '-e', action='store_true',
                       help='Exportar métricas para JSON')
    parser.add_argument('--reset', '-r', action='store_true',
                       help='Resetar métricas (apaga dados atuais)')
    parser.add_argument('--simple', '-s', action='store_true',
                       help='Visualização simples (resumo)')
    parser.add_argument('--output', '-o', default='metrics_report.json',
                       help='Arquivo de saída para export JSON')
    
    args = parser.parse_args()
    
    if args.reset:
        reset_metrics()
    elif args.export:
        export_to_json(args.output)
    elif args.simple:
        print_metrics_summary()
    else:
        generate_detailed_report()


if __name__ == "__main__":
    main()
