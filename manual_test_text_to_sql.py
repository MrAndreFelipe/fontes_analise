# test_text_to_sql.py
"""
Script de teste para Text-to-SQL
Permite testar geração e execução de SQL a partir de linguagem natural
"""

import sys
from pathlib import Path

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent / 'src'))

import os
import logging
from sql.text_to_sql_service import TextToSQLService

# Carrega variáveis do arquivo .env (se existir)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Arquivo .env carregado")
except ImportError:
    print("python-dotenv não instalado. Usando apenas variáveis de ambiente do sistema.")
    print("   Para usar .env, instale: pip install python-dotenv")
except Exception as e:
    print(f"Erro ao carregar .env: {e}")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def print_banner():
    print("=" * 60)
    print("  TEXT-TO-SQL TESTER - Cativa Têxtil")
    print("=" * 60)
    print()

def check_oracle_config():
    """Verifica se as variáveis de ambiente Oracle estão configuradas"""
    required = ['ORACLE_HOST', 'ORACLE_USER', 'ORACLE_PASSWORD']
    optional = ['ORACLE_SERVICE_NAME', 'ORACLE_SID']
    
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        print("ATENÇÃO: Variáveis Oracle não configuradas completamente")
        print(f"   Faltando: {', '.join(missing)}")
        print()
        print("   O sistema gerará apenas o SQL (sem executar).")
        print("   Para executar no Oracle, configure:")
        print()
        for var in required:
            print(f"   $env:{var} = \"<seu_valor>\"")
        print(f"   $env:ORACLE_SERVICE_NAME = \"<seu_service>\"  # ou ORACLE_SID")
        print()
        return False
    
    # Verifica service_name ou sid
    if not (os.getenv('ORACLE_SERVICE_NAME') or os.getenv('ORACLE_SID')):
        print("Configure ORACLE_SERVICE_NAME ou ORACLE_SID")
        return False
    
    print("Configuração Oracle detectada")
    print(f"  Host: {os.getenv('ORACLE_HOST')}")
    print(f"  User: {os.getenv('ORACLE_USER')}")
    print()
    return True

def test_single_query(service, question):
    """Testa uma única query"""
    print("-" * 60)
    print(f"PERGUNTA: {question}")
    print("-" * 60)
    
    result = service.generate_and_execute(question, limit=10)
    
    if not result['success']:
        print(f"ERRO: {result.get('error', 'Erro desconhecido')}")
        if 'generated_sql' in result:
            print(f"\nSQL Gerado (inválido):")
            print(result['generated_sql'])
        return
    
    print("\nSQL GERADO:")
    print(result['generated_sql'])
    print()
    
    if result.get('executed'):
        rows = result.get('rows', [])
        cols = result.get('columns', [])
        
        if rows:
            print(f"RESULTADO: {len(rows)} linha(s) retornada(s)\n")
            
            # Mostra header
            print(" | ".join(cols))
            print("-" * 60)
            
            # Mostra primeiras 5 linhas
            for row in rows[:5]:
                values = [str(row.get(c, ''))[:20] for c in cols]
                print(" | ".join(values))
            
            if len(rows) > 5:
                print(f"... (+{len(rows) - 5} linhas)")
        else:
            print("Nenhuma linha retornada")
    else:
        print("SQL não foi executado (configure Oracle para executar)")
    
    print()

def run_interactive_mode(service):
    """Modo interativo: usuário digita perguntas"""
    print("MODO INTERATIVO")
    print("Digite suas perguntas em linguagem natural.")
    print("Comandos: 'sair' para sair, 'exemplos' para ver exemplos")
    print()
    
    while True:
        try:
            question = input("Pergunta> ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['sair', 'exit', 'quit']:
                print("Saindo...")
                break
            
            if question.lower() == 'exemplos':
                show_examples()
                continue
            
            test_single_query(service, question)
        
        except KeyboardInterrupt:
            print("\nInterrompido. Saindo...")
            break
        except Exception as e:
            print(f"Erro: {e}")
            print()

def show_examples():
    """Mostra exemplos de perguntas"""
    examples = [
        "Quais foram as vendas de hoje?",
        "Mostre o total de vendas do mês atual",
        "Liste os 5 maiores pedidos do mês",
        "Qual o valor total vendido em janeiro de 2025?",
        "Mostre as vendas do representante João Silva",
        "Quais clientes compraram mais de R$ 5000 este mês?",
        "Liste os pedidos da região SP",
    ]
    
    print("\nEXEMPLOS DE PERGUNTAS:")
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. {ex}")
    print()

def run_batch_tests(service):
    """Executa testes em lote com perguntas pré-definidas"""
    test_questions = [
        "Quais foram as vendas de hoje?",
        "Mostre os 3 maiores pedidos do mês",
        "Qual o total de vendas em janeiro de 2025?",
    ]
    
    print("EXECUTANDO TESTES EM LOTE")
    print()
    
    for i, question in enumerate(test_questions, 1):
        print(f"[{i}/{len(test_questions)}]")
        test_single_query(service, question)
        print()

def main():
    print_banner()
    
    # Verifica config Oracle
    has_oracle = check_oracle_config()
    
    # Inicializa serviço
    print("Inicializando Text-to-SQL Service...")
    try:
        service = TextToSQLService()
        print("Serviço inicializado\n")
    except Exception as e:
        print(f"Erro ao inicializar: {e}")
        return
    
    # Menu
    print("OPÇÕES:")
    print("  1. Modo interativo (digite suas perguntas)")
    print("  2. Testes em lote (perguntas pré-definidas)")
    print("  3. Ver exemplos e sair")
    print()
    
    choice = input("Escolha (1/2/3): ").strip()
    print()
    
    if choice == '1':
        run_interactive_mode(service)
    elif choice == '2':
        run_batch_tests(service)
    elif choice == '3':
        show_examples()
    else:
        print("Opção inválida")

if __name__ == "__main__":
    main()
