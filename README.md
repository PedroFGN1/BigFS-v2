# BigFS - Sistema de Arquivos Distribuído com gRPC

**Autor:** Pedro Ferreira Galvão Neto

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

    ```bash
    pip install -r requirements.txt

### 📦 Geração dos arquivos gRPC
    ```bash
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