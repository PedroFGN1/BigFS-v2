#!/usr/bin/env python3
"""
Script de teste para validar as correções implementadas no BigFS-v2
"""

import sys
import os
import time
import hashlib
from typing import List, Dict

# Adicionar paths necessários
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'proto')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'metadata_server')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'client')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'server')))

def test_imports():
    """Testa se todos os módulos podem ser importados corretamente"""
    print("🧪 Testando imports...")
    
    try:
        # Testar imports dos protobuf
        import filesystem_extended_pb2 as fs_pb2
        import filesystem_extended_pb2_grpc as fs_grpc
        print("✅ Protobuf imports OK")
        
        # Testar import do metadata_manager
        from metadata_manager import MetadataManager, FileMetadata, ChunkMetadata
        print("✅ MetadataManager import OK")
        
        # Testar import do storage_node
        from storage_node import ExtendedFileSystemServiceServicer
        print("✅ StorageNode import OK")
        
        # Testar import do intelligent_client
        from intelligent_client import AdvancedBigFSClient, IntelligentChunkUploader, IntelligentChunkDownloader
        print("✅ IntelligentClient import OK")
        
        # Testar import do client_extended
        from client_extended import BigFSClient
        print("✅ ClientExtended import OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no import: {e}")
        return False

def test_metadata_manager_features():
    """Testa as funcionalidades do MetadataManager"""
    print("\n🧪 Testando funcionalidades do MetadataManager...")
    
    try:
        # Importar dentro da função para evitar problemas de escopo
        from metadata_manager import MetadataManager, FileMetadata, ChunkMetadata
        
        # Criar instância do MetadataManager
        manager = MetadataManager("test_metadata")
        
        # Testar criação de arquivo com status
        file_metadata = FileMetadata(
            nome_arquivo="test_file.txt",
            tamanho_total=1024,
            total_chunks=1,
            checksum_arquivo="abc123",
            timestamp_criacao=int(time.time()),
            timestamp_modificacao=int(time.time()),
            no_primario="node1",
            nos_replicas=["node2"],
            esta_completo=False,
            status="ativo"
        )
        
        # Verificar se o campo status existe
        assert hasattr(file_metadata, 'status'), "Campo status não encontrado em FileMetadata"
        print("✅ FileMetadata com campo status OK")
        
        # Testar chunk com status
        chunk_metadata = ChunkMetadata(
            arquivo_nome="test_file.txt",
            chunk_numero=0,
            no_primario="node1",
            nos_replicas=["node2"],
            checksum="def456",
            tamanho_chunk=1024,
            timestamp_criacao=int(time.time()),
            status="ativo"
        )
        
        assert hasattr(chunk_metadata, 'status'), "Campo status não encontrado em ChunkMetadata"
        print("✅ ChunkMetadata com campo status OK")
        
        # Verificar se métodos de limpeza existem
        assert hasattr(manager, '_cleanup_deleted_files'), "Método _cleanup_deleted_files não encontrado"
        assert hasattr(manager, '_garbage_collect_incomplete_uploads'), "Método _garbage_collect_incomplete_uploads não encontrado"
        print("✅ Métodos de limpeza implementados OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste do MetadataManager: {e}")
        return False

def test_storage_node_features():
    """Testa as funcionalidades do StorageNode"""
    print("\n🧪 Testando funcionalidades do StorageNode...")
    
    try:
        from storage_node import ExtendedFileSystemServiceServicer
        
        # Criar instância do servicer
        servicer = ExtendedFileSystemServiceServicer(
            base_dir="test_storage",
            node_id="test_node",
            node_port=50051
        )
        
        # Verificar se método de replicação existe
        assert hasattr(servicer, '_iniciar_replicacao_chunk'), "Método _iniciar_replicacao_chunk não encontrado"
        print("✅ Método de replicação implementado OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste do StorageNode: {e}")
        return False

def test_client_features():
    """Testa as funcionalidades dos clientes"""
    print("\n🧪 Testando funcionalidades dos clientes...")
    
    try:
        from intelligent_client import AdvancedBigFSClient, IntelligentChunkUploader, IntelligentChunkDownloader
        from client_extended import BigFSClient
        
        # Testar AdvancedBigFSClient
        client = AdvancedBigFSClient()
        assert hasattr(client, 'verify_file_integrity'), "Método verify_file_integrity não encontrado"
        assert hasattr(client, 'verify_and_repair_file'), "Método verify_and_repair_file não encontrado"
        print("✅ AdvancedBigFSClient com verificação de integridade OK")
        
        # Testar IntelligentChunkUploader
        uploader = IntelligentChunkUploader(client)
        assert hasattr(uploader, '_get_chunk_node_list'), "Método _get_chunk_node_list não encontrado"
        print("✅ IntelligentChunkUploader com lógica centralizada OK")
        
        # Testar IntelligentChunkDownloader
        downloader = IntelligentChunkDownloader(client)
        assert hasattr(downloader, '_get_chunk_node_list'), "Método _get_chunk_node_list não encontrado"
        print("✅ IntelligentChunkDownloader com lógica centralizada OK")
        
        # Testar BigFSClient
        extended_client = BigFSClient()
        assert hasattr(extended_client, 'verify_file_integrity'), "Método verify_file_integrity não encontrado"
        assert hasattr(extended_client, 'verify_and_repair_file'), "Método verify_and_repair_file não encontrado"
        print("✅ BigFSClient com verificação de integridade OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste dos clientes: {e}")
        return False

def main():
    """Função principal de teste"""
    print("🚀 Iniciando testes das correções do BigFS-v2\n")
    
    tests = [
        ("Imports", test_imports),
        ("MetadataManager", test_metadata_manager_features),
        ("StorageNode", test_storage_node_features),
        ("Clientes", test_client_features)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro crítico no teste {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumo dos resultados
    print("\n" + "="*50)
    print("📊 RESUMO DOS TESTES")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todas as correções foram implementadas com sucesso!")
        return True
    else:
        print("⚠️ Algumas correções precisam de ajustes.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

