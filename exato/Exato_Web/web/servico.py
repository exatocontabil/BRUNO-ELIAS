"""Liga o site SEM janela preta (usado pela tarefa "Exato Web" do Windows: `pythonw -m web.servico`).

Tudo o que o site escreveria na tela vai para `<dados>/logs/servidor_saida.log` (o arquivo antigo vira `.1` quando passa de 5 MB).
O número do processo fica em `<dados>/servidor.pid` para o PARAR_SITE.bat. Endereço e porta: EXATO_WEB_HOST (127.0.0.1) e EXATO_WEB_PORT (8443)."""
import os
import sys
from pathlib import Path


def preparar_saida(pasta_logs):
    """Redireciona a saída para o arquivo de registro (com `pythonw` não existe tela). Devolve o caminho do arquivo."""
    pasta_logs = Path(pasta_logs); pasta_logs.mkdir(parents=True, exist_ok=True); arq = pasta_logs / 'servidor_saida.log'
    try:
        if arq.exists() and arq.stat().st_size > 5 * 1024 * 1024: os.replace(arq, pasta_logs / 'servidor_saida.log.1')
    except OSError: pass
    fh = open(arq, 'a', encoding='utf-8', buffering=1); sys.stdout = fh; sys.stderr = fh; return arq


def main():
    os.environ.setdefault('EXATO_WEB_HTTPS', '1')
    from web import config
    preparar_saida(config.DADOS / 'logs')
    try: (config.DADOS / 'servidor.pid').write_text(str(os.getpid()), encoding='ascii')
    except OSError: pass
    import uvicorn
    uvicorn.run('web.app:app_producao', factory=True, host=os.environ.get('EXATO_WEB_HOST', '127.0.0.1'), port=int(os.environ.get('EXATO_WEB_PORT', '8443')), proxy_headers=True, log_level='info', use_colors=False)


if __name__ == '__main__': main()
