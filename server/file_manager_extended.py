import os
import shutil
import hashlib
import time
import json
from typing import List, Optional, Tuple, Dict

def calcular_checksum(dados: bytes) -> str:
    """Calcula checksum MD5 dos dados"""
    return hashlib.md5(dados).hexdigest()

def dividir_arquivo_em_chunks(dados: bytes, tamanho_chunk: int = 1024 * 1024) -> List[bytes]:
    """Divide arquivo em chunks de tamanho especificado (padrão: 1MB)"""
    chunks = []
    for i in range(0, len(dados), tamanho_chunk):
        chunk = dados[i:i + tamanho_chunk]
        chunks.append(chunk)
    return chunks

def recombinar_chunks(chunks: List[bytes]) -> bytes:
    """Recombina chunks em arquivo completo"""
    return b''.join(chunks)

def salvar_chunk(caminho_base: str, arquivo_nome: str, chunk_numero: int, dados: bytes) -> Tuple[bool, str]:
    """Salva um chunk específico no disco"""
    try:
        # Criar diretório para chunks se não existir
        chunks_dir = os.path.join(caminho_base, "chunks")
        os.makedirs(chunks_dir, exist_ok=True)
        
        # Nome do arquivo do chunk: arquivo_nome.chunk_numero
        chunk_filename = f"{arquivo_nome}.chunk_{chunk_numero}"
        chunk_path = os.path.join(chunks_dir, chunk_filename)
        
        with open(chunk_path, "wb") as f:
            f.write(dados)
        
        return True, f"Chunk {chunk_numero} salvo com sucesso"
    except Exception as e:
        return False, f"Erro ao salvar chunk {chunk_numero}: {str(e)}"

def ler_chunk(caminho_base: str, arquivo_nome: str, chunk_numero: int) -> Tuple[bool, str, Optional[bytes]]:
    """Lê um chunk específico do disco"""
    try:
        chunks_dir = os.path.join(caminho_base, "chunks")
        chunk_filename = f"{arquivo_nome}.chunk_{chunk_numero}"
        chunk_path = os.path.join(chunks_dir, chunk_filename)
        
        if not os.path.exists(chunk_path):
            return False, f"Chunk {chunk_numero} não encontrado", None
        
        with open(chunk_path, "rb") as f:
            dados = f.read()
        
        return True, f"Chunk {chunk_numero} lido com sucesso", dados
    except Exception as e:
        return False, f"Erro ao ler chunk {chunk_numero}: {str(e)}", None

def deletar_chunk(caminho_base: str, arquivo_nome: str, chunk_numero: int) -> Tuple[bool, str]:
    """Deleta um chunk específico do disco"""
    try:
        chunks_dir = os.path.join(caminho_base, "chunks")
        metadata_dir = os.path.join(caminho_base, "metadata")
        
        chunk_filename = f"{arquivo_nome}.chunk_{chunk_numero}"
        metadata_filename = f"{chunk_filename}.meta"
        
        chunk_path = os.path.join(chunks_dir, chunk_filename)
        metadata_path = os.path.join(metadata_dir, metadata_filename)
        
        chunk_encontrado = os.path.exists(chunk_path)
        metadata_encontrado = os.path.exists(metadata_path)

        if not chunk_encontrado and not metadata_encontrado:
            return False, f"Chunk {chunk_numero} e seus metadados não foram encontrados."

        # Excluir o arquivo do chunk, se existir
        if chunk_encontrado:
            os.remove(chunk_path)
            print(f"INFO: Chunk de dados '{chunk_path}' removido.")

        # Excluir o arquivo de metadados, se existir
        if metadata_encontrado:
            os.remove(metadata_path)
            print(f"INFO: Metadados do chunk '{metadata_path}' removidos.")

        return True, f"Chunk {chunk_numero} e seus metadados foram removidos com sucesso."
        
    except Exception as e:
        return False, f"Erro ao remover chunk {chunk_numero}: {str(e)}"

def listar_chunks_armazenados(caminho_base: str) -> List[str]:
    """Lista todos os chunks armazenados neste nó"""
    try:
        chunks_dir = os.path.join(caminho_base, "chunks")
        if not os.path.exists(chunks_dir):
            return []
        
        chunks = []
        for filename in os.listdir(chunks_dir):
             if '.chunk_' in filename:
                # Extrair nome do arquivo e número do chunk
                parts = filename.split('.chunk_')
                if len(parts) == 2:
                    arquivo_nome = parts[0]
                    chunk_numero = parts[1]
                    chunks.append(f"{arquivo_nome}:{chunk_numero}")
        
        return chunks
    except Exception as e:
        print(f"Erro ao listar chunks: {e}")
        return []

def verificar_integridade_chunk(caminho_base: str, arquivo_nome: str, chunk_numero: int, 
                               checksum_esperado: str) -> Tuple[bool, str, bool]:
    """Verifica integridade de um chunk comparando checksums"""
    try:
        sucesso, mensagem, dados = ler_chunk(caminho_base, arquivo_nome, chunk_numero)
        if not sucesso:
            return False, mensagem, False
        
        checksum_atual = calcular_checksum(dados)
        integridade_ok = checksum_atual == checksum_esperado
        
        return True, f"Verificação concluída", integridade_ok
    except Exception as e:
        return False, f"Erro na verificação de integridade: {str(e)}", False

def salvar_metadata_chunk(caminho_base: str, arquivo_nome: str, chunk_numero: int, 
                         metadata: Dict) -> bool:
    """Salva metadados de um chunk localmente"""
    try:
        metadata_dir = os.path.join(caminho_base, "metadata")
        os.makedirs(metadata_dir, exist_ok=True)
        
        metadata_filename = f"{arquivo_nome}.chunk_{chunk_numero}.meta"
        metadata_path = os.path.join(metadata_dir, metadata_filename)
        
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Erro ao salvar metadados do chunk: {e}")
        return False

