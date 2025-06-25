# Documentação da Arquitetura do Sistema BigFS-v2

Este documento descreve a arquitetura proposta para o sistema de arquivos distribuído BigFS-v2, incorporando os requisitos funcionais e não funcionais definidos, as tecnologias a serem utilizadas e um esboço de seu funcionamento. O objetivo é fornecer uma visão clara e organizada do sistema antes de prosseguir com a implementação das funcionalidades adicionais.

## 1. Visão Geral do Sistema BigFS-v2

O BigFS-v2 é uma implementação educacional de um sistema de arquivos distribuído (NFS - Network File System) que utiliza a arquitetura cliente-servidor com gRPC em Python. O projeto original já oferece funcionalidades básicas de manipulação de arquivos, como listagem, deleção, upload, download e cópia. Esta documentação foca na expansão do sistema para incluir requisitos não funcionais de replicação, tolerância a falhas e data sharding, visando maior robustez, disponibilidade e escalabilidade.

## 2. Requisitos Funcionais (RFs)

Os requisitos funcionais do BigFS-v2 abrangem as operações que o sistema deve ser capaz de realizar. Além das funcionalidades já existentes, as novas implementações introduzirão requisitos funcionais implícitos relacionados ao gerenciamento de dados distribuídos.

### 2.1. Funcionalidades Existentes

*   **Listar Conteúdo:** Permitir que clientes listem arquivos e diretórios em um caminho remoto específico.
*   **Deletar Arquivo:** Permitir que clientes removam arquivos de um caminho remoto.
*   **Upload de Arquivo:** Permitir que clientes enviem arquivos locais para o servidor remoto.
*   **Download de Arquivo:** Permitir que clientes baixem arquivos do servidor remoto para um local especificado.
*   **Copiar Arquivo Remoto:** Permitir que clientes copiem arquivos entre diferentes locais no servidor remoto.

### 2.2. Novas Funcionalidades (Implícitas pelas RNFs)

*   **Gerenciamento de Réplicas:** O sistema deve ser capaz de criar, manter e atualizar múltiplas cópias de arquivos em diferentes nós de armazenamento.
*   **Divisão e Recomposição de Chunks:** O sistema deve ser capaz de dividir arquivos grandes em blocos (chunks) para armazenamento distribuído e recompor esses chunks para operações de leitura.
*   **Redirecionamento de Operações:** Em caso de falha de um nó, o sistema deve ser capaz de redirecionar as operações de leitura/escrita para réplicas ou chunks disponíveis em outros nós.
*   **Ressincronização de Nós:** Quando um nó falho retorna, o sistema deve ser capaz de ressincronizá-lo com o estado atual dos dados.

## 3. Requisitos Não Funcionais (RNFs)

Os requisitos não funcionais detalham as qualidades do sistema, como desempenho, confiabilidade e escalabilidade. As escolhas de implementação para replicação, tolerância a falhas e data sharding são abordadas aqui.

### 3.1. Serviço de Replicação

O objetivo é garantir a disponibilidade e a resiliência dos dados mesmo diante de falhas de nós, mantendo pelo menos duas réplicas adicionais em nós distintos.

*   **3.1.1. Gerenciamento de Metadados: Servidor de Metadados Centralizado**
    *   **Descrição:** Será implementado um serviço de metadados dedicado e centralizado. Este serviço será o ponto de verdade para o mapeamento de arquivos para suas réplicas e a localização dos nós de armazenamento. Ele manterá informações sobre a saúde dos nós e a distribuição das réplicas.
    *   **Justificativa:** Simplifica a lógica do cliente e dos nós de armazenamento, que consultam um único ponto para obter informações sobre a localização dos dados. Embora introduza um ponto único de falha, para uma simulação educacional, a complexidade de replicar o próprio servidor de metadados pode ser abordada em uma fase posterior ou simplificada.

*   **3.1.2. Mecanismo de Replicação Assíncrona: Log-shipping/Journaling**
    *   **Descrição:** As operações de escrita no nó primário serão registradas em um log (journal). Este log será assincronamente enviado para as réplicas, que aplicarão as operações em sua própria cópia dos dados. O commit no nó principal ocorrerá antes da propagação completa para as réplicas.
    *   **Justificativa:** Permite baixa latência de escrita no nó primário e se alinha com o requisito de propagação de logs de operações de escrita. O `file_manager.py` existente será estendido para incluir um mecanismo de logging de operações de escrita.

