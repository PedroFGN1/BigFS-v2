import os

def listar_conteudo(caminho_base, caminho_relativo):
    # Normaliza o caminho relativo
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
        conteudo = os.listdir(caminho_absoluto)
        return True, "Conteúdo listado com sucesso", "diretorio", conteudo
    except Exception as e:
        return False, str(e), None, None

def deletar_arquivo(caminho_base, caminho_relativo):
    caminho_absoluto = os.path.abspath(os.path.join(caminho_base, caminho_relativo.lstrip("/")))

    if not os.path.exists(caminho_absoluto):
        return False, "Arquivo ou diretório não encontrado."

    if os.path.isdir(caminho_absoluto):
        return False, "Não é permitido remover diretórios neste modo."

    try:
        os.remove(caminho_absoluto)
        return True, "Arquivo removido com sucesso."
    except Exception as e:
        return False, f"Erro ao remover: {str(e)}"