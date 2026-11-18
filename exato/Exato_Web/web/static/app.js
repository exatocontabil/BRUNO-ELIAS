/* Exato Web: botão de tema, aviso de busca no topo, filtros de tabela e menu do celular. Nada daqui é necessário para a página funcionar. */
(function(){
  var d=document;
  function atual(){var t=d.documentElement.getAttribute('data-theme');if(t)return t;return (window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'escuro':'claro';}
  d.querySelectorAll('[data-tema]').forEach(function(b){b.addEventListener('click',function(){var n=atual()==='escuro'?'claro':'escuro';d.documentElement.setAttribute('data-theme',n);try{localStorage.setItem('exato-tema',n);}catch(e){}});});
  // seletores que mudam de página ao escolher (sem script dentro do HTML)
  d.querySelectorAll('select[data-nav]').forEach(function(s){s.addEventListener('change',function(){location=s.getAttribute('data-nav')+encodeURIComponent(s.value);});});
  // busca e filtros em tabelas: <input data-filtra="#tabela"> e <button data-filtro="atraso">
  var tab=d.querySelector('[data-tabela]');
  if(tab){
    var linhas=[].slice.call(tab.querySelectorAll('tbody tr[data-texto]')),vazio=tab.querySelector('tr.sem-resultado'),caixa=d.querySelector('input[data-filtra]'),filtro='todas';
    function aplicar(){var q=(caixa&&caixa.value||'').toLowerCase().trim(),n=0;
      linhas.forEach(function(l){var ok=(!q||l.getAttribute('data-texto').indexOf(q)>-1)&&(filtro==='todas'||(l.getAttribute('data-estado')||'').split(' ').indexOf(filtro)>-1);l.hidden=!ok;if(ok)n++;});
      if(vazio)vazio.hidden=n>0;}
    if(caixa)caixa.addEventListener('input',aplicar);
    d.querySelectorAll('button[data-filtro]').forEach(function(b){b.addEventListener('click',function(){filtro=b.getAttribute('data-filtro');d.querySelectorAll('button[data-filtro]').forEach(function(x){x.classList.toggle('on',x===b);});aplicar();});});
    linhas.forEach(function(l){var u=l.getAttribute('data-ir');if(u)l.addEventListener('click',function(e){if(e.target.closest('a,button,form,input'))return;location=u;});});
  }
  // aviso "buscando" no topo (só quando logado)
  var chip=d.getElementById('chip-busca');
  if(chip){
    function ver(){fetch('/busca/estado',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(e){
      if(!e)return;var t=chip.querySelector('.txt');
      if(e.rodando){chip.className='chip busy';t.textContent='Buscando'+(e.empresa?': '+e.empresa:'')+(e.total?' ('+e.indice+'/'+e.total+')':'');}
      else if(e.auto){chip.className='chip on';t.textContent='Busca automática ligada';}
      else{chip.className='chip';t.textContent='Busca automática desligada';}
    }).catch(function(){});}
    ver();setInterval(ver,6000);
  }
})();
