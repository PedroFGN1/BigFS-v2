import os
import sys
import time
import threading
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from collections import defaultdict

# Adiciona o diretório proto ao sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))

import grpc
from concurrent import futures
import filesystem_extended_pb2 as fs_pb2
import filesystem_extended_pb2_grpc as fs_grpc


@dataclass
class FileMetadata:
    """Metadados de um arquivo no sistema"""
    nome_arquivo: str
    tamanho_total: int
    total_chunks: int
    checksum_arquivo: str
    timestamp_criacao: int
    timestamp_modificacao: int
    no_primario: str
    nos_replicas: List[str]
    esta_completo: bool = False
    status: str = "ativo"  # ativo, deletando, completo



@dataclass
class ChunkMetadata:
    """Metadados de um chunk específico"""
    arquivo_nome: str
    chunk_numero: int
    no_primario: str
    replicas: List[str]  # Lista de réplicas com seus estados
    checksum: str
    tamanho_chunk: int
    timestamp_criacao: int
    disponivel: bool = True
    status: str = "ativo"  # ativo, deletando

@dataclass
class NodeInfo:
    """Informações sobre um nó de armazenamento"""
    node_id: str
    endereco: str
    porta: int
    status: str  # ATIVO, OCUPADO, MANUTENCAO, FALHA
    capacidade_storage: int
    storage_usado: int
    ultimo_heartbeat: int
    chunks_armazenados: Set[str]  # Set de "arquivo:chunk" 
    
    def __post_init__(self):
        if isinstance(self.chunks_armazenados, list):
            self.chunks_armazenados = set(self.chunks_armazenados)

