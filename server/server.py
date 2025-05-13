import grpc
from concurrent import futures
import time
import os

import sys
# Adiciona o diretório proto ao sys.path para importar os arquivos gerados
# Isso é necessário para que o Python encontre os arquivos .proto gerados
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))

import filesystem_pb2 as filesystem_pb2
import filesystem_pb2_grpc as filesystem_pb2_grpc

from file_manager import listar_conteudo, deletar_arquivo

# Caminho do diretório exportado
BASE_DIR = os.path.abspath("../storage")

class FileSystemServiceServicer(filesystem_pb2_grpc.FileSystemServiceServicer):

    def Listar(self, request, context):
        sucesso, mensagem, tipo, conteudo = listar_conteudo(BASE_DIR, request.path)

        return filesystem_pb2.ConteudoResponse(
            sucesso=sucesso,
            mensagem=mensagem,
            tipo=tipo or "",
            conteudo=conteudo or []
        )
    
    def Deletar(self, request, context):
        sucesso, mensagem = deletar_arquivo(BASE_DIR, request.path)

        return filesystem_pb2.OperacaoResponse(
            sucesso=sucesso,
            mensagem=mensagem
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    filesystem_pb2_grpc.add_FileSystemServiceServicer_to_server(
        FileSystemServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    print("Servidor gRPC iniciado em [::]:50051...")
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        print("Encerrando servidor...")
        server.stop(0)

if __name__ == "__main__":
    serve()