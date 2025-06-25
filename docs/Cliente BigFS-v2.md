# Cliente BigFS-v2

O Cliente BigFS-v2 foi completamente atualizado para interagir com o sistema distribuído, incluindo suporte a chunks, replicação, tolerância a falhas e operações paralelas.

## Componentes

### 1. client_extended.py
Cliente principal com todas as funcionalidades básicas:

#### Características:
- **Integração com Metadados**: Conecta automaticamente ao servidor de metadados
- **Suporte Transparente a Chunks**: Divisão/recombinação automática de arquivos grandes
- **Tolerância a Falhas**: Redirecionamento automático para réplicas em caso de falha
- **Interface Amigável**: Menu interativo com emojis e feedback visual
- **Cache de Conexões**: Reutiliza conexões com nós de armazenamento

#### Funcionalidades:
- **Listar**: Lista conteúdo de diretórios com informações do nó
- **Upload**: Upload com divisão automática em chunks se necessário
- **Download**: Download com recombinação automática de chunks
- **Deletar**: Remove arquivos do sistema distribuído
- **Copiar**: Copia arquivos entre locais remotos
- **Status**: Exibe status completo do sistema

### 2. advanced_client.py
Cliente avançado com operações paralelas e funcionalidades extras:

#### Características Avançadas:
- **Upload Paralelo**: Upload simultâneo de múltiplos chunks
- **Download Paralelo**: Download simultâneo de múltiplos chunks
- **Verificação de Integridade**: Verifica checksums de todos os chunks
- **Configurável**: Número de workers paralelos configurável
- **Métricas de Performance**: Medição de tempo de operações

#### Classes Auxiliares:
- **ChunkUploader**: Gerencia upload paralelo de chunks
- **ChunkDownloader**: Gerencia download paralelo de chunks

## Arquitetura do Cliente

### Fluxo de Operações:

#### Upload de Arquivo:
1. Cliente conecta ao servidor de metadados
2. Obtém nó disponível para upload
3. Se arquivo é pequeno (< chunk_size):
   - Upload direto para o nó
4. Se arquivo é grande:
   - Divide em chunks
   - Registra arquivo no servidor de metadados
   - Upload de cada chunk para nós apropriados
   - Registra cada chunk no servidor de metadados

#### Download de Arquivo:
1. Cliente consulta servidor de metadados
2. Se arquivo tem chunks:
   - Obtém localização de todos os chunks
   - Download de cada chunk (com fallback para réplicas)
   - Recombina chunks em arquivo completo
   - Verifica checksum do arquivo
3. Se arquivo é pequeno:
   - Download direto do nó

#### Tolerância a Falhas:
1. **Detecção de Falha**: Timeout ou erro de comunicação
2. **Consulta de Réplicas**: Obtém lista de réplicas do servidor de metadados
3. **Redirecionamento**: Tenta réplicas em ordem
4. **Verificação**: Valida checksum dos dados recebidos

### Cache de Conexões:
```python
storage_connections = {
    "localhost:50051": (channel, stub),
    "localhost:50053": (channel, stub),
    # ...
}
```

## Interface do Usuário

### Cliente Básico (client_extended.py):
```
==================================================
🗂️  BigFS-v2 Client - Sistema de Arquivos Distribuído
==================================================
1. 📋 Listar arquivos (ls)
2. 🗑️  Deletar arquivo
3. 📤 Upload de arquivo
4. 📥 Download de arquivo
5. 📋 Copiar arquivo remoto
6. 📊 Status do sistema
7. 🚪 Sair
==================================================
```

### Cliente Avançado (advanced_client.py):
```
============================================================
🗂️  BigFS-v2 Advanced Client
============================================================
1. 📤 Upload paralelo de arquivo grande
2. 📥 Download paralelo de arquivo grande
3. 📤 Upload simples
4. 🔍 Verificar integridade de arquivo
5. 🚪 Sair
============================================================
```

## Funcionalidades Detalhadas

### 1. Listar Arquivos:
- Obtém nó disponível do servidor de metadados
- Lista conteúdo do diretório
- Exibe informações do nó responsável

