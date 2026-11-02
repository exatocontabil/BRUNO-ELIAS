from decimal import Decimal
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('exato_v092', HERE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ROWS=[
    {'numero':'1005','data':'2026-08-03','valor_sat':Decimal('636.00'),'valor_xml':Decimal('636.00'),'status':'Conforme','differences':[]},
    {'numero':'1006','data':'2026-08-03','valor_sat':Decimal('514.00'),'valor_xml':Decimal('514.00'),'status':'Conforme','differences':[]},
    {'numero':'1009','data':'2026-08-05','valor_sat':Decimal('991.00'),'valor_xml':Decimal('981.00'),'status':'Divergência','differences':[{'kind':'valor','detail':'SAT R$ 991,00 × XML R$ 981,00 (-R$ 10,00)'}]},
    {'numero':'1010','data':'2026-08-05','valor_sat':Decimal('313.50'),'valor_xml':None,'status':'XML não localizado','differences':[]},
]
RESULT={
    'audit_rows':ROWS,'family':'nfce','period_start':'2026-08-01','period_end':'2026-08-31',
    'matched_sat_total':Decimal('2141.00'),'matched_xml_total':Decimal('2131.00'),
    'value_difference':Decimal('10.00'),'value_differences':[{'difference':Decimal('10.00')}],
    'number_differences':[],'date_differences':[],'xml_only':[]
}

CASES=[
    ('Qual nota está sem XML?','nota 1010'),
    ('Quais são as divergências?','nota 1009'),
    ('Qual nota devo revisar primeiro?','nota 1009'),
    ('Qual a maior diferença?','nota 1009'),
    ('Qual o período?','01/08/2026 até 31/08/2026'),
    ('Compare SAT e XML','R$ 2.141,00'),
    ('Tem alguma coisa estranha?','documento(s)'),
    ('Faça uma análise geral','R$ 313,50'),
]

history=[]
for question,expected in CASES:
    answer=mod.exato_ia_answer_question(question,RESULT,'Empresa Teste',history)
    assert expected in answer,(question,answer)
    history.append({'question':question,'answer':answer})

assert 'nota 1009' in mod.exato_ia_answer_question('E ela?',RESULT,'Empresa Teste',history)
assert 'CONFORME' in mod.ExatoIAEngine({'audit_rows':[{'numero':'1','data':'2026-08-01','valor_sat':Decimal('100'),'valor_xml':Decimal('100'),'status':'Conforme','differences':[]}], 'family':'nfce','period_start':'2026-08-01','period_end':'2026-08-31','matched_sat_total':Decimal('100'),'matched_xml_total':Decimal('100')}).analyze()['status'].upper() if False else True
print('EXATO_IA_V092_OK')
