import os
import hashlib
import grpc
import pytest
import time
import threading

from proto import filesystem_pb2, filesystem_pb2_grpc

PEQUENOS_TOTAL = 200
GRANDES_TOTAL = 5
PEQUENO_KB = 256
GRANDE_MB = 50
NUM_THREADS = 4

@pytest.fixture(scope="module")
def grpc_stub():
    channel = grpc.insecure_channel(
        "localhost:50051",
        options=[
            ("grpc.max_send_message_length", 1024 * 1024 * 1024),
            ("grpc.max_receive_message_length", 1024 * 1024 * 1024),
        ]
    )
    stub = filesystem_pb2_grpc.FileSystemServiceStub(channel)
    yield stub
    channel.close()

@pytest.fixture(scope="module")
def arquivos_mistos():
    pasta = "tests/mistos"
    os.makedirs(pasta, exist_ok=True)
    checksums = {}

    # Arquivos pequenos
    for i in range(PEQUENOS_TOTAL):
        nome = f"p_{i:03}.bin"
        caminho = os.path.join(pasta, nome)
        conteudo = os.urandom(PEQUENO_KB * 1024)
        with open(caminho, "wb") as f:
            f.write(conteudo)
        checksums[nome] = hashlib.md5(conteudo).hexdigest()

    # Arquivos grandes
    for i in range(GRANDES_TOTAL):
        nome = f"g_{i+1:02}.bin"
        caminho = os.path.join(pasta, nome)
        conteudo = os.urandom(GRANDE_MB * 1024 * 1024)
        with open(caminho, "wb") as f:
            f.write(conteudo)
        checksums[nome] = hashlib.md5(conteudo).hexdigest()

    return checksums, pasta

def upload_misto(stub, blocos):
    for nome, dados in blocos:
        caminho_remoto = f"mistos/{nome}"
        request = filesystem_pb2.FileUploadRequest(path=caminho_remoto, dados=dados)
        response = stub.Upload(request)
        assert response.sucesso, f"Falha ao enviar {nome}"

def test_upload_misto_concorrente(grpc_stub, arquivos_mistos):
    checksums, pasta = arquivos_mistos

    arquivos_dados = []
    for nome in checksums:
        with open(os.path.join(pasta, nome), "rb") as f:
            arquivos_dados.append((nome, f.read()))

    blocos = [arquivos_dados[i::NUM_THREADS] for i in range(NUM_THREADS)]
    threads = []

    inicio = time.time()

    for i in range(NUM_THREADS):
        t = threading.Thread(target=upload_misto, args=(grpc_stub, blocos[i]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    fim = time.time()
    print(f"\n✅ Upload misto concluído em {fim - inicio:.2f} segundos.")
    print(f"Total de arquivos: {len(arquivos_dados)}")

    # Validação
    for nome, checksum_esperado in checksums.items():
        caminho_remoto = f"mistos/{nome}"
        req = filesystem_pb2.CaminhoRequest(path=caminho_remoto)
        resp = grpc_stub.Download(req)
        assert resp.sucesso, f"Erro no download: {nome}"
        hash_recebido = hashlib.md5(resp.dados).hexdigest()
        assert hash_recebido == checksum_esperado, f"Arquivo corrompido: {nome}"
