

try:          # sem janelas de PowerShell piscando (o site roda sem console)
    from . import semjanela; semjanela.instalar()
except Exception: pass
