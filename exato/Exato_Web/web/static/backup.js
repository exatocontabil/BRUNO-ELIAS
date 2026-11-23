/* Botão "Procurar...": navega pelas pastas do computador onde o site roda e preenche o destino da cópia. Só mostra pastas (nunca arquivos). */
(function(){
  var campo=document.getElementById('bk-destino'),painel=document.getElementById('bk-nav'); if(!campo||!painel) return;
  var lista=document.getElementById('bk-lista'),atual=document.getElementById('bk-atual'),erro=document.getElementById('bk-erro'),corrente='';
  function item(texto,destino,classe){var b=document.createElement('button');b.type='button';b.className='bk-item'+(classe?' '+classe:'');b.textContent=texto;b.addEventListener('click',function(){ir(destino);});return b;}
  function ir(caminho){
    erro.textContent='';
    fetch('/backup/pastas?caminho='+encodeURIComponent(caminho||''),{credentials:'same-origin'}).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});}).then(function(x){
      if(!x.ok){erro.textContent=x.j.erro||'Não foi possível abrir essa pasta.';return;}
      var j=x.j;corrente=j.caminho||'';atual.textContent=corrente||'Este computador (escolha um disco)';lista.textContent='';
      if(j.pai!==null&&j.pai!==undefined)lista.appendChild(item('⬆ Subir um nível',j.pai,'bk-sobe'));
      (j.pastas||[]).forEach(function(p){lista.appendChild(item('📁 '+p.nome,p.caminho));});
      if(!(j.pastas||[]).length)lista.appendChild(Object.assign(document.createElement('small'),{className:'mu',textContent:'Nenhuma pasta aqui.'}));
      if(j.cortado)erro.textContent='Mostrando só as 500 primeiras pastas.';
    }).catch(function(){erro.textContent='Não consegui falar com o site.';});
  }
  document.getElementById('bk-procurar').addEventListener('click',function(){painel.hidden=false;ir(campo.value.trim());});
  document.getElementById('bk-fechar').addEventListener('click',function(){painel.hidden=true;});
  document.getElementById('bk-usar').addEventListener('click',function(){if(!corrente){erro.textContent='Escolha um disco e uma pasta antes.';return;}campo.value=corrente;painel.hidden=true;campo.focus();});
})();
