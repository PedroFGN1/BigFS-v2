# BigFS-v2: Guia de Instalação e Configuração

## Pré-requisitos

### Sistema Operacional
- Linux (Ubuntu 20.04+ recomendado)
- macOS 10.15+
- Windows 10+ (com WSL2)

### Software Necessário
- Python 3.11 ou superior
- pip (gerenciador de pacotes Python)
- Git (para clonagem do repositório)

## Instalação

### 1. Clonar o Repositório
```bash
git clone https://github.com/PedroFGN1/BigFS-v2.git
cd BigFS-v2
```

### 2. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 3. Gerar Arquivos gRPC
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/filesystem_extended.proto
```

### 4. Corrigir Imports (se necessário)
```bash
sed -i 's/from proto import filesystem_extended_pb2/import filesystem_extended_pb2/g' proto/filesystem_extended_pb2_grpc.py
sed -i 's/from proto import filesystem_pb2/import filesystem_pb2/g' proto/filesystem_pb2_grpc.py
```

## Configuração

### Estrutura de Diretórios
O sistema criará automaticamente os seguintes diretórios:
```
/bigfs_metadata/     # Metadados do servidor
/bigfs_storage_*/    # Armazenamento dos nós
```

### Configurações Padrão
- **Porta do Servidor de Metadados**: 50052
- **Portas dos Nós de Armazenamento**: 50051, 50053, 50054, ...
- **Tamanho de Chunk**: 1MB
- **Timeout de Heartbeat**: 30 segundos
- **Intervalo de Heartbeat**: 15 segundos

## Execução

### Cenário 1: Sistema Básico (1 nó)

#### Terminal 1 - Servidor de Metadados
```bash
python metadata_server/metadata_server.py
```

#### Terminal 2 - Nó de Armazenamento
```bash
python server/storage_node.py --port 50051 --node-id node_1
```

#### Terminal 3 - Cliente
```bash
python client/client_extended.py
```

### Cenário 2: Sistema Distribuído (3 nós)

#### Terminal 1 - Servidor de Metadados
```bash
python metadata_server/metadata_server.py --port 50052
```

#### Terminal 2 - Nó 1
```bash
python server/storage_node.py --port 50051 --node-id node_1 --storage-dir /tmp/bigfs_storage_1
```

#### Terminal 3 - Nó 2
```bash
python server/storage_node.py --port 50053 --node-id node_2 --storage-dir /tmp/bigfs_storage_2
```

#### Terminal 4 - Nó 3
```bash
python server/storage_node.py --port 50054 --node-id node_3 --storage-dir /tmp/bigfs_storage_3
```

#### Terminal 5 - Cliente
```bash
python client/client_extended.py
```

### Cenário 3: Cliente Inteligente
```bash
python client/intelligent_client.py
```

## Testes

### Executar Todos os Testes
```bash
python run_tests.py
```

### Executar Testes Específicos
```bash
# Testes unitários
python -m pytest tests/unit/ -v

# Testes de integração
python -m pytest tests/integration/ -v

# Testes de sistema
python -m pytest tests/system/ -v

