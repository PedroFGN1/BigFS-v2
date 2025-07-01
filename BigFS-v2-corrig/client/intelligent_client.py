import grpc
import sys
import os
import time
import threading
import hashlib
from typing import List, Optional, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'metadata_server')))

import filesystem_extended_pb2 as fs_pb2
import filesystem_extended_pb2_grpc as fs_grpc
from metadata_client2 import MetadataClient

class RetryConfig:
    """Configuração para retry inteligente"""
    def __init__(self):
        self.max_retries = 3
        self.base_delay = 1.0  # segundos
        self.max_delay = 10.0  # segundos
        self.backoff_multiplier = 2.0
        self.timeout_per_attempt = 30.0  # segundos

class ChunkOperationResult:
    """Resultado de uma operação de chunk"""
    def __init__(self, chunk_numero: int, sucesso: bool = False, 
                 dados: bytes = None, erro: str = None, node_usado: str = None):
        self.chunk_numero = chunk_numero
        self.sucesso = sucesso
        self.dados = dados
        self.erro = erro
        self.node_usado = node_usado
        self.tentativas = 0

class IntelligentChunkUploader:
    """Classe para upload paralelo de chunks com retry inteligente"""
    
    def __init__(self, client: 'AdvancedBigFSClient'):
        self.client = client
        self.results = {}
        self.lock = threading.Lock()
        self.retry_config = RetryConfig()
    
    def _get_chunk_node_list(self, arquivo_nome: str, chunk_numero: int) -> List[Dict]:
        """
        Método auxiliar para obter lista ordenada de nós para um chunk.
        Retorna [nó_primário, réplica_1, réplica_2, ...]
        """
        try:
            # Fazer uma única chamada ao metadata_client.get_chunk_locations()
            chunk_locations = self.client.metadata_client.get_chunk_locations(arquivo_nome)
            
            if not chunk_locations:
                return []
            
            # Encontrar informações do chunk específico
            chunk_info = None
            for chunk in chunk_locations:
                if chunk.chunk_numero == chunk_numero:
                    chunk_info = chunk
                    break
            
            if not chunk_info:
                return []
            
            # Montar lista ordenada: [nó_primário, réplica_1, réplica_2, ...]
            node_list = []
            
            # Adicionar nó primário primeiro
            if hasattr(chunk_info, 'no_primario') and chunk_info.no_primario:
                node_list.append({
                    'node_id': chunk_info.no_primario.node_id,
                    'endereco': chunk_info.no_primario.endereco,
                    'porta': chunk_info.no_primario.porta,
                    'tipo': 'primario'
                })
            
            # Adicionar réplicas
            if hasattr(chunk_info, 'nos_replica') and chunk_info.nos_replica:
                for replica in chunk_info.nos_replica:
                    node_list.append({
                        'node_id': replica.node_id,
                        'endereco': replica.endereco,
                        'porta': replica.porta,
                        'tipo': 'replica'
                    })
            
            return node_list
            
        except Exception as e:
            print(f"Erro ao obter lista de nós para chunk {arquivo_nome}:{chunk_numero}: {e}")
            return []
    
    def upload_chunk_with_retry(self, arquivo_nome: str, chunk_numero: int, 
                               chunk_data: bytes, checksum: str) -> ChunkOperationResult:
        """Upload de um chunk com retry inteligente"""
        result = ChunkOperationResult(chunk_numero)
        
        # Obter lista estática de nós antes de iniciar o loop de retry
        node_list = self._get_chunk_node_list(arquivo_nome, chunk_numero)
        if not node_list:
            result.erro = "Nenhum nó disponível para o chunk"
            return result
        
        # Tentar cada nó da lista em ordem
        for tentativa, node_info in enumerate(node_list):
            result.tentativas = tentativa + 1
            
            try:
                # Tentar upload
                sucesso, erro = self._attempt_chunk_upload(
                    arquivo_nome, chunk_numero, chunk_data, checksum, node_info
                )
                
                if sucesso:
                    result.sucesso = True
                    result.node_usado = node_info['node_id']
                    print(f"✅ Chunk {chunk_numero} enviado para {node_info['node_id']} ({node_info['tipo']}) (tentativa {tentativa + 1})")
                    break
                else:
                    result.erro = erro
                    print(f"⚠️ Tentativa {tentativa + 1} falhou para chunk {chunk_numero} no nó {node_info['node_id']}: {erro}")
                    
                    # Reportar falha do nó ao servidor de metadados
                    self._report_node_failure(node_info['node_id'], erro)
                    
                    # Aguardar antes da próxima tentativa (exceto na última)
                    if tentativa < len(node_list) - 1:
                        delay = min(
                            self.retry_config.base_delay * (self.retry_config.backoff_multiplier ** tentativa),
                            self.retry_config.max_delay
                        )
                        time.sleep(delay)
                        
            except Exception as e:
                result.erro = f"Erro inesperado: {str(e)}"
                print(f"❌ Erro inesperado no chunk {chunk_numero}, tentativa {tentativa + 1}: {e}")
        
        if not result.sucesso:
            print(f"❌ Falha definitiva no upload do chunk {chunk_numero} após {result.tentativas} tentativas")
        
        return result
    
    def _attempt_chunk_upload(self, arquivo_nome: str, chunk_numero: int, 
                             chunk_data: bytes, checksum: str, node_info: Dict) -> Tuple[bool, str]:
        """Tenta upload de um chunk para um nó específico"""
        try:
            stub = self.client._get_storage_connection(node_info)
            if not stub:
                return False, "Não foi possível conectar ao nó"
            
            request = fs_pb2.ChunkUploadRequest(
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero,
                dados=chunk_data,
                checksum=checksum
            )
            
            # Usar timeout por tentativa
            response = stub.UploadChunk(request, timeout=self.retry_config.timeout_per_attempt)
            
            if response.sucesso:
                return True, ""
            else:
                return False, response.mensagem
                
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                return False, f"Nó {node_info['node_id']} indisponível"
            elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                return False, f"Timeout no nó {node_info['node_id']}"
            else:
                return False, f"Erro gRPC: {e.details()}"
        except Exception as e:
            return False, f"Erro de conexão: {str(e)}"
    
    def _report_node_failure(self, node_id: str, reason: str):
        """Reporta falha de nó ao servidor de metadados"""
        try:
            self.client.metadata_client.report_node_failure(node_id, reason)
        except Exception as e:
            print(f"Erro ao reportar falha do nó {node_id}: {e}")

