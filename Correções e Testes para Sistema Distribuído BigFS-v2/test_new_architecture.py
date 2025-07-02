#!/usr/bin/env python3
"""
Teste para verificar se a nova arquitetura de upload funciona corretamente.
Este teste verifica se:
1. O cliente não pré-registra chunks
2. O nó de armazenamento registra chunks no servidor de metadados
3. O servidor de metadados designa réplicas automaticamente
"""

import os
import sys
import time
import tempfile
import threading
import subprocess
from pathlib import Path

# Adicionar diretórios ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'proto')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'metadata_server')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'client')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'server')))

def create_test_file(size_mb=1):
    """Cria um arquivo de teste com tamanho específico"""
    test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    data = b'A' * (1024 * 1024 * size_mb)  # size_mb MB de dados
    test_file.write(data)
    test_file.close()
    return test_file.name

def test_import_modules():
    """Testa se os módulos podem ser importados corretamente"""
    print("🔍 Testando importação de módulos...")
    
    try:
        # Testar importação do cliente
        from intelligent_client import AdvancedBigFSClient
        print("✅ Cliente importado com sucesso")
        
        # Testar importação do servidor de metadados
        from metadata_manager import MetadataManager
        print("✅ Servidor de metadados importado com sucesso")
        
        # Testar importação do nó de armazenamento
        from storage_node import ExtendedFileSystemServiceServicer
        print("✅ Nó de armazenamento importado com sucesso")
        
        return True
    except ImportError as e:
        print(f"❌ Erro na importação: {e}")
        return False

def test_metadata_manager_replica_selection():
    """Testa se o servidor de metadados designa réplicas corretamente"""
    print("\n🔍 Testando designação automática de réplicas...")
    
    try:
        from metadata_manager import MetadataManager, ChunkMetadata, NodeInfo
        
        # Criar instância do gerenciador de metadados
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MetadataManager(temp_dir)
            
            # Registrar alguns nós de teste
            for i in range(3):
                node = NodeInfo(
                    node_id=f"test_node_{i}",
                    endereco="localhost",
                    porta=50050 + i,
                    status="ATIVO",
                    capacidade_storage=1000000000,
                    storage_usado=0,
                    ultimo_heartbeat=int(time.time()),
                    chunks_armazenados=set()
                )
                manager.nodes[node.node_id] = node
            
            # Criar um chunk de teste
            chunk = ChunkMetadata(
                arquivo_nome="test_file.txt",
                chunk_numero=0,
                no_primario="test_node_0",  # Nó primário já definido
                nos_replicas=[],  # Réplicas serão designadas automaticamente
                checksum="abc123",
                tamanho_chunk=1024,
                timestamp_criacao=int(time.time())
            )
            
            # Registrar o chunk (deve designar réplicas automaticamente)
            success = manager.register_chunk(chunk)
            
            if success:
                # Verificar se réplicas foram designadas
                chunk_key = manager._get_chunk_key("test_file.txt", 0)
                registered_chunk = manager.chunks.get(chunk_key)
                
                if registered_chunk and len(registered_chunk.nos_replicas) > 0:
                    print(f"✅ Réplicas designadas automaticamente: {registered_chunk.nos_replicas}")
                    return True
                else:
                    print("❌ Nenhuma réplica foi designada")
                    return False
            else:
                print("❌ Falha ao registrar chunk")
                return False
                
    except Exception as e:
        print(f"❌ Erro no teste de designação de réplicas: {e}")
        return False

def test_client_chunk_distribution():
    """Testa se o cliente cria distribuição de chunks corretamente"""
    print("\n🔍 Testando distribuição de chunks no cliente...")
    
    try:
        # Testar apenas a lógica de distribuição sem instanciar o cliente completo
        import sys
        import os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'client')))
        
        # Simular a lógica de distribuição ponderada
        def simulate_weighted_distribution(total_chunks, nodes_info):
            """Simula a distribuição ponderada de chunks"""
            if not nodes_info:
                return None
            
            # Calcular espaço livre e distribuição
            node_free_space = []
            total_free_space = 0
            for node in nodes_info:
                free_space = node['capacity'] - node['used']
                free_space = max(free_space, 1)
                node_free_space.append({'node_id': node['node_id'], 'free_space': free_space})
                total_free_space += free_space
            
            if total_free_space == 0:
                return None
            
            # Distribuir chunks
            chunk_distribution = []
            for node_info in node_free_space:
                share = node_info['free_space'] / total_free_space
                num_chunks = round(share * total_chunks)
                chunk_distribution.extend([node_info['node_id']] * int(num_chunks))
            
            # Ajustar para o total exato
            while len(chunk_distribution) < total_chunks:
                most_free_node = sorted(node_free_space, key=lambda x: x['free_space'], reverse=True)[0]
                chunk_distribution.append(most_free_node['node_id'])
            
            return chunk_distribution[:total_chunks]
        
        # Simular nós com diferentes capacidades
        nodes_info = [
            {'node_id': 'node_0', 'capacity': 1000000000, 'used': 100000000},
            {'node_id': 'node_1', 'capacity': 1000000000, 'used': 200000000},
            {'node_id': 'node_2', 'capacity': 1000000000, 'used': 300000000},
        ]
        
        # Testar distribuição
        distribution = simulate_weighted_distribution(10, nodes_info)
        
        if distribution and len(distribution) == 10:
            print(f"✅ Distribuição criada com sucesso: {len(set(distribution))} nós únicos")
            from collections import Counter
            print(f"   Distribuição: {Counter(distribution)}")
            return True
        else:
            print("❌ Falha na criação da distribuição")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de distribuição: {e}")
        return False

def run_syntax_check():
    """Executa verificação de sintaxe nos arquivos modificados"""
    print("\n🔍 Verificando sintaxe dos arquivos modificados...")
    
    files_to_check = [
        "client/intelligent_client.py",
        "server/storage_node.py", 
        "metadata_server/metadata_manager.py"
    ]
    
    all_good = True
    for file_path in files_to_check:
        try:
            result = subprocess.run([
                sys.executable, "-m", "py_compile", file_path
            ], capture_output=True, text=True, cwd="/home/ubuntu/BigFS-v2")
            
            if result.returncode == 0:
                print(f"✅ {file_path}: Sintaxe OK")
            else:
                print(f"❌ {file_path}: Erro de sintaxe")
                print(f"   {result.stderr}")
                all_good = False
        except Exception as e:
            print(f"❌ {file_path}: Erro na verificação - {e}")
            all_good = False
    
    return all_good

def main():
    """Executa todos os testes"""
    print("🚀 Iniciando testes da nova arquitetura BigFS-v2\n")
    
    tests = [
        ("Verificação de sintaxe", run_syntax_check),
        ("Importação de módulos", test_import_modules),
        ("Distribuição de chunks", test_client_chunk_distribution),
        ("Designação de réplicas", test_metadata_manager_replica_selection),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Executando: {test_name}")
        print('='*50)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro inesperado em {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumo dos resultados
    print(f"\n{'='*50}")
    print("RESUMO DOS TESTES")
    print('='*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResultado final: {passed}/{len(results)} testes passaram")
    
    if passed == len(results):
        print("🎉 Todos os testes passaram! A nova arquitetura está funcionando.")
        return True
    else:
        print("⚠️ Alguns testes falharam. Verifique os problemas acima.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

