import os
import hashlib
import grpc
import pytest
import threading
import time

from proto import filesystem_pb2, filesystem_pb2_grpc

NUM_CLIENTES = 5
ARQUIVOS_POR_CLIENTE = 2
TAMANHO_MB = 50

def gerar_arquivos(pasta, prefixo, n, tam_mb):
    os.makedirs(pasta, exist_ok=True)
    checksums = {}

    for i in range(n):
        nome = f"{prefixo}_{i+1:02}.bin"
        caminho = os.path.join(pasta, nome)
        conteudo = os.urandom(tam_mb * 1024 * 1024)
        with open(caminho, "wb") as f:
            f.write(conteudo)
        checksums[nome] = hashlib.md5(conteudo).hexdigest()

    return checksums

def cliente_simulado(cliente_id, checksums, pasta):
    stub = filesystem_pb2_grpc.FileSystemServiceStub(
        grpc.insecure_channel(
            "localhost:50051",
            options=[
                ("grpc.max_send_message_length", 1024 * 1024 * 1024),
                ("grpc.max_receive_message_length", 1024 * 1024 * 1024),
            ]
        )
    )

    for nome in checksums:
        caminho_local = os.path.join(pasta, nome)
        with open(caminho_local, "rb") as f:
            dados = f.read()

        remoto = f"multicliente/cliente_{cliente_id}/{nome}"
        req = filesystem_pb2.FileUploadRequest(path=remoto, dados=dados)
        resp = stub.Upload(req)
        assert resp.sucesso, f"[Cliente {cliente_id}] Falha ao enviar {nome}"

        # download e validação
        get = stub.Download(filesystem_pb2.CaminhoRequest(path=remoto))
        assert get.sucesso
        hash_recebido = hashlib.md5(get.dados).hexdigest()
        assert hash_recebido == checksums[nome], f"[Cliente {cliente_id}] Arquivo corrompido: {nome}"

def test_concorrencia_multicliente():
    threads = []

    for i in range(1, NUM_CLIENTES + 1):
        pasta = f"tests/clientes/c{i}"
        checksums = gerar_arquivos(pasta, f"c{i}", ARQUIVOS_POR_CLIENTE, TAMANHO_MB)

        t = threading.Thread(target=cliente_simulado, args=(i, checksums, pasta))
        threads.append(t)

    inicio = time.time()

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    fim = time.time()
    print(f"\n✅ Cenário 6: {NUM_CLIENTES} clientes completaram transferências simultâneas.")
    print(f"⏱️ Tempo total: {fim - inicio:.2f} segundos")
