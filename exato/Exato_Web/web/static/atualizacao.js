/* Atualizar o Exato: mostra que o arquivo está sendo enviado (são uns 60 MB) e evita clicar duas vezes. */
(function(){
  var f=document.getElementById('at-form'),b=document.getElementById('at-botao'),m=document.getElementById('at-msg');
  if(!f)return;
  f.addEventListener('submit',function(){ if(b){b.disabled=true;} if(m){m.hidden=false;} });
})();