class IntelligentChunkDownloader:
    """Classe para download paralelo de chunks com retry inteligente"""
    
    def __init__(self, client: 'AdvancedBigFSClient'):
        self.client = client
        self.chunks_data = {}
        self.lock = threading.Lock()
        self.retry_config = RetryConfig()
    
    def _get_chunk_node_list(self, arquivo_nome: str, chunk_numero: int) -> List[Dict]:
        """
        Método auxiliar para obter lista ordenada de nós para um chunk.
        Retorna [nó_primário, réplica_1, réplica_2, ...]
        """
        try:
            # Fazer uma única chamada ao metadata_client.get_chunk_locations()
            chunk_locations = self.client.metadata_client.get_chunk_locations(arquivo_nome)
            
            if not chunk_locations:
                return []
            
            # Encontrar informações do chunk específico
            chunk_info = None
            for chunk in chunk_locations:
                if chunk.chunk_numero == chunk_numero:
                    chunk_info = chunk
                    break
            
            if not chunk_info:
                return []
            
            # Montar lista ordenada: [nó_primário, réplica_1, réplica_2, ...]
            node_list = []
            
            # Adicionar nó primário primeiro
            if hasattr(chunk_info, 'no_primario') and chunk_info.no_primario:
                node_list.append({
                    'node_id': chunk_info.no_primario.node_id,
                    'endereco': chunk_info.no_primario.endereco,
                    'porta': chunk_info.no_primario.porta,
                    'tipo': 'primario',
                    'checksum': getattr(chunk_info, 'checksum', '')
                })
            
            # Adicionar réplicas
            if hasattr(chunk_info, 'nos_replica') and chunk_info.nos_replica:
                for replica in chunk_info.nos_replica:
                    node_list.append({
                        'node_id': replica.node_id,
                        'endereco': replica.endereco,
                        'porta': replica.porta,
                        'tipo': 'replica',
                        'checksum': getattr(chunk_info, 'checksum', '')
                    })
            
            return node_list
            
        except Exception as e:
            print(f"Erro ao obter lista de nós para chunk {arquivo_nome}:{chunk_numero}: {e}")
            return []
    
    def download_chunk_with_retry(self, arquivo_nome: str, chunk_numero: int, 
                                 chunk_info: Dict = None) -> ChunkOperationResult:
        """Download de um chunk com retry inteligente"""
        result = ChunkOperationResult(chunk_numero)
        
        # Obter lista estática de nós antes de iniciar o loop de retry
        node_list = self._get_chunk_node_list(arquivo_nome, chunk_numero)
        if not node_list:
            result.erro = "Nenhum nó disponível para o chunk"
            return result
        
        # Tentar cada nó da lista em ordem
        for tentativa, node_info in enumerate(node_list):
            result.tentativas = tentativa + 1
            
            try:
                # Tentar download
                chunk_data, erro = self._attempt_chunk_download(
                    arquivo_nome, chunk_numero, node_info, node_info.get('checksum', '')
                )
                
                if chunk_data is not None:
                    result.sucesso = True
                    result.dados = chunk_data
                    result.node_usado = node_info['node_id']
                    print(f"✅ Chunk {chunk_numero} baixado de {node_info['node_id']} ({node_info['tipo']}) (tentativa {tentativa + 1})")
                    break
                else:
                    result.erro = erro
                    print(f"⚠️ Tentativa {tentativa + 1} falhou para chunk {chunk_numero} no nó {node_info['node_id']}: {erro}")
                    
                    # Reportar falha do nó
                    self._report_node_failure(node_info['node_id'], erro)
                    
                    # Aguardar antes da próxima tentativa (exceto na última)
                    if tentativa < len(node_list) - 1:
                        delay = min(
                            self.retry_config.base_delay * (self.retry_config.backoff_multiplier ** tentativa),
                            self.retry_config.max_delay
                        )
                        time.sleep(delay)
                        
            except Exception as e:
                result.erro = f"Erro inesperado: {str(e)}"
                print(f"❌ Erro inesperado no chunk {chunk_numero}, tentativa {tentativa + 1}: {e}")
        
        if not result.sucesso:
            print(f"❌ Falha definitiva no download do chunk {chunk_numero} após {result.tentativas} tentativas")
        
        return result
    
    def _attempt_chunk_download(self, arquivo_nome: str, chunk_numero: int, 
                               node_info: Dict, expected_checksum: str) -> Tuple[Optional[bytes], str]:
        """Tenta download de um chunk de um nó específico"""
        try:
            stub = self.client._get_storage_connection(node_info)
            if not stub:
                return None, "Não foi possível conectar ao nó"
            
            request = fs_pb2.ChunkDownloadRequest(
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero
            )
            
            # Usar timeout por tentativa
            response = stub.DownloadChunk(request, timeout=self.retry_config.timeout_per_attempt)
            
            if response.sucesso and response.dados:
                # Verificar integridade se checksum disponível
                if expected_checksum:
                    calculated_checksum = hashlib.md5(response.dados).hexdigest()
                    if calculated_checksum != expected_checksum:
                        return None, f"Checksum inválido: esperado {expected_checksum}, obtido {calculated_checksum}"
                
                return response.dados, ""
            else:
                return None, response.mensagem if hasattr(response, 'mensagem') else "Falha no download"
                
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                return None, f"Nó {node_info['node_id']} indisponível"
            elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                return None, f"Timeout no nó {node_info['node_id']}"
            else:
                return None, f"Erro gRPC: {e.details()}"
        except Exception as e:
            return None, f"Erro de conexão: {str(e)}"
    
    def _report_node_failure(self, node_id: str, reason: str):
        """Reporta falha de nó ao servidor de metadados"""
        try:
            self.client.metadata_client.report_node_failure(node_id, reason)
        except Exception as e:
            print(f"Erro ao reportar falha do nó {node_id}: {e}")

