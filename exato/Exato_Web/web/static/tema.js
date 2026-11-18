/* Tema claro/escuro: lê a escolha guardada antes de desenhar a página (sem piscar). */
(function(){try{var t=localStorage.getItem('exato-tema');if(t==='claro'||t==='escuro')document.documentElement.setAttribute('data-theme',t);}catch(e){}})();
