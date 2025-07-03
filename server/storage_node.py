import grpc
from concurrent import futures
import time
import os
import sys
import threading
from typing import Optional

# Adiciona o diretório proto ao sys.path para importar os arquivos gerados
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'metadata_server')))

import filesystem_extended_pb2 as fs_pb2
import filesystem_extended_pb2_grpc as fs_grpc

from file_manager import listar_conteudo, deletar_arquivo, salvar_arquivo, ler_arquivo, copiar_arquivo
from file_manager_extended import (
    calcular_checksum, dividir_arquivo_em_chunks, recombinar_chunks,
    salvar_chunk, ler_chunk, deletar_chunk, listar_chunks_armazenados,
    verificar_integridade_chunk, salvar_metadata_chunk, ler_metadata_chunk
)
from metadata_client2 import MetadataClient, HeartbeatSender

# Configurações do nó
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1MB
DEFAULT_METADATA_SERVER = "localhost:50052"

class ExtendedFileSystemServiceServicer(fs_grpc.FileSystemServiceServicer):
    """Servidor de armazenamento estendido com suporte a chunks e replicação"""
    
    def __init__(self, base_dir: str, node_id: str, node_port: int, 
                 metadata_server: str = DEFAULT_METADATA_SERVER,
                 chunk_size: int = DEFAULT_CHUNK_SIZE):
        self.base_dir = base_dir
        self.node_id = node_id
        self.node_port = node_port
        self.chunk_size = chunk_size
        self.metadata_server = metadata_server
        
        # Garantir que diretório base existe
        os.makedirs(base_dir, exist_ok=True)
        
        # Cliente para servidor de metadados
        self.metadata_client = None
        self.heartbeat_sender = None
        
        # Cache de conexões gRPC para outros nós de armazenamento
        self.node_connections = {}  # {node_id: (channel, stub)}
        self.connections_lock = threading.Lock()
        
        # Conectar ao servidor de metadados
        self._connect_to_metadata_server()
        
        if self.heartbeat_sender:
            initial_chunks = set(listar_chunks_armazenados(self.base_dir))
            self.heartbeat_sender.update_chunks(initial_chunks)

        print(f"Nó de armazenamento {node_id} iniciado")
        print(f"Diretório base: {base_dir}")
        print(f"Porta: {node_port}")
        print(f"Servidor de metadados: {metadata_server}")
    
    def _connect_to_metadata_server(self):
        """Conecta ao servidor de metadados e registra este nó"""
        try:
            self.metadata_client = MetadataClient(self.metadata_server)
            
            # Registrar nó no servidor de metadados
            capacidade_storage = 10 * 1024 * 1024 * 1024  # 10GB padrão
            response = self.metadata_client.register_node(
                self.node_id,
                "localhost",  # obter IP real
                self.node_port,
                capacidade_storage
            )
            
            if response and response.sucesso: # Acessa o atributo 'sucesso' do objeto gRPC
                self.node_id = response.node_id_atribuido # Acessa o atributo 'node_id_atribuido'
                print(f"Nó registrado no servidor de metadados: {self.node_id}")
                
                # Iniciar heartbeat
                self.heartbeat_sender = HeartbeatSender(
                    self.metadata_client, 
                    self.node_id, 
                    interval=15
                )
                self.heartbeat_sender.start()
                
                # Atualizar lista de chunks no heartbeat
                chunks = listar_chunks_armazenados(self.base_dir)
                self.heartbeat_sender.update_chunks(set(chunks))
            else:
                print("Erro ao registrar nó no servidor de metadados")
        except Exception as e:
            print(f"Erro ao conectar com servidor de metadados: {e}")
            self.metadata_client = None
    
    def _get_node_connection(self, node_info):
        """
        Obtém conexão gRPC com outro nó de armazenamento (com cache).
        Retorna o stub gRPC para comunicação.
        """
        node_id = node_info.node_id
        node_address = f"{node_info.endereco}:{node_info.porta}"
        
        with self.connections_lock:
            # Verificar se já existe conexão em cache
            if node_id in self.node_connections:
                channel, stub = self.node_connections[node_id]
                try:
                    # Testar se a conexão ainda está ativa
                    channel.get_state(try_to_connect=False)
                    return stub
                except:
                    # Conexão inválida, remover do cache
                    try:
                        channel.close()
                    except:
                        pass
                    del self.node_connections[node_id]
            
            # Criar nova conexão
            try:
                channel = grpc.insecure_channel(
                    node_address,
                    options=[
                        ('grpc.max_send_message_length', 1024 * 1024 * 1024),  # 1GB
                        ('grpc.max_receive_message_length', 1024 * 1024 * 1024),  # 1GB
                        ('grpc.keepalive_time_ms', 30000),
                        ('grpc.keepalive_timeout_ms', 5000),
                        ('grpc.keepalive_permit_without_calls', True)
                    ]
                )
                stub = fs_grpc.FileSystemServiceStub(channel)
                
                # Armazenar no cache
                self.node_connections[node_id] = (channel, stub)
                print(f"Nova conexão gRPC criada para nó {node_id} ({node_address})")
                
                return stub
                
            except Exception as e:
                print(f"Erro ao criar conexão com nó {node_id} ({node_address}): {e}")
                return None

    def close(self):
        """Fecha conexões e para heartbeat"""
        if self.heartbeat_sender:
            self.heartbeat_sender.stop()
        if self.metadata_client:
            self.metadata_client.close()
        
        # Fechar todas as conexões em cache
        with self.connections_lock:
            for node_id, (channel, stub) in self.node_connections.items():
                try:
                    channel.close()
                except:
                    pass
            self.node_connections.clear()
    
    # ========================================
    # MÉTODOS ORIGINAIS (usando protocolo estendido)
    # ========================================
    
    def Listar(self, request, context):
        try:
            sucesso, mensagem, tipo, conteudo = listar_conteudo(self.base_dir, request.path)
            return fs_pb2.ConteudoResponse(
                sucesso=sucesso,
                mensagem=mensagem,
                tipo=tipo or "",
                conteudo=conteudo or []
            )
        except Exception as e:
            return fs_pb2.ConteudoResponse(
                sucesso=False,
                mensagem=f"Erro interno no servidor: {str(e)}",
                tipo="",
                conteudo=[]
            )
    
    def Deletar(self, request, context):
        sucesso, mensagem = deletar_arquivo(self.base_dir, request.path)
        return fs_pb2.OperacaoResponse(
            sucesso=sucesso,
            mensagem=mensagem
        )
    
    def Upload(self, request, context):
        """
        Upload de arquivo completo com divisão automática em chunks se necessário
        Recebe um arquivo, o salva (dividindo em chunks se necessário) e registra APENAS os metadados dos chunks que ele armazena.
        """
        try:
            arquivo_nome = os.path.basename(request.path)
            dados = request.dados
            
            print(f"INFO: Processando upload para '{arquivo_nome}' no nó.")

            if not self.metadata_client:
                return fs_pb2.OperacaoResponse(sucesso=False, mensagem="Erro Crítico: Nó não conectado ao servidor de metadados.")

            # Se o arquivo for MENOR ou IGUAL ao tamanho do chunk, trate-o como um único chunk.
            if len(dados) <= self.chunk_size:
                print(f"INFO: Arquivo pequeno. Salvando como chunk único.")
                sucesso_salvar, _ = salvar_chunk(self.base_dir, arquivo_nome, 0, dados)
                if not sucesso_salvar:
                    return fs_pb2.OperacaoResponse(sucesso=False, mensagem="Falha ao salvar arquivo no disco.")
                
                # Salvar metadados locais do chunk
                metadata = {
                    'arquivo_nome': arquivo_nome,
                    'chunk_numero': 0,
                    'checksum': calcular_checksum(dados),
                    'tamanho': len(dados),
                    'timestamp': int(time.time())
                }
                
                sucesso_salvar = salvar_metadata_chunk(self.base_dir, arquivo_nome, 0, metadata)
                if not sucesso_salvar:
                    return fs_pb2.OperacaoResponse(sucesso=False, mensagem="Falha ao salvar arquivo no disco.")
                
                # Registre esse único chunk no servidor de metadados.
                checksum_chunk = calcular_checksum(dados)
                sucesso_registro = self.metadata_client.register_chunk(
                    arquivo_nome, 0, self.node_id, [], checksum_chunk, len(dados)
                )
                if not sucesso_registro:
                    return fs_pb2.OperacaoResponse(sucesso=False, mensagem="Falha ao registrar metadados do chunk.")
                
                # Atualizar heartbeat com novos chunks
                if self.heartbeat_sender:
                    chunks_atuais = listar_chunks_armazenados(self.base_dir)
                    self.heartbeat_sender.update_chunks(set(chunks_atuais))
                
                return fs_pb2.OperacaoResponse(
                        sucesso=True,
                        mensagem=f"Arquivo em chunk única salvo com sucesso"
                    )
            else:
                # Se o arquivo for GRANDE, divida-o e registre cada chunk.
                print(f"INFO: Arquivo grande. Dividindo em chunks...")
                
                chunks = dividir_arquivo_em_chunks(dados, self.chunk_size)
                total_chunks = len(chunks)
                checksum_arquivo = calcular_checksum(dados)
                tamanho_arquivo = len(dados)

                print(f"Dividindo arquivo em {total_chunks} chunks")
                
                # Registrar arquivo no servidor de metadados
                if self.metadata_client:
                    sucesso_registro = self.metadata_client.register_file(
                        arquivo_nome,
                        tamanho_arquivo,
                        total_chunks,
                        checksum_arquivo,
                        self.node_id,
                        []  # Réplicas serão adicionadas depois
                    )
                    
                    if not sucesso_registro:                    
                        return fs_pb2.OperacaoResponse(
                            sucesso=False,
                            mensagem="Erro ao registrar arquivo no servidor de metadados"
                        )
                
                # Salvar chunks
                chunks_salvos = 0
                for i, chunk_data in enumerate(chunks):
                    sucesso_chunk, mensagem_chunk = salvar_chunk(
                        self.base_dir, arquivo_nome, i, chunk_data
                    )
                    
                    if sucesso_chunk:
                        chunks_salvos += 1
                        
                        # Registrar chunk no servidor de metadados
                        if self.metadata_client:
                            checksum_chunk = calcular_checksum(chunk_data)
                            self.metadata_client.register_chunk(
                                arquivo_nome,
                                i,
                                self.node_id,
                                [],  # Réplicas serão designadas depois
                                checksum_chunk,
                                len(chunk_data)
                            )
                        # Salvar metadados locais do chunk
                        metadata = {
                            'arquivo_nome': arquivo_nome,
                            'chunk_numero': i,
                            'checksum': calcular_checksum(chunk_data),
                            'tamanho': len(chunk_data),
                            'timestamp': int(time.time())
                        }
                        salvar_metadata_chunk(self.base_dir, arquivo_nome, i, metadata)
                    else:
                        print(f"Erro ao salvar chunk {i}: {mensagem_chunk}")
                
                # Atualizar heartbeat com novos chunks
                if self.heartbeat_sender:
                    chunks_atuais = listar_chunks_armazenados(self.base_dir)
                    self.heartbeat_sender.update_chunks(set(chunks_atuais))

                if chunks_salvos == total_chunks:
                    return fs_pb2.OperacaoResponse(
                        sucesso=True,
                        mensagem=f"Arquivo dividido em {total_chunks} chunks e salvo com sucesso"
                    )
                else:
                    return fs_pb2.OperacaoResponse(
                        sucesso=False,
                        mensagem=f"Apenas {chunks_salvos}/{total_chunks} chunks foram salvos"
                    )
                
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro no upload: {str(e)}"
            )
    
    def Download(self, request, context):
        """Download de arquivo completo com recombinação de chunks se necessário"""
        try:
            arquivo_nome = os.path.basename(request.path)
            
            # Tentar ler arquivo completo primeiro
            sucesso, mensagem, dados = ler_arquivo(self.base_dir, request.path)
            if sucesso:
                return fs_pb2.FileDownloadResponse(
                    sucesso=True,
                    mensagem="Arquivo lido com sucesso",
                    dados=dados
                )
            
            # Se não encontrou arquivo completo, tentar recombinar chunks
            if self.metadata_client:
                chunks_info = self.metadata_client.get_chunk_locations(arquivo_nome)
                if chunks_info:
                    print(f"Recombinando {len(chunks_info)} chunks para {arquivo_nome}")
                    chunks_dados = []
                    for chunk_info in sorted(chunks_info, key=lambda x: x.chunk_numero):               
                        chunk_numero = chunk_info.chunk_numero              
                        sucesso_chunk, _, dados_chunk = ler_chunk(self.base_dir, arquivo_nome, chunk_numero)
                        
                        if sucesso_chunk:
                            chunks_dados.append(dados_chunk)
                        else:
                            return fs_pb2.FileDownloadResponse(
                                sucesso=False,
                                mensagem=f"Erro ao ler chunk {chunk_numero}",
                                dados=b""
                            )
                    
                    # Recombinar chunks
                    dados_completos = recombinar_chunks(chunks_dados)
                    
                    return fs_pb2.FileDownloadResponse(
                        sucesso=True,
                        mensagem="Arquivo recombinado com sucesso",
                        dados=dados_completos
                    )
            
            return fs_pb2.FileDownloadResponse(
                sucesso=False,
                mensagem="Arquivo não encontrado",
                dados=b""
            )
            
        except Exception as e:
            return fs_pb2.FileDownloadResponse(
                sucesso=False,
                mensagem=f"Erro no download: {str(e)}",
                dados=b""
            )
    
    def CopiarInterno(self, request, context):
        sucesso, mensagem = copiar_arquivo(self.base_dir, request.origem, request.destino)
        return fs_pb2.OperacaoResponse(
            sucesso=sucesso,
            mensagem=mensagem
        )
    
    def Copiar(self, request, context):
        # Alias para CopiarInterno
        return self.CopiarInterno(request, context)
    
    # ========================================
    # NOVOS MÉTODOS PARA CHUNKS
    # ========================================
    
    def UploadChunk(self, request, context):
        """Upload de um chunk específico"""
        try:
            sucesso, mensagem = salvar_chunk(
                self.base_dir,
                request.arquivo_nome,
                request.chunk_numero,
                request.dados
            )
            
            if sucesso:
                # Verificar checksum
                checksum_calculado = calcular_checksum(request.dados)
                if checksum_calculado != request.checksum:
                    # Remover chunk com checksum inválido
                    deletar_chunk(self.base_dir, request.arquivo_nome, request.chunk_numero)
                    return fs_pb2.OperacaoResponse(
                        sucesso=False,
                        mensagem="Checksum do chunk não confere"
                    )
                
                # Salvar metadados locais
                metadata = {
                    'arquivo_nome': request.arquivo_nome,
                    'chunk_numero': request.chunk_numero,
                    'checksum': request.checksum,
                    'tamanho': len(request.dados),
                    'timestamp': int(time.time())
                }
                salvar_metadata_chunk(
                    self.base_dir, 
                    request.arquivo_nome, 
                    request.chunk_numero, 
                    metadata
                )
                
                # NOVA ARQUITETURA: Registrar chunk no servidor de metadados
                if self.metadata_client:
                    try:
                        registro_sucesso = self.metadata_client.register_chunk(
                            request.arquivo_nome,
                            request.chunk_numero,
                            self.node_id,  # Este nó como primário
                            [],  # Réplicas serão designadas pelo servidor
                            request.checksum,
                            len(request.dados)
                        )
                        
                        if not registro_sucesso:
                            print(f"⚠️ Falha ao registrar chunk {request.chunk_numero} no servidor de metadados")
                            # Não falhar o upload por isso, mas logar o problema
                        else:
                            print(f"✅ Chunk {request.chunk_numero} registrado no servidor de metadados")
                    except Exception as e:
                        print(f"❌ Erro ao registrar chunk no servidor de metadados: {e}")
                
                # Atualizar heartbeat
                if self.heartbeat_sender:
                    chunks_atuais = set(listar_chunks_armazenados(self.base_dir))
                    self.heartbeat_sender.update_chunks(chunks_atuais)
                
                # NOVA FUNCIONALIDADE: Iniciar replicação em thread separada
                if self.metadata_client:
                    threading.Thread(
                        target=self._iniciar_replicacao_chunk,
                        args=(request.arquivo_nome, request.chunk_numero, request.dados, request.checksum),
                        daemon=True
                    ).start()
            
            return fs_pb2.OperacaoResponse(
                sucesso=sucesso,
                mensagem=mensagem
            )
            
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro no upload do chunk: {str(e)}"
            )
    
    def DownloadChunk(self, request, context):
        """Download de um chunk específico"""
        try:
            sucesso, mensagem, dados = ler_chunk(
                self.base_dir,
                request.arquivo_nome,
                request.chunk_numero
            )
            
            checksum = ""
            if sucesso and dados:
                checksum = calcular_checksum(dados)
            
            return fs_pb2.ChunkDownloadResponse(
                sucesso=sucesso,
                mensagem=mensagem,
                dados=dados or b"",
                checksum=checksum
            )
            
        except Exception as e:
            return fs_pb2.ChunkDownloadResponse(
                sucesso=False,
                mensagem=f"Erro no download do chunk: {str(e)}",
                dados=b"",
                checksum=""
            )
    
    def DeleteChunk(self, request, context):
        """Deleta um chunk específico"""
        try:
            sucesso, mensagem = deletar_chunk(
                self.base_dir,
                request.arquivo_nome,
                request.chunk_numero
            )
            
            # Atualizar heartbeat
            if sucesso and self.heartbeat_sender:
                chunks_atuais = listar_chunks_armazenados(self.base_dir)
                self.heartbeat_sender.update_chunks(set(chunks_atuais))
            
            return fs_pb2.OperacaoResponse(
                sucesso=sucesso,
                mensagem=mensagem
            )
            
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro ao deletar chunk: {str(e)}"
            )
    
    def _iniciar_replicacao_chunk(self, arquivo_nome, chunk_numero, dados, checksum):
        """
        Método auxiliar para iniciar a replicação de um chunk para os nós de réplica.
        Executa em thread separada para não bloquear a resposta ao cliente.
        """
        try:
            print(f"Iniciando replicação do chunk {arquivo_nome}:{chunk_numero}")
            
            # Consultar o MetadataServer para obter a lista de nós de réplica
            chunk_info_response = self.metadata_client.get_chunk_info(arquivo_nome, chunk_numero)
            if not chunk_info_response or not chunk_info_response.sucesso:
                print(f"AVISO: Não foi possível obter informações para o chunk {arquivo_nome}:{chunk_numero}. Mensagem: {chunk_info_response.mensagem if chunk_info_response else 'Erro desconhecido'}")
                return
            
            chunk_info = chunk_info_response.metadata
            if not chunk_info or not hasattr(chunk_info, 'replicas'):
                print(f"Nenhum metadado de chunk ou réplica encontrado para {arquivo_nome}:{chunk_numero}")
                return
            
            # Filtrar réplicas com status PENDING
            nos_replica_pendentes = [r for r in chunk_info.replicas if r.status == fs_pb2.ReplicaStatus.PENDING]

            if not nos_replica_pendentes:
                print(f"Nenhum nó de réplica PENDING encontrado para {arquivo_nome}:{chunk_numero}")
                return
            
            # Conectar a cada nó de réplica e enviar o chunk
            for replica_info in nos_replica_pendentes:
                try:
                    replica_node_id = replica_info.node_id
                    print(f"Replicando chunk para nó {replica_node_id}")
                    
                    # Obter informações completas do nó de réplica do servidor de metadados
                    replica_node_info_response = self.metadata_client.get_node_info(replica_node_id)
                    if not replica_node_info_response or not replica_node_info_response.sucesso:
                        print(f"Informações do nó {replica_node_id} não encontradas no servidor de metadados")
                        continue
                    
                    replica_node_info = replica_node_info_response.node_info
                    
                    # Usar conexão em cache para o nó de réplica
                    stub = self._get_node_connection(replica_node_info)
                    if not stub:
                        print(f"Não foi possível conectar ao nó {replica_node_id}")
                        continue
                    
                    # Criar request de replicação
                    request = fs_pb2.ReplicarChunkRequest(
                        arquivo_nome=arquivo_nome,
                        chunk_numero=chunk_numero,
                        dados=dados,
                        checksum=checksum,
                        timestamp=int(time.time()),
                        no_origem=self.node_id
                    )
                    
                    # Enviar réplica com timeout
                    response = stub.ReplicarChunk(request, timeout=30)
                    
                    if response.sucesso:
                        print(f"Réplica enviada com sucesso para {replica_node_id}")
                        
                        # Confirmar réplica no servidor de metadados
                        try:
                            confirmacao_sucesso = self.metadata_client.confirmar_replica(
                                arquivo_nome, chunk_numero, replica_node_id
                            )
                            if confirmacao_sucesso:
                                print(f"✅ Réplica {replica_node_id} confirmada no servidor de metadados")
                            else:
                                print(f"⚠️ Falha ao confirmar réplica {replica_node_id} no servidor de metadados")
                        except Exception as e:
                            print(f"❌ Erro ao confirmar réplica {replica_node_id}: {e}")
                    else:
                        print(f"Erro ao enviar réplica para {replica_node_id}: {response.mensagem}")
                    
                except Exception as e:
                    print(f"Erro ao replicar chunk para {replica_node_id}: {str(e)}")
            
        except Exception as e:
            print(f"Erro geral na replicação do chunk {arquivo_nome}:{chunk_numero}: {str(e)}")

    # ========================================
    # MÉTODOS DE REPLICAÇÃO
    # ========================================
    
    def ReplicarChunk(self, request, context):
        """Recebe uma réplica de chunk de outro nó"""
        try:
            # Salvar chunk replicado
            sucesso, mensagem = salvar_chunk(
                self.base_dir,
                request.arquivo_nome,
                request.chunk_numero,
                request.dados
            )
            
            if sucesso:
                # Verificar checksum
                checksum_calculado = calcular_checksum(request.dados)
                if checksum_calculado != request.checksum:
                    deletar_chunk(self.base_dir, request.arquivo_nome, request.chunk_numero)
                    return fs_pb2.OperacaoResponse(
                        sucesso=False,
                        mensagem="Checksum da réplica não confere"
                    )
                
                # Salvar metadados da réplica
                metadata = {
                    'arquivo_nome': request.arquivo_nome,
                    'chunk_numero': request.chunk_numero,
                    'checksum': request.checksum,
                    'tamanho': len(request.dados),
                    'timestamp': request.timestamp,
                    'no_origem': request.no_origem,
                    'tipo': 'replica'
                }
                salvar_metadata_chunk(
                    self.base_dir,
                    request.arquivo_nome,
                    request.chunk_numero,
                    metadata
                )
                
                # Atualizar heartbeat
                if self.heartbeat_sender:
                    chunks_atuais = set(listar_chunks_armazenados(self.base_dir))
                    self.heartbeat_sender.update_chunks(chunks_atuais)
                
                print(f"Réplica do chunk {request.arquivo_nome}:{request.chunk_numero} recebida de {request.no_origem}")
            
            return fs_pb2.OperacaoResponse(
                sucesso=sucesso,
                mensagem=mensagem
            )
            
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro na replicação: {str(e)}"
            )
    
    def SincronizarReplica(self, request, context):
        """Sincroniza uma réplica desatualizada"""
        try:
            # Verificar se temos o chunk
            sucesso, _, dados = ler_chunk(
                self.base_dir,
                request.arquivo_nome,
                request.chunk_numero
            )
            
            if not sucesso:
                return fs_pb2.OperacaoResponse(
                    sucesso=False,
                    mensagem="Chunk não encontrado para sincronização"
                )
            
            # Verificar checksum
            checksum_atual = calcular_checksum(dados)
            if checksum_atual != request.checksum_esperado:
                return fs_pb2.OperacaoResponse(
                    sucesso=False,
                    mensagem="Checksum não confere - chunk pode estar corrompido"
                )
            
            # Chunk está correto
            return fs_pb2.OperacaoResponse(
                sucesso=True,
                mensagem="Chunk já está sincronizado"
            )
            
        except Exception as e:
            return fs_pb2.OperacaoResponse(
                sucesso=False,
                mensagem=f"Erro na sincronização: {str(e)}"
            )
    
    # ========================================
    # MÉTODOS DE MONITORAMENTO
    # ========================================
    
    def Heartbeat(self, request, context):
        """Responde a heartbeat de outro nó ou cliente"""
        return fs_pb2.HeartbeatResponse(
            sucesso=True,
            mensagem=f"Heartbeat recebido de {request.node_id}",
            server_timestamp=int(time.time())
        )
    
    def VerificarIntegridade(self, request, context):
        """Verifica a integridade de um chunk, buscando o checksum esperado
        diretamente do servidor de metadados.
        """
        try:
            print(f"INFO: Recebida verificação de integridade para {request.arquivo_nome}:{request.chunk_numero}")
            # 1. Obter o checksum esperado DO SERVIDOR DE METADADOS.
            if not self.metadata_client:
                return fs_pb2.IntegrityResponse(sucesso=False, mensagem="Erro Crítico: Nó não conectado ao servidor de metadados.")

            chunk_info_response = self.metadata_client.get_chunk_info(request.arquivo_nome, request.chunk_numero)
            
            if not chunk_info_response or not chunk_info_response.sucesso:
                return fs_pb2.IntegrityResponse(sucesso=False, mensagem=f"Não foi possível obter os metadados do chunk do servidor. Mensagem: {chunk_info_response.mensagem if chunk_info_response else 'Erro desconhecido'}")

            checksum_esperado = chunk_info_response.metadata.checksum

            # 2. Ler os dados do chunk localmente.
            sucesso, mensagem, dados_chunk = ler_chunk(
                self.base_dir,
                request.arquivo_nome,
                request.chunk_numero
            )
            if not sucesso:
                return fs_pb2.IntegrityResponse(sucesso=False, mensagem=mensagem, integridade_ok=False)

            # 3. Calcular o checksum atual e comparar.
            checksum_atual = calcular_checksum(dados_chunk)
            integridade_ok = (checksum_atual == checksum_esperado)
            
            msg_final = "Integridade OK." if integridade_ok else "Checksum não confere!"
            
            return fs_pb2.IntegrityResponse(
                sucesso=True,
                mensagem=msg_final,
                checksum_atual=checksum_atual,
                integridade_ok=integridade_ok
            )
            
        except Exception as e:
            return fs_pb2.IntegrityResponse(
                sucesso=False,
                mensagem=f"Erro na verificação: {str(e)}",
                checksum_atual="",
                timestamp_modificacao=0,
                integridade_ok=False
            )


