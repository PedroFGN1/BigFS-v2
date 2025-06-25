import grpc
import sys
import os
import time
import threading
from typing import List, Optional, Dict, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'metadata_server')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'client')))

from client_extended import BigFSClient
import filesystem_extended_pb2 as fs_pb2
import filesystem_extended_pb2_grpc as fs_grpc
from metadata_client import MetadataClient

class ChunkUploader:
    """Classe para upload paralelo de chunks"""
    
    def __init__(self, client: 'BigFSClient'):
        self.client = client
        self.results = {}
        self.lock = threading.Lock()
    
    def upload_chunk(self, arquivo_nome: str, chunk_numero: int, chunk_data: bytes, 
                    checksum: str, node_info: Dict):
        """Upload de um chunk específico"""
        try:
            stub = self.client._get_storage_connection(node_info)
            if not stub:
                with self.lock:
                    self.results[chunk_numero] = False
                return
            
            request = fs_pb2.ChunkUploadRequest(
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero,
                dados=chunk_data,
                checksum=checksum
            )
            
            response = stub.UploadChunk(request)
            
            with self.lock:
                self.results[chunk_numero] = response.sucesso
                if response.sucesso:
                    print(f"✅ Chunk {chunk_numero} enviado para {node_info['node_id']}")
                else:
                    print(f"❌ Erro no chunk {chunk_numero}: {response.mensagem}")
                    
        except Exception as e:
            print(f"❌ Erro no upload do chunk {chunk_numero}: {e}")
            with self.lock:
                self.results[chunk_numero] = False

class ChunkDownloader:
    """Classe para download paralelo de chunks"""
    
    def __init__(self, client: 'BigFSClient'):
        self.client = client
        self.chunks_data = {}
        self.lock = threading.Lock()
    
    def download_chunk(self, arquivo_nome: str, chunk_numero: int, chunk_info: Dict):
        """Download de um chunk específico"""
        chunk_data = self.client._download_chunk_with_fallback(
            arquivo_nome, chunk_numero, chunk_info
        )
        
        with self.lock:
            self.chunks_data[chunk_numero] = chunk_data

