import os

def listar_conteudo(caminho_base, caminho_relativo):
    caminho_absoluto = os.path.abspath(os.path.join(caminho_base, caminho_relativo.lstrip("/")))

    if not os.path.exists(caminho_absoluto):
        return False, "Caminho não encontrado", None, None

    if os.path.isfile(caminho_absoluto):
        return True, "É um arquivo", "arquivo", [os.path.basename(caminho_absoluto)]

    try:
        conteudo = os.listdir(caminho_absoluto)
        return True, "Conteúdo listado com sucesso", "diretorio", conteudo
    except Exception as e:
        return False, str(e), None, None
