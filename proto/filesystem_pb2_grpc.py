# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

import filesystem_pb2 as proto_dot_filesystem__pb2

GRPC_GENERATED_VERSION = '1.71.0'
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + f' but the generated code in proto/filesystem_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class FileSystemServiceStub(object):
    """Serviço que representa operações sobre um sistema de arquivos distribuído
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Listar = channel.unary_unary(
                '/filesystem.FileSystemService/Listar',
                request_serializer=proto_dot_filesystem__pb2.CaminhoRequest.SerializeToString,
                response_deserializer=proto_dot_filesystem__pb2.ConteudoResponse.FromString,
                _registered_method=True)
        self.Copiar = channel.unary_unary(
                '/filesystem.FileSystemService/Copiar',
                request_serializer=proto_dot_filesystem__pb2.CopyRequest.SerializeToString,
                response_deserializer=proto_dot_filesystem__pb2.OperacaoResponse.FromString,
                _registered_method=True)
        self.Upload = channel.unary_unary(
                '/filesystem.FileSystemService/Upload',
                request_serializer=proto_dot_filesystem__pb2.FileUploadRequest.SerializeToString,
                response_deserializer=proto_dot_filesystem__pb2.OperacaoResponse.FromString,
                _registered_method=True)
        self.Download = channel.unary_unary(
                '/filesystem.FileSystemService/Download',
                request_serializer=proto_dot_filesystem__pb2.CaminhoRequest.SerializeToString,
                response_deserializer=proto_dot_filesystem__pb2.FileDownloadResponse.FromString,
                _registered_method=True)
        self.CopiarInterno = channel.unary_unary(
                '/filesystem.FileSystemService/CopiarInterno',
                request_serializer=proto_dot_filesystem__pb2.CopyRequest.SerializeToString,
                response_deserializer=proto_dot_filesystem__pb2.OperacaoResponse.FromString,
                _registered_method=True)
        self.Deletar = channel.unary_unary(
                '/filesystem.FileSystemService/Deletar',
                request_serializer=proto_dot_filesystem__pb2.CaminhoRequest.SerializeToString,
                response_deserializer=proto_dot_filesystem__pb2.OperacaoResponse.FromString,
                _registered_method=True)


class FileSystemServiceServicer(object):
    """Serviço que representa operações sobre um sistema de arquivos distribuído
    """

    def Listar(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Copiar(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Upload(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Download(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CopiarInterno(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Deletar(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_FileSystemServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Listar': grpc.unary_unary_rpc_method_handler(
                    servicer.Listar,
                    request_deserializer=proto_dot_filesystem__pb2.CaminhoRequest.FromString,
                    response_serializer=proto_dot_filesystem__pb2.ConteudoResponse.SerializeToString,
            ),
            'Copiar': grpc.unary_unary_rpc_method_handler(
                    servicer.Copiar,
                    request_deserializer=proto_dot_filesystem__pb2.CopyRequest.FromString,
                    response_serializer=proto_dot_filesystem__pb2.OperacaoResponse.SerializeToString,
            ),
            'Upload': grpc.unary_unary_rpc_method_handler(
                    servicer.Upload,
                    request_deserializer=proto_dot_filesystem__pb2.FileUploadRequest.FromString,
                    response_serializer=proto_dot_filesystem__pb2.OperacaoResponse.SerializeToString,
            ),
            'Download': grpc.unary_unary_rpc_method_handler(
                    servicer.Download,
                    request_deserializer=proto_dot_filesystem__pb2.CaminhoRequest.FromString,
                    response_serializer=proto_dot_filesystem__pb2.FileDownloadResponse.SerializeToString,
            ),
            'CopiarInterno': grpc.unary_unary_rpc_method_handler(
                    servicer.CopiarInterno,
                    request_deserializer=proto_dot_filesystem__pb2.CopyRequest.FromString,
                    response_serializer=proto_dot_filesystem__pb2.OperacaoResponse.SerializeToString,
            ),
            'Deletar': grpc.unary_unary_rpc_method_handler(
                    servicer.Deletar,
                    request_deserializer=proto_dot_filesystem__pb2.CaminhoRequest.FromString,
                    response_serializer=proto_dot_filesystem__pb2.OperacaoResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'filesystem.FileSystemService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('filesystem.FileSystemService', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class FileSystemService(object):
    """Serviço que representa operações sobre um sistema de arquivos distribuído
    """

    @staticmethod
    def Listar(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/filesystem.FileSystemService/Listar',
            proto_dot_filesystem__pb2.CaminhoRequest.SerializeToString,
            proto_dot_filesystem__pb2.ConteudoResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Copiar(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/filesystem.FileSystemService/Copiar',
            proto_dot_filesystem__pb2.CopyRequest.SerializeToString,
            proto_dot_filesystem__pb2.OperacaoResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Upload(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/filesystem.FileSystemService/Upload',
            proto_dot_filesystem__pb2.FileUploadRequest.SerializeToString,
            proto_dot_filesystem__pb2.OperacaoResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Download(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/filesystem.FileSystemService/Download',
            proto_dot_filesystem__pb2.CaminhoRequest.SerializeToString,
            proto_dot_filesystem__pb2.FileDownloadResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def CopiarInterno(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/filesystem.FileSystemService/CopiarInterno',
            proto_dot_filesystem__pb2.CopyRequest.SerializeToString,
            proto_dot_filesystem__pb2.OperacaoResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Deletar(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/filesystem.FileSystemService/Deletar',
            proto_dot_filesystem__pb2.CaminhoRequest.SerializeToString,
            proto_dot_filesystem__pb2.OperacaoResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
