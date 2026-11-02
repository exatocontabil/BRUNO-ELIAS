"""V183: limpeza SEGURA (só do Exato Central Fiscal, lista branca): nunca apaga XML/banco/SAT_AUDITORIA/arquivo de fora/atalho para fora; espaço em disco e níveis."""
import os, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'programa'))
import exato_limpeza as L
base=Path(tempfile.mkdtemp(prefix='exato_v183_lmp_')); raiz=base/'Dados'; fora=base/'OutroPrograma'; fora.mkdir(); (fora/'importante.xml').write_text('nao apagar'); (fora/'Exato_Backup_x_automatico.zip').write_text('nome parecido, mas de fora')
def f(p,txt='x'*1000,idade_dias=0):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(txt)
    t=time.time()-idade_dias*86400; os.utime(p,(t,t)); return p
# --- o que NUNCA pode sumir
guard=[f(raiz/'central_fiscal.db'),f(raiz/'usuarios.db'),f(raiz/'config.json'),f(raiz/'Trabalho'/'SAT_AUDITORIA'/'sat.xlsx'),f(raiz/'Trabalho'/'CONTROLES_CAPTURA'/'c.txt'),f(raiz/'auditoria_historico.json'),
       f(raiz/'Backups'/'Exato_Backup_V1_manual.zip',idade_dias=100),f(raiz/'Backups'/'leia-me.txt'),f(raiz/'Representacoes_Fiscais'/'12345678000195'/'nfse'/'nota.xml'),f(raiz/'Logs'/'exato.log'),
       f(raiz/'Documentos do cliente'/'cliente.pdf'),fora/'importante.xml',fora/'Exato_Backup_x_automatico.zip']
# --- o que pode ir
diag1=f(raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE'/'123_run1'/'0001_nfe'/'01.xml'); diag2=f(raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE'/'123_run2'/'0001_nfe'/'01.xml')
temp=f(raiz/'Backups'/'.central_fiscal_backup_20261013.db'); temp2=f(raiz/'Backups'/'.usuarios_backup_20261013.db')
auto=[f(raiz/'Backups'/f'Exato_Backup_V183_2026101{i}_automatico.zip',idade_dias=10-i) for i in range(5)]          # i=4 é o mais novo
pdf=f(raiz/'Representacoes_Fiscais'/'12345678000195'/'nfe'/'NFe_1.pdf')
guard.append(f(raiz/'Backups'/'Exato_Backup_V150_20250101_000000_antes_restauracao.zip',idade_dias=300))          # feito por pedido do usuário: nunca entra
velho_atu=f(raiz/'Backups'/'Exato_Backup_V150_20250101_000000_antes_da_atualizacao.zip',idade_dias=200)          # feito pelo Exato a cada versão: pode ir
# atalho DENTRO do diagnóstico apontando para uma pasta de fora (tentativa de levar a limpeza para fora)
try: os.symlink(str(fora),str(raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE'/'atalho'),target_is_directory=True); atalho=True
except (OSError,NotImplementedError): atalho=False
ls={x['id']:x for x in L.listar(raiz)}
assert ls['diagnostico']['arquivos']==2 and ls['backups_temp']['arquivos']==2 and ls['backups_antigos']['arquivos']==6 and ls['backups_antigos']['apagavel_arquivos']==4 and ls['pdfs']['arquivos']==1,ls
assert not any(str(fora) in x['pasta'] for x in ls.values())
# --- limpeza manual
erros=[]; r=L.limpar(raiz,['diagnostico','backups_temp','backups_antigos','pdfs','id_que_nao_existe','../../etc'],erros)
assert not erros and r['arquivos']==2+2+4+1,r
for p in guard: assert p.exists(),f'APAGOU O QUE NÃO PODIA: {p}'
for p in (diag1,diag2,temp,temp2,pdf,velho_atu,*auto[:3]): assert not p.exists(),p
assert auto[3].exists() and auto[4].exists()          # os 2 automáticos mais novos ficam
assert (raiz/'Trabalho'/'SAT_AUDITORIA'/'sat.xlsx').exists() and (fora/'importante.xml').exists()
if atalho: assert (raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE'/'atalho').is_symlink()          # o atalho nem foi seguido
assert not (raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE'/'123_run1').exists()          # pastas vazias saem (sem rmtree)
# --- limpeza automática: diagnóstico por execução (idade, quantidade e tamanho) e PDFs antigos
for i in range(6): f(raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE'/f'run{i}'/'a.xml',idade_dias=i*2)          # 0,2,4,6,8,10 dias
pdfv=f(raiz/'Representacoes_Fiscais'/'1'/'nfe'/'velho.pdf',idade_dias=90); pdfn=f(raiz/'Representacoes_Fiscais'/'1'/'nfe'/'novo.pdf',idade_dias=1)
feitos=L.limpar_automatico(raiz); desc=' '.join(d for d,_n,_b in feitos)
restam=sorted(p.name for p in (raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE').iterdir() if p.is_dir() and not p.is_symlink())
assert restam==['run0','run1','run2'],restam          # só as 3 mais novas (e as de mais de 7 dias já iriam de qualquer forma)
assert not pdfv.exists() and pdfn.exists() and 'PDFs guardados antigos' in desc and 'diagnóstico' in desc
for p in guard: assert p.exists(),f'AUTOMÁTICO APAGOU O QUE NÃO PODIA: {p}'
# nome e extensão parecidos mas fora da lista branca: ficam
f(raiz/'Backups'/'Exato_Backup_V1_manual.zip'); f(raiz/'Backups'/'minha_foto.jpg'); L.limpar_automatico(raiz); assert (raiz/'Backups'/'minha_foto.jpg').exists() and (raiz/'Backups'/'Exato_Backup_V1_manual.zip').exists()
# --- tamanhos, níveis e espaço
assert L.nivel_espaco(10*L.GB,100*L.GB)=='ok' and L.nivel_espaco(1*L.GB,100*L.GB)=='baixo' and L.nivel_espaco(10*L.GB,100*L.GB*1)=='ok' and L.nivel_espaco(4*L.GB,100*L.GB)=='baixo' and L.nivel_espaco(100*L.MB,500*L.GB)=='critico' and L.nivel_espaco(None,None)=='desconhecido'
assert L.texto_tamanho(6508*L.MB)=='6,4 GB' and L.texto_tamanho(300*L.MB)=='300 MB'
livre,total=L.espaco_livre(raiz); assert livre and total and livre<=total
uso={n:b for n,b,_x in L.resumo_uso(raiz)}; assert uso['Banco de notas']>0 and 'Backups locais' in uso
assert L.dentro_de(raiz,raiz/'Trabalho') and not L.dentro_de(raiz,fora) and not L.dentro_de(raiz,raiz/'..'/'OutroPrograma')
print('V183 limpeza segura OK')
# --- V184: a limpeza automática pára na hora se mandarem parar (começou uma busca) e não pesa o disco
for i in range(6): f(raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE'/f'big{i}'/'a.xml',idade_dias=30+i)
antes=len(list((raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE').rglob('a.xml'))); contador=[0]
def parar(): contador[0]+=1; return contador[0]>1
t0=time.time(); L.limpar_automatico(raiz,parar=parar,ritmo=0.01)
restam=[p for p in (raiz/'Trabalho'/'DIAGNOSTICO_WEBSERVICE').rglob('a.xml')]
assert len(restam)>=antes-1 and len(restam)>=5,(antes,len(restam))          # parou logo no primeiro arquivo apagado
for p in guard: assert p.exists()
print('V184 limpeza interrompível OK')
