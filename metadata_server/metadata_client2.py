import sys
import os
import time
import grpc
import threading
from typing import Optional, List, Dict

# Adiciona o diretório proto ao sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))

import filesystem_extended_pb2 as fs_pb2
import filesystem_extended_pb2_grpc as fs_grpc

class MetadataClient:
    """Cliente para interagir com o Servidor de Metadados"""
    
    def __init__(self, metadata_server_address="localhost:50052"):
        self.metadata_server_address = metadata_server_address
        self.channel = None
        self.stub = None
        self._connect()
    
    def _connect(self):
        """Estabelece conexão com o servidor de metadados"""
        try:
            self.channel = grpc.insecure_channel(
                self.metadata_server_address,
                options=[
                    ('grpc.max_send_message_length', 1024 * 1024 * 1024),
                    ('grpc.max_receive_message_length', 1024 * 1024 * 1024),
                    ('grpc.keepalive_time_ms', 30000),
                    ('grpc.keepalive_timeout_ms', 5000),
                    ('grpc.keepalive_permit_without_calls', True)
                ]
            )
            self.stub = fs_grpc.MetadataServiceStub(self.channel)
            print(f"Conectado ao servidor de metadados: {self.metadata_server_address}")
        except Exception as e:
            print(f"Erro ao conectar com servidor de metadados: {e}")
            raise
    
    def close(self):
        """Fecha a conexão com o servidor"""
        if self.channel:
            self.channel.close()
    
    def register_file(self, nome_arquivo: str, tamanho_total: int, total_chunks: int,
                     checksum_arquivo: str, no_primario: str = "", nos_replicas: list = None) -> bool:
        """Registra um novo arquivo no sistema"""
        try:
            request = fs_pb2.FileMetadataRequest(
                nome_arquivo=nome_arquivo,
                tamanho_total=tamanho_total,
                total_chunks=total_chunks,
                checksum_arquivo=checksum_arquivo,
                timestamp_criacao=int(time.time()),
                no_primario=no_primario,
                nos_replicas=nos_replicas or []
            )
            
            response = self.stub.RegistrarArquivo(request)
            if not response.sucesso:
                print(f"Erro ao registrar arquivo: {response.mensagem}")
            return response.sucesso
        except Exception as e:
            print(f"Erro na comunicação ao registrar arquivo: {e}")
            return False
    
    def get_file_metadata(self, nome_arquivo: str) -> Optional[object]:
        """Obtém metadados de um arquivo"""
        try:
            request = fs_pb2.CaminhoRequest(path=nome_arquivo)
            response = self.stub.ObterMetadataArquivo(request)
            
            if response.sucesso:
                return response.metadata
            else:
                print(f"Erro ao obter metadados: {response.mensagem}")
                return None
        except Exception as e:
            print(f"Erro na comunicação ao obter metadados: {e}")
            return None
    
    def remove_file(self, nome_arquivo: str) -> bool:
        """Remove um arquivo do sistema"""
        try:
            request = fs_pb2.CaminhoRequest(path=nome_arquivo)
            response = self.stub.RemoverArquivo(request)
            
            if not response.sucesso:
                print(f"Erro ao remover arquivo: {response.mensagem}")
            return response.sucesso
        except Exception as e:
            print(f"Erro na comunicação ao remover arquivo: {e}")
            return False
    
    def register_chunk(self, arquivo_nome: str, chunk_numero: int, no_primario: str,
                      replicas: list, checksum: str, tamanho_chunk: int) -> bool:
        """Registra um chunk no sistema"""
        try:
            # Converter a lista de ReplicaInfo (dataclass) para objetos Protobuf
            # Se 'replicas' já for uma lista de objetos Protobuf, não é necessário converter
            # A lista 'replicas' que chega aqui já deve ser de objetos fs_pb2.ReplicaInfo, pois é assim que o metadata_manager.py a constrói e a passa.
            
            request = fs_pb2.ChunkMetadataRequest(
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero,
                no_primario=no_primario,
                replicas=replicas, # replicas já deve ser uma lista de fs_pb2.ReplicaInfo
                checksum=checksum,
                tamanho_chunk=tamanho_chunk,
                timestamp_criacao=int(time.time())
            )
            
            response = self.stub.RegistrarChunk(request)
            if not response.sucesso:
                print(f"Erro ao registrar chunk: {response.mensagem}")
            return response.sucesso
        except Exception as e:
            print(f"Erro na comunicação ao registrar chunk: {e}")
            return False
    
    def get_chunk_locations(self, nome_arquivo: str) -> List[object]:
        """Obtém localização de todos os chunks de um arquivo"""
        try:
            request = fs_pb2.CaminhoRequest(path=nome_arquivo)
            response = self.stub.ObterLocalizacaoChunks(request)
            
            if response.sucesso:
                return list(response.chunks)
            else:
                print(f"Erro ao obter localização dos chunks: {response.mensagem}")
                return []
        except Exception as e:
            print(f"Erro na comunicação ao obter chunks: {e}")
            return []
    
    def get_node_for_operation(self, tipo_operacao: str, arquivo_nome: str, 
                              chunk_numero: int = -1) -> Optional[object]:
        """Obtém o melhor nó para uma operação"""
        try:
            request = fs_pb2.OperationRequest(
                tipo_operacao=tipo_operacao,
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero
            )
            
            response = self.stub.ObterNoParaOperacao(request)
            
            if response.sucesso:
                return response
            else:
                print(f"Erro ao obter nó para operação: {response.mensagem}")
                return None
        except Exception as e:
            print(f"Erro na comunicação ao obter nó: {e}")
            return None
    
    def get_available_nodes(self, apenas_ativos: bool = True) -> Optional[List[fs_pb2.NodeInfo]]:
        """Obtém lista de nós disponíveis"""
        try:
            request = fs_pb2.NodesRequest(apenas_ativos=apenas_ativos)
            response = self.stub.ObterNosDisponiveis(request)
            
            if response.sucesso:
                return list(response.nos)
            else:
                print(f"Erro ao obter nós: {response.mensagem}")
                return []
        except Exception as e:
            print(f"Erro na comunicação ao obter nós: {e}")
            return []

    def get_available_replicas(self, arquivo_nome: str, chunk_numero: int, 
                              failed_node: str = "") -> Optional[object]:
        """Obtém réplicas disponíveis para um chunk"""
        try:
            request = fs_pb2.ReplicaRequest(
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero,
                failed_node=failed_node
            )
            
            response = self.stub.ObterReplicasDisponiveis(request)
            
            if response.sucesso:
                return response
            else:
                print(f"Erro ao obter réplicas: {response.mensagem}")
                return None
        except Exception as e:
            print(f"Erro na comunicação ao obter réplicas: {e}")
            return None
    
    def report_node_failure(self, node_id: str, reason: str) -> bool:
        """Reporta falha de um nó"""
        try:
            request = fs_pb2.NodeFailureRequest(
                node_id=node_id,
                motivo_falha=reason,
                timestamp_falha=int(time.time())
            )
            
            response = self.stub.ReportarFalhaNo(request)
            
            if not response.sucesso:
                print(f"Erro ao reportar falha do nó: {response.mensagem}")
            return response.sucesso
        except Exception as e:
            print(f"Erro na comunicação ao reportar falha: {e}")
            return False
    
    def mark_file_complete(self, nome_arquivo: str) -> bool:
        """Marca um arquivo como completo"""
        try:
            request = fs_pb2.CaminhoRequest(path=nome_arquivo)
            response = self.stub.MarcarArquivoCompleto(request)
            
            if not response.sucesso:
                print(f"Erro ao marcar arquivo como completo: {response.mensagem}")
            return response.sucesso
        except Exception as e:
            print(f"Erro na comunicação ao marcar arquivo: {e}")
            return False
    
    def list_files(self, directory: str = "/") -> Optional[List[str]]:
        """Lista arquivos no diretório global"""
        try:
            request = fs_pb2.CaminhoRequest(path=directory)
            response = self.stub.ListarArquivos(request)
            
            if response.sucesso:
                return list(response.nomes_arquivos)
            else:
                print(f"Erro ao listar arquivos: {response.mensagem}")
                return []
        except Exception as e:
            print(f"Erro na comunicação ao listar arquivos: {e}")
            return []
    
    def delete_file(self, nome_arquivo: str) -> bool:
        """Deleta um arquivo"""
        try:
            request = fs_pb2.CaminhoRequest(path=nome_arquivo)
            response = self.stub.RemoverArquivo(request)
            
            if not response.sucesso:
                print(f"Erro ao deletar arquivo: {response.mensagem}")
            return response.sucesso
        except Exception as e:
            print(f"Erro na comunicação ao deletar arquivo: {e}")
            return False
    
    def get_system_status(self, incluir_detalhes: bool = True, 
                         incluir_estatisticas: bool = True) -> dict:
        """Obtém status do sistema"""
        try:
            request = fs_pb2.StatusRequest(
                incluir_detalhes_nos=incluir_detalhes,
                incluir_estatisticas=incluir_estatisticas
            )
            
            response = self.stub.ObterStatusSistema(request)
            if response.sucesso:
                status = {
                    'total_nos': response.status_sistema.total_nos,
                    'nos_ativos': response.status_sistema.nos_ativos,
                    'nos_falhos': response.status_sistema.nos_falhos,
                    'total_arquivos': response.status_sistema.total_arquivos,
                    'total_chunks': response.status_sistema.total_chunks,
                    'storage_total': response.status_sistema.storage_total,
                    'storage_usado': response.status_sistema.storage_usado
                }
                
                if incluir_detalhes:
                    status['detalhes_nos'] = []
                    for node in response.status_sistema.detalhes_nos:
                        status['detalhes_nos'].append({
                            'node_id': node.node_id,
                            'endereco': node.endereco,
                            'porta': node.porta,
                            'status': node.status,
                            'capacidade_storage': node.capacidade_storage,
                            'storage_usado': node.storage_usado,
                            'ultimo_heartbeat': node.ultimo_heartbeat
                        })
                
                if incluir_estatisticas and response.status_sistema.estatisticas:
                    stats = response.status_sistema.estatisticas
                    status['estatisticas'] = {
                        'operacoes_upload_total': stats.operacoes_upload_total,
                        'operacoes_download_total': stats.operacoes_download_total,
                        'operacoes_delete_total': stats.operacoes_delete_total,
                        'falhas_detectadas': stats.falhas_detectadas,
                        'replicacoes_realizadas': stats.replicacoes_realizadas,
                        'tempo_medio_upload': stats.tempo_medio_upload,
                        'tempo_medio_download': stats.tempo_medio_download
                    }
                
                return status
            else:
                print(f"Erro ao obter status: {response.mensagem}")
                return {}
        except Exception as e:
            print(f"Erro na comunicação ao obter status: {e}")
            return {}
        
    def register_node(self, node_id: str, endereco: str, porta: int, capacidade_storage: int) -> Optional[object]:
        """Registra um novo nó de armazenamento no sistema"""
        try:
            request = fs_pb2.NodeRegistrationRequest(
                node_id=node_id,
                endereco=endereco,
                porta=porta,
                capacidade_storage=capacidade_storage
            )
            response = self.stub.RegistrarNo(request)
            if response.sucesso:
                return response
            else:
                print(f"Erro ao registrar nó: {response.mensagem}")
                return None
        except Exception as e:
            print(f"Erro na comunicação ao registrar nó: {e}")
            return None

    def process_heartbeat(self, node_id: str, status: str, chunks_armazenados: list) -> bool:
        """Processa o heartbeat de um nó"""
        try:
            request = fs_pb2.HeartbeatData(
                node_id=node_id,
                status=fs_pb2.NodeStatus.Value(status),
                chunks_armazenados=chunks_armazenados,
                timestamp=int(time.time())
            )
            response = self.stub.ProcessarHeartbeat(request)
            if not response.sucesso:
                print(f"Erro ao processar heartbeat: {response.mensagem}")
            return response.sucesso
        except Exception as e:
            print(f"Erro na comunicação ao processar heartbeat: {e}")
            return False

    def get_file_info(self, nome_arquivo: str) -> Optional[object]:
        """Obtém informações de um arquivo"""
        try:
            request = fs_pb2.CaminhoRequest(path=nome_arquivo)
            response = self.stub.ObterMetadataArquivo(request)
            
            if response.sucesso:
                return response.metadata
            else:
                print(f"Erro ao obter informações do arquivo: {response.mensagem}")
                return None
        except Exception as e:
            print(f"Erro na comunicação ao obter informações do arquivo: {e}")
            return None

    def get_chunk_info(self, arquivo_nome: str, chunk_numero: int) -> Optional[fs_pb2.ChunkMetadataResponse]:
        """Busca os metadados de um único chunk do servidor."""
        try:
            request = fs_pb2.ChunkRequest(
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero
            )
            response = self.stub.GetChunkInfo(request)

            if response.sucesso:
                return response # Retorna o objeto ChunkMetadataResponse
            else:
                print(f"AVISO: Não foi possível obter informações para o chunk {arquivo_nome}:{chunk_numero}. Mensagem: {response.mensagem}")
                return None
        except Exception as e:
            print(f"Erro de comunicação ao buscar informações do chunk: {e}")
            return None

    def get_node_info(self, node_id: str) -> Optional[fs_pb2.NodeInfoResponse]:
        """Busca as informações de um único nó do servidor."""
        try:
            request = fs_pb2.NodeInfoRequest(node_id=node_id)
            response = self.stub.GetNodeInfo(request) # Chama a nova RPC
            
            # Retorna a resposta completa para o chamador decidir o que fazer
            return response
        except Exception as e:
            print(f"Erro de comunicação ao buscar informações do nó '{node_id}': {e}")
            return None
    
    def confirmar_replica(self, arquivo_nome: str, chunk_numero: int, replica_id: str) -> bool:
        """Confirma que uma réplica foi criada com sucesso"""
        try:
            request = fs_pb2.ConfirmReplicaRequest(
                arquivo_nome=arquivo_nome,
                chunk_numero=chunk_numero,
                replica_id=replica_id
            )
            response = self.stub.ConfirmarReplica(request)
            
            if response.sucesso:
                print(f"✅ Réplica {replica_id} confirmada para chunk {arquivo_nome}:{chunk_numero}")
                return True
            else:
                print(f"❌ Falha ao confirmar réplica {replica_id}: {response.mensagem}")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao confirmar réplica {replica_id} para chunk {arquivo_nome}:{chunk_numero}: {e}")
            return False

