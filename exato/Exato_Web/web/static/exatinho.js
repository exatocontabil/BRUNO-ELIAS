/* Exatinho: botão flutuante e conversa. Tudo vai e volta do próprio servidor (/exatinho/*). Nenhum texto de resposta é inserido como HTML. */
(function(){
  var raiz=document.getElementById('exatinho'); if(!raiz) return;
  var nome=raiz.dataset.nome||'',csrf=raiz.dataset.csrf||'',usuario=raiz.dataset.usuario||'';
  var CHAVE='exatinho:'+usuario,estado={msgs:[],ctx:{},dia:'',aberto:false,acomp:null},ocupado=false,painel,msgs,entrada,chips,topoAv,launcher,badge,pollTimer=null,progresso=null,ultimaPergunta='';
  var HUMOR={feliz:'/static/exatinho/feliz.png',alerta:'/static/exatinho/alerta.png',analisando:'/static/exatinho/analisando.png',dica:'/static/exatinho/dica.png',comemorando:'/static/exatinho/comemorando.png',lendo:'/static/exatinho/lendo.png'};
  var NOMES={nfe:'NF-e',nfce:'NFC-e',cte:'CT-e',nfse:'NFS-e'};
  function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!==undefined&&x!==null)e.textContent=x;return e;}
  var SVG={send:'<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',x:'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',trash:'<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',arrow:'<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',search:'<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',check:'<polyline points="20 6 9 17 4 12"/>'};
  function icone(n,c){var s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 24');s.setAttribute('fill','none');s.setAttribute('stroke','currentColor');s.setAttribute('stroke-width','2');s.setAttribute('stroke-linecap','round');s.setAttribute('stroke-linejoin','round');s.setAttribute('class','ic '+(c||''));s.setAttribute('aria-hidden','true');s.innerHTML=SVG[n]||'';return s;}
  function guardar(){try{localStorage.setItem(CHAVE,JSON.stringify({msgs:estado.msgs.slice(-40),ctx:estado.ctx,dia:estado.dia,aberto:estado.aberto,acomp:estado.acomp}));}catch(e){}}
  function carregar(){try{var j=JSON.parse(localStorage.getItem(CHAVE)||'null');if(j&&j.msgs){estado.msgs=j.msgs;estado.ctx=j.ctx||{};estado.dia=j.dia||'';estado.aberto=!!j.aberto;estado.acomp=j.acomp||null;}}catch(e){}}
  function hoje(){var d=new Date();return d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate();}
  function api(url,corpo){return fetch(url,{method:corpo?'POST':'GET',credentials:'same-origin',headers:corpo?{'Content-Type':'application/json','X-CSRF':csrf}:{},body:corpo?JSON.stringify(corpo):undefined}).then(function(r){return r.json().catch(function(){return {};});});}
  function rolar(){requestAnimationFrame(function(){msgs.scrollTop=msgs.scrollHeight;});}
  function iniciais(n){var p=String(n||'?').split(/\s+/).filter(Boolean);return ((p[0]||'?')[0]+(p[1]?p[1][0]:'')).toUpperCase();}
  function humor(m){var url=HUMOR[m]||HUMOR.feliz;if(topoAv.getAttribute('data-m')!==m){topoAv.setAttribute('data-m',m);var im=topoAv.querySelector('img');im.src=url;topoAv.classList.remove('pop');void topoAv.offsetWidth;topoAv.classList.add('pop');}}

  // ---------- estrutura
  launcher=el('button','exa-launcher');launcher.type='button';launcher.setAttribute('aria-label','Abrir o Exatinho');launcher.title='Exatinho (Ctrl+J)';
  var limg=el('img');limg.src=HUMOR.feliz;limg.alt='';launcher.appendChild(limg);badge=el('span','exa-badge');badge.hidden=true;launcher.appendChild(badge);
  var dica=el('div','exa-dica','Pergunte ao Exatinho');dica.appendChild(el('kbd','','Ctrl+J'));
  painel=el('div','exa-painel');painel.hidden=true;painel.setAttribute('role','dialog');painel.setAttribute('aria-label','Conversa com o Exatinho');
  var topo=el('div','exa-topo');topoAv=el('div','exa-avatar');var ti=el('img');ti.src=HUMOR.feliz;ti.alt='';topoAv.appendChild(ti);topoAv.setAttribute('data-m','feliz');
  var tt=el('div','exa-titulo');tt.appendChild(el('b','','Exatinho'));var sm=el('small');sm.appendChild(el('i'));sm.appendChild(document.createTextNode('assistente fiscal • 100% local'));tt.appendChild(sm);
  var bLimpar=el('button');bLimpar.type='button';bLimpar.title='Limpar a conversa';bLimpar.appendChild(icone('trash'));var bFechar=el('button');bFechar.type='button';bFechar.title='Fechar (Esc)';bFechar.appendChild(icone('x'));
  topo.appendChild(topoAv);topo.appendChild(tt);topo.appendChild(bLimpar);topo.appendChild(bFechar);
  msgs=el('div','exa-msgs');msgs.setAttribute('aria-live','polite');
  var rodape=el('div','exa-rodape');chips=el('div','exa-chips');var form=el('form','exa-form');entrada=el('input');entrada.type='text';entrada.placeholder='Pergunte algo ao Exatinho...';entrada.maxLength=400;entrada.autocomplete='off';entrada.setAttribute('aria-label','Sua pergunta');
  var bEnviar=el('button');bEnviar.type='submit';bEnviar.title='Enviar';bEnviar.appendChild(icone('send'));form.appendChild(entrada);form.appendChild(bEnviar);
  var nota=el('div','exa-nota');nota.appendChild(el('span','','Respondo aqui no servidor, sem IA de fora.'));
  rodape.appendChild(chips);rodape.appendChild(form);rodape.appendChild(nota);painel.appendChild(topo);painel.appendChild(msgs);painel.appendChild(rodape);
  raiz.appendChild(painel);raiz.appendChild(launcher);
  try{if(!sessionStorage.getItem('exatinho-dica')){raiz.appendChild(dica);sessionStorage.setItem('exatinho-dica','1');dica.addEventListener('animationend',function(e){if(e.animationName==='exa-some')dica.remove();});}}catch(e){}

  // ---------- peças de resposta
  function pill(estadoTxt,texto){var c={atrasado:'a',nunca:'r',em_dia:'g',sem_notas:'n'}[estadoTxt]||'n';return el('span','pill '+c,texto);}
  function botao(a){
    var b;
    if(a.kind==='goto'){b=el('a','exa-btn',a.label);b.href=a.url;b.appendChild(icone('arrow'));}
    else{b=el('button','exa-btn'+(a.kind==='buscar'||a.kind==='buscar_pendentes'?' pri':''),a.label);b.type='button';
      b.addEventListener('click',function(){
        if(a.kind==='ask')enviar(a.text);
        else if(a.kind==='buscar')pedirConfirmacao({texto:'Buscar '+(a.nome||'esta empresa')+' agora?',acao:{kind:'buscar',cnpj:a.cnpj,nome:a.nome,tipos:a.tipos}});
        else if(a.kind==='buscar_pendentes')pedirConfirmacao({texto:'Buscar só o que falta (empresas atrasadas ou nunca buscadas) agora?',acao:{kind:'buscar_pendentes'}});
        else if(a.kind==='buscar_todas')pedirConfirmacao({texto:'Buscar as notas de todas as empresas agora?',acao:{kind:'buscar_todas'}});
      });}
    return b;
  }
  function cartao(c){
    var box=el('div','exa-cartao'),cab=el('div','cab'),av=el('span','av',iniciais(c.nome));av.style.setProperty('--h',String((parseInt(String(c.cnpj).slice(-5),10)||0)%360));
    var nm=el('div');nm.appendChild(el('b','',c.nome));nm.appendChild(el('small','',c.cnpj_fmt));cab.appendChild(av);cab.appendChild(nm);box.appendChild(cab);
    (c.itens||[]).forEach(function(i){var d=el('div','exa-item'),l1=el('div','l1');l1.appendChild(el('b','',i.tipo));l1.appendChild(pill(i.estado,i.texto));d.appendChild(l1);
      if(i.causa)d.appendChild(el('div','cz '+(i.gravidade==='espera'?'g-espera':(i.gravidade==='aviso'?'g-aviso':'')),i.causa));if(i.acao)d.appendChild(el('div','ac',i.acao));box.appendChild(d);});
    if((c.botoes||[]).length){var bs=el('div','exa-botoes');c.botoes.forEach(function(b){bs.appendChild(botao(b));});box.appendChild(bs);}
    return box;
  }
  function linhaBot(humorNome){var l=el('div','exa-linha'),m=el('div','exa-mini'),im=el('img');im.src=HUMOR[humorNome]||HUMOR.feliz;im.alt='';m.appendChild(im);l.appendChild(m);var b=el('div','exa-balao');l.appendChild(b);return {linha:l,balao:b};}
  function renderBot(d,animar){
    var x=linhaBot(d.mood),b=x.balao;
    if(d.passos&&d.passos.length&&!(d.cards&&d.cards.length)){b.appendChild(el('b','t',d.text||''));}else if(d.text){b.appendChild(el('p','',d.text));}
    if(d.lines&&d.lines.length){var ul=el('ul','exa-lista');d.lines.forEach(function(t){ul.appendChild(el('li',String(t).charAt(0)==='⚠'?'alta':'',t));});b.appendChild(ul);}
    if(d.passos&&d.passos.length){var ol=el('ol','exa-passos');d.passos.forEach(function(t){ol.appendChild(el('li','',t));});b.appendChild(ol);}
    (d.cards||[]).forEach(function(c){b.appendChild(cartao(c));});
    if(d.actions&&d.actions.length){var ac=el('div','exa-acoes');d.actions.forEach(function(a){ac.appendChild(botao(a));});b.appendChild(ac);}
    if(d.confirm)b.appendChild(confirmar(d.confirm));
    if(d.sugestoes&&d.sugestoes.length){var sg=el('div','exa-sug');d.sugestoes.forEach(function(t){var bt=el('button','exa-btn',t);bt.type='button';bt.addEventListener('click',function(){enviar(t);});sg.appendChild(bt);});b.appendChild(sg);}
    if((d.ajudou||d.desconhecida)&&d.id){var aj=el('div','exa-ajuda');aj.appendChild(el('span','',d.desconhecida?'Isso ficou anotado para me ensinarem.':'Ajudou?'));
      if(!d.desconhecida){['👍','👎'].forEach(function(e,i){var bt=el('button','',e);bt.type='button';bt.title=i?'Não ajudou':'Ajudou';bt.addEventListener('click',function(){api('/exatinho/feedback',{id:d.id,util:i===0});aj.textContent='';aj.appendChild(el('span','ok',i===0?'Que bom! 😊':'Obrigado, vou aprender com isso.'));});aj.appendChild(bt);});}
      b.appendChild(aj);}
    if(!animar)x.linha.style.animation='none';
    return x.linha;
  }
  function renderEu(t){var l=el('div','exa-linha eu'),b=el('div','exa-balao',t);l.appendChild(b);return l;}
  function confirmar(cf){
    var box=el('div','exa-conf');box.appendChild(el('p','',cf.texto||'Posso fazer isso agora?'));var bs=el('div','exa-acoes');bs.style.marginTop='0';
    var sim=el('button','exa-btn pri','Sim, pode buscar');sim.type='button';var nao=el('button','exa-btn','Agora não');nao.type='button';bs.appendChild(sim);bs.appendChild(nao);box.appendChild(bs);
    sim.addEventListener('click',function(){box.classList.add('feito');executar(cf.acao);});nao.addEventListener('click',function(){box.classList.add('feito');responderLocal({text:'Tudo bem, não fiz nada.',mood:'feliz'});});
    return box;
  }
  function adicionar(d){msgs.appendChild(renderBot(d,true));rolar();}
  function responderLocal(d){estado.msgs.push({r:'bot',d:d});guardar();adicionar(d);humor(d.mood||'feliz');}
  function typing(){var x=linhaBot('analisando'),dg=el('span','exa-digitando');dg.appendChild(el('i'));dg.appendChild(el('i'));dg.appendChild(el('i'));x.balao.appendChild(dg);msgs.appendChild(x.linha);humor('analisando');rolar();return x.linha;}

  // ---------- conversa
  function enviar(texto,silencioso){
    texto=String(texto||'').trim();if(!texto||ocupado)return;abrir();ultimaPergunta=texto;ocupado=true;
    if(!silencioso){estado.msgs.push({r:'eu',t:texto});msgs.appendChild(renderEu(texto));rolar();}
    var dig=typing(),t0=Date.now();
    api('/exatinho/perguntar',{q:texto,ctx:estado.ctx}).then(function(d){
      var espera=Math.max(0,520-(Date.now()-t0));
      setTimeout(function(){
        dig.remove();ocupado=false;
        if(!d||d.erro||!d.text){d={text:(d&&d.erro)||'Não consegui falar com o servidor agora. Tente de novo em instantes.',mood:'alerta'};}
        if(d.ctx)Object.keys(d.ctx).forEach(function(k){estado.ctx[k]=d.ctx[k];});
        estado.msgs.push({r:'bot',d:d});guardar();adicionar(d);humor(d.mood||'feliz');atualizarChips(d.sugestoes);
        if(d.abrir)setTimeout(function(){location.href=d.abrir;},700);
      },espera);
    }).catch(function(){dig.remove();ocupado=false;responderLocal({text:'Não consegui falar com o servidor agora. Tente de novo em instantes.',mood:'alerta'});});
  }
  function atualizarChips(extra){
    chips.textContent='';var lista=['resumo do dia','quem não buscou notas?','como envio o certificado?','como baixo o ZIP com os eventos?','quais certificados vencem?'];
    lista.forEach(function(t){var b=el('button','exa-btn',t);b.type='button';b.addEventListener('click',function(){enviar(t);});chips.appendChild(b);});
  }

  // ---------- ações (sempre depois do "sim")
  function pedirConfirmacao(cf){var d={text:'',mood:'analisando',confirm:cf};estado.msgs.push({r:'bot',d:d});guardar();adicionar(d);humor('analisando');}
  function executar(acao){
    api('/exatinho/acao',{acao:acao}).then(function(r){
      if(!r||!r.ok){responderLocal({text:(r&&r.msg)||'Não consegui iniciar a busca.',mood:'alerta'});return;}
      mostrarProgresso(acao);
    }).catch(function(){responderLocal({text:'Não consegui falar com o servidor.',mood:'alerta'});});
  }
  function mostrarProgresso(acao,retomada){
    pararPoll();estado.acomp={acao:acao,t:Date.now()};guardar();var x=linhaBot('analisando'),b=x.balao,card=el('div','exa-prog'),tt=el('div','tt');var t1=el('span','','Preparando a busca...');tt.appendChild(t1);card.appendChild(tt);var barra=el('span','barra');barra.appendChild(el('i'));card.appendChild(barra);var lista=el('div');card.appendChild(lista);
    b.appendChild(el('p','',retomada?'Continuo acompanhando a busca para você...':'Pode deixar, estou buscando! Você pode seguir usando o site: eu aviso quando terminar.'));b.appendChild(card);msgs.appendChild(x.linha);humor('analisando');rolar();
    var viu=false,n=0;
    function ciclo(){
      api('/busca/estado').then(function(e){
        n++;var a=(e&&e.andamento)||{},tipos=a.tipos||{},ids=Object.keys(tipos),ativo=!!(e&&(e.rodando||a.ativo));
        if(ativo)viu=true;
        t1.textContent=ativo?('Buscando: '+(a.empresa||'...')+((e.total>1)?' ('+e.indice+' de '+e.total+')':'')):'Terminando...';
        lista.textContent='';ids.forEach(function(k){var s=tipos[k],r=el('div','tp');r.appendChild(el('span','',NOMES[k]||k));var txt={na_fila:'na fila',consultando:'consultando...',ok:'concluído',sem_novas:'sem notas novas',espera:'aguardando a SEFAZ',falha:'não concluído',cancelada:'cancelada'}[s.estado]||s.estado;
          r.appendChild(el('span','pill '+({consultando:'b',ok:'g',sem_novas:'g',espera:'b',falha:'r',cancelada:'a'}[s.estado]||'n'),txt+(s.novos?' • '+s.novos+' nova(s)':'')));lista.appendChild(r);});
        rolar();
        if((!ativo&&(viu||retomada))||n>1200){pararPoll();card.classList.add('feito');terminar(a);}
        else if(!ativo&&!viu&&n>6){pararPoll();terminar(a);}
        else pollTimer=setTimeout(ciclo,1500);
      }).catch(function(){pollTimer=setTimeout(ciclo,3000);});
    }
    ciclo();
  }
  function pararPoll(){if(pollTimer){clearTimeout(pollTimer);pollTimer=null;}}
  function terminar(a){
    estado.acomp=null;guardar();
    var tipos=a.tipos||{},ids=Object.keys(tipos),falhas=0,novas=0,esperas=0;ids.forEach(function(k){var s=tipos[k];novas+=s.novos||0;if(s.estado==='falha')falhas++;if(s.estado==='espera')esperas++;});
    var acoes=[];if(a.cnpj){acoes.push({label:'Ver o resultado',kind:'goto',url:'/buscar?empresa='+a.cnpj});if(a.desde)acoes.push({label:'Ver as notas novas',kind:'goto',url:'/documentos?empresa='+a.cnpj+'&desde='+encodeURIComponent(a.desde)});}
    var d;
    if(!ids.length)d={text:'A busca terminou.',mood:'feliz',actions:[{label:'Abrir Situação da busca',kind:'goto',url:'/situacao'}]};
    else if(falhas)d={text:'Terminei, mas '+falhas+' tipo(s) não concluíram. Veja a causa e o que fazer na tela de resultado.',mood:'alerta',actions:acoes};
    else d={text:'Pronto! '+novas+' nota(s) nova(s) guardada(s)'+(esperas?'. Alguns tipos aguardam a próxima janela da SEFAZ: eu continuo sozinho na busca automática.':'.'),mood:'comemorando',actions:acoes};
    responderLocal(d);
  }

  // ---------- abrir, fechar, teclado
  function abrir(){
    if(!painel.hidden)return;painel.hidden=false;estado.aberto=true;guardar();raiz.classList.add('aberto');launcher.setAttribute('aria-expanded','true');
    if(!estado.msgs.length){mostrarBoasVindas();}else{reconstruir();}
    atualizarChips();setTimeout(function(){entrada.focus();},60);
    if(estado.dia!==hoje()){estado.dia=hoje();guardar();setTimeout(function(){enviar('resumo do dia',true);},estado.msgs.length?300:900);}
  }
  function fechar(){painel.hidden=true;estado.aberto=false;guardar();raiz.classList.remove('aberto');launcher.setAttribute('aria-expanded','false');}
  function reconstruir(){msgs.textContent='';estado.msgs.forEach(function(m){msgs.appendChild(m.r==='eu'?renderEu(m.t):renderBot(m.d,false));});var u=estado.msgs.slice().reverse().find(function(m){return m.r==='bot';});humor(u&&u.d.mood?u.d.mood:'feliz');rolar();}
  function mostrarBoasVindas(){
    msgs.textContent='';var d={text:'Oi'+(nome?', '+nome.split(' ')[0]:'')+'! Eu sou o Exatinho. 👋',lines:['Posso dizer quais empresas ainda não buscaram notas e por quê, o que está pendente hoje, quantas notas uma empresa tem e tirar dúvidas de uso do sistema.','Para buscar, sempre peço a sua confirmação.'],mood:'feliz'};
    estado.msgs.push({r:'bot',d:d});guardar();msgs.appendChild(renderBot(d,true));humor('feliz');
  }
  launcher.addEventListener('click',function(){painel.hidden?abrir():fechar();});
  bFechar.addEventListener('click',fechar);
  bLimpar.addEventListener('click',function(){if(!confirm('Limpar a conversa com o Exatinho?'))return;estado.msgs=[];estado.ctx={};guardar();mostrarBoasVindas();});
  form.addEventListener('submit',function(e){e.preventDefault();var t=entrada.value;entrada.value='';enviar(t);});
  entrada.addEventListener('keydown',function(e){if(e.key==='ArrowUp'&&!entrada.value&&ultimaPergunta){entrada.value=ultimaPergunta;e.preventDefault();}});
  document.addEventListener('keydown',function(e){
    if((e.ctrlKey||e.metaKey)&&String(e.key).toLowerCase()==='j'){e.preventDefault();painel.hidden?abrir():fechar();}
    else if(e.key==='Escape'&&!painel.hidden){fechar();}
  });

  // ---------- aviso no botão (resumo do dia)
  carregar();
  if(estado.aberto)abrir();
  if(estado.acomp&&estado.acomp.acao&&(Date.now()-(estado.acomp.t||0))<7200000){abrir();mostrarProgresso(estado.acomp.acao,true);}else{estado.acomp=null;}
  api('/exatinho/resumo').then(function(r){
    if(!r||!r.text)return;var n=r.badge||0;badge.hidden=!n;badge.textContent=String(n);
    if(r.mood==='alerta'){launcher.classList.add('alerta');limg.src=HUMOR.alerta;}else if(r.mood==='comemorando'){limg.src=HUMOR.comemorando;}
  }).catch(function(){});
})();