### 2. Upload:
- **Arquivo Pequeno**: Upload direto
- **Arquivo Grande**: 
  - Divisão automática em chunks
  - Registro no servidor de metadados
  - Upload paralelo (cliente avançado)
  - Verificação de checksums

### 3. Download:
- **Arquivo Pequeno**: Download direto
- **Arquivo Grande**:
  - Consulta localização dos chunks
  - Download com fallback para réplicas
  - Download paralelo (cliente avançado)
  - Recombinação e verificação

### 4. Status do Sistema:
```
📊 Status do Sistema BigFS-v2
========================================
🖥️  Nós ativos: 3/3
📁 Arquivos: 15
📦 Chunks: 47
💾 Storage: 1,234,567 / 10,000,000 bytes

🖥️  Detalhes dos Nós:
  • node_50051: ATIVO - 12.3% usado
  • node_50053: ATIVO - 8.7% usado
  • node_50054: ATIVO - 15.2% usado

📈 Estatísticas:
  • Uploads: 25
  • Downloads: 18
  • Deletes: 3
  • Falhas detectadas: 2
  • Replicações: 12
```

### 5. Verificação de Integridade:
- Verifica checksum de todos os chunks
- Reporta chunks corrompidos
- Sugere ações de recuperação

## Configuração

### Parâmetros:
- **Servidor de Metadados**: Configurável na inicialização
- **Workers Paralelos**: Configurável no cliente avançado (padrão: 4)
- **Tamanho de Chunk**: Configurável no upload paralelo (padrão: 1MB)

### Timeouts e Limites:
- **Timeout gRPC**: Padrão do sistema
- **Tamanho Máximo de Mensagem**: 1GB
- **Máximo de Workers**: Configurável (recomendado: 4-8)

## Tratamento de Erros

### Tipos de Erro:
1. **Servidor de Metadados Indisponível**
2. **Nó de Armazenamento Indisponível**
3. **Checksum Inválido**
4. **Arquivo Não Encontrado**
5. **Espaço Insuficiente**

### Estratégias de Recuperação:
1. **Retry Automático**: Para falhas temporárias
2. **Fallback para Réplicas**: Para falhas de nós
3. **Validação de Dados**: Checksums em todas as operações
4. **Feedback Visual**: Mensagens claras para o usuário

## Uso

### Cliente Básico:
```bash
python client/client_extended.py
```

### Cliente Avançado:
```bash
python client/advanced_client.py
```

### Exemplos de Uso:

#### Upload de Arquivo Grande:
```
Escolha: 3
Arquivo local: /path/to/large_file.zip
Caminho remoto: documents/large_file.zip

📤 Enviando large_file.zip (50,000,000 bytes) para node_50051
Dividindo arquivo em 48 chunks
✅ Arquivo dividido em 48 chunks e salvo com sucesso
```

#### Download com Fallback:
```
Escolha: 4
Arquivo remoto: documents/large_file.zip
Caminho local: /tmp/downloaded_file.zip

📥 Baixando large_file.zip (50,000,000 bytes, 48 chunks)
📦 Baixando chunk 1/48
⚠️ Falha na comunicação com nó primário
✅ Chunk 1 obtido da réplica node_50053
...
🔧 Recombinando chunks...
✅ Arquivo salvo em: /tmp/downloaded_file.zip
```

## Performance

### Otimizações:
- **Cache de Conexões**: Reutiliza conexões gRPC
- **Upload/Download Paralelo**: Múltiplos chunks simultâneos
- **Verificação Assíncrona**: Checksums em background
- **Compressão**: Suporte futuro para compressão de chunks

### Métricas:
- **Tempo de Upload/Download**: Medido automaticamente
- **Taxa de Transferência**: Calculada baseada no tamanho e tempo
- **Taxa de Sucesso**: Porcentagem de operações bem-sucedidas

## Próximos Passos

O Cliente está pronto para:
1. Testes de sistema completo
2. Simulação de falhas e recuperação
3. Testes de performance com arquivos grandes
4. Integração com interface gráfica (futuro)

Todas as funcionalidades da arquitetura documentada estão implementadas e testadas.

