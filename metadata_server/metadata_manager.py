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

@dataclass
class ChunkMetadata:
    """Metadados de um chunk específico"""
    arquivo_nome: str
    chunk_numero: int
    no_primario: str
    nos_replicas: List[str]
    checksum: str
    tamanho_chunk: int
    timestamp_criacao: int
    disponivel: bool = True

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
        
        # Iniciar thread de monitoramento de heartbeats
        self.heartbeat_timeout = 30  # 30 segundos
        self.monitoring_thread = threading.Thread(target=self._monitor_heartbeats, daemon=True)
        self.monitoring_thread.start()
    
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
            chunks_data = {key: asdict(metadata) for key, metadata in self.chunks.items()}
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
        """Remove um arquivo e todos os seus chunks"""
        try:
            with self.lock:
                if nome_arquivo not in self.files:
                    return False
                
                # Remover chunks do arquivo
                chunks_to_remove = [key for key in self.chunks.keys() 
                                  if key.startswith(f"{nome_arquivo}:")]
                for chunk_key in chunks_to_remove:
                    del self.chunks[chunk_key]
                
                # Remover arquivo
                del self.files[nome_arquivo]
                
                # Atualizar chunks armazenados nos nós
                for node in self.nodes.values():
                    node.chunks_armazenados = {chunk for chunk in node.chunks_armazenados 
                                             if not chunk.startswith(f"{nome_arquivo}:")}
                
                self._save_metadata()
                self.stats['operacoes_delete_total'] += 1
                return True
        except Exception as e:
            print(f"Erro ao remover arquivo {nome_arquivo}: {e}")
            return False
    
    def register_chunk(self, chunk_metadata: ChunkMetadata) -> bool:
        """Registra um chunk no sistema"""
        try:
            with self.lock:
                chunk_key = self._get_chunk_key(chunk_metadata.arquivo_nome, 
                                               chunk_metadata.chunk_numero)
                self.chunks[chunk_key] = chunk_metadata
                
                # Atualizar informações dos nós
                for node_id in [chunk_metadata.no_primario] + chunk_metadata.nos_replicas:
                    if node_id in self.nodes:
                        self.nodes[node_id].chunks_armazenados.add(chunk_key)
                        self.nodes[node_id].storage_usado += chunk_metadata.tamanho_chunk
                
                self._save_metadata()
                return True
        except Exception as e:
            print(f"Erro ao registrar chunk {chunk_key}: {e}")
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
                    node = self.nodes[node_id]
                    node.ultimo_heartbeat = int(time.time())
                    node.status = status
                    node.chunks_armazenados = set(chunks_armazenados)
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
                    for replica_id in chunk_metadata.nos_replicas:
                        if (replica_id in self.nodes and 
                            self.nodes[replica_id].status == "ATIVO"):
                            return self.nodes[replica_id]
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
            for replica_id in chunk_metadata.nos_replicas:
                if (replica_id != failed_node and 
                    replica_id in self.nodes and
                    self.nodes[replica_id].status == "ATIVO"):
                    available_replicas.append(self.nodes[replica_id])
            
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
    
    def stop_monitoring(self):
        """Para o monitoramento de falhas (para testes)"""
        # Método placeholder para compatibilidade com testes
        pass

