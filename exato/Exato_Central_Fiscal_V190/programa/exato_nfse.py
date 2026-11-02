"""NFS-e Padrão Nacional: leitura dos XMLs e comunicação com o ADN (Ambiente de Dados Nacional).

Este módulo não depende da interface nem do banco: recebe e devolve dados simples, para poder ser testado
em qualquer computador. A comunicação real (certificado digital do Windows) fica em `adn_transport_windows`.

Base técnica (fontes públicas secundárias; conferir com o Manual dos Contribuintes - APIs ADN):
  GET {base}/contribuintes/DFe/{ultNSU}  -> JSON com LoteDFe (até 50 documentos),
  cada item com NSU, ChaveAcesso, TipoDocumento, TipoEvento, ArquivoXml (gzip + base64), DataHoraGeracao.
  Autenticação: TLS mútuo com o certificado digital do contribuinte (sem token).
"""
import base64
import gzip
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

ADN_PRODUCAO = 'https://adn.nfse.gov.br/contribuintes'
ADN_HOMOLOGACAO = 'https://adn.producaorestrita.nfse.gov.br/contribuintes'
ADN_PAGE_SIZE = 50
ADN_PAUSE_SECONDS = 0.5          # pausa entre lotes: o ADN bloqueia consultas em rajada
NFSE_CANCEL_EVENT_TYPES = {'101101', '105102'}   # cancelamento e cancelamento por substituição


class NfseError(Exception):
    """Falha esperada de comunicação ou de formato (a mensagem já é amigável)."""


# ---------------------------------------------------------------- XML
def _local(tag):
    return str(tag).rsplit('}', 1)[-1]


def _digits(value):
    return re.sub(r'\D', '', str(value or ''))


def _find_children(node, name):
    return [c for c in list(node) if _local(c.tag) == name]


def _first(node, *path):
    """Primeiro descendente seguindo o caminho de nomes locais (ignora namespace)."""
    cur = [node]
    for name in path:
        nxt = []
        for n in cur:
            nxt.extend(_find_children(n, name))
        cur = nxt
        if not cur:
            return None
    return cur[0]


def _text(node, *path):
    n = _first(node, *path) if path else node
    return (n.text or '').strip() if n is not None and n.text else ''


def _party(node):
    if node is None:
        return {'doc': '', 'nome': ''}
    return {'doc': _digits(_text(node, 'CNPJ') or _text(node, 'CPF')), 'nome': _text(node, 'xNome')}


def _decimal(value):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def is_nfse_xml(xml_bytes):
    head = bytes(xml_bytes)[:800]
    return bool(re.search(rb'<(?:[A-Za-z_][\w.-]*:)?NFSe\b', head) or b'sped.fazenda.gov.br/nfse' in head and b'infNFSe' in bytes(xml_bytes)[:4000])


def is_nfse_event_xml(xml_bytes):
    head = bytes(xml_bytes)[:1200]
    return bool(re.search(rb'<(?:[A-Za-z_][\w.-]*:)?evento\b', head) or b'pedRegEvento' in bytes(xml_bytes)[:4000])