class MetadataManager:
    """Gerenciador central de metadados do sistema"""
    
    def __init__(self, data_dir: str = "metadata_storage"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Estruturas de dados em memória
        self.files: Dict[str, FileMetadata] = {}
        self.chunks: Dict[str, ChunkMetadata] = {}  # Key: "arquivo:chunk_numero"
        self.nodes: Dict[str, NodeInfo] = {}
        
        # Estatísticas do sistema
        self.stats = {
            'operacoes_upload_total': 0,
            'operacoes_download_total': 0,
            'operacoes_delete_total': 0,
            'falhas_detectadas': 0,
            'replicacoes_realizadas': 0,
            'tempo_medio_upload': 0.0,
            'tempo_medio_download': 0.0
        }
        
        # Lock para operações thread-safe
        self.lock = threading.RLock()
        
        # Carregar dados persistidos
        self._load_metadata()
        self.storage_node_stubs = {} # Adicione um cache de stubs para nós de armazenamento

        # Iniciar thread de monitoramento de heartbeats
        self.heartbeat_timeout = 30  # 30 segundos
        self.monitoring_thread = threading.Thread(target=self._monitor_heartbeats, daemon=True)
        self.monitoring_thread.start()
        
        # Iniciar thread de limpeza (garbage collection)
        self.cleanup_thread = threading.Thread(target=self._cleanup_deleted_files, daemon=True)
        self.cleanup_thread.start()
        
        # Iniciar thread de garbage collection para uploads incompletos
        self.gc_thread = threading.Thread(target=self._garbage_collect_incomplete_uploads, daemon=True)
        self.gc_thread.start()
    
    def _load_metadata(self):
        """Carrega metadados persistidos do disco"""
        try:
            # Carregar arquivos
            files_path = os.path.join(self.data_dir, "files.json")
            if os.path.exists(files_path):
                with open(files_path, 'r') as f:
                    files_data = json.load(f)
                    for name, data in files_data.items():
                        self.files[name] = FileMetadata(**data)
            
            # Carregar chunks
            chunks_path = os.path.join(self.data_dir, "chunks.json")
            if os.path.exists(chunks_path):
                with open(chunks_path, 'r') as f:
                    chunks_data = json.load(f)
                    for key, data in chunks_data.items():
                        # Converte a lista de dicionários de réplicas de volta para uma lista de objetos ReplicaInfo
                        if 'replicas' in data and isinstance(data['replicas'], list):
                            # Agora, ReplicaInfo é um objeto Protobuf, não um dataclass
                            replicas_pb_list = []
                            for replica_dict in data['replicas']:
                                replica_pb = fs_pb2.ReplicaInfo()
                                replica_pb.node_id = replica_dict['node_id']
                                # Mapear string para enum Protobuf
                                if replica_dict['status'] == 'PENDING':
                                    replica_pb.status = fs_pb2.ReplicaStatus.PENDING
                                elif replica_dict['status'] == 'AVAILABLE':
                                    replica_pb.status = fs_pb2.ReplicaStatus.AVAILABLE
                                elif replica_dict['status'] == 'DELETING':
                                    replica_pb.status = fs_pb2.ReplicaStatus.DELETING
                                replicas_pb_list.append(replica_pb)
                            data['replicas'] = replicas_pb_list
                        else:
                            # Garante que o campo 'replicas' exista mesmo que vazio
                            data['replicas'] = []

                        # Remove o campo antigo se ele ainda existir no JSON por acidente
                        data.pop('nos_replicas', None)
                        
                        self.chunks[key] = ChunkMetadata(**data)
            
            # Carregar nós
            nodes_path = os.path.join(self.data_dir, "nodes.json")
            if os.path.exists(nodes_path):
                with open(nodes_path, 'r') as f:
                    nodes_data = json.load(f)
                    for node_id, data in nodes_data.items():
                        data['chunks_armazenados'] = set(data.get('chunks_armazenados', []))
                        self.nodes[node_id] = NodeInfo(**data)
                        
        except Exception as e:
            print(f"Erro ao carregar metadados: {e}")
    
    def _save_metadata(self):
        """Persiste metadados no disco"""
        try:
            # Salvar arquivos
            files_data = {name: asdict(metadata) for name, metadata in self.files.items()}
            with open(os.path.join(self.data_dir, "files.json"), 'w') as f:
                json.dump(files_data, f, indent=2)
            
            # Salvar chunks
            chunks_data = {}
            for key, metadata in self.chunks.items():
                # Converter objetos ReplicaInfo de Protobuf para dicionários para serialização JSON
                chunk_dict = asdict(metadata)
                if 'replicas' in chunk_dict:
                    chunk_dict['replicas'] = [
                        {'node_id': r.node_id, 'status': fs_pb2.ReplicaStatus.Name(r.status)}
                        for r in metadata.replicas
                    ]
                chunks_data[key] = chunk_dict
            with open(os.path.join(self.data_dir, "chunks.json"), 'w') as f:
                json.dump(chunks_data, f, indent=2)
            
            # Salvar nós
            nodes_data = {}
            for node_id, node_info in self.nodes.items():
                data = asdict(node_info)
                data['chunks_armazenados'] = list(node_info.chunks_armazenados)
                nodes_data[node_id] = data
            with open(os.path.join(self.data_dir, "nodes.json"), 'w') as f:
                json.dump(nodes_data, f, indent=2)
                
        except Exception as e:
            print(f"Erro ao salvar metadados: {e}")
    
    def _monitor_heartbeats(self):
        """Thread que monitora heartbeats dos nós"""
        while True:
            try:
                current_time = int(time.time())
                with self.lock:
                    for node_id, node_info in self.nodes.items():
                        if (node_info.status == "ATIVO" and 
                            current_time - node_info.ultimo_heartbeat > self.heartbeat_timeout):
                            print(f"Nó {node_id} não responde há {current_time - node_info.ultimo_heartbeat}s. Marcando como FALHA.")
                            node_info.status = "FALHA"
                            self.stats['falhas_detectadas'] += 1
                            self._save_metadata()
                
                time.sleep(10)  # Verifica a cada 10 segundos
            except Exception as e:
                print(f"Erro no monitoramento de heartbeats: {e}")
                time.sleep(10)
    
    def _get_chunk_key(self, arquivo_nome: str, chunk_numero: int) -> str:
        """Gera chave única para um chunk"""
        return f"{arquivo_nome}:{chunk_numero}"
    
    def _hash_for_node_selection(self, data: str) -> int:
        """Gera hash para seleção de nó usando hashing consistente"""
        return int(hashlib.md5(data.encode()).hexdigest(), 16)
    
    def _select_nodes_for_chunk(self, arquivo_nome: str, chunk_numero: int, 
                               num_replicas: int = 2) -> List[str]:
        """Seleciona nós para armazenar um chunk usando hashing consistente"""
        with self.lock:
            active_nodes = [node_id for node_id, node in self.nodes.items() 
                           if node.status == "ATIVO"]
            
            if len(active_nodes) == 0:
                return []
            
            # Usar hash do nome do arquivo + chunk para distribuição consistente
            chunk_key = self._get_chunk_key(arquivo_nome, chunk_numero)
            hash_value = self._hash_for_node_selection(chunk_key)
            
            # Selecionar nó primário
            primary_index = hash_value % len(active_nodes)
            selected_nodes = [active_nodes[primary_index]]
            
            # Selecionar nós para réplicas (evitando o primário)
            for i in range(1, min(num_replicas + 1, len(active_nodes))):
                replica_index = (primary_index + i) % len(active_nodes)
                selected_nodes.append(active_nodes[replica_index])
            
            return selected_nodes
        
    def _get_storage_node_stub(self, node_info: NodeInfo):
        """Cria um cache de um stub gRPC para um nó de armazenamento."""
        node_address = f"{node_info.endereco}:{node_info.porta}"
        if node_address not in self.storage_node_stubs:
            channel = grpc.insecure_channel(node_address)
            self.storage_node_stubs[node_address] = fs_grpc.FileSystemServiceStub(channel)
        return self.storage_node_stubs[node_address]
    
    def register_file(self, file_metadata: FileMetadata) -> bool:
        """Registra um novo arquivo no sistema"""
        try:
            with self.lock:
                self.files[file_metadata.nome_arquivo] = file_metadata
                self._save_metadata()
                return True
        except Exception as e:
            print(f"Erro ao registrar arquivo {file_metadata.nome_arquivo}: {e}")
            return False
    
    def get_file_metadata(self, nome_arquivo: str) -> Optional[FileMetadata]:
        """Obtém metadados de um arquivo"""
        with self.lock:
            return self.files.get(nome_arquivo)
    
    def remove_file(self, nome_arquivo: str) -> bool:
        """Remove um arquivo de forma segura (soft delete)"""
        try:
            with self.lock:
                if nome_arquivo not in self.files:
                    return False
                
                # Marcar arquivo para deleção em vez de apagar imediatamente
                self.files[nome_arquivo].status = "deletando"
                self.files[nome_arquivo].timestamp_modificacao = int(time.time())
                
                # Marcar chunks para deleção
                chunks_to_mark = self.get_chunk_locations(nome_arquivo)
                for chunk_metadata in chunks_to_mark:
                    chunk_key = self._get_chunk_key(chunk_metadata.arquivo_nome, chunk_metadata.chunk_numero)
                    if chunk_key in self.chunks:
                        self.chunks[chunk_key].status = "deletando"
                
                self._save_metadata()
                self.stats['operacoes_delete_total'] += 1
                print(f"INFO: Arquivo '{nome_arquivo}' marcado para deleção.")
                return True
                
        except Exception as e:
            print(f"ERRO: Falha ao marcar arquivo para deleção: {e}")
            return False
    
    def register_chunk(self, chunk_metadata: ChunkMetadata) -> bool:
        """Registra um chunk no sistema e designa réplicas automaticamente"""
        try:
            with self.lock:
                chunk_key = self._get_chunk_key(chunk_metadata.arquivo_nome, 
                                               chunk_metadata.chunk_numero)
                
                # NOVA ARQUITETURA: Designar réplicas automaticamente
                # O nó primário já está definido (quem enviou o chunk)
                primary_node_id = chunk_metadata.no_primario
                
                # Selecionar nós para réplicas, excluindo o nó primário
                replica_nodes = self._select_replica_nodes_for_chunk(
                    chunk_metadata.arquivo_nome, 
                    chunk_metadata.chunk_numero,
                    exclude_node=primary_node_id,
                    num_replicas=2
                )
                
                # Atualizar os metadados do chunk com as réplicas designadas
                chunk_metadata.replicas.extend(replica_nodes)
                
                replica_ids = [r.node_id for r in replica_nodes]
                print(f"✅ Chunk {chunk_key} registrado - Primário: {primary_node_id}, Réplicas: {replica_ids} (PENDING)")
                
                # Salvar os metadados do chunk
                self.chunks[chunk_key] = chunk_metadata
                
                # Atualizar informações dos nós
                # Atualizar nó primário
                if chunk_metadata.no_primario in self.nodes:
                    self.nodes[chunk_metadata.no_primario].chunks_armazenados.add(chunk_key)
                    self.nodes[chunk_metadata.no_primario].storage_usado += chunk_metadata.tamanho_chunk
                
                # Atualizar nós de réplicas
                for replica_info in chunk_metadata.replicas:
                    if replica_info.node_id in self.nodes:
                        self.nodes[replica_info.node_id].chunks_armazenados.add(chunk_key)
                        self.nodes[replica_info.node_id].storage_usado += chunk_metadata.tamanho_chunk
                
                self._save_metadata()
                return True
        except Exception as e:
            print(f"Erro ao registrar chunk {chunk_key}: {e}")
            return False
    
    def _select_replica_nodes_for_chunk(self, arquivo_nome: str, chunk_numero: int, 
                                       exclude_node: str, num_replicas: int = 2) -> List[fs_pb2.ReplicaInfo]:
        """Seleciona nós para réplicas de um chunk, excluindo o nó primário"""
        with self.lock:
            active_nodes = [node_id for node_id, node in self.nodes.items() 
                           if node.status == "ATIVO" and node_id != exclude_node]
            
            if len(active_nodes) == 0:
                return []
            
            # Usar hash do nome do arquivo + chunk para distribuição consistente
            chunk_key = self._get_chunk_key(arquivo_nome, chunk_numero)
            hash_value = self._hash_for_node_selection(chunk_key + exclude_node)  # Incluir nó primário no hash
            
            # Selecionar nós para réplicas
            selected_replicas = []
            for i in range(min(num_replicas, len(active_nodes))):
                replica_index = (hash_value + i) % len(active_nodes)
                replica_info = fs_pb2.ReplicaInfo(
                    node_id=active_nodes[replica_index],
                    status=fs_pb2.ReplicaStatus.PENDING  # Inicialmente PENDING
                )
                selected_replicas.append(replica_info)
            
            return selected_replicas
    
    def confirmar_replica(self, arquivo_nome: str, chunk_numero: int, replica_id: str) -> bool:
        """Confirma que uma réplica foi criada com sucesso, mudando seu status para AVAILABLE"""
        try:
            with self.lock:
                chunk_key = self._get_chunk_key(arquivo_nome, chunk_numero)
                
                if chunk_key not in self.chunks:
                    print(f"❌ Chunk {chunk_key} não encontrado para confirmação de réplica")
                    return False
                
                chunk_metadata = self.chunks[chunk_key]
                
                # Procurar a réplica na lista e atualizar seu status
                replica_found = False
                for replica_info in chunk_metadata.replicas:
                    if replica_info.node_id == replica_id:
                        if replica_info.status == fs_pb2.ReplicaStatus.PENDING:
                            replica_info.status = fs_pb2.ReplicaStatus.AVAILABLE
                            replica_found = True
                            print(f"✅ Réplica {replica_id} confirmada para chunk {chunk_key}")
                            break
                        else:
                            print(f"⚠️ Réplica {replica_id} já está no status {fs_pb2.ReplicaStatus.Name(replica_info.status)}")
                            return True  # Já confirmada
                
                if not replica_found:
                    print(f"❌ Réplica {replica_id} não encontrada para chunk {chunk_key}")
                    return False
                
                # Salvar metadados atualizados
                self._save_metadata()
                return True
                
        except Exception as e:
            print(f"❌ Erro ao confirmar réplica {replica_id} para chunk {arquivo_nome}:{chunk_numero}: {e}")
            return False
    
    def get_chunk_locations(self, nome_arquivo: str) -> List[ChunkMetadata]:
        """Obtém localização de todos os chunks de um arquivo"""
        with self.lock:
            chunks = []
            for key, chunk_metadata in self.chunks.items():
                if chunk_metadata.arquivo_nome == nome_arquivo:
                    chunks.append(chunk_metadata)
            
            # Ordenar por número do chunk
            chunks.sort(key=lambda x: x.chunk_numero)
            return chunks
    
    def register_node(self, node_info: NodeInfo) -> str:
        """Registra um novo nó no sistema"""
        try:
            with self.lock:
                # Se node_id não foi fornecido, gerar um
                if not node_info.node_id:
                    node_info.node_id = f"node_{len(self.nodes) + 1}_{int(time.time())}"
                
                node_info.ultimo_heartbeat = int(time.time())
                self.nodes[node_info.node_id] = node_info
                self._save_metadata()
                
                print(f"Nó {node_info.node_id} registrado: {node_info.endereco}:{node_info.porta}")
                return node_info.node_id
        except Exception as e:
            print(f"Erro ao registrar nó: {e}")
            return ""
    
    def get_available_nodes(self, status_filter: str = "ATIVO") -> List[NodeInfo]:
        """Obtém lista de nós disponíveis"""
        with self.lock:
            if status_filter:
                return [node for node in self.nodes.values() if node.status == status_filter]
            else:
                return list(self.nodes.values())
    
    def report_node_failure(self, node_id: str, reason: str) -> bool:
        """Reporta falha de um nó"""
        try:
            with self.lock:
                if node_id in self.nodes:
                    self.nodes[node_id].status = "FALHA"
                    self.stats['falhas_detectadas'] += 1
                    self._save_metadata()
                    print(f"Falha reportada para nó {node_id}: {reason}")
                    return True
                return False
        except Exception as e:
            print(f"Erro ao reportar falha do nó {node_id}: {e}")
            return False
    
    def process_heartbeat(self, node_id: str, status: str, chunks_armazenados: List[str]) -> bool:
        """Processa heartbeat de um nó"""
        try:
            with self.lock:
                if node_id in self.nodes:
                    print(f"Heartbeat recebido em process_heartbeat do nó {node_id} com status {status}")
                    node = self.nodes[node_id]
                    node.ultimo_heartbeat = int(time.time())
                    node.status = status
                    # A lista de chunks do nó é a VERDADE. Atualizamos a lista do nó diretamente.
                    chunks_reais = set(chunks_armazenados)
                    if node.chunks_armazenados != chunks_reais:
                        print(f"INFO: Reconciliando estado do nó {node_id} via heartbeat.")
                        node.chunks_armazenados = chunks_reais

                        # Recalcula o espaço utilizado com base nos chunks que o nó reportou ter.
                        storage_recalculado = 0
                        for chunk_key in node.chunks_armazenados:
                            # Verificamos se o chunk é conhecido pelo servidor de metadados.
                            # Se não for, é um "chunk órfão" que precisa ser investigado.
                            if chunk_key in self.chunks:
                                storage_recalculado += self.chunks[chunk_key].tamanho_chunk
                            else:
                                # chunk órfão!
                                print(f"AVISO: Nó {node_id} reportou um chunk ('{chunk_key}') que é desconhecido pelo servidor de metadados. Pode ser de um upload incompleto.")
                        
                        # Atualiza o storage usado do nó com o valor recalculado
                        node.storage_usado = storage_recalculado

                        # Salva os metadados no disco para refletir a mudança imediatamente.
                        self._save_metadata()
                    
                    return True
                return False
        except Exception as e:
            print(f"Erro ao processar heartbeat do nó {node_id}: {e}")
            return False
    
    def get_node_for_operation(self, tipo_operacao: str, arquivo_nome: str, 
                              chunk_numero: int = -1) -> Optional[NodeInfo]:
        """Obtém o melhor nó para uma operação"""
        with self.lock:
            if chunk_numero >= 0:
                # Operação em chunk específico
                chunk_key = self._get_chunk_key(arquivo_nome, chunk_numero)
                if chunk_key in self.chunks:
                    chunk_metadata = self.chunks[chunk_key]
                    
                    # Tentar nó primário primeiro
                    if (chunk_metadata.no_primario in self.nodes and 
                        self.nodes[chunk_metadata.no_primario].status == "ATIVO"):
                        return self.nodes[chunk_metadata.no_primario]
                    
                    # Tentar réplicas
                    for replica_info in chunk_metadata.replicas:
                        if (replica_info.node_id in self.nodes and 
                            self.nodes[replica_info.node_id].status == "ATIVO"):
                            return self.nodes[replica_info.node_id]
            else:
                # Operação em arquivo completo - selecionar nó com mais espaço disponível
                active_nodes = [node for node in self.nodes.values() if node.status == "ATIVO"]
                if active_nodes:
                    # Ordenar por espaço disponível (capacidade - usado)
                    active_nodes.sort(key=lambda n: n.capacidade_storage - n.storage_usado, reverse=True)
                    return active_nodes[0]
            
            return None
    
    def get_available_replicas(self, arquivo_nome: str, chunk_numero: int, 
                              failed_node: str = None) -> List[NodeInfo]:
        """Obtém réplicas disponíveis para um chunk"""
        with self.lock:
            chunk_key = self._get_chunk_key(arquivo_nome, chunk_numero)
            if chunk_key not in self.chunks:
                return []
            
            chunk_metadata = self.chunks[chunk_key]
            available_replicas = []
            
            # Verificar nó primário
            if (chunk_metadata.no_primario != failed_node and 
                chunk_metadata.no_primario in self.nodes and
                self.nodes[chunk_metadata.no_primario].status == "ATIVO"):
                available_replicas.append(self.nodes[chunk_metadata.no_primario])
            
            # Verificar réplicas
            for replica_info in chunk_metadata.replicas:
                if (replica_info.node_id != failed_node and 
                    replica_info.node_id in self.nodes and
                    self.nodes[replica_info.node_id].status == "ATIVO"):
                    available_replicas.append(self.nodes[replica_info.node_id])
            
            return available_replicas
    
    def get_system_status(self) -> dict:
        """Obtém status geral do sistema"""
        with self.lock:
            total_nos = len(self.nodes)
            nos_ativos = len([n for n in self.nodes.values() if n.status == "ATIVO"])
            nos_falhos = len([n for n in self.nodes.values() if n.status == "FALHA"])
            
            total_storage = sum(n.capacidade_storage for n in self.nodes.values())
            storage_usado = sum(n.storage_usado for n in self.nodes.values())
            
            return {
                'total_nos': total_nos,
                'nos_ativos': nos_ativos,
                'nos_falhos': nos_falhos,
                'total_arquivos': len(self.files),
                'total_chunks': len(self.chunks),
                'storage_total': total_storage,
                'storage_usado': storage_usado,
                'detalhes_nos': list(self.nodes.values()),
                'estatisticas': self.stats
            }
    
    def _cleanup_deleted_files(self):
        """
        Thread de limpeza que varre periodicamente os metadados em busca de arquivos
        marcados para deleção e tenta remover os chunks físicos dos nós.
        
        NOVA IMPLEMENTAÇÃO: Limpeza em duas fases
        1. Fase de Marcação: Marca todas as réplicas AVAILABLE como DELETING
        2. Fase de Deleção Física: Remove chunks físicos dos nós
        """
        while True:
            try:
                time.sleep(60)  # Executar a cada 60 segundos
                
                with self.lock:
                    # Buscar arquivos marcados para deleção
                    files_to_cleanup = [
                        (nome, metadata) for nome, metadata in self.files.items()
                        if getattr(metadata, 'status', 'ativo') == 'deletando'
                    ]
                
                for nome_arquivo, file_metadata in files_to_cleanup:
                    print(f"INFO: Iniciando limpeza do arquivo '{nome_arquivo}'")
                    
                    # Obter chunks do arquivo
                    chunks_to_remove = self.get_chunk_locations(nome_arquivo)
                    
                    # FASE 1: MARCAÇÃO - Marcar réplicas AVAILABLE como DELETING
                    self._mark_replicas_for_deletion(chunks_to_remove)
                    
                    # FASE 2: DELEÇÃO FÍSICA - Remover chunks físicos
                    all_chunks_removed = True
                    
                    for chunk_metadata in chunks_to_remove:
                        chunk_removed = self._try_remove_chunk_from_nodes(
                            nome_arquivo, chunk_metadata.chunk_numero, chunk_metadata
                        )
                        if not chunk_removed:
                            all_chunks_removed = False
                    
                    # Se todos os chunks foram removidos, apagar os registros de metadados
                    if all_chunks_removed:
                        with self.lock:
                            # Remover chunks dos metadados
                            chunk_keys_to_delete = [
                                self._get_chunk_key(c.arquivo_nome, c.chunk_numero) 
                                for c in chunks_to_remove
                            ]
                            for key in chunk_keys_to_delete:
                                if key in self.chunks:
                                    del self.chunks[key]
                            
                            # Remover arquivo dos metadados
                            if nome_arquivo in self.files:
                                del self.files[nome_arquivo]
                            
                            self._save_metadata()
                            print(f"INFO: Arquivo '{nome_arquivo}' removido completamente do sistema")
                    else:
                        print(f"AVISO: Nem todos os chunks do arquivo '{nome_arquivo}' foram removidos. Tentativa será repetida.")
                        
            except Exception as e:
                print(f"ERRO: Falha na thread de limpeza: {e}")
    
    def _mark_replicas_for_deletion(self, chunks_to_remove: List[ChunkMetadata]):
        """
        FASE 1: Marca todas as réplicas AVAILABLE como DELETING para impedir novos acessos
        """
        with self.lock:
            for chunk_metadata in chunks_to_remove:
                for replica_info in chunk_metadata.replicas:
                    if replica_info.status == fs_pb2.ReplicaStatus.AVAILABLE:
                        replica_info.status = fs_pb2.ReplicaStatus.DELETING
                        print(f"INFO: Réplica {replica_info.node_id} marcada como DELETING para chunk {chunk_metadata.arquivo_nome}:{chunk_metadata.chunk_numero}")
            
            # Salvar as alterações de status
            self._save_metadata()
    
    def _try_remove_chunk_from_nodes(self, arquivo_nome: str, chunk_numero: int, 
                                    chunk_metadata: ChunkMetadata) -> bool:
        """
        Tenta remover um chunk de todos os nós (primário e réplicas).
        
        NOVA IMPLEMENTAÇÃO:
        - Sempre tenta apagar a cópia do nó primário
        - Para réplicas, só tenta apagar se o status for DELETING
        - Implementa heurística do timestamp para nós com heartbeat recente
        
        Retorna True se conseguiu remover de todos os nós disponíveis.
        """
        removal_success = True
        
        # 1. SEMPRE tentar remover do nó primário
        primary_node_id = chunk_metadata.no_primario
        if primary_node_id in self.nodes:
            primary_removed = self._try_remove_chunk_from_single_node(
                arquivo_nome, chunk_numero, chunk_metadata, primary_node_id, is_primary=True
            )
            if not primary_removed:
                removal_success = False
        else:
            print(f"AVISO: Nó primário {primary_node_id} não encontrado nos metadados")
        
        # 2. Para réplicas, verificar status primeiro
        for replica_info in chunk_metadata.replicas:
            if replica_info.status == fs_pb2.ReplicaStatus.DELETING:
                # Só tentar apagar réplicas em estado DELETING
                replica_removed = self._try_remove_chunk_from_single_node(
                    arquivo_nome, chunk_numero, chunk_metadata, replica_info.node_id, is_primary=False
                )
                if not replica_removed:
                    removal_success = False
            elif replica_info.status in [fs_pb2.ReplicaStatus.PENDING, fs_pb2.ReplicaStatus.AVAILABLE]:
                # Ignorar réplicas que não estão marcadas para deleção
                print(f"INFO: Ignorando réplica {replica_info.node_id} com status {fs_pb2.ReplicaStatus.Name(replica_info.status)}")
        
        return removal_success
    
    def _try_remove_chunk_from_single_node(self, arquivo_nome: str, chunk_numero: int, 
                                          chunk_metadata: ChunkMetadata, node_id: str, 
                                          is_primary: bool = False) -> bool:
        """
        Tenta remover um chunk de um único nó com heurística do timestamp
        """
        if node_id not in self.nodes:
            print(f"AVISO: Nó {node_id} não encontrado nos metadados")
            return False
            
        node_info = self.nodes[node_id]
        if node_info.status != "ATIVO":
            print(f"AVISO: Nó {node_id} não está ativo. Chunk {arquivo_nome}:{chunk_numero} pode permanecer órfão.")
            return False
        
        try:
            stub = self._get_storage_node_stub(node_info)
            request = fs_pb2.ChunkRequest(
                arquivo_nome=arquivo_nome, 
                chunk_numero=chunk_numero
            )
            response = stub.DeleteChunk(request, timeout=10)
            
            if response.sucesso:
                node_type = "primário" if is_primary else "réplica"
                print(f"INFO: Chunk {arquivo_nome}:{chunk_numero} removido do nó {node_type} {node_id}")
                
                # Atualizar chunks_armazenados do nó
                chunk_key = f"{arquivo_nome}:{chunk_numero}"
                if chunk_key in node_info.chunks_armazenados:
                    node_info.chunks_armazenados.remove(chunk_key)
                    # Recalcular storage_usado
                    node_info.storage_usado = max(0, node_info.storage_usado - chunk_metadata.tamanho_chunk)
                
                return True
            else:
                mensagem_erro = response.mensagem.lower()
                # HEURÍSTICA DO TIMESTAMP: Se erro é "arquivo não encontrado" e heartbeat é recente
                # Se heartbeat foi há menos de 2 minutos (120 segundos), considerar como sucesso
                if "encontrado" in mensagem_erro:
                    current_time = int(time.time())
                    time_since_heartbeat = current_time - node_info.ultimo_heartbeat
                    
                    if time_since_heartbeat < 120: # 2 minutos
                        node_type = "primário" if is_primary else "réplica"
                        print(f"INFO: Chunk {arquivo_nome}:{chunk_numero} já não existe no nó {node_type} {node_id} (heartbeat recente)")
                        
                        chunk_key = f"{arquivo_nome}:{chunk_numero}"
                        if chunk_key in node_info.chunks_armazenados:
                            node_info.chunks_armazenados.remove(chunk_key)
                            node_info.storage_usado = max(0, node_info.storage_usado - chunk_metadata.tamanho_chunk)
                        
                        return True # A heurística foi aplicada, consideramos um sucesso.
                
                # Se a heurística não se aplica, é uma falha real.
                node_type = "primário" if is_primary else "réplica"
                print(f"AVISO: Falha ao remover chunk {arquivo_nome}:{chunk_numero} do nó {node_type} {node_id}: {response.mensagem}")
                return False
                
        except Exception as e:
            node_type = "primário" if is_primary else "réplica"
            print(f"ERRO: Exceção ao tentar remover chunk {arquivo_nome}:{chunk_numero} do nó {node_type} {node_id}: {e}")
            return False
    
    def _garbage_collect_incomplete_uploads(self):
        """
        Thread de garbage collection que procura periodicamente por arquivos que foram
        criados há um certo tempo mas que ainda não foram marcados como completos.
        Remove chunks órfãos e registros de arquivos incompletos.
        """
        while True:
            try:
                time.sleep(300)  # Executar a cada 5 minutos
                current_time = int(time.time())
                timeout_threshold = 3600  # 1 hora em segundos
                
                with self.lock:
                    # Buscar arquivos incompletos antigos
                    incomplete_files = [
                        (nome, metadata) for nome, metadata in self.files.items()
                        if (not getattr(metadata, 'esta_completo', False) and 
                            getattr(metadata, 'status', 'ativo') == 'ativo' and
                            current_time - metadata.timestamp_criacao > timeout_threshold)
                    ]
                
                for nome_arquivo, file_metadata in incomplete_files:
                    print(f"INFO: Iniciando garbage collection do arquivo incompleto '{nome_arquivo}'")
                    
                    # Obter chunks do arquivo incompleto
                    chunks_to_cleanup = self.get_chunk_locations(nome_arquivo)
                    
                    # Tentar remover chunks órfãos
                    for chunk_metadata in chunks_to_cleanup:
                        self._try_remove_chunk_from_nodes(
                            nome_arquivo, chunk_metadata.chunk_numero, chunk_metadata
                        )
                    
                    # Remover registros de metadados do arquivo incompleto
                    with self.lock:
                        # Remover chunks dos metadados
                        chunk_keys_to_delete = [
                            self._get_chunk_key(c.arquivo_nome, c.chunk_numero) 
                            for c in chunks_to_cleanup
                        ]
                        for key in chunk_keys_to_delete:
                            if key in self.chunks:
                                del self.chunks[key]
                        
                        # Remover arquivo dos metadados
                        if nome_arquivo in self.files:
                            del self.files[nome_arquivo]
                        
                        self._save_metadata()
                        print(f"INFO: Arquivo incompleto '{nome_arquivo}' removido pelo garbage collector")
                        
            except Exception as e:
                print(f"ERRO: Falha na thread de garbage collection: {e}")

    def stop_monitoring(self):
        """Para o monitoramento de falhas (para testes)"""
        # Método placeholder para compatibilidade com testes
        pass

    def list_files_in_directory(self, directory: str) -> List[str]:
            """Retorna uma lista de todos os arquivos registrados no sistema."""
            with self.lock:
                # Por enquanto retorna todos os arquivos.
                # Melhoria futura - filtrar pelo 'directory'.
                return list(self.files.keys())
            
    def mark_file_as_complete(self, nome_arquivo: str) -> bool:
        """Marca um arquivo como totalmente carregado e disponível."""
        try:
            with self.lock:
                if nome_arquivo in self.files:
                    self.files[nome_arquivo].esta_completo = True
                    self.files[nome_arquivo].timestamp_modificacao = int(time.time())
                    self._save_metadata()
                    print(f"INFO: Arquivo '{nome_arquivo}' marcado como completo.")
                    return True
                else:
                    print(f"AVISO: Tentativa de marcar arquivo inexistente '{nome_arquivo}' como completo.")
                    return False
        except Exception as e:
            print(f"ERRO: Exceção ao marcar arquivo como completo: {e}")
            return False
        
    def get_chunk_metadata_by_key(self, chunk_key: str) -> Optional[ChunkMetadata]:
        """Busca os metadados de um chunk pela sua chave ('arquivo:numero')."""
        with self.lock:
            return self.chunks.get(chunk_key)

    def get_chunk_metadata(self, arquivo_nome: str, chunk_numero: int) -> Optional[ChunkMetadata]:
        """Busca os metadados de um chunk específico."""
        chunk_key = self._get_chunk_key(arquivo_nome, chunk_numero)
        return self.get_chunk_metadata_by_key(chunk_key)
    
    def get_node_by_id(self, node_id: str) -> Optional[NodeInfo]:
        """Busca as informações de um nó específico pelo seu ID."""
        with self.lock:
            return self.nodes.get(node_id)
