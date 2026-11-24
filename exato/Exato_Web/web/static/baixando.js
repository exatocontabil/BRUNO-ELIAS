/* Atualização automática: mostra o download, depois espera o Exato sair do ar e voltar e abre a tela de entrada. */
(function(){
  var msg=document.getElementById('bx-msg'),barra=document.getElementById('bx-barra'),erro=document.getElementById('bx-erro'),volta=document.getElementById('bx-volta');
  var reiniciando=false,caiu=false,t0=0;
  function mb(n){return (n/1048576).toFixed(0);}
  function andamento(){
    fetch('/atualizacao/andamento',{cache:'no-store'}).then(function(r){return r.json();}).then(function(e){
      if(e.fase==='baixando'){msg.textContent='Baixando a versão nova... '+mb(e.bytes)+' de '+mb(e.total)+' MB';barra.style.width=Math.max(2,Math.round(100*e.bytes/Math.max(1,e.total)))+'%';}
      else if(e.fase==='conferindo'){msg.textContent='Conferindo o arquivo...';barra.style.width='100%';}
      else if(e.fase==='reiniciando'){comecaEspera();return;}
      else if(e.fase==='erro'){msg.textContent='Não foi possível atualizar.';erro.textContent=e.erro;erro.hidden=false;volta.hidden=false;return;}
      setTimeout(andamento,1200);
    }).catch(function(){ if(reiniciando)return; comecaEspera(); });
  }
  function comecaEspera(){
    if(reiniciando)return; reiniciando=true; t0=Date.now();
    msg.textContent='O Exato está se atualizando. Esta página abre o Exato de novo sozinha, em cerca de 1 ou 2 minutos.';barra.style.width='100%';
    setTimeout(ciclo,3000);
  }
  function ciclo(){
    fetch('/saude',{cache:'no-store'}).then(function(r){return r.ok;}).catch(function(){return false;}).then(function(ok){
      if(!ok)caiu=true;
      if(ok&&caiu){location.href='/login';return;}
      if(ok&&!caiu&&Date.now()-t0>90000){location.href='/atualizacao';return;}
      if(Date.now()-t0>300000){msg.textContent='Está demorando mais que o normal. Se o Exato não voltar sozinho, abra-o pelo atalho do menu Iniciar.';}
      setTimeout(ciclo,2000);
    });
  }
  andamento();
})();
