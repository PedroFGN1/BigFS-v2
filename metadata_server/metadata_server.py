import os
import sys
import time
import grpc
from concurrent import futures

# Adiciona o diretório proto ao sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))

import filesystem_extended_pb2 as fs_pb2
import filesystem_extended_pb2_grpc as fs_grpc
from metadata_manager import MetadataManager, FileMetadata, ChunkMetadata, NodeInfo, ReplicaInfo

class MetadataServiceServicer(fs_grpc.MetadataServiceServicer):
    """Implementação do serviço de metadados"""
    
    def __init__(self, data_dir: str = "metadata_storage"):
        self.metadata_manager = MetadataManager(data_dir)
        print(f"Servidor de Metadados iniciado. Dados em: {data_dir}")
    
    def ListarArquivos(self, request, context):
        """Implementação da RPC para listar arquivos globalmente."""
        try:
            # Por enquanto, ignora o request.path e lista tudo da raiz
            nomes_arquivos = self.metadata_manager.list_files_in_directory(request.path)
            return fs_pb2.FileListResponse(
                sucesso=True,
                mensagem="Arquivos listados com sucesso.",
                nomes_arquivos=nomes_arquivos
            )
        except Exception as e:
            return fs_pb2.FileListResponse(
                sucesso=False,
                mensagem=f"Erro interno ao listar arquivos: {str(e)}"
            )

    def RegistrarArquivo(self, request, context):
        """Registra metadados de um novo arquivo"""
        try:
            file_metadata = FileMetadata(
                nome_arquivo=request.nome_arquivo,
                tamanho_total=request.tamanho_total,
                total_chunks=request.total_chunks,
                checksum_arquivo=request.checksum_arquivo,
                timestamp_criacao=request.timestamp_criacao,
                timestamp_modificacao=int(time.time()),
                no_primario=request.no_primario,
                nos_replicas=list(request.nos_replicas),
                esta_completo=False
            )
            
            success = self.metadata_manager.register_file(file_metadata)
            
            return fs_pb2.OperacaoResponse(
                sucesso=success,
                mensagem=f"Arquivo {request.nome_arquivo} registrado com sucesso" if success 
                        else f"Erro ao registrar arquivo {request.nome_arquivo}"
            )
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ObterMetadataArquivo(self, request, context):
        """Obtém metadados de um arquivo"""
        try:
            file_metadata = self.metadata_manager.get_file_metadata(request.path)
            
            if file_metadata:
                metadata_pb = fs_pb2.FileMetadata(
                    nome_arquivo=file_metadata.nome_arquivo,
                    tamanho_total=file_metadata.tamanho_total,
                    total_chunks=file_metadata.total_chunks,
                    checksum_arquivo=file_metadata.checksum_arquivo,
                    timestamp_criacao=file_metadata.timestamp_criacao,
                    timestamp_modificacao=file_metadata.timestamp_modificacao,
                    no_primario=file_metadata.no_primario,
                    nos_replicas=file_metadata.nos_replicas,
                    esta_completo=file_metadata.esta_completo
                )
                
                return fs_pb2.FileMetadataResponse(
                    sucesso=True,
                    mensagem="Metadados obtidos com sucesso",
                    metadata=metadata_pb
                )
            else:
                return fs_pb2.FileMetadataResponse(
                    sucesso=False,
                    mensagem=f"Arquivo {request.path} não encontrado"
                )
        except Exception as e:
            return fs_pb2.FileMetadataResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def RemoverArquivo(self, request, context):
        """Remove metadados de um arquivo"""
        try:
            success = self.metadata_manager.remove_file(request.path)
            
            return fs_pb2.OperacaoResponse(
                sucesso=success,
                mensagem=f"Arquivo {request.path} removido com sucesso" if success 
                        else f"Arquivo {request.path} não encontrado"
            )
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
        
    def RegistrarChunk(self, request, context):
        """Registra metadados de um chunk"""
        try:
            chunk_metadata = ChunkMetadata(
                arquivo_nome=request.arquivo_nome,
                chunk_numero=request.chunk_numero,
                no_primario=request.no_primario,
                replicas=request.replicas,  # Lista de ReplicaInfo
                checksum=request.checksum,
                tamanho_chunk=request.tamanho_chunk,
                timestamp_criacao=request.timestamp_criacao,
                disponivel=True
            )
            
            success = self.metadata_manager.register_chunk(chunk_metadata)
            
            return fs_pb2.OperacaoResponse(
                sucesso=success,
                mensagem=f"Chunk {request.arquivo_nome}:{request.chunk_numero} registrado com sucesso" if success 
                        else f"Erro ao registrar chunk {request.arquivo_nome}:{request.chunk_numero}"
            )
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ObterLocalizacaoChunks(self, request, context):
        """Obtém localização de todos os chunks de um arquivo"""
        try:
            chunks_metadata = self.metadata_manager.get_chunk_locations(request.path)
            
            chunks_pb = []
            for chunk_metadata in chunks_metadata:

                # Precisamos de "traduzir" a nossa lista de dataclasses ReplicaInfo
                # para uma lista de objetos gRPC ReplicaInfo.
                
                # Obter o objeto NodeInfo completo para o nó primário
                primary_node_info_obj = self.metadata_manager.get_node_by_id(chunk_metadata.no_primario)
                
                # Construir a lista de réplicas no formato esperado pelo gRPC
                replicas_pb = []
                # Iterar sobre a lista de dataclasses ReplicaInfo
                for replica_info_dataclass in chunk_metadata.replicas:
                    # Converter a dataclass para o objeto gRPC
                    replica_info_pb = fs_pb2.ReplicaInfo(
                        node_id=replica_info_dataclass.node_id,
                        # Converte a string de status para o valor do enum gRPC
                        status=fs_pb2.ReplicaStatus.Value(replica_info_dataclass.status)
                    )
                    replicas_pb.append(replica_info_pb)


                chunk_location = fs_pb2.ChunkLocation(
                    chunk_numero=chunk_metadata.chunk_numero,
                    no_primario=chunk_metadata.no_primario,
                    replicas=replicas_pb,
                    checksum=chunk_metadata.checksum,
                    tamanho_chunk=chunk_metadata.tamanho_chunk,
                    disponivel=chunk_metadata.disponivel
                )
                chunks_pb.append(chunk_location)
            
            return fs_pb2.ChunkLocationResponse(
                sucesso=True,
                mensagem=f"Encontrados {len(chunks_pb)} chunks para {request.path}",
                chunks=chunks_pb
            )
        except Exception as e:
            return fs_pb2.ChunkLocationResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def RemoverChunk(self, request, context):
        """Remove metadados de um chunk"""
        try:
            chunk_key = f"{request.arquivo_nome}:{request.chunk_numero}"
            
            with self.metadata_manager.lock:
                if chunk_key in self.metadata_manager.chunks:
                    del self.metadata_manager.chunks[chunk_key]
                    self.metadata_manager._save_metadata()
                    success = True
                else:
                    success = False
            
            return fs_pb2.OperacaoResponse(
                sucesso=success,
                mensagem=f"Chunk {chunk_key} removido com sucesso" if success 
                        else f"Chunk {chunk_key} não encontrado"
            )
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def RegistrarNo(self, request, context):
        """Registra um novo nó no sistema"""
        try:
            node_info = NodeInfo(
                node_id=request.node_id,
                endereco=request.endereco,
                porta=request.porta,
                status="ATIVO",
                capacidade_storage=request.capacidade_storage,
                storage_usado=0,
                ultimo_heartbeat=int(time.time()),
                chunks_armazenados=set()
            )
            
            node_id = self.metadata_manager.register_node(node_info)
            
            return fs_pb2.NodeRegistrationResponse(
                sucesso=bool(node_id),
                mensagem=f"Nó registrado com sucesso" if node_id else "Erro ao registrar nó",
                node_id_atribuido=node_id
            )
        except Exception as e:
            return fs_pb2.NodeRegistrationResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ObterNosDisponiveis(self, request, context):
        """Obtém lista de nós disponíveis"""
        try:
            status_filter = None
            if request.status_filtro != fs_pb2.NodeStatus.ATIVO:  # Se não for o padrão
                status_map = {
                    fs_pb2.NodeStatus.ATIVO: "ATIVO",
                    fs_pb2.NodeStatus.OCUPADO: "OCUPADO", 
                    fs_pb2.NodeStatus.MANUTENCAO: "MANUTENCAO",
                    fs_pb2.NodeStatus.FALHA: "FALHA"
                }
                status_filter = status_map.get(request.status_filtro, "ATIVO")
            else:
                status_filter = "ATIVO" if request.apenas_ativos else None
            
            nodes = self.metadata_manager.get_available_nodes(status_filter)
            
            nodes_pb = []
            for node in nodes:
                node_pb = fs_pb2.NodeInfo(
                    node_id=node.node_id,
                    endereco=node.endereco,
                    porta=node.porta,
                    status=getattr(fs_pb2.NodeStatus, node.status),
                    capacidade_storage=node.capacidade_storage,
                    storage_usado=node.storage_usado,
                    ultimo_heartbeat=node.ultimo_heartbeat,
                    chunks_armazenados=list(node.chunks_armazenados)
                )
                nodes_pb.append(node_pb)
            
            return fs_pb2.NodesResponse(
                sucesso=True,
                mensagem=f"Encontrados {len(nodes_pb)} nós",
                nos=nodes_pb
            )
        except Exception as e:
            return fs_pb2.NodesResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ReportarFalhaNo(self, request, context):
        """Reporta falha de um nó"""
        try:
            success = self.metadata_manager.report_node_failure(
                request.node_id, 
                request.motivo_falha
            )
            
            return fs_pb2.OperacaoResponse(
                sucesso=success,
                mensagem=f"Falha do nó {request.node_id} reportada com sucesso" if success 
                        else f"Nó {request.node_id} não encontrado"
            )
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ObterNoParaOperacao(self, request, context):
        """Obtém o melhor nó para uma operação"""
        try:
            node = self.metadata_manager.get_node_for_operation(
                request.tipo_operacao,
                request.arquivo_nome,
                request.chunk_numero
            )
            
            if node:
                node_pb = fs_pb2.NodeInfo(
                    node_id=node.node_id,
                    endereco=node.endereco,
                    porta=node.porta,
                    status=getattr(fs_pb2.NodeStatus, node.status),
                    capacidade_storage=node.capacidade_storage,
                    storage_usado=node.storage_usado,
                    ultimo_heartbeat=node.ultimo_heartbeat,
                    chunks_armazenados=list(node.chunks_armazenados)
                )
                
                return fs_pb2.NodeResponse(
                    sucesso=True,
                    mensagem="Nó encontrado para operação",
                    no_recomendado=node_pb
                )
            else:
                return fs_pb2.NodeResponse(
                    sucesso=False,
                    mensagem="Nenhum nó disponível para a operação"
                )
        except Exception as e:
            return fs_pb2.NodeResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ObterReplicasDisponiveis(self, request, context):
        """Obtém réplicas disponíveis para um chunk"""
        try:
            replicas = self.metadata_manager.get_available_replicas(
                request.arquivo_nome,
                request.chunk_numero,
                request.no_primario_falho
            )
            
            replicas_pb = []
            for replica in replicas:
                replica_pb = fs_pb2.NodeInfo(
                    node_id=replica.node_id,
                    endereco=replica.endereco,
                    porta=replica.porta,
                    status=getattr(fs_pb2.NodeStatus, replica.status),
                    capacidade_storage=replica.capacidade_storage,
                    storage_usado=replica.storage_usado,
                    ultimo_heartbeat=replica.ultimo_heartbeat,
                    chunks_armazenados=list(replica.chunks_armazenados)
                )
                replicas_pb.append(replica_pb)
            
            return fs_pb2.ReplicaResponse(
                sucesso=True,
                mensagem=f"Encontradas {len(replicas_pb)} réplicas disponíveis",
                replicas_disponiveis=replicas_pb
            )
        except Exception as e:
            return fs_pb2.ReplicaResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ProcessarHeartbeat(self, request, context):
        """Processa heartbeat de um nó"""
        try:
            
            status = fs_pb2.NodeStatus.Name(request.status)
            success = self.metadata_manager.process_heartbeat(
                request.node_id,
                status,
                list(request.chunks_armazenados)
            )
            
            return fs_pb2.OperacaoResponse(
                sucesso=success,
                mensagem="Heartbeat processado com sucesso" if success 
                        else f"Nó {request.node_id} não encontrado"
            )
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )
    
    def ObterStatusSistema(self, request, context):
        """Obtém status geral do sistema"""
        try:
            status = self.metadata_manager.get_system_status()
            
            # Converter detalhes dos nós se solicitado
            detalhes_nos_pb = []
            if request.incluir_detalhes_nos:
                for node in status['detalhes_nos']:
                    node_pb = fs_pb2.NodeInfo(
                        node_id=node.node_id,
                        endereco=node.endereco,
                        porta=node.porta,
                        status=getattr(fs_pb2.NodeStatus, node.status),
                        capacidade_storage=node.capacidade_storage,
                        storage_usado=node.storage_usado,
                        ultimo_heartbeat=node.ultimo_heartbeat,
                        chunks_armazenados=list(node.chunks_armazenados)
                    )
                    detalhes_nos_pb.append(node_pb)
            
            # Converter estatísticas se solicitado
            estatisticas_pb = None
            if request.incluir_estatisticas:
                estatisticas_pb = fs_pb2.SystemStatistics(
                    operacoes_upload_total=status['estatisticas']['operacoes_upload_total'],
                    operacoes_download_total=status['estatisticas']['operacoes_download_total'],
                    operacoes_delete_total=status['estatisticas']['operacoes_delete_total'],
                    falhas_detectadas=status['estatisticas']['falhas_detectadas'],
                    replicacoes_realizadas=status['estatisticas']['replicacoes_realizadas'],
                    tempo_medio_upload=status['estatisticas']['tempo_medio_upload'],
                    tempo_medio_download=status['estatisticas']['tempo_medio_download']
                )
            
            status_sistema_pb = fs_pb2.SystemStatus(
                total_nos=status['total_nos'],
                nos_ativos=status['nos_ativos'],
                nos_falhos=status['nos_falhos'],
                total_arquivos=status['total_arquivos'],
                total_chunks=status['total_chunks'],
                storage_total=status['storage_total'],
                storage_usado=status['storage_usado'],
                detalhes_nos=detalhes_nos_pb,
                estatisticas=estatisticas_pb
            )
            
            return fs_pb2.StatusResponse(
                sucesso=True,
                mensagem="Status do sistema obtido com sucesso",
                status_sistema=status_sistema_pb
            )
        except Exception as e:
            return fs_pb2.StatusResponse(
                sucesso=False,
                mensagem=f"Erro interno: {str(e)}"
            )

    def MarcarArquivoCompleto(self, request, context):
        """Implementação da RPC para marcar um arquivo como completo."""
        try:
            sucesso = self.metadata_manager.mark_file_as_complete(request.path)
            mensagem = f"Arquivo '{request.path}' finalizado." if sucesso else f"Não foi possível finalizar o arquivo '{request.path}'."
            return fs_pb2.OperacaoResponse(sucesso=sucesso, mensagem=mensagem)
        except Exception as e:
            return fs_pb2.OperacaoResponse(sucesso=False, mensagem=f"Erro interno: {str(e)}")

    def GetChunkInfo(self, request, context):
        """Implementação da RPC para buscar metadados de um único chunk."""
        try:
            chunk_metadata = self.metadata_manager.get_chunk_metadata(
                request.arquivo_nome,
                request.chunk_numero
            )

            if chunk_metadata:
                # Traduzir a lista de réplicas para o formato do protocolo
                replica_ids = [replica for replica in chunk_metadata.replicas]

                # Converte o objeto ChunkMetadata do dataclass para o objeto ChunkLocation do protobuf
                chunk_location_pb = fs_pb2.ChunkLocation(
                    chunk_numero=chunk_metadata.chunk_numero,
                    no_primario=chunk_metadata.no_primario,
                    replicas=replica_ids,
                    checksum=chunk_metadata.checksum,
                    tamanho_chunk=chunk_metadata.tamanho_chunk,
                    disponivel=chunk_metadata.disponivel
                )
                return fs_pb2.ChunkMetadataResponse(
                    sucesso=True,
                    mensagem="Metadados do chunk encontrados.",
                    metadata=chunk_location_pb
                )
            else:
                return fs_pb2.ChunkMetadataResponse(sucesso=False, mensagem="Chunk não encontrado.")
        except Exception as e:
            return fs_pb2.ChunkMetadataResponse(sucesso=False, mensagem=f"Erro interno: {str(e)}")
        
    def GetNodeInfo(self, request, context):
        """Implementação da RPC para buscar informações de um único nó."""
        try:
            node_info = self.metadata_manager.get_node_by_id(request.node_id)
            
            if node_info:
                # Converte o objeto NodeInfo do dataclass para o objeto NodeInfo do protobuf
                node_info_pb = fs_pb2.NodeInfo(
                    node_id=node_info.node_id,
                    endereco=node_info.endereco,
                    porta=node_info.porta,
                    status=fs_pb2.NodeStatus.Value(node_info.status),
                    capacidade_storage=node_info.capacidade_storage,
                    storage_usado=node_info.storage_usado,
                    ultimo_heartbeat=node_info.ultimo_heartbeat,
                    chunks_armazenados=list(node_info.chunks_armazenados)
                )
                return fs_pb2.NodeInfoResponse(
                    sucesso=True,
                    mensagem="Informações do nó encontradas.",
                    node_info=node_info_pb
                )
            else:
                return fs_pb2.NodeInfoResponse(sucesso=False, mensagem=f"Nó com ID '{request.node_id}' não encontrado.")
        except Exception as e:
            return fs_pb2.NodeInfoResponse(sucesso=False, mensagem=f"Erro interno: {str(e)}")
    
    def ConfirmarReplica(self, request, context):
        """Confirma que uma réplica foi criada com sucesso"""
        try:
            sucesso = self.metadata_manager.confirmar_replica(
                request.arquivo_nome,
                request.chunk_numero,
                request.replica_id
            )
            
            if sucesso:
                return fs_pb2.OperacaoResponse(
                    sucesso=True,
                    mensagem=f"Réplica {request.replica_id} confirmada para chunk {request.chunk_numero}"
                )
            else:
                return fs_pb2.OperacaoResponse(
                    sucesso=False,
                    mensagem=f"Falha ao confirmar réplica {request.replica_id}"
                )
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro interno ao confirmar réplica: {str(e)}"
            )

def serve(port=50052, data_dir="metadata_storage"):
    """Inicia o servidor de metadados"""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 1024 * 1024 * 1024),  # 1GB
            ('grpc.max_receive_message_length', 1024 * 1024 * 1024)  # 1GB
        ]
    )
    
    # Adicionar o serviço de metadados
    fs_grpc.add_MetadataServiceServicer_to_server(
        MetadataServiceServicer(data_dir), server
    )
    
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    
    print(f"Servidor de Metadados rodando na porta {port}")
    print(f"Dados armazenados em: {os.path.abspath(data_dir)}")
    print("Pressione Ctrl+C para parar o servidor.")
    
    try:
        while True:
            time.sleep(86400)  # Dormir por um dia
    except KeyboardInterrupt:
        print("Encerrando servidor de metadados...")
    finally:
        server.stop(0)
        print("Servidor de metadados parado.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Servidor de Metadados BigFS-v2")
    parser.add_argument("--port", type=int, default=50052, help="Porta do servidor (padrão: 50052)")
    parser.add_argument("--data-dir", default="metadata_storage", help="Diretório para dados (padrão: metadata_storage)")
    
    args = parser.parse_args()
    serve(args.port, args.data_dir)

