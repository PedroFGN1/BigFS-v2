# BigFS - Sistema de Arquivos Distribuído com gRPC

👨‍💻 **Autor:** Pedro Ferreira Galvão Neto — Projeto acadêmico para a disciplina Sistemas Distribuídos I

BigFS é uma implementação educacional de um sistema **NFS (Network File System)** usando a arquitetura cliente-servidor com gRPC em Python.

O projeto permite operações remotas como listar, copiar, deletar, enviar e baixar arquivos entre clientes e um servidor central que exporta um diretório local.

---

## 📁 Estrutura do Projeto
    BigFS-v2/
    ├── client/ # Cliente interativo gRPC
    │ └── client.py
    ├── server/ # Servidor NFS
    │ ├── server.py
    │ └── file_manager.py
    ├── proto/ # Definições .proto e gerados
    │ └── filesystem.proto
    ├── storage/ # Diretório compartilhado exportado pelo servidor
    ├── local/ # Pasta opcional para testes locais
    ├── requirements.txt
    └── README.md

---

## ⚙️ Requisitos

    - Python 3.10+
    - `grpcio`
    - `grpcio-tools`

    Instale com:

        pip install -r requirements.txt

### 📦 Geração dos arquivos gRPC

    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/filesystem.proto

### 🚀 Como executar

1. Iniciar o servidor:
    ```bash
    python server.py

2. Executar o cliente:
    ```bash
    python client.py

### 🧭 Funcionalidades disponíveis
O cliente oferece um menu interativo com as seguintes opções:

1. Listar arquivos remotos
    ```bash
    ls remoto:/subpasta

2. Deletar arquivo remoto
    ```bash
    delete remoto:/arquivo.txt

3. Enviar arquivo local para o servidor (upload)
    ```bash
    copy local.txt remoto:/subpasta/destino.txt

4. Baixar arquivo remoto para local (download)
    ```bash
    copy remoto:/arquivo.txt local.txt

5. Copiar arquivo remoto para outro local remoto
    ```bash
    copy remoto:/arquivo1.txt remoto:/copia_arquivo1.txt

### 🔒 Segurança
*Todos os caminhos são restritos ao diretório storage/.

*Qualquer tentativa de acessar fora do escopo resulta em erro.

*Uploads e downloads suportam qualquer tipo de arquivo via bytes.

### 🧪 Exemplos práticos
1. **Upload**
    Crie arquivos_local/exemplo.txt. Use a opção 3 no menu e envie como: 
    ```bash
    arquivos_local/exemplo.txt → remoto:/exemplo.txt

2. **Download**
    Escolha a opção 4 no menu:
    ```bash
    remoto:/exemplo.txt → arquivos_local/copia.txt

3. **Cópia remota**
    Com o arquivo remoto:/exemplo.txt já no servidor:
    ```bash
    copy remoto:/exemplo.txt remoto:/backup/exemplo_bkp.txt

### 📜 Arquitetura gRPC
    O serviço FileSystemService define os seguintes métodos:
    
    service FileSystemService {
    rpc Listar (CaminhoRequest) returns (ConteudoResponse);
    rpc Deletar (CaminhoRequest) returns (OperacaoResponse);
    rpc Upload (FileUploadRequest) returns (OperacaoResponse);
    rpc Download (CaminhoRequest) returns (FileDownloadResponse);
    rpc CopiarInterno (CopyRequest) returns (OperacaoResponse);
    }

## Print de Execução:

### Cliente
![terminal do cliente](images/client.png)

### Servidor
![terminal do servidor](images/server.png)

# ✅ Testes de Validação do Sistema BigFS

Este diretório contém a suíte automatizada de testes para validação da implementação do sistema de arquivos distribuído **BigFS**, desenvolvido com Python e gRPC.

Os testes foram escritos com a biblioteca **pytest**, simulando os cenários exigidos para validação de desempenho, integridade, concorrência e robustez.

**Para executar o teste é preciso elevar o arquivo de teste da pasta do cenário para a pasta proto.**

---

## 📦 Como executar os testes

1. Certifique-se de que o servidor está ativo:
   ```bash
   python -m server.server
   ```

2. Em outro terminal, rode os testes:
   ```bash
   pytest -s -v tests/
   ```

> A flag `-s` exibe os `print()` com tempos e validações.

---

## 🔧 Requisitos

Instale o `pytest`:

```bash
pip install pytest
```

Certifique-se também de que os arquivos `.proto` foram gerados corretamente e que o módulo `proto` está acessível.

---

## 🧪 Testes implementados

### ✅ `upload_pytest.py`
**Cenário 1 – Upload sequencial de arquivos pequenos**  
Cria 100 arquivos de 512 KB, envia um por um e valida integridade via `md5`.

---

### ✅ `concorrent_download_pytest.py`
**Cenário 2 – Upload/download concorrente com arquivos pequenos**  
1000 arquivos são divididos entre 10 threads para upload e outras 10 threads para download simultâneo.

---

### ✅ `test_grandes_sequenciais.py`
**Cenário 5 – Envio de múltiplos arquivos grandes sequenciais**  
10 arquivos grandes (simulados com 10–100 MB) são enviados um a um e baixados para validação.

---

### ✅ `test_upload_grande_unico.py`
**Cenário 4 – Envio de 1 arquivo de 5 GB (ou simulado)**  
Simula o envio de um único arquivo gigante e verifica a integridade completa após o download.

---

### ✅ `test_carga_mista.py`
**Cenário 8 – Transferência mista de arquivos grandes e pequenos em paralelo**  
Envia 200 arquivos pequenos + 5 grandes, em paralelo, com 4 threads.

---

### ✅ `test_multicliente_grandes.py`
**Cenário 6 – Vários clientes enviando arquivos grandes ao mesmo tempo**  
5 clientes simulados (threads com conexões distintas) enviam 2 arquivos grandes cada, simultaneamente.

---

### ✅ `test_leitura_massa_pequenos.py`
**Cenário 3 / 7 – Leitura em massa de arquivos pequenos**  
1.000 arquivos pequenos são lidos e validados em paralelo com 10 threads.

---

## 🗂 Organização dos arquivos gerados

Os arquivos de teste são organizados por pasta:

```
proto/
├── upload_pytest.py                         # arquivos pequenos (cenário 1)
├── concorrent_download_pytest.py            # upload concorrente
├── test_grandes_sequenciais.py              # arquivos grandes sequenciais
├── test_carga_mista.py                      # carga mista
├── test_multicliente_grandes.py             # múltiplos usuários
├── test_leitura_massa_pequenos.py           # leitura em massa
```

---

## 📌 Observações finais

- Todos os testes validam **sucesso da resposta gRPC** e **integridade do conteúdo via hash**.
- Os limites de tamanho de mensagem gRPC foram ajustados para suportar grandes arquivos.
- Você pode aumentar os tamanhos dos arquivos nos testes alterando as constantes `TAMANHO_MB`, `TOTAL_ARQUIVOS`, etc.

---

## 👨‍🔬 Autor dos testes

Pedro Galvão – Projeto acadêmico para disciplina de **Sistemas Distribuídos I**