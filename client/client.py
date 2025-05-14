import grpc
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))

import filesystem_pb2
import filesystem_pb2_grpc

def exibir_listagem(response):

    if response.sucesso:
        print(f"\nTipo: {response.tipo}")
        for item in response.conteudo:
            print("  -", item)
    else:
        print("❌ Erro:", response.mensagem)

def listar(stub):
    caminho = input("Digite o caminho remoto (ex: remoto:/): ").strip()
    if not caminho.startswith("remoto:/"):
        print("Caminho remoto inválido.")
        return

    caminho_remoto = caminho.replace("remoto:/", "", 1).strip("\\/")

    request = filesystem_pb2.CaminhoRequest(path=caminho_remoto)
    response = stub.Listar(request)
    exibir_listagem(response)

def deletar(stub):
    caminho = input("Digite o caminho do arquivo a ser deletado (ex: remoto:/arquivo.txt): ").strip()
    if not caminho.startswith("remoto:/"):
        print("Caminho remoto inválido.")
        return

    caminho_remoto = caminho.replace("remoto:/", "", 1).strip("\\/")

    request = filesystem_pb2.CaminhoRequest(path=caminho_remoto)
    response = stub.Deletar(request)
    if response.sucesso:
        print("✅", response.mensagem)
    else:
        print("❌ Erro:", response.mensagem)

def upload(stub):
    caminho_local = input("Digite o caminho do arquivo local (ex: caminho relativo): ").strip()
    caminho_remoto = input("Digite o caminho remoto de destino (ex: remoto:/destino.txt): ").strip()

    if not os.path.exists(caminho_local):
        print("❌ Arquivo local não encontrado.")
        return

    if not caminho_remoto.startswith("remoto:/"):
        print("❌ Caminho remoto inválido.")
        return

    with open(caminho_local, "rb") as f:
        dados = f.read()

    request = filesystem_pb2.FileUploadRequest(
        path=caminho_remoto.replace("remoto:/", "", 1),
        dados=dados
    )

    response = stub.Upload(request)
    if response.sucesso:
        print("✅", response.mensagem)
    else:
        print("❌ Erro:", response.mensagem)

def download(stub):
    caminho_remoto = input("Digite o caminho remoto (ex: remoto:/arquivo.txt): ").strip()
    caminho_local = input("Digite o caminho local para salvar o arquivo: ").strip()

    if not caminho_remoto.startswith("remoto:/"):
        print("❌ Caminho remoto inválido.")
        return

    request = filesystem_pb2.CaminhoRequest(
        path=caminho_remoto.replace("remoto:/", "", 1)
    )

    response = stub.Download(request)

    if response.sucesso:
        try:
            with open(caminho_local, "wb") as f:
                f.write(response.dados)
            print("✅ Arquivo salvo com sucesso em:", caminho_local)
        except Exception as e:
            print("❌ Erro ao salvar o arquivo local:", str(e))
    else:
        print("❌ Erro no download:", response.mensagem)

def copiar_remoto(stub):
    origem = input("Digite o caminho remoto de origem (ex: remoto:/origem.txt): ").strip()
    destino = input("Digite o caminho remoto de destino (ex: remoto:/copia.txt): ").strip()

    if not origem.startswith("remoto:/") or not destino.startswith("remoto:/"):
        print("❌ Caminhos remotos inválidos.")
        return

    request = filesystem_pb2.CopyRequest(
        origem=origem.replace("remoto:/", "", 1).strip("\\/"),
        destino=destino.replace("remoto:/", "", 1).strip("\\/")
    )

    response = stub.CopiarInterno(request)
    if response.sucesso:
        print("✅", response.mensagem)
    else:
        print("❌ Erro:", response.mensagem)


def menu():
    print("\n--- Menu BigFS Client ---")
    print("1. Listar arquivos (ls)")
    print("2. Deletar arquivo (delete)")
    print("3. Enviar arquivo para o servidor (upload)")
    print("4. Baixar arquivo do servidor (download)")
    print("5. Copiar entre arquivos remotos")
    print("6. Sair")

def main():
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = filesystem_pb2_grpc.FileSystemServiceStub(channel)

        while True:
            menu()
            escolha = input("Escolha uma opção: ").strip()

            if escolha == "1":
                listar(stub)
            elif escolha == "2":
                deletar(stub)
            elif escolha == "3":
                upload(stub)
            elif escolha == "4":
                download(stub)
            elif escolha == "5":
                copiar_remoto(stub)
            elif escolha == "6":
                print("Encerrando cliente.")
                break
            else:
                print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()