def parse_nfse(xml_bytes, consulta_cnpj=''):
    """Metadados de uma NFS-e nacional, no mesmo formato usado pelas demais famílias."""
    result = {'family': 'nfse', 'tipo': 'NFS-e', 'empresa': 'Empresa não identificada', 'direcao': 'Entrada',
              'numero': '', 'serie': '', 'data': '', 'valor': Decimal('0.00'), 'chave': '',
              'prestador': {'doc': '', 'nome': ''}, 'tomador': {'doc': '', 'nome': ''}, 'intermediario': {'doc': '', 'nome': ''},
              'municipio': '', 'situacao': 'Autorizado'}
    try:
        root = ET.fromstring(bytes(xml_bytes))
    except ET.ParseError as exc:
        raise NfseError(f'O arquivo não é um XML de NFS-e válido.')
    inf = root if _local(root.tag) == 'infNFSe' else _first(root, 'infNFSe')
    if inf is None:
        raise NfseError('O arquivo não é uma NFS-e do padrão nacional.')
    ident = inf.attrib.get('Id') or ''
    m = re.search(r'(\d{50})', ident)
    result['chave'] = m.group(1) if m else _digits(ident)
    result['numero'] = _text(inf, 'nNFSe')
    result['municipio'] = _text(inf, 'xLocEmi') or _text(inf, 'xLocPrestacao')
    dps = _first(inf, 'DPS', 'infDPS')
    emit = _party(_first(inf, 'emit'))
    prest = _party(_first(dps, 'prest')) if dps is not None else {'doc': '', 'nome': ''}
    if not prest['doc']:
        prest = dict(emit)
    elif not prest['nome'] and (not emit['doc'] or emit['doc'] == prest['doc']):
        prest['nome'] = emit['nome']      # a DPS traz só o CNPJ; o nome está no bloco do emitente
    result['prestador'] = prest
    if dps is not None:
        result['tomador'] = _party(_first(dps, 'toma'))
        result['intermediario'] = _party(_first(dps, 'interm'))
        result['serie'] = _text(dps, 'serie')
        result['data'] = _text(dps, 'dhEmi') or _text(dps, 'dCompet')
        valor = _decimal(_text(dps, 'valores', 'vServPrest', 'vServ'))
    else:
        valor = None
    if not result['data']:
        result['data'] = _text(inf, 'dhProc')
    if valor is None:
        valor = _decimal(_text(inf, 'valores', 'vLiq'))
    result['valor'] = valor if valor is not None else Decimal('0.00')
    cnpjq = _digits(consulta_cnpj)
    if cnpjq and cnpjq == prest['doc']:
        result['direcao'] = 'Saída'; result['empresa'] = prest['nome'] or 'Empresa não identificada'
    elif cnpjq and cnpjq == result['tomador']['doc']:
        result['direcao'] = 'Entrada'; result['empresa'] = result['tomador']['nome'] or prest['nome'] or 'Empresa não identificada'
    elif cnpjq and cnpjq == result['intermediario']['doc']:
        result['direcao'] = 'Entrada'; result['empresa'] = result['intermediario']['nome'] or prest['nome'] or 'Empresa não identificada'
    else:
        # O CNPJ consultado não participa da nota: não inventa o nome da empresa.
        result['empresa'] = 'Empresa não identificada' if cnpjq else (prest['nome'] or result['tomador']['nome'] or 'Empresa não identificada')
        result['direcao'] = 'Saída' if prest['doc'] else 'Entrada'
    return result


def _desc(node, name):
    """Texto do primeiro descendente com esse nome local (ignora namespace)."""
    if node is None:
        return ''
    for n in node.iter():
        if _local(n.tag) == name and n.text and n.text.strip():
            return n.text.strip()
    return ''


_UF_POR_CODIGO = {'11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE', '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE', '29': 'BA',
                  '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP', '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF'}


def _address(node, cities=None):
    """Endereço da parte. `cities`: {código IBGE: nome} conhecidos pela própria nota (o XML traz o código, o nome vem de xLocEmi etc.)."""
    if node is None:
        return {'logradouro': '', 'numero': '', 'complemento': '', 'bairro': '', 'municipio': '', 'uf': '', 'cep': '', 'fone': '', 'email': ''}
    code = _desc(node, 'cMun')
    uf = _desc(node, 'UF') or (_UF_POR_CODIGO.get(code[:2], '') if len(code) == 7 else '')
    return {'logradouro': _desc(node, 'xLgr'), 'numero': _desc(node, 'nro'), 'complemento': _desc(node, 'xCpl'), 'bairro': _desc(node, 'xBairro'),
            'municipio': _desc(node, 'xMun') or (cities or {}).get(code, ''), 'uf': uf, 'cep': _desc(node, 'CEP'),
            'fone': _desc(node, 'fone'), 'email': _desc(node, 'email')}


