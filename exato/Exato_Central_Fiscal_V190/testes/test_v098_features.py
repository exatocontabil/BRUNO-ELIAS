from pathlib import Path
import os, tempfile, importlib.util
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]


def load_app():
    td = tempfile.TemporaryDirectory()
    os.environ["EXATO_DATA_DIR"] = td.name
    spec = importlib.util.spec_from_file_location("exato_v098", BASE / "exato_central_fiscal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, td


def mkxml(model="55", tp="1", number="1005", cnpj="23187104000152", dest="11111111000111",
          nat="VENDA DE MERCADORIA", value="10.00"):
    return f'''<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe4226082318710400015255{number:0>8}"><ide><cUF>42</cUF><cNF>12345678</cNF><natOp>{nat}</natOp><mod>{model}</mod><serie>1</serie><nNF>{number}</nNF><dhEmi>2026-08-03T17:53:26-03:00</dhEmi><dhSaiEnt>2026-08-03T18:00:00-03:00</dhSaiEnt><tpNF>{tp}</tpNF></ide><emit><CNPJ>{cnpj if tp=='1' else dest}</CNPJ><xNome>{'EMPRESA TESTE' if tp=='1' else 'FORNECEDOR TESTE'}</xNome><enderEmit><xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro><xMun>ARARANGUA</xMun><UF>SC</UF><CEP>88900000</CEP></enderEmit><IE>123456789</IE><fone>4833333333</fone></emit><dest><CNPJ>{dest if tp=='1' else cnpj}</CNPJ><xNome>{'CLIENTE TESTE' if tp=='1' else 'EMPRESA TESTE'}</xNome><enderDest><xLgr>RUA B</xLgr><nro>20</nro><xBairro>CENTRO</xBairro><xMun>TUBARAO</xMun><UF>SC</UF><CEP>88700000</CEP></enderDest><IE>987654321</IE></dest><det nItem="1"><prod><cProd>1</cProd><xProd>PRODUTO TESTE</xProd><NCM>22021000</NCM><CFOP>{'5102' if tp=='1' else '1102'}</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>{value}</vUnCom><vProd>{value}</vProd></prod><imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><vBC>{value}</vBC><vICMS>1.20</vICMS><pICMS>12.00</pICMS></ICMS00></ICMS></imposto></det><total><ICMSTot><vBC>{value}</vBC><vICMS>1.20</vICMS><vBCST>0.00</vBCST><vST>0.00</vST><vII>0.00</vII><vIPI>0.00</vIPI><vProd>{value}</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg><vDesc>0.00</vDesc><vOutro>0.00</vOutro><vNF>{value}</vNF></ICMSTot></total><transp><modFrete>9</modFrete></transp><infAdic><infCpl>TESTE</infCpl></infAdic></infNFe></NFe></nfeProc>'''.encode()


mod, td = load_app()
try:
    with tempfile.TemporaryDirectory() as out:
        cnpj = "23187104000152"
        docs = [
            {"family": "nfe", "xml": mkxml("55", "1", "1005", cnpj), "cnpj": cnpj,
             "data": "2026-08-03", "issued_at": "2026-08-03", "direction": "Saída",
             "number": "1005", "series": "1"},
            {"family": "nfe", "xml": mkxml("55", "0", "1006", cnpj,
             "11111111000111", "COMPRA PARA COMERCIALIZACAO", "200.00"), "cnpj": cnpj,
             "data": "2026-08-04", "issued_at": "2026-08-04", "direction": "Entrada",
             "number": "1006", "series": "1"},
            {"family": "nfce", "xml": mkxml("65", "1", "1007", cnpj,
             "11111111000111", "VENDA DE MERCADORIA", "50.00"), "cnpj": cnpj,
             "data": "2026-08-05", "issued_at": "2026-08-05", "direction": "Saída",
             "number": "1007", "series": "1"},
        ]

        # Fiscal representations still generate as before.
        nfe = Path(out) / "nfe.pdf"
        nfce = Path(out) / "nfce.pdf"
        mod.generate_fiscal_representation_pdf([docs[0]], str(nfe), family="nfe")
        mod.generate_fiscal_representation_pdf([docs[2]], str(nfce), family="nfce")
        assert nfe.exists() and nfe.stat().st_size > 1000
        assert nfce.exists() and nfce.stat().st_size > 1000

        # Approved report layout: 1 executive + Entry + Exit, never mixed on detail pages.
        report = Path(out) / "report.pdf"
        mod.generate_documents_pdf(docs, str(report), consulta_cnpj=cnpj,
                                   period_start="2026-08-01", period_end="2026-08-31")
        reader = PdfReader(str(report))
        assert len(reader.pages) == 3, len(reader.pages)
        texts = [p.extract_text() or "" for p in reader.pages]
        assert "EXATO IA" in texts[0]
        assert "DOCUMENTOS DE ENTRADA" in texts[1]
        assert "DOCUMENTOS DE SAÍDA" in texts[2]
        assert "NATUREZA DA OPERAÇÃO" in texts[1]
        assert "NATUREZA DA OPERAÇÃO" in texts[2]
        assert "TODOS" not in texts[1]
        assert "TODOS" not in texts[2]
        assert "VENDA DE MERCADORIA" in texts[2]
        assert "COMPRA PARA" in texts[1] and "COMERCIALIZACAO" in texts[1]
        assert "DOCUMENTOS DE SAÍDA" not in texts[1]
        assert "DOCUMENTOS DE ENTRADA" not in texts[2]
        assert "TOTAL DE DOCUMENTOS\n3" in texts[0]

        # Export structure: XML and its individual PDF stay together.
        saved, errors = mod.save_documents_organized(
            docs, out, cnpj, {"company_names": {cnpj: "EMPRESA TESTE"}},
            generate_companion_pdf=True,
            period_start="2026-08-01", period_end="2026-08-31")
        assert not errors, errors
        month = Path(out) / "EMPRESA TESTE" / "2026" / "08 - Agosto"
        entry_dir = month / "Entrada" / "NF-e"
        exit_nfe_dir = month / "Saída" / "NF-e"
        exit_nfce_dir = month / "Saída" / "NFC-e"
        assert entry_dir.is_dir()
        assert exit_nfe_dir.is_dir()
        assert exit_nfce_dir.is_dir()
        assert any(p.suffix.lower() == ".xml" for p in entry_dir.iterdir())
        assert any(p.suffix.lower() == ".pdf" for p in entry_dir.iterdir())
        assert any(p.suffix.lower() == ".xml" for p in exit_nfe_dir.iterdir())
        assert any(p.suffix.lower() == ".pdf" for p in exit_nfe_dir.iterdir())
        assert any(p.suffix.lower() == ".xml" for p in exit_nfce_dir.iterdir())
        assert any(p.suffix.lower() == ".pdf" for p in exit_nfce_dir.iterdir())
        assert not (month / "PDFs Fiscais").exists()
        assert not (month / "NF-e").exists()
        assert not (month / "NFC-e").exists()

        # No blank direction pages for one-sided data.
        one_side = Path(out) / "one_side.pdf"
        mod.generate_documents_pdf([docs[0], docs[2]], str(one_side), consulta_cnpj=cnpj,
                                   period_start="2026-08-01", period_end="2026-08-31")
        assert len(PdfReader(str(one_side)).pages) == 2

    print("V098_REPORT_EXPORT_OK")
finally:
    td.cleanup()
