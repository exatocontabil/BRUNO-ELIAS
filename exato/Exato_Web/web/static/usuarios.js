/* Tela Usuários: copiar a senha provisória e pedir confirmação antes de uma ação. */
(function(){
  document.querySelectorAll('[data-copiar]').forEach(function(b){b.addEventListener('click',function(){var el=document.getElementById(b.getAttribute('data-copiar'));if(!el)return;var t=el.textContent.trim();
    function ok(){var o=b.textContent;b.textContent='Copiada!';setTimeout(function(){b.textContent=o;},1500);}
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok).catch(function(){sel(el);});}else{sel(el);}
    function sel(e){var r=document.createRange();r.selectNodeContents(e);var s=window.getSelection();s.removeAllRanges();s.addRange(r);try{document.execCommand('copy');ok();}catch(x){}}});});
  document.querySelectorAll('form[data-confirmar]').forEach(function(f){f.addEventListener('submit',function(e){var a=f.querySelector('select[name=acao]'),t=a?a.options[a.selectedIndex].text:'';if(!window.confirm((f.getAttribute('data-confirmar')||'Confirma?')+'\n\nAção: '+t))e.preventDefault();});});
})();