*   **3.1.3. Verificação de Integridade Periódica: Checksums/Hashes e Timestamp/Version Numbers**
    *   **Descrição:** Um processo em segundo plano verificará periodicamente a integridade e a sincronização das réplicas. Isso será feito comparando checksums (e.g., SHA256) dos arquivos e/ou timestamps de última modificação/números de versão entre o nó primário e suas réplicas. Discrepâncias acionarão a ressincronização.
    *   **Justificativa:** Garante que as réplicas eventualmente se tornem consistentes com o nó primário, corrigindo possíveis desvios devido à natureza assíncrona da replicação.

*   **3.1.4. Redirecionamento de Clientes em Caso de Falha: Servidor de Metadados Ativo**
    *   **Descrição:** Em caso de falha do nó primário de um arquivo, o servidor de metadados ativo será responsável por identificar uma réplica saudável e redirecionar as requisições do cliente para essa réplica. O cliente sempre consultará o servidor de metadados para obter o endereço do nó mais adequado para a operação.
    *   **Justificativa:** Centraliza a lógica de failover e garante que os clientes sempre obtenham informações atualizadas sobre a localização dos dados, sem a necessidade de lógica complexa de failover em cada cliente.

### 3.2. Tolerância a Falhas

O sistema deve continuar operando mesmo com falhas de rede ou de componentes, com detecção de falhas, redirecionamento automático, consistência eventual e recuperação.

*   **3.2.1. Detecção de Falhas de Nós: Timeouts RPC e Heartbeats**
    *   **Descrição:** A detecção de falhas será realizada através de uma combinação de timeouts RPC (para detectar nós que não respondem) e um mecanismo de heartbeats. Os nós de armazenamento enviarão periodicamente mensagens de heartbeat para o servidor de metadados. A ausência de heartbeats por um período configurável indicará uma falha.
    *   **Justificativa:** Oferece um mecanismo robusto para identificar nós inativos, permitindo que o sistema reaja rapidamente a falhas.

*   **3.2.2. Redirecionamento Automático: Gerenciado pelo Servidor de Metadados**
    *   **Descrição:** Conforme detalhado na seção de replicação, o servidor de metadados será o responsável por gerenciar o redirecionamento de operações para réplicas disponíveis quando um nó falhar. Ele manterá um mapa atualizado da saúde dos nós e da localização das réplicas.
    *   **Justificativa:** Centraliza a inteligência de failover, tornando o sistema mais fácil de gerenciar e depurar.

*   **3.2.3. Consistência Eventual: Anti-Entropy/Gossip**
    *   **Descrição:** O sistema adotará um modelo de consistência eventual. Para garantir que as atualizações sejam propagadas a todos os nós réplicas, serão implementados mecanismos de anti-entropy ou gossip. Processos em segundo plano compararão periodicamente o estado dos dados entre as réplicas e sincronizarão as diferenças, complementando a replicação baseada em log.
    *   **Justificativa:** É um modelo mais prático para sistemas distribuídos em larga escala, permitindo alta disponibilidade e desempenho, enquanto garante que os dados convergirão para um estado consistente ao longo do tempo.

*   **3.2.4. Recuperação de Falhas e Ressincronização: Reconstrução a partir de Réplicas e Journal/Write-Ahead Log (WAL) Simulado**
    *   **Descrição:** Quando um nó falho retorna, ele será ressincronizado com o estado atual do sistema. Isso envolverá a reconstrução de seu estado a partir de réplicas saudáveis e a aplicação de operações perdidas através de um Journal/Write-Ahead Log (WAL) simulado. O WAL registrará todas as operações de escrita, permitindo que o nó que retorna "reproduza" as operações que ocorreram enquanto estava offline.
    *   **Justificativa:** Garante a durabilidade dos dados e a capacidade de recuperação do sistema após falhas, minimizando a perda de informações.

