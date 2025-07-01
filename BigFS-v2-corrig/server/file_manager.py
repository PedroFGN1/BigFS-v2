import os
import shutil

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
