/* Andamento ao vivo da busca manual: uma linha por tipo de nota, com o que está acontecendo e o resultado final em português. */
(function(){
  var box=document.getElementById('andamento'); if(!box) return;
  var NOMES={nfe:'NF-e',nfce:'NFC-e',cte:'CT-e',nfse:'NFS-e'};
  var EST={na_fila:['Na fila','n'],consultando:['Consultando...','b busy'],ok:['Concluído','g'],sem_novas:['Sem notas novas','g'],espera:['Aguardando a SEFAZ','b'],falha:['Não concluído','r'],cancelada:['Cancelada','a']};
  var MODOS={continuar:'só o que veio depois',recomecar:'desde o começo',data:'a partir de uma data'};
  var rodou=false;
  function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!==undefined)e.textContent=x;return e;}
  function tempo(s){s=Math.max(0,s|0);return s>=60?(Math.floor(s/60)+' min '+('0'+s%60).slice(-2)+' s'):(s+' s');}
  function dataBR(i){return i&&i.length>=10?i.slice(8,10)+'/'+i.slice(5,7)+'/'+i.slice(0,4):'';}
  function num(n){return String(n||0).replace(/\B(?=(\d{3})+(?!\d))/g,'.');}
  function render(e){
    var a=e.andamento||{},tipos=a.tipos||{},ids=Object.keys(tipos),ativo=!!(e.rodando||a.ativo);
    if(!ids.length&&!ativo){box.hidden=true;return;}
    box.hidden=false;box.textContent='';
    var cab=el('div','and-cab'),t=el('div');
    t.appendChild(el('h2','',ativo?('Buscando: '+(a.empresa||'...')):('Resultado: '+(a.empresa||''))));
    var sub=MODOS[a.modo]||'';if(a.modo==='data'&&a.de)sub='a partir de '+dataBR(a.de)+(a.ate?' até '+dataBR(a.ate):'');
    t.appendChild(el('small','mu',(sub?('Modo: '+sub+' • '):'')+(ativo?'tempo decorrido ':'durou ')+tempo(a.decorrido)));
    cab.appendChild(t);cab.appendChild(el('span','pill '+(ativo?'b busy':'n'),ativo?'Em andamento':'Terminou'));box.appendChild(cab);
    if(!ids.length)box.appendChild(el('p','mu','Preparando a busca...'));
    if(ativo&&a.etapa)box.appendChild(el('p','mu',a.etapa));
    var novas=0,falhas=0,esperas=0;
    ids.forEach(function(k){
      var x=tipos[k],est=EST[x.estado]||EST.na_fila,l=el('div','and-l and-'+x.estado);
      var esq=el('div','and-t');esq.appendChild(el('b','',NOMES[k]||k));esq.appendChild(el('span','pill '+est[1],est[0]));l.appendChild(esq);
      var nums=[];if(x.consultas)nums.push(num(x.consultas)+' consulta(s)');if(x.notas)nums.push(num(x.notas)+' nota(s) recebida(s)');if(x.novos)nums.push(num(x.novos)+' nova(s) guardada(s)');if(x.duplicados)nums.push(num(x.duplicados)+' já estava(m) guardada(s)');if(x.eventos)nums.push(num(x.eventos)+' evento(s) (cancelamento etc.)');if(x.ignorados)nums.push(num(x.ignorados)+' ignorada(s)');
      var dir=el('div','and-i');dir.appendChild(el('div','mu',nums.length?nums.join(' • '):(x.estado==='na_fila'?'Esperando a vez':(x.estado==='consultando'?'Consultando a SEFAZ...':''))));
      if(x.titulo&&x.estado!=='ok'&&x.estado!=='sem_novas'){var m=el('div','and-m g-'+(x.estado==='espera'?'espera':(x.gravidade||'erro')));m.appendChild(el('b','',x.titulo));if(x.acao)m.appendChild(el('span','',' — '+x.acao));dir.appendChild(m);}
      if(x.estado==='falha'&&x.detalhe)dir.appendChild(el('small','mu',x.detalhe));
      l.appendChild(dir);box.appendChild(l);
      novas+=x.novos||0;if(x.estado==='falha')falhas++;if(x.estado==='espera')esperas++;
    });
    if(!ativo&&ids.length){
      var cls=falhas?'erro':(esperas?'b':'ok'),msg=falhas?('Terminou com '+falhas+' tipo(s) com problema. Veja a causa e o que fazer acima.'):(esperas?('Terminou. '+novas+' nota(s) nova(s). Alguns tipos aguardam a próxima janela da SEFAZ: o Exato continua sozinho na busca automática.'):('Busca concluída: '+novas+' nota(s) nova(s) guardada(s).'));
      var r=el('div','aviso '+cls);r.appendChild(el('span','',msg));box.appendChild(r);
      var acoes=el('div','linha'),u=encodeURIComponent;acoes.style.marginTop='6px';
      var z=a.zip;
      if(z&&z.estado==='pronto'){var b1=el('a','botao','Baixar o ZIP das notas novas ('+(z.notas||0)+' nota(s), '+(z.eventos||0)+' evento(s))');b1.href='/exportar/'+z.id+'/zip';acoes.appendChild(b1);}
      else if(z&&z.estado==='gerando'){acoes.appendChild(el('span','pill b busy','Gerando o ZIP...'));}
      else if(z&&(z.estado==='sem_notas'||z.estado==='erro')){acoes.appendChild(el('span','mu',z.estado==='sem_notas'?'Nenhuma nota nova para o ZIP.':('ZIP: '+(z.erro||'não foi possível gerar.'))));}
      else if(a.cnpj&&a.desde){var b2=el('a','botao sec','Baixar as notas novas em ZIP');b2.href='/exportar?empresa='+u(a.cnpj)+'&desde='+u(a.desde);b2.style.background='var(--surface)';b2.style.color='var(--tx)';b2.style.border='1px solid var(--line)';acoes.appendChild(b2);}
      if(a.cnpj&&a.desde){var b3=el('a','botao sec','Ver as notas novas');b3.href='/documentos?empresa='+u(a.cnpj)+'&desde='+u(a.desde);b3.style.background='var(--surface)';b3.style.color='var(--tx)';b3.style.border='1px solid var(--line)';acoes.appendChild(b3);}
      if(z&&z.sem_evento)box.appendChild(el('div','aviso','No ZIP: '+z.sem_evento+' nota(s) cancelada(s) sem o XML do cancelamento. O Exato nunca inventa esse arquivo; veja o AVISOS.txt dentro do ZIP.'));
      box.appendChild(acoes);
    }
  }
  function ciclo(){
    fetch('/busca/estado',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(e){
      if(!e)return;var ativo=!!(e.rodando||(e.andamento&&e.andamento.ativo));render(e);
      if(rodou&&!ativo){location.reload();return;}
      rodou=ativo;
    }).catch(function(){}).then(function(){setTimeout(ciclo,rodou?1500:5000);});
  }
  ciclo();
})();
