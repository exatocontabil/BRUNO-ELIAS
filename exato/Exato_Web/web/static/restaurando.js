/* Depois de pedir a restauração: espera o Exato sair do ar e voltar, e abre a tela de entrada. */
(function(){
  var msg=document.getElementById('rs-msg'),caiu=false,t0=Date.now();
  function ciclo(){
    fetch('/saude',{cache:'no-store'}).then(function(r){return r.ok;}).catch(function(){return false;}).then(function(ok){
      if(!ok)caiu=true;
      if(ok&&caiu){location.href='/login';return;}
      if(Date.now()-t0>240000){if(msg)msg.textContent='Está demorando mais que o normal. Se o Exato não voltar sozinho, abra-o de novo pelo atalho.';}
      setTimeout(ciclo,3000);
    });
  }
  setTimeout(ciclo,3000);
})();