class AdvancedBigFSClient:
    """Cliente BigFS-v2 avançado com upload/download paralelo e funcionalidades extras"""
    
    def __init__(self, metadata_server: str = "localhost:50052", max_workers: int = 4):
        self.metadata_server = metadata_server
        self.metadata_client = None
        self.storage_connections = {}
        self.max_workers = max_workers
        
        # Conectar ao servidor de metadados
        self._connect_to_metadata_server()
    
    def _connect_to_metadata_server(self):
        """Conecta ao servidor de metadados"""
        try:
            self.metadata_client = MetadataClient(self.metadata_server)
            print(f"✅ Conectado ao servidor de metadados: {self.metadata_server}")
        except Exception as e:
            print(f"❌ Erro ao conectar com servidor de metadados: {e}")
            self.metadata_client = None
    
    def _get_storage_connection(self, node_info: Dict) -> Optional[fs_grpc.FileSystemServiceStub]:
        """Obtém conexão com nó de armazenamento (com cache)"""
        node_address = f"{node_info['endereco']}:{node_info['porta']}"
        
        if node_address not in self.storage_connections:
            try:
                channel = grpc.insecure_channel(
                    node_address,
                    options=[
                        ("grpc.max_send_message_length", 1024 * 1024 * 1024),
                        ("grpc.max_receive_message_length", 1024 * 1024 * 1024)
                    ]
                )
                stub = fs_grpc.FileSystemServiceStub(channel)
                self.storage_connections[node_address] = (channel, stub)
            except Exception as e:
                print(f"❌ Erro ao conectar com nó {node_address}: {e}")
                return None
        
        return self.storage_connections[node_address][1]
    
    def _close_connections(self):
        """Fecha todas as conexões"""
        for channel, _ in self.storage_connections.values():
            channel.close()
        self.storage_connections.clear()
        
        if self.metadata_client:
            self.metadata_client.close()
    
    def _download_chunk_with_fallback(self, arquivo_nome: str, chunk_numero: int, 
                                    chunk_info: Dict) -> Optional[bytes]:
        """Download de chunk com fallback para réplicas em caso de falha"""
        # Tentar nó primário primeiro
        primary_node = {
            'endereco': 'localhost',
            'porta': 50051
        }
        
        stub = self._get_storage_connection(primary_node)
        if stub:
            try:
                request = fs_pb2.ChunkRequest(
                    arquivo_nome=arquivo_nome,
                    chunk_numero=chunk_numero
                )
                response = stub.DownloadChunk(request)
                
                if response.sucesso:
                    import hashlib
                    checksum_calculado = hashlib.md5(response.dados).hexdigest()
                    if checksum_calculado == chunk_info['checksum']:
                        return response.dados
                    else:
                        print(f"⚠️ Checksum inválido para chunk {chunk_numero}")
                else:
                    print(f"⚠️ Erro no download do chunk {chunk_numero}: {response.mensagem}")
            except Exception as e:
                print(f"⚠️ Falha na comunicação com nó primário: {e}")
        
        return None
    
    def upload_large_file_parallel(self, caminho_local: str, caminho_remoto: str, 
                                 chunk_size: int = 1024*1024) -> bool:
        """Upload paralelo de arquivo grande dividido em chunks"""
        if not os.path.exists(caminho_local):
            print("❌ Arquivo local não encontrado")
            return False
        
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        arquivo_nome = os.path.basename(caminho_remoto)
        
        # Ler e dividir arquivo
        with open(caminho_local, "rb") as f:
            dados = f.read()
        
        tamanho_arquivo = len(dados)
        
        if tamanho_arquivo <= chunk_size:
            print("📤 Arquivo pequeno, usando upload normal...")
            return self.upload_simple(caminho_local, caminho_remoto)
        
        # Dividir em chunks
        chunks = []
        for i in range(0, tamanho_arquivo, chunk_size):
            chunk_data = dados[i:i + chunk_size]
            chunks.append(chunk_data)
        
        total_chunks = len(chunks)
        import hashlib
        checksum_arquivo = hashlib.md5(dados).hexdigest()
        
        print(f"📤 Upload paralelo: {arquivo_nome} ({tamanho_arquivo:,} bytes, {total_chunks} chunks)")
        
        # Registrar arquivo no servidor de metadados
        sucesso_registro = self.metadata_client.register_file(
            arquivo_nome,
            tamanho_arquivo,
            total_chunks,
            checksum_arquivo,
            "client_upload",  # Nó temporário
            []
        )
        
        if not sucesso_registro:
            print("❌ Erro ao registrar arquivo no servidor de metadados")
            return False
        
        # Upload paralelo dos chunks
        uploader = ChunkUploader(self)
        threads = []
        
        for i, chunk_data in enumerate(chunks):
            # Obter nó para este chunk
            node = self.metadata_client.get_node_for_operation("upload", f"{arquivo_nome}:{i}")
            if not node:
                print(f"❌ Nenhum nó disponível para chunk {i}")
                return False
            
            checksum_chunk = hashlib.md5(chunk_data).hexdigest()
            
            # Registrar chunk no servidor de metadados
            self.metadata_client.register_chunk(
                arquivo_nome,
                i,
                node['node_id'],
                [],
                checksum_chunk,
                len(chunk_data)
            )
            
            # Criar thread para upload
            thread = threading.Thread(
                target=uploader.upload_chunk,
                args=(arquivo_nome, i, chunk_data, checksum_chunk, node)
            )
            threads.append(thread)
            
            # Limitar número de threads simultâneas
            if len(threads) >= self.max_workers:
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                threads = []
        
        # Executar threads restantes
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verificar resultados
        chunks_sucesso = sum(1 for success in uploader.results.values() if success)
        
        if chunks_sucesso == total_chunks:
            print(f"✅ Upload paralelo concluído: {chunks_sucesso}/{total_chunks} chunks")
            return True
        else:
            print(f"❌ Upload parcialmente falhou: {chunks_sucesso}/{total_chunks} chunks")
            return False
    
    def download_large_file_parallel(self, caminho_remoto: str, caminho_local: str) -> bool:
        """Download paralelo de arquivo grande com chunks"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        arquivo_nome = os.path.basename(caminho_remoto)
        
        # Obter metadados do arquivo
        file_metadata = self.metadata_client.get_file_metadata(arquivo_nome)
        if not file_metadata:
            print("❌ Arquivo não encontrado nos metadados")
            return False
        
        # Obter localização dos chunks
        chunks_info = self.metadata_client.get_chunk_locations(arquivo_nome)
        if not chunks_info:
            print("❌ Não foi possível obter localização dos chunks")
            return False
        
        total_chunks = len(chunks_info)
        print(f"📥 Download paralelo: {arquivo_nome} ({file_metadata['tamanho_total']:,} bytes, {total_chunks} chunks)")
        
        # Download paralelo dos chunks
        downloader = ChunkDownloader(self)
        threads = []
        
        for chunk_info in chunks_info:
            thread = threading.Thread(
                target=downloader.download_chunk,
                args=(arquivo_nome, chunk_info['chunk_numero'], chunk_info)
            )
            threads.append(thread)
            
            # Limitar número de threads simultâneas
            if len(threads) >= self.max_workers:
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                threads = []
        
        # Executar threads restantes
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verificar se todos os chunks foram baixados
        chunks_baixados = sum(1 for data in downloader.chunks_data.values() if data is not None)
        
        if chunks_baixados != total_chunks:
            print(f"❌ Download falhou: {chunks_baixados}/{total_chunks} chunks")
            return False
        
        # Recombinar chunks
        print("🔧 Recombinando chunks...")
        chunks_ordenados = []
        for i in range(total_chunks):
            if i not in downloader.chunks_data or downloader.chunks_data[i] is None:
                print(f"❌ Chunk {i} não foi baixado")
                return False
            chunks_ordenados.append(downloader.chunks_data[i])
        
        dados_completos = b''.join(chunks_ordenados)
        
        # Verificar checksum do arquivo completo
        import hashlib
        checksum_calculado = hashlib.md5(dados_completos).hexdigest()
        if checksum_calculado != file_metadata['checksum_arquivo']:
            print("❌ Checksum do arquivo não confere")
            return False
        
        # Salvar arquivo
        try:
            os.makedirs(os.path.dirname(caminho_local), exist_ok=True)
            with open(caminho_local, "wb") as f:
                f.write(dados_completos)
            print(f"✅ Download paralelo concluído: {caminho_local}")
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar arquivo: {e}")
            return False
    
    def upload_simple(self, caminho_local: str, caminho_remoto: str) -> bool:
        """Upload simples para arquivos pequenos"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        arquivo_nome = os.path.basename(caminho_remoto)
        node = self.metadata_client.get_node_for_operation("upload", arquivo_nome)
        if not node:
            print("❌ Nenhum nó disponível para upload")
            return False
        
        stub = self._get_storage_connection(node)
        if not stub:
            return False
        
        try:
            with open(caminho_local, "rb") as f:
                dados = f.read()
            
            request = fs_pb2.FileUploadRequest(
                path=caminho_remoto,
                dados=dados
            )
            
            response = stub.Upload(request)
            
            if response.sucesso:
                print("✅", response.mensagem)
                return True
            else:
                print("❌ Erro no upload:", response.mensagem)
                return False
                
        except Exception as e:
            print(f"❌ Erro na comunicação: {e}")
            return False
    
    def verificar_integridade_arquivo(self, arquivo_nome: str) -> bool:
        """Verifica integridade de todos os chunks de um arquivo"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        chunks_info = self.metadata_client.get_chunk_locations(arquivo_nome)
        if not chunks_info:
            print("❌ Arquivo não encontrado ou sem chunks")
            return False
        
        print(f"🔍 Verificando integridade de {arquivo_nome} ({len(chunks_info)} chunks)")
        
        chunks_ok = 0
        for chunk_info in chunks_info:
            # Obter nó primário do chunk
            primary_node = {
                'endereco': 'localhost',
                'porta': 50051
            }
            
            stub = self._get_storage_connection(primary_node)
            if not stub:
                continue
            
            try:
                request = fs_pb2.IntegrityRequest(
                    arquivo_nome=arquivo_nome,
                    chunk_numero=chunk_info['chunk_numero']
                )
                
                response = stub.VerificarIntegridade(request)
                
                if response.sucesso and response.integridade_ok:
                    chunks_ok += 1
                    print(f"✅ Chunk {chunk_info['chunk_numero']}: OK")
                else:
                    print(f"❌ Chunk {chunk_info['chunk_numero']}: {response.mensagem}")
                    
            except Exception as e:
                print(f"❌ Erro ao verificar chunk {chunk_info['chunk_numero']}: {e}")
        
        total_chunks = len(chunks_info)
        if chunks_ok == total_chunks:
            print(f"✅ Integridade OK: {chunks_ok}/{total_chunks} chunks")
            return True
        else:
            print(f"❌ Problemas de integridade: {chunks_ok}/{total_chunks} chunks OK")
            return False

def main_advanced():
    print("🚀 BigFS-v2 Advanced Client")
    
    metadata_server = input("Servidor de metadados (Enter para localhost:50052): ").strip()
    if not metadata_server:
        metadata_server = "localhost:50052"
    
    max_workers = input("Máximo de workers paralelos (Enter para 4): ").strip()
    if not max_workers:
        max_workers = 4
    else:
        max_workers = int(max_workers)
    
    client = AdvancedBigFSClient(metadata_server, max_workers)
    
    try:
        while True:
            print("\n" + "="*60)
            print("🗂️  BigFS-v2 Advanced Client")
            print("="*60)
            print("1. 📤 Upload paralelo de arquivo grande")
            print("2. 📥 Download paralelo de arquivo grande")
            print("3. 📤 Upload simples")
            print("4. 🔍 Verificar integridade de arquivo")
            print("5. 🚪 Sair")
            print("="*60)
            
            escolha = input("Escolha uma opção: ").strip()
            
            if escolha == "1":
                caminho_local = input("Arquivo local: ").strip()
                caminho_remoto = input("Caminho remoto: ").strip()
                chunk_size = input("Tamanho do chunk em MB (Enter para 1): ").strip()
                
                if not chunk_size:
                    chunk_size = 1
                else:
                    chunk_size = int(chunk_size)
                
                chunk_size_bytes = chunk_size * 1024 * 1024
                
                if caminho_local and caminho_remoto:
                    start_time = time.time()
                    sucesso = client.upload_large_file_parallel(caminho_local, caminho_remoto, chunk_size_bytes)
                    end_time = time.time()
                    
                    if sucesso:
                        print(f"⏱️ Tempo total: {end_time - start_time:.2f} segundos")
                
            elif escolha == "2":
                caminho_remoto = input("Arquivo remoto: ").strip()
                caminho_local = input("Caminho local para salvar: ").strip()
                
                if caminho_remoto and caminho_local:
                    start_time = time.time()
                    sucesso = client.download_large_file_parallel(caminho_remoto, caminho_local)
                    end_time = time.time()
                    
                    if sucesso:
                        print(f"⏱️ Tempo total: {end_time - start_time:.2f} segundos")
                
            elif escolha == "3":
                caminho_local = input("Arquivo local: ").strip()
                caminho_remoto = input("Caminho remoto: ").strip()
                
                if caminho_local and caminho_remoto:
                    client.upload_simple(caminho_local, caminho_remoto)
                
            elif escolha == "4":
                arquivo_nome = input("Nome do arquivo: ").strip()
                if arquivo_nome:
                    client.verificar_integridade_arquivo(arquivo_nome)
                
            elif escolha == "5":
                print("👋 Encerrando cliente avançado...")
                break
                
            else:
                print("❌ Opção inválida")
                
            input("\nPressione Enter para continuar...")
            
    except KeyboardInterrupt:
        print("\n👋 Cliente interrompido pelo usuário")
    finally:
        client._close_connections()

if __name__ == "__main__":
    main_advanced()