def ler_metadata_chunk(caminho_base: str, arquivo_nome: str, chunk_numero: int) -> Optional[Dict]:
    """Lê metadados de um chunk localmente"""
    try:
        metadata_dir = os.path.join(caminho_base, "metadata")
        metadata_filename = f"{arquivo_nome}.chunk_{chunk_numero}.meta"
        metadata_path = os.path.join(metadata_dir, metadata_filename)
        
        if not os.path.exists(metadata_path):
            return None
        
        with open(metadata_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao ler metadados do chunk: {e}")
        return None

# ========================================
# FUNÇÕES ORIGINAIS (mantidas para compatibilidade)
# ========================================

def listar_conteudo(caminho_base, caminho_relativo):
    # Normaliza o caminho relativo
    print(f'PROCEDURE: listar_conteudo (ls)')
    print(f"[DEBUG] BASE: {caminho_base}, REQ: {caminho_relativo}")
    caminho_relativo = caminho_relativo.strip().lstrip("\\/")

    # Resolve o caminho absoluto e verifica se está contido dentro do diretório base
    caminho_absoluto = os.path.abspath(os.path.join(caminho_base, caminho_relativo))

    if not caminho_absoluto.startswith(os.path.abspath(caminho_base)):
        return False, "Acesso negado: fora da área exportada", None, None
    
    if not os.path.exists(caminho_absoluto):
        return False, "Caminho não encontrado", None, None

    if os.path.isfile(caminho_absoluto):
        return True, "É um arquivo", "arquivo", [os.path.basename(caminho_absoluto)]

    try:
        print(f'Processando arquivo...: {caminho_absoluto}')
        conteudo = os.listdir(caminho_absoluto)
        return True, "Conteúdo listado com sucesso", "diretorio", conteudo
    except Exception as e:
        return False, str(e), None, None


def deletar_arquivo(caminho_base, caminho_relativo):
    caminho_absoluto = os.path.abspath(os.path.join(caminho_base, caminho_relativo.lstrip("/")))
    print(f'PROCEDURE: deletar_arquivo (delete)')
    print(f"[DEBUG] BASE: {caminho_base}, REQ: {caminho_relativo}")
    # Verifica se o caminho absoluto está dentro do diretório base
    if not os.path.exists(caminho_absoluto):
        return False, "Arquivo ou diretório não encontrado."

    if os.path.isdir(caminho_absoluto):
        return False, "Não é permitido remover diretórios neste modo."

    try:
        print(f'Processando arquivo...: {caminho_absoluto}')
        os.remove(caminho_absoluto)
        return True, "Arquivo removido com sucesso."
    except Exception as e:
        return False, f"Erro ao remover: {str(e)}"


def salvar_arquivo(caminho_base, caminho_relativo, dados):
    caminho_absoluto = os.path.abspath(os.path.join(caminho_base, caminho_relativo.lstrip("/")))
    diretorio = os.path.dirname(caminho_absoluto)
    print(f'PROCEDURE: salvar_arquivo (save)')
    print(f"[DEBUG] BASE: {caminho_base}, REQ: {caminho_relativo}")
    # Verifica se o caminho absoluto está dentro do diretório base
    try:
        print(f'Processando arquivo...: {caminho_absoluto}')
        os.makedirs(diretorio, exist_ok=True)  # garante que diretórios intermediários existam
        with open(caminho_absoluto, "wb") as f:
            f.write(dados)
        return True, "Arquivo salvo com sucesso."
    except Exception as e:
        return False, f"Erro ao salvar arquivo: {str(e)}"


def ler_arquivo(caminho_base, caminho_relativo):
    caminho_absoluto = os.path.abspath(os.path.join(caminho_base, caminho_relativo.lstrip("/")))
    print(f'PROCEDURE: ler_arquivo (read)')
    print(f"[DEBUG] BASE: {caminho_base}, REQ: {caminho_relativo}")

    if not os.path.isfile(caminho_absoluto):
        return False, "Arquivo não encontrado ou não é um arquivo.", None

    try:
        print(f'Processando arquivo...: {caminho_absoluto}')
        with open(caminho_absoluto, "rb") as f:
            dados = f.read()
        return True, "Arquivo lido com sucesso.", dados
    except Exception as e:
        return False, f"Erro ao ler arquivo: {str(e)}", None


def copiar_arquivo(caminho_base, origem_relativa, destino_relativa):
    origem_abs = os.path.abspath(os.path.join(caminho_base, origem_relativa.strip("\\/")))
    destino_abs = os.path.abspath(os.path.join(caminho_base, destino_relativa.strip("\\/")))
    
    print(f'PROCEDURE: copiar_arquivo (copy)')
    print(f"[DEBUG] BASE: {caminho_base}, REQ: {origem_relativa}, {destino_relativa}")
    # Verificação de segurança
    base_abs = os.path.abspath(caminho_base)
    if not origem_abs.startswith(base_abs) or not destino_abs.startswith(base_abs):
        return False, "Acesso negado: caminho fora da área exportada."

    if not os.path.isfile(origem_abs):
        return False, "Arquivo de origem não encontrado ou não é um arquivo."

    try:
        print(f"Processando arquivo...: {origem_abs}")
        os.makedirs(os.path.dirname(destino_abs), exist_ok=True)
        shutil.copy2(origem_abs, destino_abs)
        return True, "Arquivo copiado com sucesso."
    except Exception as e:
        return False, f"Erro ao copiar: {str(e)}"

