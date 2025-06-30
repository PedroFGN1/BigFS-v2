import grpc
import sys
import os
import time
from typing import List, Optional, Dict, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'proto')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'metadata_server')))

import filesystem_extended_pb2 as fs_pb2
import filesystem_extended_pb2_grpc as fs_grpc
from metadata_client2 import MetadataClient

class BigFSClient:
    """Cliente BigFS-v2 com suporte a chunks, replicação e tolerância a falhas"""
    
    def __init__(self, metadata_server: str = "localhost:50052"):
        self.metadata_server = metadata_server
        self.metadata_client = None
        self.storage_connections = {}  # Cache de conexões com nós de armazenamento
        
        # Conectar ao servidor de metadados
        self._connect_to_metadata_server()
    
    def _connect_to_metadata_server(self):
        """Conecta ao servidor de metadados"""
        try:
            self.metadata_client = MetadataClient(self.metadata_server)
            print(f"✅ Conectado ao servidor de metadados: {self.metadata_server}")
        except Exception as e:
            print(f"❌ Erro ao conectar com servidor de metadados: {e}")
            self.metadata_client = None
    
    def _get_storage_connection(self, node_info: fs_pb2.NodeInfo) -> Optional[fs_grpc.FileSystemServiceStub]:
        """Obtém conexão com nó de armazenamento (com cache)"""
        if not node_info:
            return None
        node_address = f"{node_info.endereco}:{node_info.porta}"
        
        if node_address not in self.storage_connections:
            try:
                channel = grpc.insecure_channel(
                    node_address,
                    options=[
                        ("grpc.max_send_message_length", 1024 * 1024 * 1024),
                        ("grpc.max_receive_message_length", 1024 * 1024 * 1024)
                    ]
                )
                stub = fs_grpc.FileSystemServiceStub(channel)
                self.storage_connections[node_address] = (channel, stub)
                print(f"🔗 Conectado ao nó de armazenamento: {node_address}")
            except Exception as e:
                print(f"❌ Erro ao conectar com nó {node_address}: {e}")
                return None
        
        return self.storage_connections[node_address][1]
    
    def _close_connections(self):
        """Fecha todas as conexões"""
        for channel, _ in self.storage_connections.values():
            channel.close()
        self.storage_connections.clear()
        
        if self.metadata_client:
            self.metadata_client.close()
    
    def _download_chunk_with_fallback(self, arquivo_nome: str, chunk_numero: int, 
                                    chunk_info: fs_pb2.ChunkLocation) -> Optional[bytes]:
        """Download de chunk com fallback para réplicas em caso de falha"""
        # Tentar nó primário primeiro
        primary_node = self.metadata_client.get_node_for_operation("download", arquivo_nome)
        if not primary_node:
            print(f"⚠️ Nenhum nó primário disponível para o arquivo {arquivo_nome}")
            return None
        
        stub = self._get_storage_connection(primary_node)
        
        # Se chegou aqui, tentar réplicas
        if self.metadata_client:
            replicas = self.metadata_client.get_available_replicas(arquivo_nome, chunk_numero)
            for replica in replicas:
                try:
                    replica_stub = self._get_storage_connection(replica)
                    if replica_stub:
                        request = fs_pb2.ChunkRequest(
                            arquivo_nome=arquivo_nome,
                            chunk_numero=chunk_numero
                        )
                        response = replica_stub.DownloadChunk(request)
                        
                        if response.sucesso:
                            import hashlib
                            checksum_calculado = hashlib.md5(response.dados).hexdigest()
                            if checksum_calculado == chunk_info.checksum:
                                print(f"✅ Chunk {chunk_numero} obtido da réplica {replica.node_id}")
                                return response.dados
                except Exception as e:
                    print(f"⚠️ Falha na réplica {replica.node_id}: {e}")
                    continue
        
        print(f"❌ Não foi possível obter chunk {chunk_numero}")
        return None
    
    def listar(self, caminho: str = "/") -> bool:
        """Lista conteúdo de diretório"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        print(f"\n📁 Listando conteúdo de: '{caminho}' (visão global)")
        
        try:
            # Chama a nova função que consulta o metadata server
            nomes_arquivos = self.metadata_client.list_files(caminho)
        
            if nomes_arquivos is not None:
                if not nomes_arquivos:
                    print("  (Diretório vazio)")
                else:
                    for item in nomes_arquivos:
                        print("  📄", item)
                return True
            else:
                # A mensagem de erro já foi impressa por list_files_globally
                return False
        except Exception as e:
            print(f"❌ Erro na comunicação: {e}")
            return False
    
    def upload(self, caminho_local: str, caminho_remoto: str) -> bool:
        """Upload de arquivo com suporte automático a chunks"""
        if not os.path.exists(caminho_local):
            print("❌ Arquivo local não encontrado")
            return False
        
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        arquivo_nome = os.path.basename(caminho_remoto)
        
        # Obter nó para upload
        node_response = self.metadata_client.get_node_for_operation("upload", arquivo_nome)
        if not node_response and node_response.sucesso:
            print("❌ Nenhum nó disponível para upload")
            return False
        
        node_info = node_response.no_recomendado

        stub = self._get_storage_connection(node_info)

        if not stub:
            return False
        
        try:
            # Ler arquivo
            with open(caminho_local, "rb") as f:
                dados = f.read()
            
            tamanho_arquivo = len(dados)
            print(f"📤 Enviando {arquivo_nome} ({tamanho_arquivo} bytes) para {node_info.node_id}")
            
            # Fazer upload (o nó decidirá se divide em chunks)
            request = fs_pb2.FileUploadRequest(
                path=caminho_remoto,
                dados=dados
            )
            
            response = stub.Upload(request)
            
            if response.sucesso:
                print("✅", response.mensagem)
                return True
            else:
                print("❌ Erro no upload:", response.mensagem)
                return False
                
        except Exception as e:
            print(f"❌ Erro na comunicação: {e}")
            return False
    
    def download(self, caminho_remoto: str, caminho_local: str) -> bool:
        """Download de arquivo com suporte automático a chunks"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        arquivo_nome = os.path.basename(caminho_remoto)
        
        # Verificar se arquivo existe nos metadados
        file_metadata = self.metadata_client.get_file_metadata(arquivo_nome)
        
        if file_metadata:
            # Arquivo grande com chunks
            print(f"📥 Baixando {arquivo_nome} ({file_metadata.tamanho_total} bytes, {file_metadata.total_chunks} chunks)")
            
            # Obter localização dos chunks
            chunks_info = self.metadata_client.get_chunk_locations(arquivo_nome)
            if not chunks_info:
                print("❌ Não foi possível obter localização dos chunks")
                return False
            
            # Download paralelo dos chunks (simplificado - sequencial por enquanto)
            chunks_dados = []
            for chunk_info in sorted(chunks_info, key=lambda x: x.chunk_numero):
                chunk_numero = chunk_info.chunk_numero
                print(f"📦 Baixando chunk {chunk_numero + 1}/{len(chunks_info)}")
                
                chunk_data = self._download_chunk_with_fallback(arquivo_nome, chunk_numero, chunk_info)
                if chunk_data is None:
                    print(f"❌ Falha ao baixar chunk {chunk_numero}")
                    return False
                
                chunks_dados.append(chunk_data)
            
            # Recombinar chunks
            print("🔧 Recombinando chunks...")
            dados_completos = b''.join(chunks_dados)
            
            # Verificar checksum do arquivo completo
            import hashlib
            checksum_calculado = hashlib.md5(dados_completos).hexdigest()
            if checksum_calculado != file_metadata['checksum_arquivo']:
                print("❌ Checksum do arquivo não confere")
                return False
            
        else:
            # Tentar download direto (arquivo pequeno ou não encontrado nos metadados)
            node_response = self.metadata_client.get_node_for_operation("download", arquivo_nome)
            if not node_response and node_response.sucesso:
                print("❌ Nenhum nó disponível para download")
                return False
            
            node_info = node_response.no_recomendado

            stub = self._get_storage_connection(node_info)
            if not stub:
                return False
            
            try:
                request = fs_pb2.CaminhoRequest(path=caminho_remoto)
                response = stub.Download(request)
                
                if not response.sucesso:
                    print("❌ Erro no download:", response.mensagem)
                    return False
                
                dados_completos = response.dados
                print(f"📥 Baixando {arquivo_nome} ({len(dados_completos)} bytes) de {node_info['node_id']}")
                
            except Exception as e:
                print(f"❌ Erro na comunicação: {e}")
                return False
        
        # Salvar arquivo
        try:
            os.makedirs(os.path.dirname(caminho_local), exist_ok=True)
            with open(caminho_local, "wb") as f:
                f.write(dados_completos)
            print(f"✅ Arquivo salvo em: {caminho_local}")
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar arquivo: {e}")
            return False
    
    def deletar(self, caminho_remoto: str) -> bool:
        """Deleta arquivo do sistema"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        arquivo_nome = os.path.basename(caminho_remoto)
        
        # Remover do servidor de metadados (isso remove arquivo e chunks)
        sucesso = self.metadata_client.remove_file(arquivo_nome)
        if sucesso:
            print(f"✅ Arquivo {arquivo_nome} removido do sistema")
            return True
        else:
            print(f"❌ Erro ao remover arquivo {arquivo_nome}")
            return False
    
    def copiar(self, origem: str, destino: str) -> bool:
        """Copia arquivo entre locais remotos"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        # Obter nó para operação de cópia
        node = self.metadata_client.get_node_for_operation("copy", origem)
        if not node:
            print("❌ Nenhum nó disponível para cópia")
            return False
        
        stub = self._get_storage_connection(node)
        if not stub:
            return False
        
        try:
            request = fs_pb2.CopyRequest(origem=origem, destino=destino)
            response = stub.Copiar(request)
            
            if response.sucesso:
                print("✅", response.mensagem)
                return True
            else:
                print("❌ Erro na cópia:", response.mensagem)
                return False
        except Exception as e:
            print(f"❌ Erro na comunicação: {e}")
            return False
    
    def status_sistema(self) -> bool:
        """Exibe status do sistema"""
        if not self.metadata_client:
            print("❌ Servidor de metadados não disponível")
            return False
        
        try:
            status = self.metadata_client.get_system_status()
            if not status:
                print("❌ Erro ao obter status do sistema")
                return False
            
            print("\n📊 Status do Sistema BigFS-v2")
            print("=" * 40)
            print(f"🖥️  Nós ativos: {status['nos_ativos']}/{status['total_nos']}")
            print(f"📁 Arquivos: {status['total_arquivos']}")
            print(f"📦 Chunks: {status['total_chunks']}")
            print(f"💾 Storage: {status['storage_usado']:,} / {status['storage_total']:,} bytes")
            
            if 'detalhes_nos' in status:
                print("\n🖥️  Detalhes dos Nós:")
                for node in status['detalhes_nos']:
                    storage_percent = (node['storage_usado'] / node['capacidade_storage'] * 100) if node['capacidade_storage'] > 0 else 0
                    print(f"  • {node['node_id']}: {node['status']} - {storage_percent:.1f}% usado")
            
            if 'estatisticas' in status:
                stats = status['estatisticas']
                print("\n📈 Estatísticas:")
                print(f"  • Uploads: {stats['operacoes_upload_total']}")
                print(f"  • Downloads: {stats['operacoes_download_total']}")
                print(f"  • Deletes: {stats['operacoes_delete_total']}")
                print(f"  • Falhas detectadas: {stats['falhas_detectadas']}")
                print(f"  • Replicações: {stats['replicacoes_realizadas']}")
            
            return True
        except Exception as e:
            print(f"❌ Erro ao obter status: {e}")
            return False

