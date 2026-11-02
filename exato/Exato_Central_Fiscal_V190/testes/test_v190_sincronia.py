"""V182: sincronia pelo servidor: empresas (mescla, remoção só marcada), versão/formato (Exato velho não grava), pacote de atualização, histórico de auditorias e Excel do SAT."""
import os, sys, tempfile, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_sinc_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_sincronia as S, exato_repositorio as R, exato_busca_compartilhada as C
srv=Path(tempfile.mkdtemp(prefix='exato_v183_srv_')); base=str(srv)
# ---- empresas
assert S.ler_empresas(base) is None
assert S.publicar_empresas(base,[('11222333000181','ALFA LTDA'),('45723174000110','Empresa_45723174000110'),('123','invalida')],computador='PC1')
e=S.ler_empresas(base); assert set(e)=={'11222333000181','45723174000110'} and e['11222333000181']['nome']=='ALFA LTDA' and e['45723174000110']['nome']=='' ,e          # nome provisório não vai
assert not S.publicar_empresas(base,[('11222333000181','ALFA LTDA')])          # nada novo: não regrava
dif=S.comparar_empresas(S.ler_empresas(base),[('45723174000110','Beta'),('99888777000166','GAMA')])
assert dif['entram']==[('11222333000181','ALFA LTDA')] and [c for c,_ in dif['sobem']]==['99888777000166'] and dif['saem']==[] and dif['removidas_sobem']==[]
assert S.publicar_empresas(base,[('99888777000166','GAMA')]) and set(S.ler_empresas(base))=={'11222333000181','45723174000110','99888777000166'}
# remoção: só marca (nunca apaga) e depois some das duas listas "entram"
assert S.publicar_empresas(base,[],{'99888777000166':'Bruno Elias'})
e=S.ler_empresas(base); assert e['99888777000166']['removida'] and e['99888777000166']['removida_por']=='Bruno Elias' and len(e)==3
dif=S.comparar_empresas(e,[('99888777000166','GAMA')]); assert dif['saem']==['99888777000166'] and dif['entram']==[('11222333000181','ALFA LTDA'),] or dif['saem']==['99888777000166']
dif=S.comparar_empresas(e,[('11222333000181','ALFA LTDA'),('45723174000110','B')],removidas_locais=['99888777000166']); assert dif['entram']==[] and dif['saem']==[] and dif['removidas_sobem']==[]
assert S.reativar_empresa(base,'99888777000166') and not S.ler_empresas(base)['99888777000166']['removida']
# ---- versão e formato
assert S.avaliar_versao(base,'V182')['pode_gravar'] and not S.avaliar_versao(base,'V182')['atualizar']
assert S.registrar_versao(base,'V182','PC1') and not S.registrar_versao(base,'V181','PC2')          # só cresce
assert S.ler_versao(base)['mais_nova']=='V182' and S.ler_versao(base)['formato']==1
a=S.avaliar_versao(base,'V181',formato=1); assert a['pode_gravar'] and not a['atualizar']          # sem pacote publicado ainda
(srv/'Repositório'/'.indice'/'versao.json').write_text(json.dumps({'formato':2,'mais_nova':'V190','pacote':'.atualizacao/Exato_Central_Fiscal_V190.zip'}),encoding='utf-8')
a=S.avaliar_versao(base,'V182',formato=1); assert not a['pode_gravar'] and a['atualizar'] and a['motivo']=='versao_antiga' and a['mais_nova']=='V190'
R.BLOQUEADO='versao_antiga'
assert R.copiar_pendentes(str(srv/'x.db'),base)['motivo']=='versao_antiga' and C.publicar(base,{'11222333000181:nfe':5},{})==False          # Exato velho não grava
R.BLOQUEADO=''
# ---- pacote de atualização
inst=Path(tempfile.mkdtemp(prefix='exato_inst_'))/'Exato_Central_Fiscal_V182'; (inst/'programa'/'__pycache__').mkdir(parents=True); (inst/'ferramentas').mkdir(); (inst/'ajuda').mkdir()
(inst/'INICIAR.bat').write_text('rem x'); (inst/'LEIA-ME.txt').write_text('x'); (inst/'VERSAO.txt').write_text('Versão V182'); (inst/'programa'/'a.py').write_text('print(1)'); (inst/'programa'/'__pycache__'/'a.pyc').write_bytes(b'x'); (inst/'ferramentas'/'x.bat').write_text('x')
rel=S.publicar_pacote(base,inst,'V182'); assert rel=='.atualizacao/Exato_Central_Fiscal_V182.zip' and (srv/'Repositório'/rel).exists()
assert S.publicar_pacote(base,inst,'V182')==rel          # uma vez por versão
import zipfile; nomes=zipfile.ZipFile(srv/'Repositório'/rel).namelist(); assert 'Exato_Central_Fiscal_V182/INICIAR.bat' in nomes and 'Exato_Central_Fiscal_V182/programa/a.py' in nomes and not any(n.endswith('.pyc') for n in nomes)
pai=Path(tempfile.mkdtemp(prefix='exato_dest_')); nova=S.instalar_pacote(base,rel,pai); assert nova and (Path(nova)/'INICIAR.bat').exists() and (Path(nova)/'programa'/'a.py').read_text()=='print(1)'
assert S.instalar_pacote(base,rel,pai)==nova          # já instalada: devolve a mesma, não mexe
assert S.montar_pacote(Path(tempfile.mkdtemp()),srv/'z.zip')==''          # pasta sem a estrutura: não monta
# ---- auditorias: mescla, nada some, Excel sobe e desce
A=lambda ts,c,fam='nfce',fs=('sat.xlsx',): {'timestamp':ts,'cnpj':c,'company':'X','family':fam,'status':'conforme','source_files':list(fs),'period_start':'2026-09-01','period_end':'2026-09-30'}
local=[A('2026-10-01T10:00:00','49894842000123'),A('2026-10-02T10:00:00','49894842000123',fs=('sat2.xlsx',))]
assert S.publicar_auditorias(base,local)==2 and S.publicar_auditorias(base,local)==0          # repetir não duplica
outro=[A('2026-10-05T09:00:00','49894842000123',fs=('sat3.xlsx',)),A('2026-10-01T10:00:00','49894842000123')]
assert S.publicar_auditorias(base,outro)==1
ts=[e['timestamp'] for e in S.ler_auditorias(base)]; assert sorted(ts)==['2026-10-01T10:00:00','2026-10-02T10:00:00','2026-10-05T09:00:00']
m=S.mesclar_auditorias(local,outro,S.ler_auditorias(base)); assert [e['timestamp'] for e in m]==['2026-10-05T09:00:00','2026-10-02T10:00:00','2026-10-01T10:00:00']          # mais nova primeiro
sat=Path(tempfile.mkdtemp())/'SAT_NFCe.xlsx'; sat.write_bytes(b'PK-excel')
assert S.subir_excels(base,'ELYON CASA - 49894842000123','2026-09-01',[str(sat)])==1 and S.subir_excels(base,'ELYON CASA - 49894842000123','2026-09-01',[str(sat)])==0
assert (srv/'Repositório'/'ELYON CASA - 49894842000123'/'2026'/'09'/'Auditoria'/'SAT_NFCe.xlsx').read_bytes()==b'PK-excel'
casa=Path(tempfile.mkdtemp(prefix='exato_sat_')); assert S.trazer_excels(base,casa)==1 and (casa/'servidor'/'SAT_NFCe.xlsx').read_bytes()==b'PK-excel' and S.trazer_excels(base,casa)==0
print('V182 sincronia OK')