# Testes de tolerância a falhas
python -m pytest tests/fault_tolerance/ -v
```

## Uso Básico

### Upload de Arquivo
1. Executar cliente: `python client/client_extended.py`
2. Escolher opção "3. 📤 Upload de arquivo"
3. Informar caminho local e remoto
4. Aguardar conclusão

### Download de Arquivo
1. Executar cliente: `python client/client_extended.py`
2. Escolher opção "4. 📥 Download de arquivo"
3. Informar caminho remoto e local
4. Aguardar conclusão

### Listar Arquivos
1. Executar cliente: `python client/client_extended.py`
2. Escolher opção "1. 📋 Listar arquivos (ls)"
3. Informar diretório (ou Enter para raiz)

### Status do Sistema
1. Executar cliente: `python client/client_extended.py`
2. Escolher opção "6. 📊 Status do sistema"

## Configurações Avançadas

### Personalizar Tamanho de Chunk
```bash
python server/storage_node.py --chunk-size 2048  # 2MB chunks
```

### Personalizar Capacidade de Armazenamento
```bash
python server/storage_node.py --capacity 10737418240  # 10GB
```

### Personalizar Servidor de Metadados
```bash
python client/client_extended.py --metadata-server localhost:50055
```

## Monitoramento

### Logs do Sistema
Os componentes geram logs no console. Para salvar em arquivo:
```bash
python metadata_server/metadata_server.py > metadata.log 2>&1 &
python server/storage_node.py --port 50051 > node1.log 2>&1 &
```

### Status em Tempo Real
Use a opção "Status do sistema" no cliente para monitorar:
- Nós ativos/inativos
- Arquivos e chunks armazenados
- Uso de storage
- Estatísticas de operações

## Solução de Problemas

### Erro: "Address already in use"
```bash
# Verificar processos usando a porta
lsof -i :50051

# Matar processo se necessário
kill -9 <PID>
```

### Erro: "No module named 'filesystem_extended_pb2'"
```bash
# Regenerar arquivos gRPC
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/filesystem_extended.proto
```

### Erro: "Metadata server unavailable"
1. Verificar se servidor de metadados está rodando
2. Verificar conectividade de rede
3. Verificar porta configurada

### Erro: "No storage nodes available"
1. Verificar se nós de armazenamento estão rodando
2. Verificar se nós se registraram no servidor de metadados
3. Aguardar alguns segundos para heartbeats

### Erro de Permissão
```bash
# Dar permissões aos diretórios
chmod -R 755 /bigfs_*
```

## Performance

### Otimizações Recomendadas
1. **SSD**: Use SSD para armazenamento dos nós
2. **Rede**: Use rede Gigabit ou superior
3. **RAM**: Mínimo 4GB por nó
4. **CPU**: Múltiplos cores para operações paralelas

### Limites Conhecidos
- **Arquivo máximo**: 1GB (limitação gRPC)
- **Chunk máximo**: 64MB (recomendado 1-4MB)
- **Nós simultâneos**: Testado até 10 nós
- **Clientes simultâneos**: Testado até 20 clientes

## Backup e Recuperação

### Backup de Metadados
```bash
# Metadados são salvos automaticamente em:
/tmp/bigfs_metadata/files.json
/tmp/bigfs_metadata/chunks.json
/tmp/bigfs_metadata/nodes.json

# Fazer backup manual
cp -r /tmp/bigfs_metadata/ backup_metadata_$(date +%Y%m%d_%H%M%S)/
```

### Recuperação após Falha
1. **Falha de Nó**: Sistema redireciona automaticamente para réplicas
2. **Falha de Metadados**: Restaurar backup dos arquivos JSON
3. **Falha Total**: Restaurar metadados e reiniciar nós

## Segurança

### Considerações de Segurança
- Sistema não implementa autenticação (desenvolvimento)
- Dados não são criptografados em trânsito
- Acesso baseado em rede (firewall recomendado)

### Recomendações para Produção
1. Implementar TLS/SSL para gRPC
2. Adicionar autenticação de nós
3. Criptografar dados em repouso
4. Implementar logs de auditoria

## Desenvolvimento

### Adicionar Novo Nó
```bash
python server/storage_node.py --port <NOVA_PORTA> --node-id <NOVO_ID>
```

### Modificar Protocolo
1. Editar `proto/filesystem_extended.proto`
2. Regenerar arquivos Python
3. Atualizar implementações
4. Executar testes

### Contribuir
1. Fork do repositório
2. Criar branch para feature
3. Implementar mudanças
4. Executar testes
5. Criar pull request

Este guia cobre os aspectos essenciais para instalação, configuração e uso do BigFS-v2. Para informações mais detalhadas, consulte a documentação específica de cada componente.