class HeartbeatSender:
    """Classe para envio de heartbeats periódicos ao servidor de metadados"""
    
    def __init__(self, metadata_client: MetadataClient, node_id: str, 
                 interval: int = 15):
        self.metadata_client = metadata_client
        self.node_id = node_id
        self.interval = interval
        self.running = False
        self.thread = None
        # Esta lista em memória é a fonte da verdade para o heartbeat.
        self.chunks_armazenados = set()
        self.lock = threading.Lock() # Lock para proteger o acesso ao set

    def start(self):
        """Inicia o envio de heartbeats"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.thread.start()
            print(f"Heartbeats iniciados para nó {self.node_id} (intervalo: {self.interval}s)")

    def stop(self):
        """Para o envio de heartbeats"""
        self.running = False
        if self.thread:
            self.thread.join()
        print(f"Heartbeats parados para nó {self.node_id}")

    def update_chunks(self, chunks: set):
        """Atualiza a lista de chunks armazenados de forma segura."""
        with self.lock:
            self.chunks_armazenados = chunks.copy()
            print(f"INFO: Lista de chunks do Heartbeat para o nó {self.node_id} foi atualizada. Total: {len(self.chunks_armazenados)}")

    def _heartbeat_loop(self):
        """Loop principal de envio de heartbeats"""
        while self.running:
            try:
                # Envia a lista de chunks que está em memória
                with self.lock:
                    chunks_para_enviar = list(self.chunks_armazenados)

                success = self.metadata_client.process_heartbeat(
                    self.node_id,
                    "ATIVO",
                    chunks_para_enviar
                )
                
                if not success:
                    print(f"Falha ao enviar heartbeat para {self.node_id}")
                
                time.sleep(self.interval)
            except Exception as e:
                print(f"Erro no heartbeat para {self.node_id}: {e}")
                # Aguarda o intervalo mesmo em caso de erro para não sobrecarregar
                time.sleep(self.interval)
                
# Exemplo de uso
if __name__ == "__main__":
    # Teste básico do cliente
    client = MetadataClient()
    
    try:
        # Obter status do sistema
        status = client.get_system_status()
        if status:
            print("Status do Sistema:")
            print(f"  Nós ativos: {status['nos_ativos']}/{status['total_nos']}")
            print(f"  Arquivos: {status['total_arquivos']}")
            print(f"  Chunks: {status['total_chunks']}")
            print(f"  Storage: {status['storage_usado']}/{status['storage_total']} bytes")
        
        # Obter nós disponíveis
        nodes = client.get_available_nodes()
        print(f"\nNós disponíveis: {len(nodes)}")
        for node in nodes:
            print(f"  {node['node_id']}: {node['endereco']}:{node['porta']} ({node['status']})")
    
    finally:
        client.close()

