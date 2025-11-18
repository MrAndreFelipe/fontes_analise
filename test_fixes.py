#!/usr/bin/env python
# test_fixes.py
"""
Testa as correções implementadas:
1. Detecção de perguntas fora de escopo (piadas, geografia, etc.)
2. Consultas por semana no Oracle 11g (TO_CHAR com 'IW')
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from sql.text_to_sql_generator import TextToSQLGenerator
from sql.schema_introspector import SchemaIntrospector

def test_out_of_scope():
    """Testa detecção de perguntas fora de escopo"""
    print("\n" + "="*60)
    print("TESTE 1: Detecção de Perguntas Fora de Escopo")
    print("="*60)
    
    generator = TextToSQLGenerator()
    introspector = SchemaIntrospector()
    schema = introspector.get_schema_for_llm()
    
    test_cases = [
        "Me conta uma piada?",
        "Qual a capital da França?",
        "Valor vendido hoje na capital da França",
        "Como você está?",
    ]
    
    for question in test_cases:
        print(f"\n📝 Pergunta: '{question}'")
        sql = generator.generate_sql(question, schema)
        
        if sql == 'OUT_OF_SCOPE':
            print(f"   ✅ CORRETO: Detectada como fora de escopo")
        elif sql is None:
            print(f"   ⚠️  LLM indisponível")
        else:
            print(f"   ❌ ERRO: Gerou SQL: {sql[:100]}...")


def test_week_queries():
    """Testa consultas por semana"""
    print("\n" + "="*60)
    print("TESTE 2: Consultas por Semana (Oracle 11g)")
    print("="*60)
    
    generator = TextToSQLGenerator()
    introspector = SchemaIntrospector()
    schema = introspector.get_schema_for_llm()
    
    test_cases = [
        "Valor vendido na semana 40",
        "Quantos pedidos na semana 40?",
        "Faturamento da semana 40",
    ]
    
    for question in test_cases:
        print(f"\n📝 Pergunta: '{question}'")
        sql = generator.generate_sql(question, schema)
        
        if sql == 'OUT_OF_SCOPE':
            print(f"   ❌ ERRO: Detectada como fora de escopo (deveria ser válida)")
        elif sql is None:
            print(f"   ⚠️  LLM indisponível")
        else:
            # Verifica se usou TO_CHAR com 'IW'
            if "TO_CHAR" in sql.upper() and "'IW'" in sql:
                print(f"   ✅ CORRETO: Usa TO_CHAR(... 'IW')")
            elif "WEEK(" in sql.upper():
                print(f"   ❌ ERRO: Ainda usa WEEK() (inválido no Oracle 11g)")
            else:
                print(f"   ⚠️  ATENÇÃO: Método desconhecido")
            
            print(f"   SQL gerado: {sql}")


def main():
    print("\n" + "="*60)
    print("🧪 TESTES DE CORREÇÕES - Sistema RAG Cativa Têxtil")
    print("="*60)
    
    try:
        test_out_of_scope()
        test_week_queries()
        
        print("\n" + "="*60)
        print("✅ TESTES CONCLUÍDOS")
        print("="*60)
        print("\nSe todos os testes passaram, reinicie o bot:")
        print("  python whatsapp_bot.py")
        print()
        
    except Exception as e:
        print(f"\n❌ ERRO durante testes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
