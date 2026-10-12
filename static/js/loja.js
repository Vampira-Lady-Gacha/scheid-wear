/* SCHEID · loja
   - Sacola guardada no navegador (localStorage); preço, frete e estoque sempre vêm do servidor.
   - Tag da peça: cor, aba de tamanho, quantidade e "Adicionar à sacola" (a tag balança).
   - Sacola: cotação com cupom, CEP preenche o endereço (ViaCEP), envio do pedido.
   - Pedido: copiar o Pix copia-e-cola. */

(() => {
  "use strict";

  const CHAVE = "scheid-sacola";
  const CHAVE_DADOS = "scheid-entrega";
  const reduzMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------ sacola (localStorage)

  const Sacola = {
    ler() {
      try {
        const itens = JSON.parse(localStorage.getItem(CHAVE) || "[]");
        return Array.isArray(itens) ? itens.filter((i) => Number.isInteger(i.v) && i.q > 0) : [];
      } catch {
        return [];
      }
    },
    gravar(itens) {
      try { localStorage.setItem(CHAVE, JSON.stringify(itens)); } catch { /* modo privado */ }
      atualizarContador();
    },
    pecas() { return this.ler().reduce((s, i) => s + i.q, 0); },
    por(varianteId, qtd) {
      const itens = this.ler();
      const item = itens.find((i) => i.v === varianteId);
      if (item) item.q = Math.min(99, item.q + qtd);
      else itens.push({ v: varianteId, q: qtd });
      this.gravar(itens);
    },
    definir(varianteId, qtd) {
      this.gravar(this.ler().map((i) => (i.v === varianteId ? { ...i, q: qtd } : i)).filter((i) => i.q > 0));
    },
    limpar() { this.gravar([]); },
  };

  function atualizarContador(pulsar = false) {
    const total = Sacola.pecas();
    document.querySelectorAll("[data-contador]").forEach((el) => {
      el.textContent = total > 99 ? "99+" : String(total);
      el.toggleAttribute("data-zero", total === 0);
    });
    document.querySelectorAll("[data-botao-sacola]").forEach((link) =>
      link.setAttribute("aria-label", `Sacola, ${total} ${total === 1 ? "peça" : "peças"}`));
    if (pulsar) {
      const botao = document.querySelector("[data-botao-sacola]");
      if (botao) {
        botao.classList.remove("pulsa");
        void botao.offsetWidth;
        botao.classList.add("pulsa");
      }
    }
  }

  // ------------------------------------------------------------ recado

  let tempoRecado;
  function recado(texto, link) {
    const caixa = document.querySelector("[data-recado]");
    if (!caixa) return;
    caixa.innerHTML = "";
    const p = document.createElement("span");
    p.textContent = texto;
    caixa.append(p);
    if (link) {
      const a = document.createElement("a");
      a.href = link.href;
      a.textContent = link.texto;
      caixa.append(a);
    }
    caixa.hidden = false;
    caixa.style.animation = "none";
    void caixa.offsetWidth;
    caixa.style.animation = "";
    clearTimeout(tempoRecado);
    tempoRecado = setTimeout(() => { caixa.hidden = true; }, 5200);
  }

  function balancar(form) {
    const tag = form.closest("[data-tag-balanca]");
    if (!tag || reduzMovimento) return;
    tag.classList.remove("balancando");
    void tag.offsetWidth;
    tag.classList.add("balancando");
  }

  // ------------------------------------------------------------ tag da peça: escolher e pôr na sacola

  function prepararCompra(form) {
    let grade = [];
    try { grade = JSON.parse(form.querySelector("[data-grade]").textContent); } catch { /* sem grade */ }
    const aviso = form.querySelector("[data-estoque-aviso]");
    const confirma = form.querySelector("[data-confirma]");
    const campoQtd = form.querySelector("[data-quantidade]");
    const nomeCor = form.querySelector("[data-cor-nome]");

    const corAtual = () =>
      form.querySelector("[data-cor]:checked")?.value ?? form.querySelector("[data-cor-unica]")?.value ?? grade[0]?.cor;
    const tamanhoAtual = () => form.querySelector("[data-tamanho]:checked")?.value;
    const variante = () => grade.find((v) => v.cor === corAtual() && v.tamanho === tamanhoAtual());

    function refletirCor() {
      const cor = corAtual();
      if (nomeCor) nomeCor.textContent = cor;
      form.querySelectorAll("[data-tamanho]").forEach((radio) => {
        const v = grade.find((g) => g.cor === cor && g.tamanho === radio.value);
        radio.disabled = !v || v.estoque <= 0;
        const rotulo = radio.nextElementSibling;
        rotulo?.querySelector(".sr")?.remove();
        if (radio.disabled) {
          if (radio.checked) radio.checked = false;
          const sr = document.createElement("span");
          sr.className = "sr";
          sr.textContent = " (esgotado)";
          rotulo?.append(sr);
        }
      });
      refletirTamanho();
    }

    function refletirTamanho() {
      const v = variante();
      aviso.classList.remove("pouco");
      if (!tamanhoAtual() || !v) aviso.textContent = "";
      else if (v.estoque <= 3) {
        aviso.textContent = v.estoque === 1 ? `Última peça no ${v.tamanho}.` : `Últimas ${v.estoque} no ${v.tamanho}.`;
        aviso.classList.add("pouco");
      } else aviso.textContent = `${v.tamanho} disponível.`;
      if (campoQtd && v) {
        campoQtd.max = String(Math.min(10, v.estoque));
        if (+campoQtd.value > v.estoque) campoQtd.value = String(v.estoque);
      }
      confirma.textContent = "";
      confirma.classList.remove("erro");
    }

    form.addEventListener("change", (e) => {
      if (e.target.matches("[data-cor]")) refletirCor();
      if (e.target.matches("[data-tamanho]")) refletirTamanho();
    });

    form.querySelector("[data-menos]")?.addEventListener("click", () => {
      campoQtd.value = String(Math.max(1, (+campoQtd.value || 1) - 1));
    });
    form.querySelector("[data-mais]")?.addEventListener("click", () => {
      const max = +campoQtd.max || 10;
      campoQtd.value = String(Math.min(max, (+campoQtd.value || 1) + 1));
    });

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const v = variante();
      if (!tamanhoAtual() || !v) {
        confirma.textContent = "Escolha o tamanho primeiro.";
        confirma.classList.add("erro");
        form.querySelector("[data-tamanho]:not(:disabled)")?.focus();
        return;
      }
      const qtd = Math.max(1, Math.min(v.estoque, parseInt(campoQtd?.value || "1", 10) || 1));
      const jaTem = Sacola.ler().find((i) => i.v === v.id)?.q || 0;
      if (jaTem + qtd > v.estoque) {
        confirma.textContent = `Você já tem ${jaTem} na sacola e só temos ${v.estoque} no ${v.tamanho}.`;
        confirma.classList.add("erro");
        return;
      }
      Sacola.por(v.id, qtd);
      atualizarContador(true);
      balancar(form);
      confirma.classList.remove("erro");
      confirma.textContent = "";
      recado(`${qtd > 1 ? qtd + " peças" : "Peça"} na sacola · ${v.cor} · ${v.tamanho}`, { href: "/sacola", texto: "Ver sacola" });
    });

    refletirCor();
  }

  // ------------------------------------------------------------ galeria e barra do celular

  function prepararGaleria() {
    const principal = document.querySelector(".galeria [data-foto-principal]");
    document.querySelectorAll("[data-miniatura]").forEach((botao) => {
      botao.addEventListener("click", () => {
        if (!principal) return;
        principal.src = botao.dataset.miniatura;
        document.querySelectorAll("[data-miniatura]").forEach((b) => b.setAttribute("aria-pressed", String(b === botao)));
      });
    });

    const barra = document.querySelector("[data-barra-celular]");
    const compra = document.querySelector("[data-compra-ancora]");
    if (barra && compra && "IntersectionObserver" in window) {
      new IntersectionObserver(([e]) => barra.classList.toggle("mostra", !e.isIntersecting && e.boundingClientRect.top < 0))
        .observe(compra);
      barra.querySelector("[data-ir-compra]").addEventListener("click", (e) => {
        e.preventDefault();
        compra.scrollIntoView({ behavior: reduzMovimento ? "auto" : "smooth", block: "center" });
        compra.querySelector("[data-tamanho]:not(:disabled)")?.focus({ preventScroll: true });
      });
    }
  }

  // ------------------------------------------------------------ sacola

  async function postar(url, corpo) {
    const resp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const detalhe = Array.isArray(dados.detail) ? "Confira os campos e tente de novo." : null;
      throw new Error(dados.erro || detalhe || "Não foi possível falar com a loja. Confira a internet e tente de novo.");
    }
    return dados;
  }

  const soDigitos = (t) => (t || "").replace(/\D/g, "");

  function mascaraCep(valor) {
    const d = soDigitos(valor).slice(0, 8);
    return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
  }

  function mascaraTelefone(valor) {
    let d = soDigitos(valor);
    if (d.startsWith("55") && d.length > 11) d = d.slice(2);
    d = d.slice(0, 11);
    if (d.length <= 2) return d ? `(${d}` : "";
    if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
    if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
    return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  }

  function prepararSacola(secao) {
    const q = (s) => secao.querySelector(s);
    const lista = q("[data-linhas]");
    const modelo = q("[data-modelo-linha]");
    const form = q("[data-form-envio]");
    const formCupom = q("[data-form-cupom]");
    const retornoCupom = q("[data-cupom-retorno]");
    const erro = q("[data-erro]");
    let cupom = "";
    let cotacao = null;
    let atraso;

    // dados de entrega lembrados neste aparelho
    try {
      const salvo = JSON.parse(localStorage.getItem(CHAVE_DADOS) || "{}");
      for (const [k, v] of Object.entries(salvo)) if (form.elements[k] && typeof v === "string") form.elements[k].value = v;
    } catch { /* sem dados */ }

    function render() {
      q("[data-carregando]").hidden = true;
      const vazio = !cotacao || cotacao.linhas.length === 0;
      q("[data-vazio]").hidden = !vazio;
      q("[data-cheio]").hidden = vazio;
      if (vazio) return;

      lista.innerHTML = "";
      for (const l of cotacao.linhas) {
        const no = modelo.content.firstElementChild.cloneNode(true);
        const $ = (s) => no.querySelector(s);
        no.querySelectorAll("[data-l-link]").forEach((a) => (a.href = `/peca/${l.slug}`));
        if (l.foto) $("[data-l-foto]").src = l.foto;
        $("[data-l-numero]").textContent = l.numero;
        $("[data-l-nome]").textContent = l.peca;
        $("[data-l-amostra]").style.setProperty("--amostra", l.cor_hex);
        $("[data-l-cor]").textContent = l.cor;
        $("[data-l-tam]").textContent = `Tam. ${l.tamanho}`;
        $("[data-l-subtotal]").textContent = l.subtotal_fmt;
        $("[data-l-unit]").textContent = l.quantidade > 1 ? `${l.preco_fmt} cada` : "";
        const campo = $("[data-l-qtd]");
        campo.value = String(l.quantidade);
        campo.max = String(Math.max(l.disponivel, 1));
        campo.setAttribute("aria-label", `Quantidade de ${l.peca}, tamanho ${l.tamanho}`);
        $("[data-l-menos]").addEventListener("click", () => mudar(l.variante_id, l.quantidade - 1));
        $("[data-l-mais]").disabled = l.quantidade >= l.disponivel;
        $("[data-l-mais]").addEventListener("click", () => mudar(l.variante_id, l.quantidade + 1));
        campo.addEventListener("change", () => mudar(l.variante_id, Math.max(0, parseInt(campo.value, 10) || 0)));
        $("[data-l-tirar]").addEventListener("click", () => mudar(l.variante_id, 0));
        $("[data-l-tirar]").setAttribute("aria-label", `Tirar ${l.peca} ${l.tamanho} da sacola`);
        if (l.quantidade > l.disponivel) {
          const alerta = $("[data-l-alerta]");
          alerta.hidden = false;
          alerta.textContent = l.disponivel > 0
            ? `Só temos ${l.disponivel} em estoque. Diminua para continuar.`
            : "Esgotou. Tire da sacola para continuar.";
        }
        lista.append(no);
      }
      q("[data-qtd-total]").textContent = `· ${cotacao.quantidade}`;
      q("[data-subtotal]").textContent = cotacao.subtotal_fmt;
      q("[data-frete]").textContent = cotacao.frete_fmt;
      q("[data-total]").textContent = cotacao.total_fmt;
      q("[data-linha-desconto]").hidden = !cotacao.desconto;
      q("[data-desconto]").textContent = cotacao.desconto ? `−${cotacao.desconto_fmt}` : "";
      q("[data-cupom-nome]").textContent = cotacao.cupom;
      const falta = q("[data-frete-falta]");
      falta.hidden = !cotacao.falta_frete_gratis_fmt;
      falta.textContent = cotacao.falta_frete_gratis_fmt ? `Faltam ${cotacao.falta_frete_gratis_fmt} para o frete grátis.` : "";

      retornoCupom.className = "cupom-retorno";
      if (cotacao.erro_cupom) {
        retornoCupom.textContent = cotacao.erro_cupom;
        retornoCupom.classList.add("erro");
      } else if (cotacao.cupom) {
        retornoCupom.textContent = `Cupom ${cotacao.cupom} aplicado.`;
        retornoCupom.classList.add("ok");
      } else retornoCupom.textContent = "";
    }

    async function cotar() {
      const itens = Sacola.ler();
      if (!itens.length) { cotacao = null; render(); return; }
      try {
        cotacao = await postar("/api/cotacao", { itens: itens.map((i) => ({ variante_id: i.v, quantidade: i.q })), cupom });
        if (cotacao.removidos.length) Sacola.gravar(itens.filter((i) => !cotacao.removidos.includes(i.v)));
        if (cotacao.erro_cupom) cupom = "";
        render();
      } catch (e) {
        const aviso = q("[data-carregando]");
        aviso.hidden = false;
        aviso.innerHTML = "";
        const p = document.createElement("span");
        p.className = "erro-form";
        p.textContent = e.message;
        aviso.append(p);
      }
    }

    function mudar(varianteId, qtd) {
      Sacola.definir(varianteId, qtd);
      clearTimeout(atraso);
      atraso = setTimeout(cotar, 120);
    }

    formCupom.addEventListener("submit", (e) => {
      e.preventDefault();
      cupom = formCupom.elements.cupom.value.trim().toUpperCase();
      cotar();
    });

    // CEP → endereço (ViaCEP)
    const campoCep = form.elements.cep;
    const retornoCep = q("[data-cep-retorno]");
    const ajudaCep = retornoCep.innerHTML;
    let ultimoCep = "";
    campoCep.addEventListener("input", async () => {
      campoCep.value = mascaraCep(campoCep.value);
      const cep = soDigitos(campoCep.value);
      if (cep.length !== 8 || cep === ultimoCep) return;
      ultimoCep = cep;
      retornoCep.textContent = "Buscando endereço…";
      try {
        const resp = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const d = await resp.json();
        if (d.erro) throw new Error("cep");
        const preencher = (nome, valor) => { if (valor && form.elements[nome]) form.elements[nome].value = valor; };
        preencher("rua", d.logradouro);
        preencher("bairro", d.bairro);
        preencher("cidade", d.localidade);
        preencher("uf", d.uf);
        retornoCep.textContent = `${d.localidade}/${d.uf}`;
        (d.logradouro ? form.elements.numero : form.elements.rua).focus();
      } catch {
        retornoCep.innerHTML = ajudaCep;
        retornoCep.prepend("Não achamos esse CEP. Preencha o endereço à mão. ");
      }
    });
    form.elements.whatsapp.addEventListener("input", (e) => { e.target.value = mascaraTelefone(e.target.value); });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      erro.textContent = "";
      form.querySelectorAll("[aria-invalid]").forEach((c) => c.removeAttribute("aria-invalid"));
      const dados = Object.fromEntries(new FormData(form));
      const invalido = (nome, msg) => {
        const campo = form.elements[nome];
        campo.setAttribute("aria-invalid", "true");
        campo.focus();
        erro.textContent = msg;
      };
      const nome = (dados.nome || "").trim();
      if (nome.length < 3 || !nome.includes(" ")) return invalido("nome", "Informe seu nome e sobrenome.");
      if (soDigitos(dados.whatsapp).length < 10) return invalido("whatsapp", "Informe seu WhatsApp com DDD.");
      if (soDigitos(dados.cep).length !== 8) return invalido("cep", "Informe o CEP com 8 números.");
      for (const [campo, msg] of [["rua", "Informe a rua."], ["numero", "Informe o número (ou S/N)."], ["bairro", "Informe o bairro."], ["cidade", "Informe a cidade."], ["uf", "Escolha o estado."]]) {
        if (!(dados[campo] || "").trim()) return invalido(campo, msg);
      }
      if (cotacao?.linhas.some((l) => l.quantidade > l.disponivel)) {
        erro.textContent = "Ajuste as peças marcadas na sacola antes de fechar.";
        return;
      }

      const botao = q("[data-enviar]");
      const original = botao.innerHTML;
      botao.disabled = true;
      botao.innerHTML = '<span class="carregando" aria-hidden="true"></span> Registrando o pedido…';
      try {
        const r = await postar("/api/pedidos", {
          ...dados,
          cupom,
          itens: Sacola.ler().map((i) => ({ variante_id: i.v, quantidade: i.q })),
        });
        try {
          const { observacao, ...lembrar } = dados;
          delete lembrar.pagamento;
          localStorage.setItem(CHAVE_DADOS, JSON.stringify(lembrar));
        } catch { /* modo privado */ }
        Sacola.limpar();
        window.location.href = r.url;
      } catch (falha) {
        erro.textContent = falha.message;
        botao.disabled = false;
        botao.innerHTML = original;
        cotar();
      }
    });

    cotar();
  }

  // ------------------------------------------------------------ pedido: copiar Pix

  function prepararPix() {
    const botao = document.querySelector("[data-copiar-pix]");
    const campo = document.querySelector("[data-pix-codigo]");
    if (!botao || !campo) return;
    campo.addEventListener("focus", () => campo.select());
    botao.addEventListener("click", async () => {
      const rotulo = botao.querySelector("span");
      try {
        await navigator.clipboard.writeText(campo.value);
      } catch {
        campo.select();
        document.execCommand("copy");
      }
      rotulo.textContent = "Código copiado. Cole no app do banco";
      setTimeout(() => { rotulo.textContent = "Copiar código Pix"; }, 4000);
    });
  }

  // ------------------------------------------------------------ início

  document.addEventListener("DOMContentLoaded", () => {
    atualizarContador();
    document.querySelectorAll("[data-compra]").forEach(prepararCompra);
    prepararGaleria();
    document.querySelectorAll("[data-auto-enviar]").forEach((s) => s.addEventListener("change", () => s.form.submit()));
    const sacola = document.querySelector("[data-pagina-sacola]");
    if (sacola) prepararSacola(sacola);
    prepararPix();
  });
  window.addEventListener("storage", (e) => e.key === CHAVE && atualizarContador());
})();
