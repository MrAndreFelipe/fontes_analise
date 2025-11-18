import sys
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.sql.text_to_sql_generator import TextToSQLGenerator
from src.sql.schema_introspector import SchemaIntrospector
from src.ai.openai_client import OpenAIClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_conversation_context():
    """
    Testa se o sistema mantem contexto temporal em perguntas de seguimento
    """
    
    print("\n" + "="*80)
    print("TESTE DE CONTEXTO TEMPORAL EM CONVERSAS")
    print("="*80 + "\n")
    
    try:
        # Inicializa componentes
        openai_client = OpenAIClient()
        generator = TextToSQLGenerator(openai_client)
        introspector = SchemaIntrospector()
        schema_text = introspector.get_schema_for_llm()
        
        # Cenario 1: Pergunta inicial sobre "hoje"
        print("[CENARIO 1] Pergunta inicial: 'Principais pedidos de hoje?'\n")
        
        conversation_history_1 = []
        
        sql_1 = generator.generate_sql(
            question="Principais pedidos de hoje?",
            schema_text=schema_text,
            conversation_history=conversation_history_1
        )
        
        print(f"SQL GERADO 1:\n{sql_1}\n")
        
        # Simula resposta do bot
        bot_response_1 = "Posso te mostrar de duas formas: um total geral das vendas ou uma listagem detalhada dos pedidos. Qual prefere?"
        
        # Atualiza historico
        conversation_history_2 = [
            {
                'user': 'Principais pedidos de hoje?',
                'bot': bot_response_1
            }
        ]
        
        # Cenario 2: Pergunta de seguimento "Pode ser o total geral" (DEVE MANTER "hoje")
        print("-" * 80)
        print("[CENARIO 2] Pergunta de seguimento: 'Pode ser o total geral'\n")
        print("HISTORICO DISPONIVEL:")
        for msg in conversation_history_2:
            print(f"  Usuario: {msg['user']}")
            print(f"  Bot: {msg['bot'][:80]}...")
        print()
        
        sql_2 = generator.generate_sql(
            question="Pode ser o total geral",
            schema_text=schema_text,
            conversation_history=conversation_history_2
        )
        
        print(f"SQL GERADO 2:\n{sql_2}\n")
        
        # Validacao
        print("="*80)
        print("VALIDACAO DOS RESULTADOS:")
        print("="*80 + "\n")
        
        # Verifica se SQL 2 mantem o filtro de data
        if sql_2:
            has_date_filter = any([
                'TRUNC(DATA_VENDA) = TRUNC(SYSDATE)' in sql_2.upper(),
                'TRUNC(SYSDATE)' in sql_2.upper(),
                'DATA_VENDA' in sql_2.upper() and 'SYSDATE' in sql_2.upper()
            ])
            
            if has_date_filter:
                print("[OK] SQL mantem filtro de data 'hoje' do contexto anterior")
                print("     Contexto temporal foi preservado corretamente!\n")
                return True
            else:
                print("[ERRO] SQL NAO mantem filtro de data")
                print("       O sistema PERDEU o contexto temporal 'hoje'")
                print("       SQL retornaria dados de TODOS os periodos!\n")
                return False
        else:
            print("[ERRO] SQL nao foi gerado (LLM indisponivel ou erro)\n")
            return False
            
    except Exception as e:
        logger.error(f"Erro durante teste: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_additional_scenarios():
    """
    Testa cenarios adicionais de contexto
    """
    
    print("\n" + "="*80)
    print("CENARIOS ADICIONAIS DE CONTEXTO")
    print("="*80 + "\n")
    
    try:
        openai_client = OpenAIClient()
        generator = TextToSQLGenerator(openai_client)
        introspector = SchemaIntrospector()
        schema_text = introspector.get_schema_for_llm()
        
        # Cenario 3: Mudanca explicita de periodo
        print("[CENARIO 3] Mudanca explicita de periodo\n")
        
        conversation_history = [
            {
                'user': 'Vendas de hoje?',
                'bot': 'Total de vendas de hoje: R$ 50.000,00'
            }
        ]
        
        sql_3 = generator.generate_sql(
            question="E de ontem?",
            schema_text=schema_text,
            conversation_history=conversation_history
        )
        
        print(f"Pergunta: 'E de ontem?'")
        print(f"SQL GERADO:\n{sql_3}\n")
        
        if sql_3 and 'SYSDATE - 1' in sql_3.upper():
            print("[OK] Sistema interpretou corretamente mudanca para 'ontem'\n")
        else:
            print("[ATENCAO] Sistema pode nao ter interpretado 'ontem' corretamente\n")
        
        # Cenario 4: Referencia implicita a entidade
        print("-" * 80)
        print("[CENARIO 4] Referencia implicita a entidade\n")
        
        conversation_history = [
            {
                'user': 'Vendas do cliente CONFECCOES EDINELI',
                'bot': 'Cliente CONFECCOES EDINELI tem vendas de R$ 100.000,00'
            }
        ]
        
        sql_4 = generator.generate_sql(
            question="E os pedidos dele?",
            schema_text=schema_text,
            conversation_history=conversation_history
        )
        
        print(f"Pergunta: 'E os pedidos dele?'")
        print(f"SQL GERADO:\n{sql_4}\n")
        
        if sql_4 and 'CONFECCOES EDINELI' in sql_4.upper():
            print("[OK] Sistema manteve referencia ao cliente do contexto\n")
        else:
            print("[ATENCAO] Sistema pode nao ter mantido referencia ao cliente\n")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro nos testes adicionais: {e}")
        return False

if __name__ == "__main__":
    print("\nINICIANDO TESTES DE CONTEXTO DE CONVERSA\n")
    
    resultado_principal = test_conversation_context()
    resultado_adicional = test_additional_scenarios()
    
    print("\n" + "="*80)
    print("RESUMO DOS TESTES")
    print("="*80)
    print(f"Teste principal (contexto temporal): {'PASSOU' if resultado_principal else 'FALHOU'}")
    print(f"Testes adicionais: {'PASSOU' if resultado_adicional else 'FALHOU'}")
    print()
    
    if resultado_principal and resultado_adicional:
        print("TODOS OS TESTES PASSARAM")
        sys.exit(0)
    else:
        print("ALGUNS TESTES FALHARAM - Revise as melhorias necessarias")
        sys.exit(1)
