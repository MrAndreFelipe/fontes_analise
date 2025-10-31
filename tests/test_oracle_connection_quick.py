# test_oracle_connection_quick.py
"""
Teste rápido da conexão Oracle usando configurações do .env
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'src'))

import os

# Carrega .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Arquivo .env carregado\n")
except ImportError:
    print("python-dotenv não instalado\n")

# Mostra configurações
print("=" * 60)
print("CONFIGURAÇÕES ORACLE DO .ENV")
print("=" * 60)
print(f"ORACLE_HOST: {os.getenv('ORACLE_HOST')}")
print(f"ORACLE_PORT: {os.getenv('ORACLE_PORT')}")
print(f"ORACLE_USER: {os.getenv('ORACLE_USER')}")
print(f"ORACLE_PASSWORD: {'*' * len(os.getenv('ORACLE_PASSWORD', ''))}")
print(f"ORACLE_SID: {os.getenv('ORACLE_SID')}")
print(f"ORACLE_SERVICE_NAME: {os.getenv('ORACLE_SERVICE_NAME')}")
print(f"ORACLE_SCHEMA: {os.getenv('ORACLE_SCHEMA')}")
print("=" * 60)
print()

# Testa conexão
print("Testando conexão Oracle...")
try:
    import cx_Oracle
    
    host = os.getenv('ORACLE_HOST')
    port = int(os.getenv('ORACLE_PORT', 1521))
    user = os.getenv('ORACLE_USER')
    password = os.getenv('ORACLE_PASSWORD')
    sid = os.getenv('ORACLE_SID')
    service_name = os.getenv('ORACLE_SERVICE_NAME')
    
    # Usa SID (mesma lógica do database_adapter.py)
    if service_name:
        print(f"Usando SERVICE_NAME: {service_name}")
        dsn = cx_Oracle.makedsn(host, port, service_name=service_name)
    elif sid:
        print(f"Usando SID: {sid}")
        dsn = cx_Oracle.makedsn(host, port, sid=sid)
    else:
        print("Nem SID nem SERVICE_NAME configurados!")
        sys.exit(1)
    
    print(f"DSN: {dsn}")
    print()
    
    # Conecta
    connection = cx_Oracle.connect(user=user, password=password, dsn=dsn, encoding="UTF-8")
    print("Conexão estabelecida com sucesso!")
    
    # Testa query simples
    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM DUAL")
    result = cursor.fetchone()
    print(f"Teste de query: {result[0]}")
    
    # Testa acesso à view
    cursor.execute("SELECT COUNT(*) FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA WHERE ROWNUM <= 1")
    result = cursor.fetchone()
    print(f"Acesso à view: OK (count={result[0]})")
    
    cursor.close()
    connection.close()
    print("\nTODOS OS TESTES PASSARAM!")
    print("\nAgora execute: python test_text_to_sql.py")
    
except ImportError:
    print("Erro: cx_Oracle não instalado")
    print("   Instale com: pip install cx_Oracle")
except Exception as e:
    print(f"Erro ao conectar: {e}")
    import traceback
    traceback.print_exc()
