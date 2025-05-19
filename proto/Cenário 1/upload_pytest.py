import os
import grpc
import hashlib
import time
import pytest

import filesystem_pb2
import filesystem_pb2_grpc

@pytest.fixture(scope="module")
def grpc_stub():
    channel = grpc.insecure_channel("localhost:50051")
    stub = filesystem_pb2_grpc.FileSystemServiceStub(channel)
    yield stub
    channel.close()

@pytest.fixture(scope="module")
def arquivos_pequenos():
    total = 100
    tamanho_kb = 512
    pasta = "tests/arquivos_teste"
    os.makedirs(pasta, exist_ok=True)

    checksums = {}

    for i in range(total):
        nome = f"arquivo_{i:03}.bin"
        caminho = os.path.join(pasta, nome)
        conteudo = os.urandom(tamanho_kb * 1024)
        with open(caminho, "wb") as f:
            f.write(conteudo)
        checksums[nome] = hashlib.md5(conteudo).hexdigest()

    return checksums, pasta

def test_upload_e_integridade(grpc_stub, arquivos_pequenos):
    checksums, pasta = arquivos_pequenos
    latencias = []

    for nome, checksum_esperado in checksums.items():
        caminho_local = os.path.join(pasta, nome)
        caminho_remoto = f"cen1/{nome}"

        with open(caminho_local, "rb") as f:
            dados = f.read()

        request = filesystem_pb2.FileUploadRequest(path=caminho_remoto, dados=dados)

        inicio = time.time()
        response = grpc_stub.Upload(request)
        fim = time.time()

        assert response.sucesso, f"Falha no upload de {nome}"
        latencias.append(fim - inicio)

        # Baixa e verifica integridade
        get_req = filesystem_pb2.CaminhoRequest(path=caminho_remoto)
        get_resp = grpc_stub.Download(get_req)
        assert get_resp.sucesso, f"Falha no download de {nome}"
        hash_recebido = hashlib.md5(get_resp.dados).hexdigest()
        assert hash_recebido == checksum_esperado, f"Arquivo corrompido: {nome}"

    media = sum(latencias) / len(latencias)
    print(f"\n✅ Upload de {len(checksums)} arquivos concluído.")
    print(f"⏱️ Latência média por arquivo: {media:.3f} segundos")
