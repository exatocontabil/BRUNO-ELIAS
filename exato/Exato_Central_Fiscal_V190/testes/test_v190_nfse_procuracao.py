"""V190: NFS-e pelo certificado do escritório (procuração na Receita Federal): empresa sem certificado próprio é buscada com o certificado escolhido na tela NFS-e;
aceita = lembrada e incluída nas rodadas; recusada = motivo explicado e sem insistir a cada rodada; opção desligável; Situação da busca mostra "por procuração"."""
import os, sys, tempfile, json, time
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v190_proc_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(Path(__file__).parent))
import exato_nfse_procuracao as P, exato_busca_motivos as BM, exato_situacao_busca as S
import exato_central_fiscal as m
from test_v190_nfse_core import nfse_xml, chave, pack, PREST
A,B,C=PREST,'11222333000181','45723174000110'          # A: tem certificado próprio; B: procuração aceita; C: procuração recusada
# ---- módulo (sem tela)
assert P.raiz('12.345.678/0001-95')=='12345678' and P.raiz('12345678909')==''
assert P.modo_para('12345678000195','12345678000276')=='proprio'          # outro estabelecimento da mesma raiz
assert P.modo_para('99888777000166','12345678000195')=='procuracao' and P.modo_para('12345678909','12345678000195')=='procuracao' and P.modo_para('','12345678000195')=='procuracao'
cfg={}; assert P.ligada(cfg) and not P.ligada({'nfse_prefs':{'procuracao':False}})
agora=datetime(2026,11,3,10,0,0)
P.registrar(cfg,B,'procuracao',False,'x',agora=agora)
assert not P.tentar_agora(cfg,B,agora=agora+timedelta(hours=1)) and P.tentar_agora(cfg,B,agora=agora+timedelta(hours=13)) and P.tentar_agora(cfg,B,manual=True,agora=agora+timedelta(hours=1))
P.registrar(cfg,B,'procuracao',True,agora=agora); assert P.tentar_agora(cfg,B,agora=agora) and P.rotulo(cfg,B)=='por procuração (certificado do escritório)'
assert P.parece_recusa('Este certificado não pertence a esta empresa (o CNPJ base é diferente)') and not P.parece_recusa('Tempo esgotado ao consultar')
assert 'procuração eletrônica' in P.mensagem('procuracao','CNPJ base diferente') and P.mensagem('proprio','CNPJ base diferente')=='CNPJ base diferente'
# causas em português, sem jargão
for cod in ('procuracao_a_tentar','procuracao_nao_aceita'):
    e=BM.explicar(cod); assert e['codigo']==cod and e['acao'] and 'ADN' not in e['explicacao']+e['acao'] and 'Receita Federal' in e['explicacao']+e['acao']
assert BM.diagnosticar({'cert_escolhido':True,'empresa_tem_cert':False,'procuracao':True})['nfse']=='procuracao_a_tentar'
assert BM.diagnosticar({'cert_escolhido':True,'empresa_tem_cert':False})['nfse']=='sem_certificado_empresa'
# ---- na tela
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaProc#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaProc#2026')
CERT_A={'Thumbprint':'PROPRIO_A','Document':A,'FriendlyName':'ALFA','NotAfter':'2099-01-01'}
m.enumerate_windows_certificates=lambda *a,**k:([CERT_A],'')          # a lista do Windows é relida em alguns pontos; a empresa A sempre tem o seu
for cn,nm in ((A,'ALFA LTDA'),(B,'BETA LTDA'),(C,'GAMA LTDA')): m.db_register_company(cn,nm)
infos=[]; m.messagebox.showinfo=lambda *a,**k:infos.append(a); m.messagebox.showwarning=lambda *a,**k:infos.append(a); m.messagebox.showerror=lambda *a,**k:infos.append(a)
m.messagebox.askyesno=lambda *a,**k:True
app=m.App(current_user=user)
def wait(cond,t=15,start=None):
    end=time.time()+t; res=[False]
    def tick():
        if cond(): res[0]=True; app.quit()
        elif time.time()>end: app.quit()
        else: app.after(30,tick)
    if start: app.after(0,start)
    app.after(40,tick); app.mainloop(); return res[0]
calls=[]
def fake(url,thumb):
    cn=url.split('cnpjConsulta=')[1] if 'cnpjConsulta=' in url else ''; calls.append((cn,thumb)); nsu=int(url.split('/DFe/')[1].split('?')[0])
    if cn==C and thumb=='ESCRITORIO': return 400,json.dumps({'Erros':[{'Descricao':'O CNPJ base do certificado difere do CNPJ consultado'}]})
    if nsu==0:
        n={A:11,B:12}[cn]; return 200,json.dumps({'StatusProcessamento':'DOCUMENTOS_LOCALIZADOS','LoteDFe':[{'NSU':1,'ChaveAcesso':chave(n),'TipoDocumento':'NFSE','ArquivoXml':pack(nfse_xml(n,prest=cn))}]})
    return 404,json.dumps({'StatusProcessamento':'NENHUM_DOCUMENTO_LOCALIZADO'})
