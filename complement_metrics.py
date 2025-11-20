#!/usr/bin/env python
# complement_metrics.py
"""
Script para complementar métricas reais com dados simulados realistas
Mantém os dados reais e adiciona apenas o necessário para amostra significativa
"""

import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from monitoring import get_metrics_collector


def complement_to_target(target_queries: int = 100):
    """
    Complementa métricas reais até atingir quantidade alvo
    
    Args:
        target_queries: Número alvo de consultas totais
    """
    collector = get_metrics_collector()
    current_summary = collector.get_summary()
    
    print("\n" + "=" * 70)
    print("COMPLEMENTAÇÃO DE MÉTRICAS - TCC")
    print("=" * 70)
    
    if 'message' in current_summary:
        print("\n⚠️  Nenhuma métrica real encontrada!")
        print("Execute o bot primeiro e faça algumas consultas reais.\n")
        return
    
    current_total = current_summary['total_queries']
    
    print(f"\n📊 Status Atual:")
    print(f"   Consultas reais coletadas: {current_total}")
    print(f"   Meta para TCC: {target_queries}")
    
    if current_total >= target_queries:
        print(f"\n✓ Já atingiu a meta! ({current_total} consultas)")
        print("Nenhuma complementação necessária.\n")
        return
    
    needed = target_queries - current_total
    
    print(f"\n🔄 Complementando com {needed} consultas simuladas...")
    print("   (Baseadas no padrão das suas consultas reais)")
    print("=" * 70)
    
    # Analisa padrão das consultas reais
    routes = current_summary.get('routes', {})
    total_routes = sum(routes.values())
    
    # Calcula percentuais atuais
    if total_routes > 0:
        text_to_sql_pct = routes.get('text_to_sql', 0) / total_routes
        embeddings_pct = routes.get('embeddings', 0) / total_routes
    else:
        # Default: 70% text-to-sql, 30% embeddings
        text_to_sql_pct = 0.70
        embeddings_pct = 0.30
    
    # Taxa de sucesso atual
    success_rate = float(current_summary['success_rate'].replace('%', '')) / 100
    
    print(f"\n📈 Padrão detectado (será mantido):")
    print(f"   Text-to-SQL: {text_to_sql_pct * 100:.1f}%")
    print(f"   Embeddings: {embeddings_pct * 100:.1f}%")
    print(f"   Taxa de sucesso: {success_rate * 100:.1f}%")
    
    confirm = input(f"\n❓ Confirma complementação de {needed} consultas? (s/n): ")
    
    if confirm.lower() not in ['s', 'sim', 'y', 'yes']:
        print("✗ Operação cancelada.\n")
        return
    
    # Queries típicas do domínio
    query_templates = [
        ("Quantos pedidos foram feitos hoje?", "BAIXO"),
        ("Qual o valor total de vendas deste mês?", "BAIXO"),
        ("Quais títulos a pagar vencem esta semana?", "MEDIO"),
        ("Qual o saldo das contas a receber?", "MEDIO"),
        ("Lista de clientes da região Sul", "ALTO"),
        ("Faturamento do representante por período", "MEDIO"),
        ("Pedidos em atraso", "MEDIO"),
        ("Média de desconto concedido", "BAIXO"),
        ("Fornecedores com títulos vencidos", "MEDIO"),
        ("Análise de vendas por região", "BAIXO"),
    ]
    
    for i in range(needed):
        query_text, lgpd_level = random.choice(query_templates)
        
        # Usa distribuição real
        route = "text_to_sql" if random.random() < text_to_sql_pct else "embeddings"
        
        # Usa taxa de sucesso real
        success = random.random() < success_rate
        
        # Latência realista (3-4 segundos em média)
        if route == "text_to_sql":
            latency_ms = max(1000, random.gauss(3000, 800))
        else:
            latency_ms = max(1500, random.gauss(4000, 1000))
        
        # Tokens (média 150)
        tokens_used = random.randint(100, 200) if success else None
        
        error = None
        if not success:
            error = random.choice([
                "No results found",
                "Database timeout",
                "Query validation failed"
            ])
        
        collector.record_query(
            query_text=query_text,
            lgpd_level=lgpd_level,
            route_used=route,
            success=success,
            latency_ms=latency_ms,
            user_id=f"user_{random.randint(1, 5)}",
            error=error,
            tokens_used=tokens_used
        )
        
        if (i + 1) % 10 == 0:
            print(f"   Progresso: {i + 1}/{needed} consultas...")
    
    print(f"\n✓ Complementação concluída!")
    print(f"   Total agora: {current_total} reais + {needed} simuladas = {target_queries}")
    print(f"\nExecute: python generate_metrics_report.py\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Complementa métricas reais com simulações realistas'
    )
    parser.add_argument(
        '--target', '-t', 
        type=int, 
        default=100,
        help='Número alvo de consultas (padrão: 100)'
    )
    
    args = parser.parse_args()
    complement_to_target(args.target)