### 3.3. Data Sharding (Particionamento de Dados)

O objetivo é permitir que arquivos grandes sejam armazenados de forma distribuída, simulando escalabilidade horizontal e acesso eficiente.

*   **3.3.1. Divisão em Chunks: Lógica no Servidor**
    *   **Descrição:** Arquivos com tamanho superior a um limite configurável (e.g., 1MB) serão automaticamente divididos em blocos (chunks) pelo servidor após o recebimento do arquivo completo do cliente. Cada chunk será então armazenado em um nó diferente.
    *   **Justificativa:** Simplifica a lógica do cliente, que envia o arquivo completo, e o servidor se encarrega da complexidade da divisão e distribuição dos chunks.

*   **3.3.2. Gerenciamento de Metadados para Chunks: Servidor de Metadados Dedicado com Hashing Consistente**
    *   **Descrição:** O servidor de metadados centralizado será estendido para armazenar o mapeamento de `(nome_arquivo, número_chunk) -> nó_armazenamento`. Para a distribuição dos chunks entre os nós, será utilizado um algoritmo de Hashing Consistente. Isso permitirá que o servidor de metadados (ou até mesmo o cliente, em um cenário mais avançado) determine qual nó armazena um determinado chunk de forma eficiente.
    *   **Justificativa:** Um servidor de metadados dedicado é essencial para rastrear a localização de cada chunk. O Hashing Consistente ajuda a distribuir a carga de forma uniforme e minimiza o rebalanceamento quando nós são adicionados ou removidos.

*   **3.3.3. Operações de Leitura e Escrita com Múltiplos Chunks: Leitura Paralela e Escrita Paralela**
    *   **Descrição:** As operações de leitura e escrita de arquivos grandes serão tratadas com suporte a múltiplos chunks. Para leitura, o cliente (ou o servidor, agindo como proxy) poderá solicitar múltiplos chunks em paralelo de diferentes nós de armazenamento e recombiná-los na ordem correta. Para escrita, os chunks serão enviados para diferentes nós em paralelo.
    *   **Justificativa:** Permite o aproveitamento do paralelismo e melhora o desempenho para arquivos grandes, simulando uma arquitetura de alta vazão.

*   **3.3.4. Estratégia de Sharding: Hashing de Nomes de Arquivos/Chunks**
    *   **Descrição:** A estratégia de sharding será baseada em uma função de hash aplicada ao nome do arquivo e/ou ao ID do chunk para determinar o nó de armazenamento. Isso visa uma distribuição uniforme dos dados entre os nós disponíveis.
    *   **Justificativa:** Ajuda a distribuir a carga de forma mais equilibrada e a evitar hotspots em nós específicos.

## 4. Tecnologias Utilizadas

*   **Python:** Linguagem de programação principal para o desenvolvimento de todos os componentes do sistema.
*   **gRPC:** Framework de RPC de alto desempenho para a comunicação entre o cliente, o servidor de metadados e os nós de armazenamento.
*   **Múltiplos Processos Python:** Para simular os diferentes nós (servidor de metadados, nós de armazenamento), serão utilizados múltiplos processos Python rodando em ambiente local. Cada processo representará um nó distinto com seu próprio diretório de armazenamento.
*   **Persistência em Arquivos Locais:** Os dados dos arquivos e chunks serão persistidos em arquivos locais dentro dos diretórios de armazenamento de cada nó. Os metadados serão gerenciados pelo servidor de metadados, que também poderá persistir seu estado.
*   **Docker Compose (Uso Posterior):** Embora a simulação inicial seja com múltiplos processos Python, o uso de Docker Compose será considerado posteriormente para criar um ambiente de simulação mais realista e isolado, facilitando a orquestração e a simulação de falhas de rede.

## 5. Esboço de Funcionamento (Arquitetura Proposta)

A arquitetura proposta para o BigFS-v2 com as novas funcionalidades incluirá os seguintes componentes e fluxos de interação:

*   **Cliente BigFS:** Interage com o sistema através de chamadas gRPC. Para operações de arquivo, ele primeiro consulta o Servidor de Metadados para obter a localização dos dados (nó primário, réplicas, chunks).

