from pathlib import Path
import os
import tempfile
import importlib.util

base = Path(__file__).resolve().parents[1]


def load_app():
    td = tempfile.TemporaryDirectory()
    os.environ["EXATO_DATA_DIR"] = td.name
    spec = importlib.util.spec_from_file_location("exato_v097", base / "exato_central_fiscal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, td


def mkxml(model="55", tp="1", number="1005", cnpj="23187104000152", dest="11111111000111"):
    return f'''<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe4226082318710400015255{number:0>8}"><ide><cUF>42</cUF><cNF>12345678</cNF><natOp>VENDA DE MERCADORIA</natOp><mod>{model}</mod><serie>1</serie><nNF>{number}</nNF><dhEmi>2026-08-03T17:53:26-03:00</dhEmi><dhSaiEnt>2026-08-03T18:00:00-03:00</dhSaiEnt><tpNF>{tp}</tpNF></ide><emit><CNPJ>{cnpj}</CNPJ><xNome>EMPRESA TESTE</xNome><enderEmit><xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro><xMun>ARARANGUA</xMun><UF>SC</UF><CEP>88900000</CEP></enderEmit><IE>123456789</IE><fone>4833333333</fone></emit><dest><CNPJ>{dest}</CNPJ><xNome>CLIENTE TESTE</xNome><enderDest><xLgr>RUA B</xLgr><nro>20</nro><xBairro>CENTRO</xBairro><xMun>TUBARAO</xMun><UF>SC</UF><CEP>88700000</CEP></enderDest><IE>987654321</IE></dest><det nItem="1"><prod><cProd>1</cProd><xProd>PRODUTO TESTE</xProd><NCM>22021000</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>10.00</vUnCom><vProd>10.00</vProd></prod><imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><vBC>10.00</vBC><vICMS>1.20</vICMS><pICMS>12.00</pICMS></ICMS00></ICMS><IPI><IPITrib><vIPI>0.00</vIPI><pIPI>0.00</pIPI></IPITrib></IPI></imposto></det><total><ICMSTot><vBC>10.00</vBC><vICMS>1.20</vICMS><vBCST>0.00</vBCST><vST>0.00</vST><vII>0.00</vII><vIPI>0.00</vIPI><vProd>10.00</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg><vDesc>0.00</vDesc><vOutro>0.00</vOutro><vNF>10.00</vNF></ICMSTot></total><transp><modFrete>9</modFrete></transp><infAdic><infCpl>TESTE</infCpl></infAdic></infNFe></NFe></nfeProc>'''.encode()


mod, td = load_app()
try:
    with tempfile.TemporaryDirectory() as out:
        nfe = Path(out) / "nfe.pdf"
        nfce = Path(out) / "nfce.pdf"
        mod.generate_fiscal_representation_pdf([{"family": "nfe", "xml": mkxml("55")}], str(nfe), family="nfe")
        mod.generate_fiscal_representation_pdf([{"family": "nfce", "xml": mkxml("65")}], str(nfce), family="nfce")
        assert nfe.exists() and nfe.stat().st_size > 1000
        assert nfce.exists() and nfce.stat().st_size > 1000

        cnpj = "23187104000152"
        docs = [
            {"family":"nfe","xml":mkxml("55","1","1005"),"cnpj":cnpj,"data":"2026-08-03","issued_at":"2026-08-03","direction":"Saída","access_key":"42260823187104000152550010000010051116119685","number":"1005","series":"1"},
            {"family":"nfce","xml":mkxml("65","0","1006"),"cnpj":cnpj,"data":"2026-08-04","issued_at":"2026-08-04","direction":"Entrada","access_key":"42260823187104000152650010000010061116119686","number":"1006","series":"1"},
        ]
        saved, errors = mod.save_documents_organized(docs, out, cnpj, {"company_names": {cnpj: "EMPRESA TESTE"}}, generate_companion_pdf=True, period_start="2026-08-01", period_end="2026-08-31")
        assert not errors, errors
        month = Path(out) / "EMPRESA TESTE" / "2026" / "08 - Agosto"
        assert (month / "Entrada" / "NFC-e").is_dir()
        assert (month / "Saída" / "NF-e").is_dir()
        assert list((month / "Entrada" / "NFC-e").glob('*.pdf'))
        assert list((month / "Saída" / "NF-e").glob('*.pdf'))
        assert not (month / "PDFs Fiscais").exists()
    print("V097_FOLDER_RENDER_CURRENT_STRUCTURE_OK")
finally:
    td.cleanup()