class AdvancedBigFSClient:
    """Cliente BigFS-v2 avançado com upload/download paralelo e retry inteligente"""
    
    def __init__(self, metadata_server: str = "localhost:50052", max_workers: int = 4):
        self.metadata_server = metadata_server
        self.metadata_client = None
        self.storage_connections = {}
        self.max_workers = max_workers
        self.chunk_size = 1024 * 1024  # 1MB
        
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
        if not node_info:
            return None
        node_address = f"{node_info['endereco']}:{node_info['porta']}"
        
        if node_address not in self.storage_connections:
            try:
                channel = grpc.insecure_channel(
                    node_address,
                    options=[
                        ('grpc.keepalive_time_ms', 30000),
                        ('grpc.keepalive_timeout_ms', 5000),
                        ('grpc.keepalive_permit_without_calls', True),
                        ('grpc.http2.max_pings_without_data', 0),
                        ('grpc.http2.min_time_between_pings_ms', 10000),
                        ('grpc.http2.min_ping_interval_without_data_ms', 300000)
                    ]
                )
                stub = fs_grpc.FileSystemServiceStub(channel)
                self.storage_connections[node_address] = stub
            except Exception as e:
                print(f"Erro ao conectar com {node_address}: {e}")
                return None
        
        return self.storage_connections.get(node_address)
    
    def verify_file_integrity(self, local_path: str, remote_path: str) -> bool:
        """
        Verifica a integridade de um arquivo completo comparando checksums.
        Primeiro baixa o arquivo, depois compara o checksum com o registrado no servidor.
        """
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        try:
            print(f"🔍 Iniciando verificação de integridade: {remote_path}")
            
            # 1. Obter metadados do arquivo do servidor
            file_metadata = self.metadata_client.get_file_metadata(remote_path)
            if not file_metadata:
                print(f"❌ Arquivo '{remote_path}' não encontrado no servidor")
                return False
            
            expected_checksum = file_metadata.checksum_arquivo
            print(f"📋 Checksum esperado: {expected_checksum}")
            
            # 2. Baixar o arquivo usando a lógica de download paralelo
            success = self.download_file_parallel(remote_path, local_path)
            if not success:
                print(f"❌ Falha ao baixar arquivo para verificação")
                return False
            
            # 3. Calcular checksum do arquivo baixado
            with open(local_path, 'rb') as f:
                file_data = f.read()
                calculated_checksum = self._calculate_checksum(file_data)
            
            print(f"📋 Checksum calculado: {calculated_checksum}")
            
            # 4. Comparar checksums
            if calculated_checksum == expected_checksum:
                print(f"✅ Integridade do arquivo '{remote_path}' confirmada!")
                return True
            else:
                print(f"❌ Integridade comprometida! Checksums não conferem:")
                print(f"   Esperado: {expected_checksum}")
                print(f"   Calculado: {calculated_checksum}")
                return False
                
        except Exception as e:
            print(f"❌ Erro durante verificação de integridade: {e}")
            return False
    
    def verify_and_repair_file(self, local_path: str, remote_path: str, max_attempts: int = 3) -> bool:
        """
        Verifica integridade e tenta reparar o arquivo se necessário.
        Faz múltiplas tentativas de download se a integridade falhar.
        """
        for attempt in range(max_attempts):
            print(f"🔄 Tentativa {attempt + 1} de {max_attempts}")
            
            if self.verify_file_integrity(local_path, remote_path):
                return True
            
            if attempt < max_attempts - 1:
                print(f"⚠️ Tentativa {attempt + 1} falhou. Tentando novamente...")
                # Remover arquivo corrompido antes da próxima tentativa
                if os.path.exists(local_path):
                    os.remove(local_path)
                time.sleep(1)  # Pequena pausa antes da próxima tentativa
        
        print(f"❌ Falha na verificação após {max_attempts} tentativas")
        return False
    
    def _calculate_checksum(self, data: bytes) -> str:
        """Calcula checksum MD5 dos dados"""
        return hashlib.md5(data).hexdigest()
    
    def _divide_file_into_chunks(self, file_path: str) -> List[Tuple[int, bytes, str]]:
        """Divide arquivo em chunks e calcula checksums"""
        chunks = []
        chunk_numero = 0
        
        with open(file_path, 'rb') as f:
            while True:
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                
                checksum = self._calculate_checksum(chunk_data)
                chunks.append((chunk_numero, chunk_data, checksum))
                chunk_numero += 1
        
        return chunks
    
    def upload_file_parallel(self, local_path: str, remote_path: str) -> bool:
        """Upload de arquivo com processamento paralelo e retry inteligente"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        if not os.path.exists(local_path):
            print(f"❌ Arquivo local não encontrado: {local_path}")
            return False
        
        try:
            print(f"📤 Iniciando upload: {local_path} -> {remote_path}")
            
            # Dividir arquivo em chunks
            chunks = self._divide_file_into_chunks(local_path)
            if not chunks:
                print("❌ Arquivo vazio")
                return False
            
            file_size = os.path.getsize(local_path)
            file_checksum = self._calculate_checksum(open(local_path, 'rb').read())
            
            print(f"📊 Arquivo: {len(chunks)} chunks, {file_size} bytes")
            
            # Registrar arquivo no servidor de metadados
            success = self.metadata_client.register_file(
                remote_path, file_size, len(chunks), file_checksum
            )
            
            if not success:
                print("❌ Erro ao registrar arquivo no servidor de metadados")
                return False
            
            # Upload paralelo com retry inteligente
            uploader = IntelligentChunkUploader(self)
            upload_results = []
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submeter tarefas de upload
                future_to_chunk = {}
                for chunk_numero, chunk_data, checksum in chunks:
                    future = executor.submit(
                        uploader.upload_chunk_with_retry,
                        remote_path, chunk_numero, chunk_data, checksum
                    )
                    future_to_chunk[future] = chunk_numero
                
                # Coletar resultados
                for future in as_completed(future_to_chunk):
                    result = future.result()
                    upload_results.append(result)
            
            # Verificar resultados
            successful_chunks = [r for r in upload_results if r.sucesso]
            failed_chunks = [r for r in upload_results if not r.sucesso]
            
            print(f"📊 Resultados: {len(successful_chunks)}/{len(chunks)} chunks enviados com sucesso")
            
            if failed_chunks:
                print("❌ Chunks que falharam:")
                for result in failed_chunks:
                    print(f"  - Chunk {result.chunk_numero}: {result.erro}")
                return False
            
            # Marcar arquivo como completo
            self.metadata_client.mark_file_complete(remote_path)
            print(f"✅ Upload concluído com sucesso: {remote_path}")
            return True
            
        except Exception as e:
            print(f"❌ Erro no upload: {e}")
            return False
    
    def download_file_parallel(self, remote_path: str, local_path: str) -> bool:
        """Download de arquivo com processamento paralelo e retry inteligente"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        try:
            print(f"📥 Iniciando download: {remote_path} -> {local_path}")
            
            # Obter metadados do arquivo
            file_metadata = self.metadata_client.get_file_metadata(remote_path)
            if not file_metadata:
                print(f"❌ Arquivo não encontrado: {remote_path}")
                return False
            
            # Obter localização dos chunks
            chunk_locations = self.metadata_client.get_chunk_locations(remote_path)
            if not chunk_locations:
                print("❌ Nenhum chunk encontrado para o arquivo")
                return False
            
            print(f"📊 Arquivo: {len(chunk_locations)} chunks, {file_metadata.tamanho_total} bytes")
            
            # Download paralelo com retry inteligente
            downloader = IntelligentChunkDownloader(self)
            download_results = []
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submeter tarefas de download
                future_to_chunk = {}
                for chunk_info in chunk_locations:
                    chunk_dict = {
                        'checksum': chunk_info.checksum,
                        'tamanho': chunk_info.tamanho_chunk
                    }
                    future = executor.submit(
                        downloader.download_chunk_with_retry,
                        remote_path, chunk_info.chunk_numero, chunk_dict
                    )
                    future_to_chunk[future] = chunk_info.chunk_numero
                
                # Coletar resultados
                for future in as_completed(future_to_chunk):
                    result = future.result()
                    download_results.append(result)
            
            # Verificar resultados
            successful_chunks = [r for r in download_results if r.sucesso]
            failed_chunks = [r for r in download_results if not r.sucesso]
            
            print(f"📊 Resultados: {len(successful_chunks)}/{len(chunk_locations)} chunks baixados com sucesso")
            
            if failed_chunks:
                print("❌ Chunks que falharam:")
                for result in failed_chunks:
                    print(f"  - Chunk {result.chunk_numero}: {result.erro}")
                return False
            
            # Recombinar chunks
            successful_chunks.sort(key=lambda x: x.chunk_numero)
            
            with open(local_path, 'wb') as f:
                for result in successful_chunks:
                    f.write(result.dados)
            
            # Verificar integridade do arquivo final
            downloaded_checksum = self._calculate_checksum(open(local_path, 'rb').read())
            if downloaded_checksum != file_metadata.checksum_arquivo:
                print(f"❌ Checksum do arquivo não confere!")
                print(f"   Esperado: {file_metadata.checksum_arquivo}")
                print(f"   Obtido: {downloaded_checksum}")
                os.remove(local_path)
                return False
            
            print(f"✅ Download concluído com sucesso: {local_path}")
            return True
            
        except Exception as e:
            print(f"❌ Erro no download: {e}")
            return False
    
    def list_files(self, directory: str = "/") -> List[str]:
        """Lista arquivos no diretório remoto"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return []
        
        try:
            files = self.metadata_client.list_files(directory)
            return files
        except Exception as e:
            print(f"❌ Erro ao listar arquivos: {e}")
            return []
    
    def delete_file(self, remote_path: str) -> bool:
        """Deleta arquivo remoto"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        try:
            success = self.metadata_client.delete_file(remote_path)
            if success:
                print(f"✅ Arquivo deletado: {remote_path}")
            else:
                print(f"❌ Erro ao deletar arquivo: {remote_path}")
            return success
        except Exception as e:
            print(f"❌ Erro ao deletar arquivo: {e}")
            return False
    
    def get_system_status(self) -> Dict:
        """Obtém status do sistema"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return {}
        
        try:
            status = self.metadata_client.get_system_status()
            return status
        except Exception as e:
            print(f"❌ Erro ao obter status: {e}")
            return {}

def main():
    """Interface principal do cliente avançado"""
    print("🚀 BigFS-v2 Cliente Avançado com Retry Inteligente")
    print("=" * 60)
    
    # Configuração inicial
    metadata_server = input("Servidor de metadados (Enter para localhost:50052): ").strip()
    if not metadata_server:
        metadata_server = "localhost:50052"
    
    max_workers = input("Número máximo de workers paralelos (Enter para 4): ").strip()
    if not max_workers:
        max_workers = 4
    else:
        try:
            max_workers = int(max_workers)
        except ValueError:
            max_workers = 4
    
    client = AdvancedBigFSClient(metadata_server, max_workers)
    
    while True:
        print("\n" + "=" * 60)
        print("📋 MENU PRINCIPAL")
        print("=" * 60)
        print("1. 📋 Listar arquivos")
        print("2. 📤 Upload de arquivo (paralelo)")
        print("3. 📥 Download de arquivo (paralelo)")
        print("4. 🗑️  Deletar arquivo")
        print("5. 📊 Status do sistema")
        print("6. ⚙️  Configurações de retry")
        print("7. 🚪 Sair")
        
        opcao = input("\nEscolha uma opção: ").strip()
        
        if opcao == "1":
            directory = input("Diretório (Enter para raiz): ").strip()
            if not directory:
                directory = "/"
            
            files = client.list_files(directory)
            if files:
                print(f"\n📁 Arquivos em {directory}:")
                for file in files:
                    print(f"  📄 {file}")
            else:
                print("📭 Nenhum arquivo encontrado")
        
        elif opcao == "2":
            local_path = input("Caminho local do arquivo: ").strip()
            remote_path = input("Caminho remoto: ").strip()
            
            if local_path and remote_path:
                start_time = time.time()
                success = client.upload_file_parallel(local_path, remote_path)
                end_time = time.time()
                
                if success:
                    print(f"⏱️  Tempo total: {end_time - start_time:.2f} segundos")
                else:
                    print("❌ Upload falhou")
        
        elif opcao == "3":
            remote_path = input("Caminho remoto: ").strip()
            local_path = input("Caminho local de destino: ").strip()
            
            if remote_path and local_path:
                start_time = time.time()
                success = client.download_file_parallel(remote_path, local_path)
                end_time = time.time()
                
                if success:
                    print(f"⏱️  Tempo total: {end_time - start_time:.2f} segundos")
                else:
                    print("❌ Download falhou")
        
        elif opcao == "4":
            remote_path = input("Caminho remoto do arquivo: ").strip()
            
            if remote_path:
                confirm = input(f"Confirma deleção de '{remote_path}'? (s/N): ").strip().lower()
                if confirm == 's':
                    client.delete_file(remote_path)
        
        elif opcao == "5":
            status = client.get_system_status()
            if status:
                print("\n📊 STATUS DO SISTEMA")
                print("-" * 40)
                print(f"Nós ativos: {status.get('nos_ativos', 0)}")
                print(f"Nós falhos: {status.get('nos_falhos', 0)}")
                print(f"Total de arquivos: {status.get('total_arquivos', 0)}")
                print(f"Total de chunks: {status.get('total_chunks', 0)}")
                print(f"Storage usado: {status.get('storage_usado', 0)} bytes")
        
        elif opcao == "6":
            print("\n⚙️  CONFIGURAÇÕES DE RETRY")
            print("-" * 40)
            print(f"Max retries: {client.max_workers}")
            print(f"Workers paralelos: {client.max_workers}")
            print(f"Chunk size: {client.chunk_size} bytes")
            
            new_workers = input(f"Novo número de workers (atual: {client.max_workers}): ").strip()
            if new_workers:
                try:
                    client.max_workers = int(new_workers)
                    print(f"✅ Workers atualizados para: {client.max_workers}")
                except ValueError:
                    print("❌ Valor inválido")
        
        elif opcao == "7":
            print("👋 Encerrando cliente...")
            break
        
        else:
            print("❌ Opção inválida")

if __name__ == "__main__":
    main()

