# Servidor de Metadados BigFS-v2

O Servidor de Metadados é o componente central da arquitetura BigFS-v2, responsável por gerenciar todas as informações sobre arquivos, chunks e nós do sistema distribuído.

## Componentes

### 1. MetadataManager (`metadata_manager.py`)
Classe principal que gerencia:
- **Metadados de Arquivos**: Nome, tamanho, chunks, checksums, timestamps
- **Metadados de Chunks**: Localização, réplicas, integridade
- **Informações de Nós**: Status, capacidade, heartbeats
- **Estatísticas do Sistema**: Operações, falhas, desempenho

#### Funcionalidades Principais:
- **Persistência**: Salva/carrega metadados em arquivos JSON
- **Hashing Consistente**: Distribui chunks uniformemente entre nós
- **Monitoramento**: Thread dedicada para detectar falhas via heartbeats
- **Thread-Safety**: Operações protegidas por locks

### 2. MetadataServiceServicer (`metadata_server.py`)
Implementação do serviço gRPC que expõe as operações:

#### Gerenciamento de Arquivos:
- `RegistrarArquivo`: Registra metadados de novo arquivo
- `ObterMetadataArquivo`: Obtém metadados de arquivo existente
- `RemoverArquivo`: Remove arquivo e todos os seus chunks

#### Gerenciamento de Chunks:
- `RegistrarChunk`: Registra metadados de chunk
- `ObterLocalizacaoChunks`: Obtém localização de todos os chunks de um arquivo
- `RemoverChunk`: Remove metadados de chunk específico

#### Gerenciamento de Nós:
- `RegistrarNo`: Registra novo nó no sistema
- `ObterNosDisponiveis`: Lista nós disponíveis
- `ReportarFalhaNo`: Reporta falha de nó

#### Operações de Redirecionamento:
- `ObterNoParaOperacao`: Obtém melhor nó para operação
- `ObterReplicasDisponiveis`: Obtém réplicas disponíveis para chunk

#### Monitoramento:
- `ProcessarHeartbeat`: Processa heartbeats dos nós
- `ObterStatusSistema`: Obtém status geral do sistema

### 3. MetadataClient (`metadata_client.py`)
Cliente Python para interagir com o servidor de metadados:

#### Funcionalidades:
- **Conexão Automática**: Estabelece conexão com servidor
- **Métodos Simplificados**: Wrappers para todas as operações gRPC
- **Tratamento de Erros**: Captura e reporta erros de comunicação
- **HeartbeatSender**: Classe auxiliar para envio automático de heartbeats

## Arquitetura de Dados

### Estruturas Principais:

```python
@dataclass
class FileMetadata:
    nome_arquivo: str
    tamanho_total: int
    total_chunks: int
    checksum_arquivo: str
    timestamp_criacao: int
    timestamp_modificacao: int
    no_primario: str
    nos_replicas: List[str]
    esta_completo: bool

@dataclass
class ChunkMetadata:
    arquivo_nome: str
    chunk_numero: int
    no_primario: str
    nos_replicas: List[str]
    checksum: str
    tamanho_chunk: int
    timestamp_criacao: int
    disponivel: bool

@dataclass
class NodeInfo:
    node_id: str
    endereco: str
    porta: int
    status: str  # ATIVO, OCUPADO, MANUTENCAO, FALHA
    capacidade_storage: int
    storage_usado: int
    ultimo_heartbeat: int
    chunks_armazenados: Set[str]
```

## Persistência

Os metadados são persistidos em arquivos JSON:
- `files.json`: Metadados de arquivos
- `chunks.json`: Metadados de chunks
- `nodes.json`: Informações de nós

## Tolerância a Falhas

### Detecção de Falhas:
- **Heartbeats**: Nós enviam sinais de vida a cada 15 segundos
- **Timeout**: Nós sem heartbeat por 30 segundos são marcados como FALHA
- **Thread de Monitoramento**: Verifica status dos nós a cada 10 segundos

### Recuperação:
- **Redirecionamento Automático**: Operações são redirecionadas para réplicas
- **Ressincronização**: Nós que retornam são atualizados automaticamente

## Hashing Consistente

Para distribuição uniforme de chunks:
```python
def _hash_for_node_selection(self, data: str) -> int:
    return int(hashlib.md5(data.encode()).hexdigest(), 16)

def _select_nodes_for_chunk(self, arquivo_nome: str, chunk_numero: int, 
                           num_replicas: int = 2) -> List[str]:
    # Usa hash do nome do arquivo + chunk para distribuição consistente
    chunk_key = f"{arquivo_nome}:{chunk_numero}"
    hash_value = self._hash_for_node_selection(chunk_key)
    # Seleciona nó primário e réplicas baseado no hash
```

## Uso

### Iniciar Servidor:
```bash
python metadata_server/metadata_server.py --port 50052 --data-dir metadata_storage
```

### Usar Cliente:
```python
from metadata_client import MetadataClient

client = MetadataClient("localhost:50052")

# Registrar arquivo
client.register_file("arquivo.txt", 1024, 2, "checksum123", "node1", ["node2"])

# Obter chunks
chunks = client.get_chunk_locations("arquivo.txt")

# Obter nó para operação
node = client.get_node_for_operation("upload", "arquivo.txt")

client.close()
```

### Heartbeat Automático:
```python
from metadata_client import MetadataClient, HeartbeatSender

client = MetadataClient()
heartbeat = HeartbeatSender(client, "node1", interval=15)
heartbeat.start()

# ... operações do nó ...

heartbeat.stop()
client.close()
```

## Configuração

### Parâmetros do Servidor:
- `--port`: Porta do servidor (padrão: 50052)
- `--data-dir`: Diretório para persistência (padrão: metadata_storage)

### Configurações de Timeout:
- `heartbeat_timeout`: 30 segundos (configurável no MetadataManager)
- `monitoring_interval`: 10 segundos (thread de monitoramento)

## Estatísticas

O servidor mantém estatísticas de:
- Operações de upload/download/delete
- Falhas detectadas
- Replicações realizadas
- Tempos médios de operação

Acessíveis via `get_system_status()` no cliente.

## Próximos Passos

O Servidor de Metadados está pronto para integração com:
1. Nós de Armazenamento adaptados
2. Cliente atualizado
3. Testes de sistema completo

Todas as funcionalidades da arquitetura documentada estão implementadas e testadas.