_REGIME_SN = {'1': 'Não optante pelo Simples Nacional', '2': 'Optante pelo Simples Nacional (MEI)', '3': 'Optante pelo Simples Nacional (ME/EPP)'}


def _format_trib_nacional(code):
    d = re.sub(r'\D', '', str(code or ''))
    return f'{d[0:2]}.{d[2:4]}.{d[4:6]}' if len(d) == 6 else (code or '')


def parse_nfse_details(xml_bytes, consulta_cnpj=''):
    """Tudo o que a representação em PDF da NFS-e precisa. Campos que o XML não traz ficam vazios."""
    base = parse_nfse(xml_bytes, consulta_cnpj)
    root = ET.fromstring(bytes(xml_bytes))
    inf = root if _local(root.tag) == 'infNFSe' else _first(root, 'infNFSe')
    dps = _first(inf, 'DPS', 'infDPS')
    emit = _first(inf, 'emit')
    prest = _first(dps, 'prest') if dps is not None else None
    toma = _first(dps, 'toma') if dps is not None else None
    interm = _first(dps, 'interm') if dps is not None else None
    serv = _first(dps, 'serv') if dps is not None else None
    vals_nfse = _first(inf, 'valores')
    vals_dps = _first(dps, 'valores') if dps is not None else None
    cities = {c: n for c, n in ((_text(inf, 'cLocIncid'), _text(inf, 'xLocIncid')), (_desc(dps, 'cLocEmi') if dps is not None else '', _text(inf, 'xLocEmi')),
                                (_desc(serv, 'cLocPrestacao') if serv is not None else '', _text(inf, 'xLocPrestacao'))) if c and n}
    def money(*sources):
        for node, name in sources:
            v = _decimal(_desc(node, name))
            if v is not None:
                return v
        return None
    base.update({
        'processamento': _text(inf, 'dhProc'), 'competencia': _text(dps, 'dCompet') if dps is not None else '', 'ambiente': _text(inf, 'ambGer'),
        'numero_dps': _text(dps, 'nDPS') if dps is not None else '',
        'local_emissao': _text(inf, 'xLocEmi'), 'local_prestacao': _text(inf, 'xLocPrestacao'), 'local_incidencia': _text(inf, 'xLocIncid'),
        'prestador_im': _desc(prest, 'IM') or _desc(emit, 'IM'),
        'prestador_end': _address(_first(emit, 'enderNac') if emit is not None and _first(emit, 'enderNac') is not None else emit, cities),
        'tomador_end': _address(toma, cities), 'tomador_im': _desc(toma, 'IM'),
        'servico_codigo': _desc(serv, 'cTribNac') or _text(inf, 'xTribNac'), 'servico_descricao': _desc(serv, 'xDescServ'),
        'servico_trib_nacional': _text(inf, 'xTribNac'), 'servico_codigo_municipal': _desc(serv, 'cTribMun'),
        'info_complementar': _desc(serv, 'xInfComp') or _desc(dps, 'xInfComp'),
        'valor_servico': money((vals_dps, 'vServ')),
        'valor_desconto': money((vals_dps, 'vDescIncond')), 'valor_base': money((vals_nfse, 'vBC')),
        'aliquota': _desc(vals_nfse, 'pAliqAplic') or _desc(vals_dps, 'pAliq'), 'valor_iss': money((vals_nfse, 'vISSQN')),
        'valor_retido': money((vals_nfse, 'vTotalRet')), 'valor_liquido': money((vals_nfse, 'vLiq')),
        'regime': _desc(prest, 'opSimpNac'), 'retencao_iss': _desc(vals_dps, 'tpRetISSQN') or _desc(dps, 'tpRetISSQN'),
        'regime_texto': _REGIME_SN.get(_desc(prest, 'opSimpNac'), ''), 'tributos_aprox_sn': _desc(vals_dps, 'pTotTribSN'),
        'servico_codigo_formatado': _format_trib_nacional(_desc(serv, 'cTribNac')), 'servico_nbs': _text(inf, 'xNBS'),
        'ambiente_dps': {'1': 'Produção', '2': 'Homologação'}.get(_desc(dps, 'tpAmb') if dps is not None else '', ''),
    })
    # telefone e e-mail do prestador ficam no bloco do emitente (ou da DPS), fora do endereço
    pend = base['prestador_end']
    pend['fone'] = pend['fone'] or _desc(emit, 'fone') or _desc(prest, 'fone')
    pend['email'] = pend['email'] or _desc(emit, 'email') or _desc(prest, 'email')
    return base


