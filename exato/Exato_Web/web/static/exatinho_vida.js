/* Exatinho com vida: respira, pisca, olha para o mouse, acena ao abrir, comemora ou balança a cabeça quando a busca acaba, dorme quando ninguém usa
   e (só se a pessoa ligar) passeia pelo rodapé da tela. Só enfeita o botão que o exatinho.js já criou; não mexe na conversa. */
(function(){
  var raiz=document.getElementById('exatinho'); if(!raiz) return;
  var launcher=raiz.querySelector('.exa-launcher'),painel=raiz.querySelector('.exa-painel'),topo=raiz.querySelector('.exa-topo'); if(!launcher||!painel) return;
  var img=launcher.querySelector('img'),usuario=raiz.dataset.usuario||'',CHAVE='exatinho-passeia:'+usuario;
  var calmo=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!==undefined)e.textContent=x;return e;}
  function lerPref(){try{return localStorage.getItem(CHAVE)==='1';}catch(e){return false;}}
  function gravarPref(v){try{localStorage.setItem(CHAVE,v?'1':'0');}catch(e){}}
  function tocar(c,ms){launcher.classList.remove(c);void launcher.offsetWidth;launcher.classList.add(c);setTimeout(function(){launcher.classList.remove(c);},ms);}
  if(calmo){launcher.classList.add('calmo');}

  // ---------- olhar para o mouse (move só um pouquinho) e acordar
  var ultimoMov=Date.now(),dorme=false,zz=null,quadro=0,mx=0,my=0;
  function acordar(){ultimoMov=Date.now();if(dorme){dorme=false;launcher.classList.remove('dorme');if(zz){zz.remove();zz=null;}tocar('acena',900);}}
  document.addEventListener('mousemove',function(e){mx=e.clientX;my=e.clientY;acordar();if(calmo||quadro)return;quadro=requestAnimationFrame(function(){quadro=0;
    var r=launcher.getBoundingClientRect(),dx=mx-(r.left+r.width/2),dy=my-(r.top+r.height/2),d=Math.max(1,Math.hypot(dx,dy)),f=Math.min(1,d/260);
    img.style.setProperty('--lx',(dx/d*3*f).toFixed(1)+'px');img.style.setProperty('--ly',(dy/d*2*f).toFixed(1)+'px');});},{passive:true});
  document.addEventListener('keydown',acordar);document.addEventListener('click',acordar);

  // ---------- piscar de vez em quando
  (function piscar(){setTimeout(function(){if(!calmo&&!dorme&&!document.hidden)tocar('pisca',260);piscar();},2800+Math.random()*4200);})();

  // ---------- dormir depois de um tempo sem uso (e só com o painel fechado)
  setInterval(function(){
    if(calmo||dorme||document.hidden||!painel.hidden||launcher.classList.contains('alerta')||passeando) return;
    if(Date.now()-ultimoMov>120000){dorme=true;launcher.classList.add('dorme');zz=el('span','exa-zz');['z','z','Z'].forEach(function(t){zz.appendChild(el('i','',t));});launcher.appendChild(zz);}
  },5000);

  // ---------- acenar ao abrir o painel
  var av=painel.querySelector('.exa-avatar');
  new MutationObserver(function(){if(!painel.hidden){voltarParaCasa();if(av&&!calmo){av.classList.remove('acena');void av.offsetWidth;av.classList.add('acena');}}else if(passeando){clearTimeout(tPasseio);tPasseio=setTimeout(function(){if(passeando&&painel.hidden)irPara();},2500);}}).observe(painel,{attributes:true,attributeFilter:['hidden']});

  // ---------- reagir ao fim da busca: comemora (ou balança a cabeça se algum tipo não concluiu)
  var rodavaAntes=false,posesOriginais=null;
  function pose(url,ms){var antes=img.getAttribute('src');img.src=url;setTimeout(function(){if(img.getAttribute('src')===url)img.src=launcher.classList.contains('alerta')?'/static/exatinho/alerta.png':antes;},ms);}
  function verBusca(){
    if(document.hidden)return;
    fetch('/busca/estado',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null;}).then(function(e){
      if(!e)return;var a=e.andamento||{},rodando=!!(e.rodando||a.ativo);
      if(rodavaAntes&&!rodando){var falhas=0,novas=0;Object.keys(a.tipos||{}).forEach(function(k){var t=a.tipos[k];if(t.estado==='falha')falhas++;novas+=t.novos||0;});
        if(falhas){tocar('nega',1400);pose('/static/exatinho/alerta.png',3500);}else{tocar('pula',1500);pose('/static/exatinho/comemorando.png',3500);}}
      else if(rodando&&!rodavaAntes){acordar();if(painel.hidden)pose('/static/exatinho/analisando.png',2500);}
      rodavaAntes=rodando;
    }).catch(function(){});
  }
  setInterval(verBusca,12000);verBusca();

  // ---------- passear (opcional): anda pelo rodapé da tela; ao abrir o painel volta para o canto
  var passeando=false,tPasseio=null,btn=null;
  function larguraTela(){return document.documentElement.clientWidth;}
  function irPara(dir){
    var maxDir=Math.max(22,larguraTela()-110),alvo=Math.round(22+Math.random()*(maxDir-22)),atual=parseInt(raiz.style.right||'22',10)||22;
    if(Math.abs(alvo-atual)<60)alvo=atual>larguraTela()/2?22:maxDir;
    var olhaEsq=alvo>atual;                       // 'right' maior = mais para a esquerda
    img.style.setProperty('--dir',olhaEsq?'-1':'1');
    var dur=Math.max(2.5,Math.abs(alvo-atual)/70);raiz.style.transition='right '+dur.toFixed(1)+'s linear';launcher.classList.add('anda');raiz.style.right=alvo+'px';
    clearTimeout(tPasseio);tPasseio=setTimeout(function(){launcher.classList.remove('anda');img.style.setProperty('--dir','1');tPasseio=setTimeout(function(){if(passeando)irPara();},4000+Math.random()*7000);},dur*1000+100);
  }
  function voltarParaCasa(){if(!passeando&&!raiz.style.right)return;clearTimeout(tPasseio);launcher.classList.remove('anda');raiz.style.transition='right .5s ease';raiz.style.right='22px';img.style.setProperty('--dir','1');if(passeando)tPasseio=setTimeout(function(){if(passeando&&painel.hidden)irPara();},9000);}
  function ligarPasseio(v){
    passeando=!!v;gravarPref(passeando);if(btn){btn.classList.toggle('on',passeando);btn.title=passeando?'O Exatinho está passeando. Clique para ele ficar quietinho':'Deixar o Exatinho passear pela tela';}
    clearTimeout(tPasseio);
    if(passeando&&!calmo&&larguraTela()>700){acordar();if(painel.hidden)tPasseio=setTimeout(irPara,800);}else{launcher.classList.remove('anda');raiz.style.transition='right .5s ease';raiz.style.right='22px';img.style.setProperty('--dir','1');}
  }
  if(topo&&!calmo){
    btn=el('button');btn.type='button';btn.setAttribute('aria-label','Passear pela tela');
    btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:18px;height:18px"><polyline points="7 8 3 12 7 16"/><polyline points="17 8 21 12 17 16"/><line x1="3" y1="12" x2="21" y2="12"/></svg>';
    btn.addEventListener('click',function(){ligarPasseio(!passeando);});
    topo.insertBefore(btn,topo.querySelectorAll('button')[0]);
    ligarPasseio(lerPref());
  }
  document.addEventListener('visibilitychange',function(){if(!document.hidden&&passeando&&painel.hidden){clearTimeout(tPasseio);tPasseio=setTimeout(irPara,1500);}});
  window.addEventListener('resize',function(){if(passeando){var r=parseInt(raiz.style.right||'22',10)||22;if(r>larguraTela()-110){raiz.style.transition='none';raiz.style.right='22px';}}});
})();
