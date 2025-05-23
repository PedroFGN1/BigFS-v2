import os
import hashlib
import grpc
import pytest
import time

import filesystem_pb2, filesystem_pb2_grpc

FAKE_SIZE_MB = 200  # Altere para 5120 para 5 GB

@pytest.fixture(scope="module")
def grpc_stub():
    channel = grpc.insecure_channel(
        "localhost:50051",
        options=[
            ("grpc.max_send_message_length", 6 * 1024 * 1024 * 1024),
            ("grpc.max_receive_message_length", 6 * 1024 * 1024 * 1024),
        ]
    )
    stub = filesystem_pb2_grpc.FileSystemServiceStub(channel)
    yield stub
    channel.close()

def test_upload_unico_arquivo_grande(grpc_stub):
    pasta = "tests/arquivo_grande"
    os.makedirs(pasta, exist_ok=True)

    nome = f"grande_{FAKE_SIZE_MB}mb.bin"
    caminho = os.path.join(pasta, nome)

    # Gera o arquivo de teste (se não existir)
    if not os.path.exists(caminho):
        with open(caminho, "wb") as f:
            f.write(os.urandom(FAKE_SIZE_MB * 1024 * 1024))

    # Calcula o hash
    with open(caminho, "rb") as f:
        dados = f.read()
        hash_origem = hashlib.md5(dados).hexdigest()

    caminho_remoto = f"grande_unico/{nome}"

    # Upload
    print(f"\n⬆️ Enviando arquivo de {FAKE_SIZE_MB} MB...")
    inicio = time.time()
    resp = grpc_stub.Upload(filesystem_pb2.FileUploadRequest(
        path=caminho_remoto,
        dados=dados
    ))
    fim = time.time()
    assert resp.sucesso, f"Falha no upload: {resp.mensagem}"
    print(f"✅ Upload concluído em {fim - inicio:.2f} s")

    # Download e validação
    print("⬇️ Fazendo download para verificação...")
    get = grpc_stub.Download(filesystem_pb2.CaminhoRequest(path=caminho_remoto))
    assert get.sucesso, f"Erro no download: {get.mensagem}"

    hash_recebido = hashlib.md5(get.dados).hexdigest()
    assert hash_recebido == hash_origem, "❌ Arquivo corrompido após envio"

    print("✅ Arquivo íntegro após upload e download.")