RETENCAO_ISS = {'1': 'Não', '2': 'Sim', '3': 'Sim'}      # tpRetISSQN: 1 = não retido, 2 = retido pelo tomador, 3 = retido pelo intermediário


def retencao_iss_texto(codigo):
    """'Sim' / 'Não' conforme o código da nota (tpRetISSQN); None quando a nota não informa (nunca assume "Não")."""
    return RETENCAO_ISS.get(str(codigo or '').strip())


def parse_nfse_tributos(xml_bytes):
    """Alíquota, ISS e retenção do ISS de uma NFS-e (o que o relatório mostra): {'aliquota': Decimal|None, 'valor_iss': Decimal|None, 'iss_retido': 'Sim'|'Não'|None}."""
    try:
        root = ET.fromstring(bytes(xml_bytes))
    except ET.ParseError:
        return {'aliquota': None, 'valor_iss': None, 'iss_retido': None}
    inf = root if _local(root.tag) == 'infNFSe' else _first(root, 'infNFSe')
    if inf is None:
        return {'aliquota': None, 'valor_iss': None, 'iss_retido': None}
    dps = _first(inf, 'DPS', 'infDPS')
    vals_nfse = _first(inf, 'valores'); vals_dps = _first(dps, 'valores') if dps is not None else None
    aliq = _decimal(_desc(vals_nfse, 'pAliqAplic') or _desc(vals_dps, 'pAliq'))
    iss = _decimal(_desc(vals_nfse, 'vISSQN'))
    ret = _desc(vals_dps, 'tpRetISSQN') or _desc(dps, 'tpRetISSQN')
    return {'aliquota': aliq, 'valor_iss': iss, 'iss_retido': retencao_iss_texto(ret)}


def parse_nfse_municipio(xml_bytes):
    """Município onde o ISS é devido, em relação ao do prestador (V179): {'incid_cod','incid_nome','prest_cod','prest_nome','fora': 'SIM'|'NÃO'|None}.
    A comparação é pelo CÓDIGO do município (IBGE), nunca pelo nome; faltando um dos dois códigos, `fora` é None (mostra "—", nunca "NÃO" por falta de dado)."""
    vazio = {'incid_cod': '', 'incid_nome': '', 'prest_cod': '', 'prest_nome': '', 'fora': None}
    try:
        root = ET.fromstring(bytes(xml_bytes))
    except ET.ParseError:
        return vazio
    inf = root if _local(root.tag) == 'infNFSe' else _first(root, 'infNFSe')
    if inf is None:
        return vazio
    emit = _first(inf, 'emit')
    cod_prest = _digits(_desc(_first(emit, 'enderNac') if emit is not None else None, 'cMun')) or _digits(_desc(inf, 'cLocEmi'))
    out = {'incid_cod': _digits(_desc(inf, 'cLocIncid')), 'incid_nome': _desc(inf, 'xLocIncid'),
           'prest_cod': cod_prest, 'prest_nome': _desc(inf, 'xLocEmi'), 'fora': None}
    if out['incid_cod'] and out['prest_cod']:
        out['fora'] = 'NÃO' if out['incid_cod'] == out['prest_cod'] else 'SIM'
    return out


