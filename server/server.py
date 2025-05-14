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

from file_manager import listar_conteudo, deletar_arquivo, salvar_arquivo, ler_arquivo, copiar_arquivo

# Caminho do diretório exportado
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../storage"))

class FileSystemServiceServicer(filesystem_pb2_grpc.FileSystemServiceServicer):

    # Método para listar arquivos e diretórios
    # O método recebe um caminho e retorna o conteúdo desse caminho
    def Listar(self, request, context):

        try:
            sucesso, mensagem, tipo, conteudo = listar_conteudo(BASE_DIR, request.path)
            return filesystem_pb2.ConteudoResponse(
                sucesso=sucesso,
                mensagem=mensagem,
                tipo=tipo or "",
                conteudo=conteudo or []
            )
        
        except Exception as e:
            return filesystem_pb2.ConteudoResponse(
                sucesso=False,
                mensagem=f"Erro interno no servidor: {str(e)}",
                tipo="",
                conteudo=[]
            )
    
    # Método para deletar arquivos
    # O método recebe um caminho e deleta o arquivo correspondente
    def Deletar(self, request, context):
        sucesso, mensagem = deletar_arquivo(BASE_DIR, request.path)

        return filesystem_pb2.OperacaoResponse(
            sucesso=sucesso,
            mensagem=mensagem
        )
    
    # Método para upload de arquivos
    # O método recebe um caminho e os dados do arquivo
    def Upload(self, request, context):
        sucesso, mensagem = salvar_arquivo(BASE_DIR, request.path, request.dados)
        return filesystem_pb2.OperacaoResponse(
            sucesso=sucesso,
            mensagem=mensagem
        )

    # Método para download de arquivos
    # O método recebe um caminho e retorna os dados do arquivo
    def Download(self, request, context):
        sucesso, mensagem, dados = ler_arquivo(BASE_DIR, request.path)
        return filesystem_pb2.FileDownloadResponse(
            sucesso=sucesso,
            mensagem=mensagem,
            dados=dados or b""
        )
    
    # Método para copiar arquivos
    # O método recebe um caminho de origem e um caminho de destino
    def CopiarInterno(self, request, context):
        sucesso, mensagem = copiar_arquivo(BASE_DIR, request.origem, request.destino)
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