def exibir_menu():
    print("\n" + "="*50)
    print("🗂️  BigFS-v2 Client - Sistema de Arquivos Distribuído")
    print("="*50)
    print("1. 📋 Listar arquivos (ls)")
    print("2. 🗑️  Deletar arquivo")
    print("3. 📤 Upload de arquivo")
    print("4. 📥 Download de arquivo")
    print("5. 📋 Copiar arquivo remoto")
    print("6. 📊 Status do sistema")
    print("7. 🚪 Sair")
    print("="*50)

def main():
    print("🚀 Iniciando BigFS-v2 Client...")
    
    # Permitir configuração do servidor de metadados
    metadata_server = input("Servidor de metadados (Enter para localhost:50052): ").strip()
    if not metadata_server:
        metadata_server = "localhost:50052"
    
    client = BigFSClient(metadata_server)
    
    try:
        while True:
            exibir_menu()
            escolha = input("Escolha uma opção: ").strip()
            
            if escolha == "1":
                caminho = input("Digite o caminho remoto (Enter para raiz): ").strip()
                client.listar(caminho)
                
            elif escolha == "2":
                caminho = input("Digite o caminho do arquivo a ser deletado: ").strip()
                if caminho:
                    client.deletar(caminho)
                else:
                    print("❌ Caminho não pode estar vazio")
                    
            elif escolha == "3":
                caminho_local = input("Digite o caminho do arquivo local: ").strip()
                caminho_remoto = input("Digite o caminho remoto de destino: ").strip()
                if caminho_local and caminho_remoto:
                    client.upload(caminho_local, caminho_remoto)
                else:
                    print("❌ Caminhos não podem estar vazios")
                    
            elif escolha == "4":
                caminho_remoto = input("Digite o caminho remoto do arquivo: ").strip()
                caminho_local = input("Digite o caminho local para salvar: ").strip()
                if caminho_remoto and caminho_local:
                    client.download(caminho_remoto, caminho_local)
                else:
                    print("❌ Caminhos não podem estar vazios")
                    
            elif escolha == "5":
                origem = input("Digite o caminho remoto de origem: ").strip()
                destino = input("Digite o caminho remoto de destino: ").strip()
                if origem and destino:
                    client.copiar(origem, destino)
                else:
                    print("❌ Caminhos não podem estar vazios")
                    
            elif escolha == "6":
                client.status_sistema()
                
            elif escolha == "7":
                print("👋 Encerrando cliente...")
                break
                
            else:
                print("❌ Opção inválida. Tente novamente.")
                
            input("\nPressione Enter para continuar...")
            
    except KeyboardInterrupt:
        print("\n👋 Cliente interrompido pelo usuário")
    finally:
        client._close_connections()
        print("🔌 Conexões fechadas")

if __name__ == "__main__":
    main()

