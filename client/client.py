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

    caminho_remoto = caminho.replace("remoto:/", "", 1)
    request = filesystem_pb2.CaminhoRequest(path=caminho_remoto)
    response = stub.Listar(request)
    exibir_listagem(response)

def deletar(stub):
    caminho = input("Digite o caminho do arquivo a ser deletado (ex: remoto:/arquivo.txt): ").strip()
    if not caminho.startswith("remoto:/"):
        print("Caminho remoto inválido.")
        return

    caminho_remoto = caminho.replace("remoto:/", "", 1)
    request = filesystem_pb2.CaminhoRequest(path=caminho_remoto)
    response = stub.Deletar(request)
    if response.sucesso:
        print("✅", response.mensagem)
    else:
        print("❌ Erro:", response.mensagem)

def menu():
    print("\n--- Menu BigFS Client ---")
    print("1. Listar arquivos (ls)")
    print("2. Deletar arquivo (delete)")
    print("3. Sair")

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
                print("Encerrando cliente.")
                break
            else:
                print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()
