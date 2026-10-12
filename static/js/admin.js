/* Painel: confirmações e nova cor na grade de estoque. */
(() => {
  "use strict";

  document.querySelectorAll("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!confirm(form.dataset.confirmar)) e.preventDefault();
    });
  });

  document.querySelectorAll("[data-confirmar-botao]").forEach((botao) => {
    botao.addEventListener("click", (e) => {
      if (!confirm(botao.dataset.confirmarBotao)) e.preventDefault();
    });
  });

  const grade = document.querySelector("[data-grade-form]");
  if (grade) {
    const corpo = grade.querySelector("[data-linhas-cor]");
    const modelo = grade.querySelector("[data-modelo-cor]");
    grade.querySelector("[data-nova-cor]").addEventListener("click", () => {
      const indice = corpo.children.length;
      const linha = modelo.content.firstElementChild.cloneNode(true);
      linha.querySelectorAll("[data-nome]").forEach((campo) => {
        campo.name = campo.dataset.nome.replace("__I__", String(indice));
      });
      corpo.append(linha);
      linha.querySelector('input[type="text"]').focus();
    });
  }
})();
