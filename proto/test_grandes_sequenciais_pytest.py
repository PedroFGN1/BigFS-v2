import os
import hashlib
import grpc
import pytest
import time

import filesystem_pb2, filesystem_pb2_grpc

TOTAL_ARQUIVOS = 10
TAMANHO_MB = 1024  # Altere para 2048 para testar com 2 GB reais

@pytest.fixture(scope="module")
def grpc_stub():
    channel = grpc.insecure_channel("localhost:50051")
    stub = filesystem_pb2_grpc.FileSystemServiceStub(channel)
    yield stub
    channel.close()

@pytest.fixture(scope="module")
def arquivos_grandes():
    pasta = "tests/grandes"
    os.makedirs(pasta, exist_ok=True)
    checksums = {}

    for i in range(TOTAL_ARQUIVOS):
        nome = f"grande_{i+1:02}.bin"
        caminho = os.path.join(pasta, nome)
        conteudo = os.urandom(TAMANHO_MB * 1024 * 1024)
        with open(caminho, "wb") as f:
            f.write(conteudo)
        checksums[nome] = hashlib.md5(conteudo).hexdigest()

    return checksums, pasta

def test_upload_grandes_sequencial(grpc_stub, arquivos_grandes):
    checksums, pasta = arquivos_grandes
    total_tempo = 0

    for nome, checksum_esperado in checksums.items():
        caminho_local = os.path.join(pasta, nome)
        with open(caminho_local, "rb") as f:
            dados = f.read()

        request = filesystem_pb2.FileUploadRequest(
            path=f"grandes/{nome}",
            dados=dados
        )

        inicio = time.time()
        response = grpc_stub.Upload(request)
        fim = time.time()

        assert response.sucesso, f"Falha no upload de {nome}"
        total_tempo += (fim - inicio)
        print(f"✅ Upload de {nome} em {fim - inicio:.2f} s")

        # Validação via download
        resp = grpc_stub.Download(filesystem_pb2.CaminhoRequest(path=f"grandes/{nome}"))
        assert resp.sucesso, f"Falha no download de {nome}"
        hash_recebido = hashlib.md5(resp.dados).hexdigest()
        assert hash_recebido == checksum_esperado, f"Arquivo corrompido: {nome}"

    print(f"\n📦 Upload de {TOTAL_ARQUIVOS} arquivos grandes finalizado.")
    print(f"⏱️ Tempo total: {total_tempo:.2f} segundos")