def parse_nfse_event(xml_bytes):
    """Dados mínimos de um evento de NFS-e: chave da nota, tipo (101101 = cancelamento) e se cancela."""
    out = {'key': '', 'type': '', 'seq': '1', 'cancels': False}
    data = bytes(xml_bytes)
    m = re.search(rb'<(?:[A-Za-z_][\w.-]*:)?chNFSe\s*>\s*(\d{50})\s*<', data)
    if m:
        out['key'] = m.group(1).decode('ascii')
    m = re.search(rb'<(?:[A-Za-z_][\w.-]*:)?tpEvento\s*>\s*(\d+)\s*<', data) or re.search(rb'<(?:[A-Za-z_][\w.-]*:)?e(\d{6})\b', data)
    if m:
        out['type'] = m.group(1).decode('ascii')
    m = re.search(rb'<(?:[A-Za-z_][\w.-]*:)?nPedRegEvento\s*>\s*(\d+)\s*<', data)
    if m:
        out['seq'] = m.group(1).decode('ascii')
    out['cancels'] = bool(out['key'] and out['type'] in NFSE_CANCEL_EVENT_TYPES)
    return out


# ---------------------------------------------------------------- ADN (JSON)
def decode_arquivo_xml(value):
    """ArquivoXml do ADN: base64 de um arquivo gzip. Aceita também XML puro em base64."""
    try:
        raw = base64.b64decode(value, validate=False)
    except Exception as exc:
        raise NfseError(f'Um documento recebido do Emissor Nacional veio em formato inesperado.')
    try:
        return gzip.decompress(raw)
    except OSError:
        if raw.lstrip()[:1] == b'<':
            return raw
        raise NfseError('Não foi possível abrir um documento recebido do Emissor Nacional.')


