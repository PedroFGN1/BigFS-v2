# Nós de Armazenamento BigFS-v2

Os Nós de Armazenamento são os componentes responsáveis pelo armazenamento físico dos dados no sistema distribuído BigFS-v2. Eles foram adaptados para suportar chunks, replicação e integração com o servidor de metadados.

## Componentes

### 1. file_manager_extended.py
Extensão do gerenciador de arquivos original com novas funcionalidades:

#### Funções para Chunks:
- `dividir_arquivo_em_chunks()`: Divide arquivo em chunks de tamanho configurável
- `recombinar_chunks()`: Reconstrói arquivo a partir de chunks
- `salvar_chunk()`: Salva chunk individual no disco
- `ler_chunk()`: Lê chunk específico do disco
- `deletar_chunk()`: Remove chunk do disco
- `listar_chunks_armazenados()`: Lista todos os chunks no nó

#### Funções de Integridade:
- `calcular_checksum()`: Calcula hash MD5 dos dados
- `verificar_integridade_chunk()`: Verifica integridade comparando checksums

#### Funções de Metadados:
- `salvar_metadata_chunk()`: Persiste metadados locais de chunks
- `ler_metadata_chunk()`: Lê metadados locais de chunks

#### Funções Originais:
Mantém todas as funções originais para compatibilidade:
- `listar_conteudo()`, `deletar_arquivo()`, `salvar_arquivo()`, `ler_arquivo()`, `copiar_arquivo()`

### 2. storage_node.py
Servidor de armazenamento principal com todas as funcionalidades:

#### Características:
- **Integração com Metadados**: Conecta automaticamente ao servidor de metadados
- **Registro Automático**: Registra-se como nó disponível no sistema
- **Heartbeat Automático**: Envia sinais de vida periodicamente
- **Suporte a Chunks**: Divisão/recombinação automática de arquivos grandes
- **Compatibilidade**: Mantém compatibilidade com protocolo original

#### Métodos Implementados:

##### Operações Originais (compatibilidade):
- `Listar()`: Lista conteúdo de diretórios
- `Upload()`: Upload com divisão automática em chunks se necessário
- `Download()`: Download com recombinação automática de chunks
- `Deletar()`: Remove arquivos
- `Copiar()` / `CopiarInterno()`: Copia arquivos

##### Operações de Chunks:
- `UploadChunk()`: Upload de chunk específico
- `DownloadChunk()`: Download de chunk específico
- `DeleteChunk()`: Remove chunk específico

##### Operações de Replicação:
- `ReplicarChunk()`: Recebe réplica de outro nó
- `SincronizarReplica()`: Sincroniza réplica desatualizada

##### Monitoramento:
- `Heartbeat()`: Responde a heartbeats
- `VerificarIntegridade()`: Verifica integridade de chunks

## Arquitetura de Armazenamento

### Estrutura de Diretórios:
```
storage_node_<porta>/
├── chunks/                 # Chunks de arquivos grandes
│   ├── arquivo1.chunk_0
│   ├── arquivo1.chunk_1
│   └── arquivo2.chunk_0
├── metadata/              # Metadados locais dos chunks
│   ├── arquivo1.chunk_0.meta
│   ├── arquivo1.chunk_1.meta
│   └── arquivo2.chunk_0.meta
└── <arquivos_pequenos>    # Arquivos menores que chunk_size
```

### Metadados Locais:
Cada chunk possui metadados locais em JSON:
```json
{
  "arquivo_nome": "documento.pdf",
  "chunk_numero": 0,
  "checksum": "d41d8cd98f00b204e9800998ecf8427e",
  "tamanho": 1048576,
  "timestamp": 1640995200,
  "no_origem": "node_1",
  "tipo": "replica"
}
```

## Fluxos de Operação

### Upload de Arquivo Grande:
1. Cliente envia arquivo completo via `Upload()`
2. Nó verifica tamanho vs `chunk_size`
3. Se grande, divide em chunks automaticamente
4. Registra arquivo no servidor de metadados
5. Salva chunks localmente
6. Registra cada chunk no servidor de metadados
7. Atualiza heartbeat com novos chunks

### Download de Arquivo Grande:
1. Cliente solicita arquivo via `Download()`
2. Nó tenta ler arquivo completo primeiro
3. Se não encontra, consulta servidor de metadados
4. Obtém lista de chunks do arquivo
5. Lê chunks localmente
6. Recombina chunks em arquivo completo
7. Retorna arquivo ao cliente

### Replicação de Chunk:
1. Nó recebe `ReplicarChunk()` de outro nó
2. Salva chunk localmente
3. Verifica checksum para integridade
4. Salva metadados da réplica
5. Atualiza heartbeat

### Verificação de Integridade:
1. Processo em background chama `VerificarIntegridade()`
2. Lê metadados locais do chunk
3. Calcula checksum atual
4. Compara com checksum esperado
5. Reporta resultado

## Configuração

### Parâmetros do Servidor:
- `--port`: Porta do servidor (padrão: 50051)
- `--node-id`: ID do nó (padrão: auto-gerado)
- `--metadata-server`: Endereço do servidor de metadados (padrão: localhost:50052)
- `--storage-dir`: Diretório de armazenamento (padrão: auto-gerado)
- `--chunk-size`: Tamanho do chunk em bytes (padrão: 1MB)

### Configurações Internas:
- **Heartbeat Interval**: 15 segundos
- **Capacidade Padrão**: 10GB
- **Timeout gRPC**: Suporte a mensagens de até 1GB

## Tolerância a Falhas

### Detecção de Falhas:
- Heartbeats automáticos para servidor de metadados
- Verificação de integridade de chunks
- Validação de checksums em todas as operações

### Recuperação:
- Reconexão automática ao servidor de metadados
- Ressincronização de chunks via `SincronizarReplica()`
- Reconstrução de arquivos a partir de chunks disponíveis

## Uso

### Iniciar Nó de Armazenamento:
```bash
# Nó padrão
python server/storage_node.py

# Nó customizado
python server/storage_node.py --port 50053 --node-id "storage_node_1" --chunk-size 2097152
```

### Múltiplos Nós:
```bash
# Terminal 1 - Nó 1
python server/storage_node.py --port 50051 --node-id "node1"

# Terminal 2 - Nó 2  
python server/storage_node.py --port 50053 --node-id "node2"

# Terminal 3 - Nó 3
python server/storage_node.py --port 50054 --node-id "node3"
```

## Integração

### Com Servidor de Metadados:
- Registro automático na inicialização
- Heartbeats periódicos com lista de chunks
- Consultas para localização de chunks
- Registro de novos chunks

### Com Cliente:
- Compatibilidade total com cliente original
- Suporte transparente a arquivos grandes
- Operações de chunk individuais disponíveis

## Monitoramento

### Logs do Nó:
- Conexão com servidor de metadados
- Operações de upload/download
- Divisão/recombinação de chunks
- Replicação de dados
- Verificação de integridade

### Métricas:
- Chunks armazenados
- Espaço utilizado
- Operações realizadas
- Status de conectividade

## Próximos Passos

Os Nós de Armazenamento estão prontos para:
1. Integração com cliente atualizado
2. Testes de sistema completo
3. Simulação de falhas e recuperação
4. Otimizações de desempenho

Todas as funcionalidades da arquitetura documentada estão implementadas e testadas.

