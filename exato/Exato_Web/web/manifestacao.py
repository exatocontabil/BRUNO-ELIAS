"""Manifestação do Destinatário (NF-e) no Exato Web: "Ciência da Operação" (evento 210210).

Por que existe: as NF-e de fornecedores chegam primeiro só como RESUMO. A SEFAZ só entrega o XML completo depois que o destinatário manifesta a Ciência da
Operação. O site manifesta a ciência das notas pendentes de uma empresa e o XML completo chega na busca seguinte.

Regras: é um ato em nome do cliente, por isso NUNCA é automático por padrão (a empresa precisa ser ligada de propósito, ou a pessoa pede e confirma); cada nota
é manifestada uma vez; só a Ciência (a manifestação conclusiva — confirmar, desconhecer, operação não realizada — é decisão do contador, fora daqui).
O evento é montado e ASSINADO aqui (XML-DSig, RSA-SHA1, como o layout da NF-e exige) com a chave do A1 guardado, e enviado ao Ambiente Nacional com o
certificado no repositório do Windows (mesma forma das consultas de distribuição). Testado só com a SEFAZ simulada: use primeiro o ambiente de homologação."""
import base64, hashlib, re, sqlite3, subprocess, sys, threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from . import config, nucleo
from .cofre import CofreErro

NS = 'http://www.portalfiscal.inf.br/nfe'
NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'
C14N = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
URL = {1: 'https://www.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx', 2: 'https://hom.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx'}
WSDL = 'http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4'
ACAO = WSDL + '/nfeRecepcaoEvento'
TP_CIENCIA = '210210'
OK_CSTAT = {'135': 'registrada', '136': 'registrada'}          # evento registrado (vinculado ou não à NF-e)
JA_CSTAT = {'573': 'ja_registrada'}                            # duplicidade: a ciência já estava registrada
LIMITE_PADRAO = 50


class ManifestacaoErro(Exception): pass