def _ci(d, *names):
    """Lê uma chave de um dict ignorando maiúsculas/minúsculas."""
    low = {str(k).lower(): v for k, v in (d or {}).items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def parse_adn_response(status_code, body_text):
    """Interpreta a resposta do ADN. Devolve dict(items, status, errors, max_nsu, empty)."""
    out = {'items': [], 'status': '', 'errors': [], 'max_nsu': 0, 'empty': False, 'http': int(status_code)}
    text = (body_text or '').strip()
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    out['status'] = str(_ci(data, 'StatusProcessamento') or '')
    for err in (_ci(data, 'Erros', 'Erro') or []):
        if isinstance(err, dict):
            out['errors'].append(str(_ci(err, 'Descricao', 'Mensagem', 'Codigo') or err)[:200])
        else:
            out['errors'].append(str(err)[:200])
    code = int(status_code)
    if code in (401, 403):
        raise NfseError('O Emissor Nacional recusou o certificado digital (acesso negado). Confira se o certificado é válido e pertence à empresa consultada.')
    if code == 429:
        raise NfseError('O Emissor Nacional pediu para aguardar antes de uma nova consulta (muitas consultas seguidas). Tente novamente em alguns minutos.')
    if code >= 500:
        raise NfseError(f'O Emissor Nacional está indisponível no momento (código {code}). Tente novamente mais tarde.')
    lote = _ci(data, 'LoteDFe') or []
    for item in lote if isinstance(lote, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            nsu = int(_ci(item, 'NSU') or 0)
        except (TypeError, ValueError):
            nsu = 0
        tipo = str(_ci(item, 'TipoDocumento') or '').upper()
        arquivo = _ci(item, 'ArquivoXml')
        xml = decode_arquivo_xml(arquivo) if arquivo else b''
        out['items'].append({'nsu': nsu, 'chave': _digits(_ci(item, 'ChaveAcesso')), 'tipo_documento': tipo,
                             'tipo_evento': str(_ci(item, 'TipoEvento') or ''), 'xml': xml,
                             'gerado_em': str(_ci(item, 'DataHoraGeracao') or '')})
        out['max_nsu'] = max(out['max_nsu'], nsu)
    status_up = out['status'].upper()
    out['empty'] = not out['items'] and (code == 404 or 'NENHUM' in status_up or code == 200)
    if code >= 400 and code != 404 and not out['items']:
        detail = '; '.join(out['errors']) or text[:160]
        if re.search(r'cnpj base', detail, re.I) or re.search(r'cnpj base', text, re.I):          # V183: certificado de outra raiz de CNPJ
            raise NfseError('Este certificado não pertence a esta empresa (o CNPJ base é diferente). Escolha o certificado digital da própria empresa, ou um certificado com procuração para ela.')
        raise NfseError(f'O Emissor Nacional recusou a consulta (código {code}). {detail}'.strip())
    return out


def classify_item(item):
    """'nfse' | 'evento' | 'outro' para um item do lote do ADN."""
    tipo = item.get('tipo_documento') or ''
    xml = item.get('xml') or b''
    if 'EVENTO' in tipo or (xml and is_nfse_event_xml(xml)):
        return 'evento'
    if 'NFSE' in tipo.replace('-', '').replace('_', '') or (xml and is_nfse_xml(xml)):
        return 'nfse'
    return 'outro'


# ---------------------------------------------------------------- transporte
_PS_GET = r'''param([string]$Thumbprint,[string]$Url)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$cert=$null
foreach($path in @("Cert:\CurrentUser\My\$Thumbprint","Cert:\LocalMachine\My\$Thumbprint")) { try { $c=Get-Item -Path $path -ErrorAction Stop; if($c.HasPrivateKey){$cert=$c;break} } catch {} }
if(-not $cert){throw 'Certificado com chave privada não localizado no repositório do Windows.'}
$request=[System.Net.HttpWebRequest]::Create($Url); $request.Method='GET'; $request.Accept='application/json'
$request.UserAgent='ExatoCentralFiscal/1.0'; $request.ClientCertificates.Add($cert)|Out-Null; $request.Timeout=60000
try { $response=[Net.HttpWebResponse]$request.GetResponse(); $code=[int]$response.StatusCode; $reader=New-Object IO.StreamReader($response.GetResponseStream(),[Text.Encoding]::UTF8); $content=$reader.ReadToEnd(); $reader.Close(); $response.Close() }
catch [Net.WebException] { $resp=$_.Exception.Response; if($resp){ $code=[int]$resp.StatusCode; $reader=New-Object IO.StreamReader($resp.GetResponseStream(),[Text.Encoding]::UTF8); $content=$reader.ReadToEnd(); $reader.Close(); $resp.Close() } else { throw } }
Write-Output ('STATUS:'+$code); Write-Output $content'''


def adn_transport_windows(url, thumbprint, timeout=75):
    """GET com o certificado do Windows (TLS mútuo). Devolve (status_http, corpo_texto). Só funciona no Windows."""
    thumb = re.sub(r'\s+', '', thumbprint or '').upper()
    if not thumb:
        raise NfseError('Certificado digital não informado.')
    script = base64.b64encode(_PS_GET.encode('utf-8')).decode('ascii')
    command = ("$s=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + script + "'));$sb=[ScriptBlock]::Create($s);& $sb "
               + f"-Thumbprint '{thumb}' -Url '{url}'")
    try:
        proc = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', command],
                              capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace')
    except FileNotFoundError:
        raise NfseError('A busca de NFS-e com certificado só funciona no Windows (PowerShell não encontrado).')
    except subprocess.TimeoutExpired:
        raise NfseError('A comunicação com o Emissor Nacional demorou demais. Tente novamente.')
    out = (proc.stdout or '').strip()
    m = re.match(r'STATUS:(\d{3})\s*\n?(.*)', out, re.S)
    if not m:
        err = (proc.stderr or out or '').strip()
        raise NfseError('Não foi possível consultar o Emissor Nacional: ' + (err[:300] or 'sem resposta.'))
    return int(m.group(1)), m.group(2)


def adn_fetch_batch(thumbprint, ult_nsu, homologacao=False, cnpj_consulta='', transport=adn_transport_windows):
    """Uma consulta ao ADN a partir do último NSU conhecido."""
    base = ADN_HOMOLOGACAO if homologacao else ADN_PRODUCAO
    url = f'{base}/DFe/{int(ult_nsu)}'
    if cnpj_consulta:
        url += f'?cnpjConsulta={_digits(cnpj_consulta)}'
    status, body = transport(url, thumbprint)
    return parse_adn_response(status, body)


def fetch_all_new(thumbprint, ult_nsu, homologacao=False, cnpj_consulta='', transport=adn_transport_windows,
                  max_batches=400, progress=None, cancelled=None, sleep=time.sleep):
    """Busca em lotes até acabar. Devolve (items, ultimo_nsu, resumo). Não grava nada."""
    items, last = [], int(ult_nsu)
    batches = 0
    while batches < max_batches:
        if cancelled and cancelled():
            return items, last, {'batches': batches, 'cancelled': True}
        res = adn_fetch_batch(thumbprint, last, homologacao, cnpj_consulta, transport)
        batches += 1
        if not res['items']:
            break
        items.extend(res['items'])
        new_last = max(res['max_nsu'], last)
        if progress:
            progress(len(items), batches)
        if new_last <= last:
            break
        last = new_last
        sleep(ADN_PAUSE_SECONDS)
    return items, last, {'batches': batches, 'cancelled': False}


# ---------------------------------------------------------------- importação de arquivos (XML ou ZIP)
def read_nfse_files(paths, consulta_cnpj):
    """Lê XMLs de NFS-e (soltos ou dentro de ZIP) baixados do Emissor Nacional.

    Devolve dict(items, outros_cnpj, invalidos, lidos). Só entram as notas em que o CNPJ da empresa é
    prestador, tomador ou intermediário; eventos entram se forem de uma nota dessa empresa ou ainda desconhecida.
    """
    import zipfile
    from pathlib import Path
    cnpjq = _digits(consulta_cnpj)
    out = {'items': [], 'outros_cnpj': 0, 'invalidos': [], 'lidos': 0}
    seen = set()

    def handle(name, data):
        out['lidos'] += 1
        try:
            if is_nfse_event_xml(data):
                ev = parse_nfse_event(data)
                if not ev['key']:
                    raise NfseError('evento sem chave de NFS-e')
                if cnpjq and ev['key'][8:22] != cnpjq and cnpjq not in ev['key']:
                    pass  # a chave do evento não indica as partes; o evento só tem efeito sobre notas já guardadas desta empresa
                key = ('E', ev['key'], ev['type'], ev['seq'])
                if key not in seen:
                    seen.add(key)
                    out['items'].append({'nsu': 0, 'chave': ev['key'], 'tipo_documento': 'EVENTO', 'tipo_evento': ev['type'], 'xml': data})
                return
            meta = parse_nfse(data, cnpjq)
            parties = {meta['prestador']['doc'], meta['tomador']['doc'], meta['intermediario']['doc']}
            if cnpjq and cnpjq not in parties:
                out['outros_cnpj'] += 1
                return
            key = ('N', meta['chave'])
            if key not in seen:
                seen.add(key)
                out['items'].append({'nsu': 0, 'chave': meta['chave'], 'tipo_documento': 'NFSE', 'tipo_evento': '', 'xml': data})
        except NfseError as exc:
            out['invalidos'].append(f'{name}: {exc}')

    for raw in paths or []:
        path = Path(raw)
        try:
            if path.suffix.lower() == '.zip':
                with zipfile.ZipFile(path) as zf:
                    for info in zf.infolist():
                        if info.filename.lower().endswith('.xml') and not info.is_dir():
                            handle(f'{path.name}/{info.filename}', zf.read(info))
            elif path.suffix.lower() == '.xml':
                handle(path.name, path.read_bytes())
        except (OSError, zipfile.BadZipFile) as exc:
            out['invalidos'].append(f'{path.name}: {exc}')
    return out
