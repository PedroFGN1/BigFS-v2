# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: proto/filesystem.proto
# Protobuf Python Version: 5.29.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    0,
    '',
    'proto/filesystem.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x16proto/filesystem.proto\x12\nfilesystem\"\x1e\n\x0e\x43\x61minhoRequest\x12\x0c\n\x04path\x18\x01 \x01(\t\"0\n\x11\x46ileUploadRequest\x12\x0c\n\x04path\x18\x01 \x01(\t\x12\r\n\x05\x64\x61\x64os\x18\x02 \x01(\x0c\"H\n\x14\x46ileDownloadResponse\x12\x0f\n\x07sucesso\x18\x01 \x01(\x08\x12\x10\n\x08mensagem\x18\x02 \x01(\t\x12\r\n\x05\x64\x61\x64os\x18\x03 \x01(\x0c\".\n\x0b\x43opyRequest\x12\x0e\n\x06origem\x18\x01 \x01(\t\x12\x0f\n\x07\x64\x65stino\x18\x02 \x01(\t\"5\n\x10OperacaoResponse\x12\x0f\n\x07sucesso\x18\x01 \x01(\x08\x12\x10\n\x08mensagem\x18\x02 \x01(\t\"U\n\x10\x43onteudoResponse\x12\x0f\n\x07sucesso\x18\x01 \x01(\x08\x12\x0c\n\x04tipo\x18\x02 \x01(\t\x12\x10\n\x08\x63onteudo\x18\x03 \x03(\t\x12\x10\n\x08mensagem\x18\x04 \x01(\t2\xb6\x03\n\x11\x46ileSystemService\x12\x42\n\x06Listar\x12\x1a.filesystem.CaminhoRequest\x1a\x1c.filesystem.ConteudoResponse\x12?\n\x06\x43opiar\x12\x17.filesystem.CopyRequest\x1a\x1c.filesystem.OperacaoResponse\x12\x45\n\x06Upload\x12\x1d.filesystem.FileUploadRequest\x1a\x1c.filesystem.OperacaoResponse\x12H\n\x08\x44ownload\x12\x1a.filesystem.CaminhoRequest\x1a .filesystem.FileDownloadResponse\x12\x46\n\rCopiarInterno\x12\x17.filesystem.CopyRequest\x1a\x1c.filesystem.OperacaoResponse\x12\x43\n\x07\x44\x65letar\x12\x1a.filesystem.CaminhoRequest\x1a\x1c.filesystem.OperacaoResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'proto.filesystem_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_CAMINHOREQUEST']._serialized_start=38
  _globals['_CAMINHOREQUEST']._serialized_end=68
  _globals['_FILEUPLOADREQUEST']._serialized_start=70
  _globals['_FILEUPLOADREQUEST']._serialized_end=118
  _globals['_FILEDOWNLOADRESPONSE']._serialized_start=120
  _globals['_FILEDOWNLOADRESPONSE']._serialized_end=192
  _globals['_COPYREQUEST']._serialized_start=194
  _globals['_COPYREQUEST']._serialized_end=240
  _globals['_OPERACAORESPONSE']._serialized_start=242
  _globals['_OPERACAORESPONSE']._serialized_end=295
  _globals['_CONTEUDORESPONSE']._serialized_start=297
  _globals['_CONTEUDORESPONSE']._serialized_end=382
  _globals['_FILESYSTEMSERVICE']._serialized_start=385
  _globals['_FILESYSTEMSERVICE']._serialized_end=823
# @@protoc_insertion_point(module_scope)