# ------------------------------------------------------------------ evento e assinatura
def _fuso(agora):
    off = agora.astimezone().utcoffset() if agora.tzinfo is None else agora.utcoffset()
    off = off or timedelta(0); m = int(off.total_seconds() // 60); sinal = '+' if m >= 0 else '-'; m = abs(m)
    return f'{sinal}{m // 60:02d}:{m % 60:02d}'


def id_evento(chave, tp=TP_CIENCIA, seq=1): return f'ID{tp}{chave}{seq:02d}'


def inf_evento(chave, cnpj, amb, agora, tp=TP_CIENCIA, seq=1):
    """`infEvento` como texto, já na forma canônica (C14N): xmlns primeiro, depois o Id; elementos vazios não existem aqui."""
    dh = agora.strftime('%Y-%m-%dT%H:%M:%S') + _fuso(agora)
    return (f'<infEvento xmlns="{NS}" Id="{id_evento(chave, tp, seq)}"><cOrgao>91</cOrgao><tpAmb>{amb}</tpAmb><CNPJ>{cnpj}</CNPJ><chNFe>{chave}</chNFe><dhEvento>{dh}</dhEvento>'
            f'<tpEvento>{tp}</tpEvento><nSeqEvento>{seq}</nSeqEvento><verEvento>1.00</verEvento><detEvento versao="1.00"><descEvento>Ciencia da Operacao</descEvento></detEvento></infEvento>')


def _assinatura(inf_canonico, ref_id, chave_priv, cert):
    digest = base64.b64encode(hashlib.sha1(inf_canonico.encode('utf-8')).digest()).decode('ascii')
    si = (f'<SignedInfo xmlns="{NS_DSIG}"><CanonicalizationMethod Algorithm="{C14N}"></CanonicalizationMethod><SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"></SignatureMethod>'
          f'<Reference URI="#{ref_id}"><Transforms><Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"></Transform><Transform Algorithm="{C14N}"></Transform></Transforms>'
          f'<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"></DigestMethod><DigestValue>{digest}</DigestValue></Reference></SignedInfo>')
    valor = base64.b64encode(chave_priv.sign(si.encode('utf-8'), padding.PKCS1v15(), hashes.SHA1())).decode('ascii')
    der = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode('ascii')
    si_dentro = si.replace(f' xmlns="{NS_DSIG}"', '', 1)          # dentro de <Signature xmlns=...> o namespace já vale para os filhos
    return (f'<Signature xmlns="{NS_DSIG}">{si_dentro}<SignatureValue>{valor}</SignatureValue><KeyInfo><X509Data><X509Certificate>{der}</X509Certificate></X509Data></KeyInfo></Signature>')


def montar_lote(chave, cnpj, amb, agora, chave_priv, cert, id_lote=1):
    """`envEvento` assinado (pronto para o corpo SOAP)."""
    inf = inf_evento(chave, cnpj, amb, agora); assinatura = _assinatura(inf, id_evento(chave), chave_priv, cert)
    inf_dentro = inf.replace(f' xmlns="{NS}"', '', 1)          # dentro do envEvento o namespace vem do pai
    return f'<envEvento xmlns="{NS}" versao="1.00"><idLote>{id_lote}</idLote><evento versao="1.00">{inf_dentro}{assinatura}</evento></envEvento>'


def soap(env_evento):
    return (f'<?xml version="1.0" encoding="utf-8"?><soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"><soap12:Body>'
            f'<nfeDadosMsg xmlns="{WSDL}">{env_evento}</nfeDadosMsg></soap12:Body></soap12:Envelope>')


def interpretar(resposta):
    """(cstat do evento, motivo, protocolo) da resposta SOAP. Sem resposta clara: ('', texto, '')."""
    t = str(resposta or '')
    def pega(tag, bloco=t):
        m = re.search(rf'<(?:\w+:)?{tag}[^>]*>([^<]*)</(?:\w+:)?{tag}>', bloco); return m.group(1).strip() if m else ''
    ev = re.search(r'<(?:\w+:)?retEvento\b.*?</(?:\w+:)?retEvento>', t, re.S)
    if ev: return pega('cStat', ev.group(0)), pega('xMotivo', ev.group(0)), pega('nProt', ev.group(0))
    return pega('cStat'), pega('xMotivo') or t[:160], ''


# ------------------------------------------------------------------ transporte (Windows)
_PS = r'''param([string]$Thumbprint,[string]$Url,[string]$SoapAction,[string]$BodyBase64)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$cert=$null
foreach($path in @("Cert:\CurrentUser\My\$Thumbprint","Cert:\LocalMachine\My\$Thumbprint")) { try { $c=Get-Item -Path $path -ErrorAction Stop; if($c.HasPrivateKey){$cert=$c;break} } catch {} }
if(-not $cert){throw 'Certificado com chave privada não localizado no repositório do Windows.'}
$body=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($BodyBase64))
$request=[System.Net.HttpWebRequest]::Create($Url); $request.Method='POST'
$request.ContentType='application/soap+xml; charset=utf-8; action="'+$SoapAction+'"'; $request.Accept='application/soap+xml, text/xml'
$request.UserAgent='ExatoWeb/0.1'; $request.ClientCertificates.Add($cert)|Out-Null
$bytes=[Text.Encoding]::UTF8.GetBytes($body); $request.ContentLength=$bytes.Length
$stream=$request.GetRequestStream();$stream.Write($bytes,0,$bytes.Length);$stream.Close()
try {$response=[Net.HttpWebResponse]$request.GetResponse();$reader=New-Object IO.StreamReader($response.GetResponseStream(),[Text.Encoding]::UTF8);Write-Output $reader.ReadToEnd();$reader.Close();$response.Close()}
catch [Net.WebException] {$resp=$_.Exception.Response;if($resp){$reader=New-Object IO.StreamReader($resp.GetResponseStream(),[Text.Encoding]::UTF8);Write-Output $reader.ReadToEnd();$reader.Close();$resp.Close()}else{throw}}'''


def transporte_windows(thumb, url, corpo):
    """Envia o SOAP com o certificado do repositório do Windows. Devolve o texto da resposta."""
    if sys.platform != 'win32': raise ManifestacaoErro('O envio ao Ambiente Nacional só funciona no servidor Windows.')
    ps_b64 = base64.b64encode(_PS.encode('utf-8')).decode('ascii'); body_b64 = base64.b64encode(corpo.encode('utf-8')).decode('ascii')
    cmd = ("$s=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + ps_b64 + "'));$sb=[ScriptBlock]::Create($s);& $sb " + f"-Thumbprint '{thumb}' -Url '{url}' -SoapAction '{ACAO}' -BodyBase64 '{body_b64}'")
    try:
        p = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', cmd], capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired: raise ManifestacaoErro('O Ambiente Nacional não respondeu em 60 segundos.')
    if not (p.stdout or '').strip(): raise ManifestacaoErro((p.stderr or 'Sem resposta do Ambiente Nacional.').strip().splitlines()[0][:200])
    return p.stdout


# ------------------------------------------------------------------ pendências e registro
class Manifestador:
    def __init__(self, core, cofre, certificado_para, transporte=None, homologacao=False):
        self.core, self.cofre, self.certificado_para = core, cofre, certificado_para; self.transporte = transporte or transporte_windows; self.homologacao = homologacao
        self.caminho = config.DADOS / 'web.db'; self._trava = threading.Lock()
        c = self._con(); c.execute("""CREATE TABLE IF NOT EXISTS manifestacoes(chave TEXT NOT NULL, tipo TEXT NOT NULL, cnpj TEXT NOT NULL, estado TEXT NOT NULL, cstat TEXT, motivo TEXT, protocolo TEXT, em TEXT, por TEXT, PRIMARY KEY(chave, tipo))"""); c.commit(); c.close()

    def _con(self): return sqlite3.connect(self.caminho, timeout=15)

    def _db(self): return sqlite3.connect(str(self.core.DB_PATH), timeout=30)

    def pendentes(self, cnpj='', limite=2000):
        """NF-e de ENTRADA que ainda são só resumo (sem o XML completo) e cuja ciência ainda não foi manifestada. [{'doc_id','cnpj','chave','data','numero'}]"""
        con = self._db(); cnpj = re.sub(r'\D', '', cnpj or '')
        try:
            sql = ("SELECT doc_id, cnpj, access_key, issued_at, number FROM documents WHERE family='nfe' AND direction='Entrada' AND status<>'Evento' AND length(COALESCE(access_key,''))=44 "
                   "AND (instr(substr(CAST(xml AS TEXT),1,400),'<resNFe')>0 OR instr(substr(CAST(xml AS TEXT),1,400),':resNFe')>0)" + (' AND cnpj=?' if cnpj else '') + " ORDER BY issued_at LIMIT ?")
            rows = con.execute(sql, ((cnpj,) if cnpj else ()) + (int(limite),)).fetchall()
        finally: con.close()
        feitas = set(self._chaves_ok())
        return [{'doc_id': r[0], 'cnpj': r[1], 'chave': r[2], 'data': str(r[3] or '')[:10], 'numero': r[4] or ''} for r in rows if r[2] not in feitas]

    def _chaves_ok(self):
        c = self._con()
        try: return [r[0] for r in c.execute("SELECT chave FROM manifestacoes WHERE tipo=? AND estado IN ('registrada','ja_registrada')", (TP_CIENCIA,))]
        finally: c.close()

    def contagem(self):
        """{cnpj: pendentes}"""
        out = {}
        for p in self.pendentes(limite=100000): out[p['cnpj']] = out.get(p['cnpj'], 0) + 1
        return out

    def _registrar(self, chave, cnpj, estado, cstat, motivo, protocolo, por, agora):
        c = self._con(); c.execute("INSERT OR REPLACE INTO manifestacoes(chave,tipo,cnpj,estado,cstat,motivo,protocolo,em,por) VALUES(?,?,?,?,?,?,?,?,?)",
                                   (chave, TP_CIENCIA, cnpj, estado, cstat, str(motivo)[:300], protocolo, agora.isoformat(timespec='seconds'), por)); c.commit(); c.close()

    def historico(self, limite=100, cnpj=''):
        c = self._con(); c.row_factory = sqlite3.Row
        try: return [dict(r) for r in c.execute("SELECT * FROM manifestacoes" + (" WHERE cnpj=?" if cnpj else "") + " ORDER BY em DESC LIMIT ?", ((cnpj,) if cnpj else ()) + (limite,))]
        finally: c.close()

    def manifestar(self, cnpj, limite=LIMITE_PADRAO, por='', agora=None, cancelar=None):
        """Manifesta a Ciência das pendentes da empresa (até `limite`). Devolve {'registradas','ja','erros': [texto], 'pendentes_restantes'}."""
        cnpj = re.sub(r'\D', '', cnpj or ''); agora = agora or datetime.now(); res = {'registradas': 0, 'ja': 0, 'erros': [], 'restantes': 0}
        if not self._trava.acquire(blocking=False): res['erros'].append('Já existe uma manifestação em andamento.'); return res
        try:
            lista = self.pendentes(cnpj, limite=100000); res['restantes'] = max(0, len(lista) - int(limite)); lista = lista[:int(limite)]
            if not lista: return res
            cid = self.certificado_para(cnpj)
            if cid is None: res['erros'].append('Esta empresa não tem certificado A1 guardado (nem o do escritório).'); return res
            amb = 2 if self.homologacao else 1
            try:
                chave_priv, cert = self.cofre.material(cid)
                with self.cofre.usar(cid) as thumb:
                    for item in lista:
                        if cancelar and cancelar(): break
                        try:
                            corpo = soap(montar_lote(item['chave'], cnpj, amb, agora, chave_priv, cert))
                            cstat, motivo, prot = interpretar(self.transporte(thumb, URL[amb], corpo))
                        except ManifestacaoErro as exc:
                            res['erros'].append(str(exc)); self._registrar(item['chave'], cnpj, 'erro', '', str(exc), '', por, agora); break          # falha de rede: para e tenta depois
                        if cstat in OK_CSTAT: self._registrar(item['chave'], cnpj, OK_CSTAT[cstat], cstat, motivo, prot, por, agora); res['registradas'] += 1
                        elif cstat in JA_CSTAT: self._registrar(item['chave'], cnpj, JA_CSTAT[cstat], cstat, motivo, prot, por, agora); res['ja'] += 1
                        else:
                            self._registrar(item['chave'], cnpj, 'erro', cstat, motivo, '', por, agora)
                            res['erros'].append(f"{item['numero'] or item['chave'][-9:]}: " + (f'cStat {cstat} — ' if cstat else '') + (motivo or 'o Ambiente Nacional não aceitou'))
                            if len(res['erros']) >= 3: break          # recusas seguidas: algo está errado (certificado/procuração): não insiste
            except CofreErro as exc: res['erros'].append(str(exc))
            return res
        finally:
            self._trava.release()