try:
    app.geometry('1366x700+0+0'); app.update(); m.nfse_mod.ADN_PAUSE_SECONDS=0; app._nfse_transport=fake
    app.certificates=[CERT_A]
    app._nfse_ensure_built(); app.update()
    assert hasattr(app,'nfse_proc_var') and app.nfse_proc_var.get()
    # sem certificado do escritório escolhido: B e C ficam de fora (como antes)
    app.nfse_selected=None; trab,fora=app._nfse_trabalho(); assert [(c['cnpj'],v) for c,k,v in trab]==[(A,'proprio')] and {c['cnpj'] for c in fora}=={B,C}
    # com o certificado do escritório (um CPF): B e C entram por procuração
    app.nfse_selected={'Thumbprint':'ESCRITORIO','Document':'12345678909','FriendlyName':'CONTADOR','NotAfter':'2099-01-01'}
    trab,fora=app._nfse_trabalho(); assert {c['cnpj']:v for c,k,v in trab}=={A:'proprio',B:'procuracao',C:'procuracao'} and not fora
    assert [c['cnpj'] for c,k,v in app._nfse_trabalho(only=[B])[0]]==[B]
    # rodada automática
    assert wait(lambda: (not app._nfse_running) and len(calls)>=3,start=lambda: app._nfse_run_all(auto=True,quiet=True)),calls
    assert (A,'PROPRIO_A') in calls and (B,'ESCRITORIO') in calls and (C,'ESCRITORIO') in calls
    assert m.db_nfse_stats(A)['total']==1 and m.db_nfse_stats(B)['total']==1 and m.db_nfse_stats(C)['total']==0
    ac=app.config_data['nfse_acesso']; assert ac[B]['modo']=='procuracao' and ac[B]['ok'] and ac[C]['modo']=='procuracao' and not ac[C]['ok'] and A not in ac
    oc=BM.ultimas(str(m.DB_PATH)); assert oc[(C,'nfse')]['codigo']=='procuracao_nao_aceita' and oc[(B,'nfse')]['resultado']=='ok',oc
    assert not infos          # rodada automática: nenhuma janela de erro
    # segunda rodada logo depois: a recusa de C não é repetida; B e A continuam
    calls.clear(); assert wait(lambda: (not app._nfse_running) and len(calls)>=2,start=lambda: app._nfse_run_all(auto=True,quiet=True))
    assert (C,'ESCRITORIO') not in calls and (B,'ESCRITORIO') in calls,calls
    # busca manual tenta C de novo e fala em procuração
    calls.clear(); assert wait(lambda: (not app._nfse_running) and calls,start=lambda: app._nfse_run_all(auto=False))
    assert (C,'ESCRITORIO') in calls and 'não aceitou o certificado do escritório' in app.nfse_detail.cget('text'),app.nfse_detail.cget('text')
    # uma empresa só (tela NFS-e, certificado do escritório)
    app.nfse_company.set(m._format_cnpj(C)); calls.clear(); app._nfse_via='certificado'
    assert wait(lambda: (not app._nfse_running) and calls,start=lambda: app._nfse_run_certificate(C))
    assert 'procuração eletrônica' in app.nfse_detail.cget('text') and 'CNPJ base' not in app.nfse_detail.cget('text'),app.nfse_detail.cget('text')
    # Situação da busca: B "por procuração"; C com a causa; empresa sem certificado e sem tentativa = "será buscada..."
    app.config_data['nfse_acesso'].pop(C,None); BM.registrar(str(m.DB_PATH),C,['nfse'],'ok')
    base,com=app._sit_contexto_diagnostico(); assert base['procuracao'] is True
    diag={cn:BM.diagnosticar(dict(base,empresa_tem_cert=cn in com,portal_login=False,procuracao=True)) for cn in (A,B,C)}
    lin={l['cnpj']:l for l in S.linhas(str(m.DB_PATH),app.config_data,None,ocorrencias=BM.ultimas(str(m.DB_PATH)),diagnostico=diag,acessos=app.config_data['nfse_acesso'])}
    assert lin[B]['celulas']['nfse']['via']=='procuração' and 'por procuração' in lin[B]['celulas']['nfse']['detalhe'] and lin[A]['celulas']['nfse']['via']=='' and lin[C]['celulas']['nfse']['via']==''
    # opção desligada: volta ao comportamento anterior
    app.nfse_proc_var.set(False); app._nfse_save_prefs(); assert not P.ligada(app.config_data)
    trab,fora=app._nfse_trabalho(); assert [v for c,k,v in trab]==['proprio'] and {c['cnpj'] for c in fora}=={B,C}
    app.nfse_proc_var.set(True); app._nfse_save_prefs(); assert P.ligada(app.config_data)
    print('V190 NFS-e por procuração OK')
finally:
    try: app.destroy()
    except Exception: pass
