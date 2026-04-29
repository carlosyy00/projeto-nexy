
const usuario = localStorage.getItem("usuario");

// só protege páginas privadas
const paginasProtegidas = ["/dashboard", "/chatpage", "/meeting"];

const paginaAtual = window.location.pathname;

const precisaLogin = paginasProtegidas.some(p => paginaAtual.startsWith(p));

if (precisaLogin && !usuario) {
    window.location.href = "/loginpage";
}

// CHAT IA
// 🔥 MENSAGEM AUTOMÁTICA DA IA
window.addEventListener("load", () => {

    const chat = document.getElementById("chat");

    if (chat) {
        chat.innerHTML += `
            <div style="
                color:#38bdf8;
                background:#0f172a;
                padding:10px;
                border-radius:10px;
                margin-bottom:10px;
            ">
                <b>Nexy:</b><br>
                Olá 👋 Eu sou a IA da Nexy.

                Posso te ajudar durante a reunião com:
                • Resumos
                • Explicações
                • Dúvidas técnicas
                • Organização da conversa

                Pode perguntar o que quiser 🙂
            </div>
        `;
    }
});


// 🔥 ENVIO DE MENSAGEM (SEU CÓDIGO MELHORADO)
async function enviarMensagem() {

    const input = document.getElementById("mensagem");
    const texto = input.value;

    if (texto.trim() === "") return;

    const chat = document.getElementById("chat");

    // mensagem do usuário
    chat.innerHTML += `
        <div style="text-align:right; margin:5px;">
            <b>${usuario}:</b> ${texto}
        </div>
    `;

    input.value = "";

    try {
        const resposta = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ msg: texto })
        });

        const dados = await resposta.json();

        // resposta da IA
        chat.innerHTML += `
            <div style="
                color:#38bdf8;
                background:#020617;
                padding:10px;
                border-radius:10px;
                margin:5px;
                text-align:left;
            ">
                <b>Nexy:</b> ${dados.resposta}
            </div>
        `;

        // 🔥 scroll automático
        chat.scrollTop = chat.scrollHeight;

    } catch (erro) {
        chat.innerHTML += `
            <div style="color:red;">
                Erro ao falar com a Nexy
            </div>
        `;
        console.error(erro);
    }
}                                                                                           
// 🔥 GERAR CÓDIGO DA SALA
function gerarCodigo() {
    return Math.random().toString(36).substring(2, 8);
}

// 🔥 CRIAR REUNIÃO (NGROK AUTOMÁTICO + FALLBACK)
async function criarSala() {

  const codigo = Math.random().toString(36).substring(2, 8);

  let baseURL;

  try {
    const res = await fetch("/config");
    const data = await res.json();

    baseURL = data.base_url;

    // 🔥 força usar ngrok se estiver local
    if(baseURL.includes("localhost") || baseURL.includes("127.0.0.1")){
        baseURL = "https://SEU-LINK-NGROK-AQUI";
    }

  } catch {
    baseURL = "https://SEU-LINK-NGROK-AQUI";
  }

  const link = baseURL + "/meeting/" + codigo;

  document.getElementById("areaReuniao").innerHTML = `
    <div class="card">
      <h3>🚀 Sala criada</h3>

      <input type="text" value="${link}" id="linkInput" readonly>

      <button onclick="copiarLink()">Copiar</button>
      <button onclick="entrar('${codigo}')">Entrar</button>
    </div>
  `;
}

// 🔥 ENTRAR NA REUNIÃO
function entrarSala() {
  const codigo = prompt("Digite o código da sala:");

  if (codigo) {
    window.location.href = "/meeting/" + codigo;
  }
}

// 🔥 COPIAR LINK
function copiarLink() {

    const input = document.getElementById("linkInput");

    if (!input) return;

    navigator.clipboard.writeText(input.value)
        .then(() => {
            alert("Link copiado!");
        })
        .catch(() => {
            alert("Erro ao copiar");
        });
}

function entrar(codigo){
    window.location.href = "/meeting/" + codigo;
}

// 🔥 VOLTAR
function voltar(){
    window.location.href = "/dashboard";
}

// 🔥 LOGOUT
function logout(){
    localStorage.clear();
    window.location.href = "/loginpage";
}

// 🔥 MOSTRAR NOME NO DASHBOARD
window.onload = () => {

    const nomeEl = document.getElementById("nomeUsuario");
    const userEl = document.getElementById("user");
    const welcomeEl = document.getElementById("welcome");

    if (nomeEl) {
        nomeEl.innerText = `Bem-vindo, ${usuario}`;
    }

    if (userEl) {
        userEl.innerText = usuario;
    }

    if (welcomeEl) {
        welcomeEl.innerText = `Bem-vindo, ${usuario}`;
    }
};