def serve(port=50051, node_id=None, metadata_server=DEFAULT_METADATA_SERVER, 
          storage_dir=None, chunk_size=DEFAULT_CHUNK_SIZE):
    """Inicia o servidor de armazenamento"""
    
    # Configurar diretório de armazenamento
    if storage_dir is None:
        storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../storage_node_{port}"))
    
    # Configurar node_id
    if node_id is None:
        node_id = f"node_{port}_{int(time.time())}"
    
    # Criar servicer
    servicer = ExtendedFileSystemServiceServicer(
        storage_dir, node_id, port, metadata_server, chunk_size
    )
    
    # Configurar servidor gRPC
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=[
            ('grpc.max_send_message_length', 1024 * 1024 * 1024),  # 1GB
            ('grpc.max_receive_message_length', 1024 * 1024 * 1024)  # 1GB
        ]
    )
    
    # Adicionar serviço estendido
    fs_grpc.add_FileSystemServiceServicer_to_server(servicer, server)
    
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    
    print("Conectando ao servidor...")
    time.sleep(1)

    print(f"Servidor rodando na porta {port} - " + time.strftime("%d-%m-%Y às %H:%M:%S"))
    print("Pressione Ctrl+C para parar o servidor.")
    try:
        channel = grpc.insecure_channel("localhost:50052")
        grpc.channel_ready_future(channel).result(timeout=3)
        print("✅ Conectado ao metadata server!")
    except Exception as e:
        print("❌ Falha ao conectar:", e)
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        print("Encerrando servidor...")
    finally:
        servicer.close()
        server.stop(0)
        print("Servidor parado.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Servidor de Armazenamento BigFS-v2")
    parser.add_argument("--port", type=int, default=50051, help="Porta do servidor (padrão: 50051)")
    parser.add_argument("--node-id", help="ID do nó (padrão: auto-gerado)")
    parser.add_argument("--metadata-server", default=DEFAULT_METADATA_SERVER, 
                       help=f"Endereço do servidor de metadados (padrão: {DEFAULT_METADATA_SERVER})")
    parser.add_argument("--storage-dir", help="Diretório de armazenamento (padrão: auto-gerado)")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                       help=f"Tamanho do chunk em bytes (padrão: {DEFAULT_CHUNK_SIZE})")
    
    args = parser.parse_args()
    serve(args.port, args.node_id, args.metadata_server, args.storage_dir, args.chunk_size)



