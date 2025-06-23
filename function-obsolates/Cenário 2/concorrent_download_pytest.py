import os
import hashlib
import threading
import grpc
import time
import pytest

import filesystem_pb2
import filesystem_pb2_grpc

NUM_THREADS = 10
TOTAL_ARQUIVOS = 1000
TAMANHO_KB = 256

@pytest.fixture(scope="module")
def grpc_stub():
    channel = grpc.insecure_channel("localhost:50051")
    stub = filesystem_pb2_grpc.FileSystemServiceStub(channel)
    yield stub
    channel.close()

@pytest.fixture(scope="module")
def arquivos_pequenos():
    pasta = "tests/concorrente"
    os.makedirs(pasta, exist_ok=True)

    checksums = {}
    for i in range(TOTAL_ARQUIVOS):
        nome = f"arquivo_{i:04}.bin"
        caminho = os.path.join(pasta, nome)
        conteudo = os.urandom(TAMANHO_KB * 1024)
        with open(caminho, "wb") as f:
            f.write(conteudo)
        checksums[nome] = hashlib.md5(conteudo).hexdigest()

    return checksums, pasta

def upload_thread(stub, arquivos):
    for nome, dados in arquivos:
        request = filesystem_pb2.FileUploadRequest(
            path=f"concorrente/{nome}",
            dados=dados
        )
        response = stub.Upload(request)
        assert response.sucesso, f"Falha no upload: {nome}"

def download_thread(stub, arquivos, checksums):
    for nome in arquivos:
        request = filesystem_pb2.CaminhoRequest(path=f"concorrente/{nome}")
        response = stub.Download(request)
        assert response.sucesso, f"Falha no download: {nome}"
        hash_recebido = hashlib.md5(response.dados).hexdigest()
        assert hash_recebido == checksums[nome], f"Checksum incorreto: {nome}"

def test_upload_concorrente(grpc_stub, arquivos_pequenos):
    checksums, pasta = arquivos_pequenos

    arquivos_dados = []
    for nome in checksums:
        caminho = os.path.join(pasta, nome)
        with open(caminho, "rb") as f:
            arquivos_dados.append((nome, f.read()))

    blocos = [arquivos_dados[i::NUM_THREADS] for i in range(NUM_THREADS)]
    threads = []

    inicio = time.time()

    for i in range(NUM_THREADS):
        t = threading.Thread(target=upload_thread, args=(grpc_stub, blocos[i]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    fim = time.time()
    print(f"\n✅ Upload concorrente de {TOTAL_ARQUIVOS} arquivos concluído.")
    print(f"⏱️ Tempo total: {fim - inicio:.2f} segundos")

def test_download_concorrente(grpc_stub, arquivos_pequenos):
    checksums, _ = arquivos_pequenos
    nomes = list(checksums.keys())[:500]  # apenas 500 arquivos

    blocos = [nomes[i::NUM_THREADS] for i in range(NUM_THREADS)]
    threads = []

    inicio = time.time()

    for i in range(NUM_THREADS):
        t = threading.Thread(target=download_thread, args=(grpc_stub, blocos[i], checksums))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    fim = time.time()
    print(f"\n✅ Download concorrente de 500 arquivos concluído.")
    print(f"⏱️ Tempo total: {fim - inicio:.2f} segundos")
