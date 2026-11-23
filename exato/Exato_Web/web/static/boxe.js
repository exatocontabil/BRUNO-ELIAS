/* Box-e: escolher o provedor do e-mail preenche servidor, porta e segurança sozinho. */
(function(){
  var p=document.getElementById('bx-prov'); if(!p) return;
  var S=document.getElementById('bx-servidor'),P=document.getElementById('bx-porta'),G=document.getElementById('bx-seg'),D=document.getElementById('bx-avancado');
  var MAPA={gmail:['smtp.gmail.com','587','STARTTLS'],outlook:['smtp.office365.com','587','STARTTLS']};
  var s=(S.value||'').toLowerCase();if(s==='smtp.gmail.com')p.value='gmail';else if(s==='smtp.office365.com'||s==='smtp-mail.outlook.com')p.value='outlook';else if(s)p.value='outro';
  p.addEventListener('change',function(){var m=MAPA[p.value];if(m){S.value=m[0];P.value=m[1];G.value=m[2];D.open=false;}else if(p.value==='outro'){D.open=true;S.focus();}});
})();
