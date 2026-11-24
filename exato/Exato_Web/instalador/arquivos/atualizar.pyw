"""Auxiliar da atualização pela tela: roda o instalador novo em silêncio e sai logo.
Quem chama é o site; o instalador desliga o site para trocar os arquivos, por isso ele NÃO pode ser "filho" do site (seria desligado junto).
Este auxiliar só inicia o instalador separado e termina; o instalador liga o Exato de novo no fim."""
import subprocess, sys, time
from pathlib import Path

DESTACADO = 0x00000008 | 0x00000200 | 0x08000000          # sem vínculo com quem chamou, sem janela


def main(argv):
    exe, inst, dados = argv[1], argv[2], argv[3]
    endereco = argv[4] if len(argv) > 4 else ''
    time.sleep(2)                                           # deixa a página de "atualizando" ser entregue
    log = Path(dados) / 'logs'; log.mkdir(parents=True, exist_ok=True)
    # Uma linha só, com as aspas no valor (como o instalador espera), para funcionar com espaços nos caminhos.
    cmd = f'"{exe}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="{inst}" /DADOS="{dados}" /LOG="{log / "atualizacao.log"}"'
    if endereco: cmd += f' /ENDERECO="{endereco}"'
    subprocess.Popen(cmd, creationflags=DESTACADO if sys.platform == 'win32' else 0, close_fds=True)
    return 0


if __name__ == '__main__': sys.exit(main(sys.argv))