*   **Servidor de Metadados (SM):** Um serviço gRPC centralizado que:
    *   Mantém o mapeamento de arquivos para nós de armazenamento primários e réplicas.
    *   Armazena o índice de chunks para arquivos grandes (`(nome_arquivo, número_chunk) -> nó_armazenamento`).
    *   Monitora a saúde dos nós de armazenamento via heartbeats e timeouts RPC.
    *   Gerencia o redirecionamento de clientes para réplicas em caso de falha do nó primário.
    *   Coordena a ressincronização de nós que retornam.

*   **Nós de Armazenamento (NA):** Múltiplos processos Python, cada um atuando como um servidor gRPC e gerenciando um diretório de armazenamento local. Cada NA:
    *   Armazena arquivos completos ou chunks de arquivos grandes.
    *   Recebe requisições de leitura/escrita de clientes (redirecionadas pelo SM).
    *   Envia heartbeats para o SM.
    *   Participa do mecanismo de replicação (recebendo logs de operações e aplicando-os).
    *   Realiza a divisão de arquivos em chunks para operações de upload.
    *   Participa da verificação de integridade periódica.

### 5.1. Fluxo de Upload de Arquivo Grande (com Sharding e Replicação)

1.  **Cliente -> SM:** Cliente solicita ao SM o upload de um arquivo grande.
2.  **SM -> Cliente:** SM retorna ao cliente o endereço do nó de armazenamento primário para o upload inicial.
3.  **Cliente -> NA (Primário):** Cliente envia o arquivo completo para o nó de armazenamento primário.
4.  **NA (Primário):** O NA primário recebe o arquivo, divide-o em chunks e persiste cada chunk em seu diretório local.
5.  **NA (Primário) -> SM:** NA primário notifica o SM sobre a criação dos chunks e suas localizações (usando hashing consistente para determinar os NAs de destino para cada chunk).
6.  **SM -> NAs (Réplicas/Chunks):** SM coordena a replicação assíncrona dos chunks para os nós de armazenamento designados como réplicas, enviando logs de operações.
7.  **NAs (Réplicas):** NAs réplicas aplicam as operações do log e armazenam as cópias dos chunks.

### 5.2. Fluxo de Download de Arquivo Grande (com Sharding e Tolerância a Falhas)

1.  **Cliente -> SM:** Cliente solicita ao SM o download de um arquivo grande.
2.  **SM -> Cliente:** SM consulta seu índice de metadados e retorna ao cliente a lista de nós de armazenamento onde os chunks do arquivo estão localizados, priorizando nós saudáveis.
3.  **Cliente -> NAs (Paralelo):** Cliente envia requisições de download para os NAs correspondentes a cada chunk, possivelmente em paralelo.
4.  **NA -> Cliente:** Cada NA envia o chunk solicitado de volta ao cliente.
5.  **Cliente:** Cliente recombina os chunks na ordem correta para formar o arquivo completo.
6.  **Detecção de Falha (Exemplo):** Se um NA falhar durante o download de um chunk, o cliente (ou o SM) detecta a falha (via timeout RPC) e o SM redireciona a requisição para uma réplica do chunk em outro NA.

## 6. Próximos Passos

Com esta arquitetura documentada, os próximos passos para o desenvolvimento incluem:

1.  **Definição Detalhada do Protocolo gRPC:** Estender o `filesystem.proto` com novos serviços e mensagens para o Servidor de Metadados e as operações de replicação/sharding.
2.  **Implementação do Servidor de Metadados:** Desenvolver o serviço centralizado para gerenciar metadados de arquivos e chunks, monitoramento de nós e lógica de failover.
3.  **Adaptação dos Nós de Armazenamento:** Modificar o `server.py` e `file_manager.py` para suportar a divisão de arquivos em chunks, o armazenamento de réplicas e a participação nos mecanismos de detecção de falhas e ressincronização.
4.  **Atualização do Cliente:** Modificar o `client.py` para interagir com o Servidor de Metadados e lidar com operações de arquivos grandes e redirecionamento.
5.  **Desenvolvimento de Testes:** Criar testes abrangentes para validar todas as novas funcionalidades e a resiliência do sistema a falhas.
