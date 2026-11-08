(function(){
  var caixa=document.getElementById('estado-busca'); if(!caixa) return;
  var rodava=caixa.dataset.rodando==='1';
  function atualizar(){
    fetch('/busca/estado',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(e){
      if(!e) return;
      if(e.rodando){ caixa.hidden=false; caixa.textContent='Buscando: '+(e.empresa||'')+' ('+e.indice+' de '+e.total+')'+(e.progresso?' • '+e.progresso:''); rodava=true; }
      else if(rodava){ location.reload(); }
    }).catch(function(){});
  }
  setInterval(atualizar,3000); atualizar();
})();
