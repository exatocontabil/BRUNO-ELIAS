/* Tela de entrada: "Salvar a senha neste computador".
   O Exato NUNCA guarda a senha de ninguém. Esta opção só pede ao navegador (Chrome, Edge...) para guardar a senha no cofre dele, neste computador.
   Só aparece se o navegador sabe fazer isso. Se o login falhar, mostra o erro aqui mesmo (sem tentar duas vezes). Sem a opção marcada, o formulário funciona como sempre. */
(function(){
  var form=document.querySelector('form[action="/login"]'); if(!form) return;
  var linha=document.getElementById('salvar-linha'),cb=document.getElementById('salvar-senha'),email=form.elements['email'],senha=form.elements['senha'],botao=form.querySelector('button');
  var chave='exato_lembrar_email';
  function guardado(){try{return localStorage.getItem(chave)||'';}catch(e){return '';}}
  function lembrar(v){try{if(v)localStorage.setItem(chave,v);else localStorage.removeItem(chave);}catch(e){}}
  var pode=!!(window.PasswordCredential&&navigator.credentials&&navigator.credentials.store&&window.fetch&&window.URLSearchParams);
  if(!pode||!linha||!cb||!email||!senha) return;
  linha.hidden=false; var ajuda=document.getElementById('salvar-ajuda'); if(ajuda)ajuda.hidden=false;
  var antes=guardado(); if(antes&&!email.value){email.value=antes;cb.checked=true;try{senha.focus();}catch(e){}}
  function erro(texto){
    var caixa=document.getElementById('entrar-erro');
    if(!caixa){caixa=document.createElement('div');caixa.id='entrar-erro';caixa.className='aviso erro';caixa.setAttribute('role','alert');caixa.appendChild(document.createElement('span'));form.insertBefore(caixa,form.firstChild);}
    caixa.firstChild.textContent=texto;caixa.hidden=false;
  }
  function textoDoErro(html){
    try{var d=new DOMParser().parseFromString(html,'text/html');var s=d.querySelector('.aviso.erro span');if(s&&s.textContent.trim())return s.textContent.trim();}catch(e){}
    return 'Não foi possível entrar. Confira o e-mail e a senha.';
  }
  form.addEventListener('submit',function(ev){
    if(!cb.checked){lembrar('');return;}          // sem a opção: envio normal
    ev.preventDefault(); if(botao)botao.disabled=true;
    var corpo=new URLSearchParams(new FormData(form));
    fetch(form.action,{method:'POST',body:corpo,credentials:'same-origin'}).then(function(r){
      var ok=r.redirected&&!/\/login\/?(\?.*)?$/.test(new URL(r.url).pathname);
      if(!ok){return r.text().then(function(h){erro(textoDoErro(h));if(botao)botao.disabled=false;try{senha.value='';senha.focus();}catch(e){}});}
      lembrar(email.value);
      var depois=function(){location.assign(r.url);};
      try{navigator.credentials.store(new PasswordCredential({id:email.value,password:senha.value,name:email.value})).then(depois,depois);}catch(e){depois();}
    }).catch(function(){form.submit();});          // sem rede/erro inesperado: volta ao envio normal
  });
})();
