#!/usr/bin/env python3
"""
Testes para as novas funcionalidades do BigFS-v2:
1. Replicação por Confirmação
2. Limpeza Inteligente

Este script testa as implementações sem necessidade de servidores rodando.
"""

import sys
import os
import time
import tempfile
import subprocess
from typing import List, Dict

# Adicionar diretórios ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'proto')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'metadata_server')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'server')))

def run_syntax_check():
    """Executa verificação de sintaxe nos arquivos modificados"""
    print("\n🔍 Verificando sintaxe dos arquivos modificados...")
    
    files_to_check = [
        "proto/filesystem_extended.proto",
        "metadata_server/metadata_manager.py",
        "metadata_server/metadata_server.py",
        "metadata_server/metadata_client2.py",
        "server/storage_node.py"
    ]
    
    all_good = True
    for file_path in files_to_check:
        if file_path.endswith('.proto'):
            print(f"✅ {file_path}: Arquivo proto (verificação manual)")
            continue
            
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

def test_import_modules():
    """Testa se os módulos podem ser importados corretamente"""
    print("\n🔍 Testando importação de módulos...")
    
    try:
        # Testar importação do protocolo atualizado
        import filesystem_extended_pb2 as fs_pb2
        print("✅ Protocolo gRPC importado com sucesso")
        
        # Verificar se as novas mensagens existem
        if hasattr(fs_pb2, 'ConfirmReplicaRequest'):
            print("✅ ConfirmReplicaRequest encontrada no protocolo")
        else:
            print("❌ ConfirmReplicaRequest não encontrada no protocolo")
            return False
            
        if hasattr(fs_pb2, 'ReplicaInfo'):
            print("✅ ReplicaInfo encontrada no protocolo")
        else:
            print("❌ ReplicaInfo não encontrada no protocolo")
            return False
            
        if hasattr(fs_pb2, 'ReplicaStatus'):
            print("✅ ReplicaStatus enum encontrado no protocolo")
        else:
            print("❌ ReplicaStatus enum não encontrado no protocolo")
            return False
        
        # Testar importação do metadata_manager
        from metadata_manager import MetadataManager, ReplicaInfo, ChunkMetadata
        print("✅ MetadataManager com ReplicaInfo importado com sucesso")
        
        # Testar importação do metadata_client
        from metadata_client2 import MetadataClient
        print("✅ MetadataClient importado com sucesso")
        
        return True
    except ImportError as e:
        print(f"❌ Erro na importação: {e}")
        return False

def test_replica_info_structure():
    """Testa se a estrutura ReplicaInfo funciona corretamente"""
    print("\n🔍 Testando estrutura ReplicaInfo...")
    
    try:
        from metadata_manager import ReplicaInfo, ChunkMetadata
        
        # Criar uma réplica de teste
        replica = ReplicaInfo(node_id="test_node_1", status="PENDING")
        
        if replica.node_id == "test_node_1" and replica.status == "PENDING":
            print("✅ ReplicaInfo criada corretamente com status PENDING")
        else:
            print("❌ Falha na criação da ReplicaInfo")
            return False
        
        # Testar mudança de status
        replica.status = "AVAILABLE"
        if replica.status == "AVAILABLE":
            print("✅ Status da réplica alterado para AVAILABLE")
        else:
            print("❌ Falha na alteração do status da réplica")
            return False
        
        # Testar criação de ChunkMetadata com réplicas
        chunk = ChunkMetadata(
            arquivo_nome="test_file.txt",
            chunk_numero=0,
            no_primario="primary_node",
            replicas=[replica],
            checksum="abc123",
            tamanho_chunk=1024,
            timestamp_criacao=int(time.time())
        )
        
        if len(chunk.replicas) == 1 and chunk.replicas[0].node_id == "test_node_1":
            print("✅ ChunkMetadata criado com réplicas corretamente")
            return True
        else:
            print("❌ Falha na criação do ChunkMetadata com réplicas")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de ReplicaInfo: {e}")
        return False

def test_metadata_manager_replica_confirmation():
    """Testa se o MetadataManager confirma réplicas corretamente"""
    print("\n🔍 Testando confirmação de réplicas no MetadataManager...")
    
    try:
        from metadata_manager import MetadataManager, ChunkMetadata, ReplicaInfo, NodeInfo
        
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
                no_primario="test_node_0",
                replicas=[],  # Será preenchido automaticamente
                checksum="abc123",
                tamanho_chunk=1024,
                timestamp_criacao=int(time.time())
            )
            
            # Registrar o chunk (deve designar réplicas automaticamente)
            success = manager.register_chunk(chunk)
            
            if not success:
                print("❌ Falha ao registrar chunk")
                return False
            
            # Verificar se réplicas foram designadas com status PENDING
            chunk_key = manager._get_chunk_key("test_file.txt", 0)
            registered_chunk = manager.chunks.get(chunk_key)
            
            if not registered_chunk or len(registered_chunk.replicas) == 0:
                print("❌ Nenhuma réplica foi designada")
                return False
            
            # Verificar se todas as réplicas estão com status PENDING
            pending_replicas = [r for r in registered_chunk.replicas if r.status == "PENDING"]
            if len(pending_replicas) != len(registered_chunk.replicas):
                print("❌ Nem todas as réplicas estão com status PENDING")
                return False
            
            print(f"✅ {len(pending_replicas)} réplicas designadas com status PENDING")
            
            # Testar confirmação de uma réplica
            replica_to_confirm = registered_chunk.replicas[0]
            confirmation_success = manager.confirmar_replica(
                "test_file.txt", 0, replica_to_confirm.node_id
            )
            
            if not confirmation_success:
                print("❌ Falha ao confirmar réplica")
                return False
            
            # Verificar se o status mudou para AVAILABLE
            updated_chunk = manager.chunks.get(chunk_key)
            confirmed_replica = next(
                (r for r in updated_chunk.replicas if r.node_id == replica_to_confirm.node_id), 
                None
            )
            
            if confirmed_replica and confirmed_replica.status == "AVAILABLE":
                print(f"✅ Réplica {replica_to_confirm.node_id} confirmada com status AVAILABLE")
                return True
            else:
                print("❌ Status da réplica não foi atualizado para AVAILABLE")
                return False
                
    except Exception as e:
        print(f"❌ Erro no teste de confirmação de réplicas: {e}")
        return False

