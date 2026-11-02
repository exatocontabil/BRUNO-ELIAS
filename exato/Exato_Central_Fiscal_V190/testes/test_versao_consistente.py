"""Garante a regra de versão: o número do programa aparece em todos os lugares e a documentação da versão existe."""
import os, re, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_versao_')
sys.path.insert(0,str(ROOT/'programa'))
import exato_central_fiscal as m
v=m.APP_VERSION
assert re.fullmatch(r'V\d+',v),v
assert ROOT.name==f'Exato_Central_Fiscal_{v}',f'pasta {ROOT.name} != {v}'
for name in ('VERSAO.txt','LEIA-ME.txt','INICIAR.bat','ferramentas/EXECUTAR_COM_DIAGNOSTICO.bat'):
    assert v in (ROOT/name).read_text(encoding='utf-8',errors='replace'),f'{name} não cita {v}'
for rel in (f'docs/{v}_NOTAS.txt',f'docs/CONTINUIDADE_PROJETO_{v}.txt',f'documentacao/{v}_CHECKLIST.txt',f'documentacao/{v}_PROTECAO_NUCLEOS_SHA256.txt'):
    assert (ROOT/rel).exists(),f'falta {rel}'
# V156: estrutura organizada e pacote do usuário só com o necessário
import subprocess, tempfile, zipfile
assert (ROOT/'programa'/'exato_central_fiscal.py').exists() and (ROOT/'programa'/'assets'/'exato_central_fiscal.ico').exists() and (ROOT/'programa'/'third_party').is_dir()
assert not list(ROOT.glob('*.py')) and (ROOT/'ferramentas'/'INSTALAR_COMPONENTE_NFSE.bat').exists() and (ROOT/'ferramentas'/'CRIAR_ATALHO.bat').exists() and (ROOT/'ajuda'/'COMO_INSTALAR_EXATO.txt').exists()
out=Path(tempfile.mkdtemp()); r=subprocess.run([sys.executable,str(ROOT/'scripts'/'montar_pacote.py'),str(out)],capture_output=True,text=True); assert r.returncode==0,r.stderr
zp=out/f'{ROOT.name}.zip'; names=zipfile.ZipFile(zp).namelist()
top={n.split('/')[1] for n in names}; assert top=={'INICIAR.bat','LEIA-ME.txt','VERSAO.txt','programa','ferramentas','ajuda'},top
assert not [n for n in names if '__pycache__' in n or '/testes/' in n or '/docs/' in n or '/archive/' in n or '/referencias/' in n]
# o pacote abre de verdade: carrega o programa a partir do ZIP descompactado (assets, bibliotecas e logo na mesma estrutura)
ext=out/'x'; zipfile.ZipFile(zp).extractall(ext); prog=ext/ROOT.name/'programa'
code="import sys; sys.path.insert(0,'.'); import exato_central_fiscal as m; assert m.PROGRAM_DIR.name=='programa' and m.ASSETS_DIR.exists() and m.LOGO_PATH.exists() and m.APP_ICON_PATH.exists() and m.THIRD_PARTY_DIR.exists() and m.APP_DIR.name==m.__dict__['APP_DIR'].name; import pypdf; print(m.APP_VERSION)"
import os
env=dict(os.environ,EXATO_DATA_DIR=str(out/'dados')); r=subprocess.run([sys.executable,'-B','-c',code],cwd=prog,env=env,capture_output=True,text=True); assert r.returncode==0 and r.stdout.strip()==v,(r.stdout,r.stderr)
assert not list(prog.rglob('__pycache__')),'não deve criar __pycache__ na pasta do programa'
print(f'Versão consistente: {v}: OK')
