/* Depois de pedir a atualização: espera o Exato sair do ar e voltar e abre a tela de entrada.
   Se o Exato NÃO sair do ar (a atualização não começou ou foi desfeita), leva para a tela "Atualizar o Exato", que mostra o resultado. */
(function(){
  var msg=document.getElementById('rs-msg'),caiu=false,t0=Date.now();
  function ciclo(){
    fetch('/saude',{cache:'no-store'}).then(function(r){return r.ok;}).catch(function(){return false;}).then(function(ok){
      if(!ok)caiu=true;
      if(ok&&caiu){location.href='/login';return;}
      if(ok&&!caiu&&Date.now()-t0>90000){location.href='/atualizacao';return;}
      if(Date.now()-t0>300000){if(msg)msg.textContent='Está demorando mais que o normal. Se o Exato não voltar sozinho, abra-o de novo pelo atalho do menu Iniciar.';}
      setTimeout(ciclo,2000);
    });
  }
  setTimeout(ciclo,3000);
})();