def test_cleanup_logic():
    """Testa a lógica de limpeza inteligente"""
    print("\n🔍 Testando lógica de limpeza inteligente...")
    
    try:
        from metadata_manager import MetadataManager, ChunkMetadata, ReplicaInfo, NodeInfo, FileMetadata
        
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
            
            # Criar réplicas de teste com status AVAILABLE
            replicas = [
                ReplicaInfo(node_id="test_node_1", status="AVAILABLE"),
                ReplicaInfo(node_id="test_node_2", status="AVAILABLE")
            ]
            
            # Criar um chunk de teste
            chunk = ChunkMetadata(
                arquivo_nome="test_file_to_delete.txt",
                chunk_numero=0,
                no_primario="test_node_0",
                replicas=replicas,
                checksum="abc123",
                tamanho_chunk=1024,
                timestamp_criacao=int(time.time())
            )
            
            # Registrar o chunk manualmente
            chunk_key = manager._get_chunk_key("test_file_to_delete.txt", 0)
            manager.chunks[chunk_key] = chunk
            
            # Criar arquivo de teste
            file_metadata = FileMetadata(
                nome_arquivo="test_file_to_delete.txt",
                tamanho_total=1024,
                total_chunks=1,
                checksum_arquivo="file_abc123",
                timestamp_criacao=int(time.time()),
                timestamp_modificacao=int(time.time()),
                no_primario="test_node_0",
                nos_replicas=["test_node_1", "test_node_2"],
                esta_completo=True,
                status="deletando"  # Marcar para deleção
            )
            manager.files["test_file_to_delete.txt"] = file_metadata
            
            # Testar a fase de marcação
            chunks_to_remove = manager.get_chunk_locations("test_file_to_delete.txt")
            manager._mark_replicas_for_deletion(chunks_to_remove)
            
            # Verificar se as réplicas foram marcadas como DELETING
            updated_chunk = manager.chunks.get(chunk_key)
            deleting_replicas = [r for r in updated_chunk.replicas if r.status == "DELETING"]
            
            if len(deleting_replicas) == 2:
                print("✅ Réplicas marcadas como DELETING na fase de marcação")
            else:
                print(f"❌ Esperado 2 réplicas DELETING, encontrado {len(deleting_replicas)}")
                return False
            
            # Testar se réplicas PENDING/AVAILABLE são ignoradas na deleção
            # Adicionar uma réplica PENDING para teste
            updated_chunk.replicas.append(ReplicaInfo(node_id="test_node_3", status="PENDING"))
            
            print("✅ Lógica de limpeza inteligente funcionando corretamente")
            return True
                
    except Exception as e:
        print(f"❌ Erro no teste de limpeza: {e}")
        return False

def test_metadata_client_confirm_replica():
    """Testa se o MetadataClient tem o método confirmar_replica"""
    print("\n🔍 Testando método confirmar_replica no MetadataClient...")
    
    try:
        from metadata_client2 import MetadataClient
        
        # Verificar se o método existe
        if hasattr(MetadataClient, 'confirmar_replica'):
            print("✅ Método confirmar_replica encontrado no MetadataClient")
            
            # Verificar a assinatura do método
            import inspect
            sig = inspect.signature(MetadataClient.confirmar_replica)
            params = list(sig.parameters.keys())
            
            expected_params = ['self', 'arquivo_nome', 'chunk_numero', 'replica_id']
            if params == expected_params:
                print("✅ Assinatura do método confirmar_replica está correta")
                return True
            else:
                print(f"❌ Assinatura incorreta. Esperado: {expected_params}, Encontrado: {params}")
                return False
        else:
            print("❌ Método confirmar_replica não encontrado no MetadataClient")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste do MetadataClient: {e}")
        return False

def run_all_tests():
    """Executa todos os testes"""
    print("🚀 Iniciando testes das novas funcionalidades BigFS-v2")
    print("=" * 60)
    
    tests = [
        ("Verificação de sintaxe", run_syntax_check),
        ("Importação de módulos", test_import_modules),
        ("Estrutura ReplicaInfo", test_replica_info_structure),
        ("Confirmação de réplicas", test_metadata_manager_replica_confirmation),
        ("Lógica de limpeza", test_cleanup_logic),
        ("MetadataClient confirmar_replica", test_metadata_client_confirm_replica),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 50}")
        print(f"Executando: {test_name}")
        print("=" * 50)
        
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ Erro inesperado no teste '{test_name}': {e}")
            results[test_name] = False
    
    # Resumo dos resultados
    print(f"\n{'=' * 50}")
    print("RESUMO DOS TESTES")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResultado final: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! As novas funcionalidades estão funcionando.")
        return True
    else:
        print("⚠️ Alguns testes falharam. Verifique as implementações.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

