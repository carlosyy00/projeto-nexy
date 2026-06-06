const socket = io();

const room = window.location.pathname.split("/")[2];
let nomeUsuario = localStorage.getItem("usuario");

if (!nomeUsuario) {
    nomeUsuario = prompt("Digite seu nome para entrar na reunião:");

    if (!nomeUsuario || !nomeUsuario.trim()) {
        alert("Nome é necessário para entrar na reunião.");
        window.location.href = "/";
    } else {
        nomeUsuario = nomeUsuario.trim();
        localStorage.setItem("usuario", nomeUsuario);
    }
}

let peers = {};
window.localStream = null;

// nome de cada participante por socket id
const nomesPorId = {};

function atualizarNome(id, nome) {
    if (!id || !nome) return;
    nomesPorId[id] = nome;

    const container = document.getElementById("user_" + id);
    if (container) {
        const span = container.querySelector(".nome-video");
        if (span) span.innerText = nome;
    }
}

const config = {
    iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        { urls: "stun:stun1.l.google.com:19302" },
        { urls: "stun:stun2.l.google.com:19302" }
    ]
};

function mostrarAvisoCamera(msg, tipo = "erro") {
    const el = document.getElementById("cameraAviso");
    if (!el) {
        alert(msg);
        return;
    }
    el.textContent = msg;
    el.className = "camera-aviso show " + tipo;
}

async function iniciar() {
    // getUserMedia só existe em contexto seguro (HTTPS ou localhost).
    // Em http://IP-local (ex.: 192.168.x.x) o navegador bloqueia câmera/microfone.
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        mostrarAvisoCamera(
            "Câmera/microfone bloqueados: esta página não está em HTTPS. " +
            "Para usar a câmera em outro computador ou celular, entre pelo LINK DE CONVITE " +
            "(que é HTTPS), e não pelo endereço de IP local."
        );
        // ainda entra na sala para poder usar o chat
        socket.emit("join", { room, nome: nomeUsuario });
        return;
    }

    // getUserMedia({video,audio}) exige os DOIS dispositivos ao mesmo tempo.
    // Se faltar um (ex.: tem câmera mas não tem microfone), tentamos em ordem:
    // câmera+mic  ->  só câmera  ->  só microfone.
    const tentativas = [
        { video: true, audio: true },
        { video: true, audio: false },
        { video: false, audio: true }
    ];

    let ultimoErro = null;
    for (const constraints of tentativas) {
        try {
            window.localStream = await navigator.mediaDevices.getUserMedia(constraints);
            break;
        } catch (e) {
            ultimoErro = e;
            console.warn("getUserMedia falhou:", constraints, e.name);
        }
    }

    if (!window.localStream) {
        mostrarAvisoCamera(
            "Não foi possível acessar câmera nem microfone (" +
            (ultimoErro ? ultimoErro.name : "desconhecido") + "). " +
            "Verifique se há câmera/microfone conectados e as permissões do navegador."
        );
    } else {
        const temVideo = window.localStream.getVideoTracks().length > 0;
        const temAudio = window.localStream.getAudioTracks().length > 0;

        if (!temVideo) {
            mostrarAvisoCamera(
                "Você entrou apenas com áudio — nenhuma câmera disponível foi encontrada.",
                "aviso"
            );
        } else if (!temAudio) {
            mostrarAvisoCamera(
                "Câmera ligada, mas nenhum microfone foi encontrado, então você não " +
                "consegue falar. Conecte um microfone ou fone com mic (ex.: seus AirPods) " +
                "e recarregue a página para ativar o áudio.",
                "aviso"
            );
        }
    }

    const localVideo = document.getElementById("localVideo");
    if (localVideo && window.localStream) {
        localVideo.srcObject = window.localStream;
        localVideo.play().catch(() => {});
    }

    // mostra o próprio nome no vídeo local
    const localNome = document.getElementById("localNome");
    if (localNome && nomeUsuario) {
        localNome.innerText = nomeUsuario + " (você)";
    }

    socket.emit("join", { room, nome: nomeUsuario });
}

function criarPeer(id) {
    if (peers[id]) {
        return peers[id];
    }

    const pc = new RTCPeerConnection(config);

    if (window.localStream) {
        window.localStream.getTracks().forEach(track => {
            pc.addTrack(track, window.localStream);
        });
    }

    pc.ontrack = (event) => {
        let container = document.getElementById("user_" + id);

        if (!container) {
            container = document.createElement("div");
            container.id = "user_" + id;
            container.classList.add("video-wrapper");

            const video = document.createElement("video");
            video.autoplay = true;
            video.playsInline = true;

            const nome = document.createElement("span");
            nome.classList.add("nome-video");
            nome.innerText = nomesPorId[id] || "Usuário";

            container.appendChild(video);
            container.appendChild(nome);

            document.querySelector(".videos").appendChild(container);
        }

        container.querySelector("video").srcObject = event.streams[0];
    };

    pc.onicecandidate = (event) => {
        if (event.candidate) {
            socket.emit("ice", { to: id, candidate: event.candidate });
        }
    };

    pc.onconnectionstatechange = () => {
        if (
            pc.connectionState === "disconnected" ||
            pc.connectionState === "failed" ||
            pc.connectionState === "closed"
        ) {
            removeVideo(id);
        }
    };

    peers[id] = pc;
    return pc;
}

/* ================= SOCKET ================= */

socket.on("all_users", async (data) => {
    // registra os nomes dos participantes já presentes
    if (Array.isArray(data.usuarios)) {
        data.usuarios.forEach(u => {
            if (u.id !== socket.id) atualizarNome(u.id, u.nome);
        });
    }

    for (let id of data.users) {
        if (id === socket.id) continue;

        const pc = criarPeer(id);

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        socket.emit("offer", { to: id, offer });
    }
});

socket.on("offer", async ({ from, offer }) => {
    let pc = peers[from];

    if (!pc) {
        pc = criarPeer(from);
    }

    await pc.setRemoteDescription(new RTCSessionDescription(offer));

    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    socket.emit("answer", { to: from, answer });
});

socket.on("answer", async ({ from, answer }) => {
    const pc = peers[from];
    if (!pc) return;

    await pc.setRemoteDescription(new RTCSessionDescription(answer));
});

socket.on("ice", async ({ from, candidate }) => {
    const pc = peers[from];
    if (!pc) return;

    try {
        await pc.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (e) {
        console.log("Erro ICE", e);
    }
});

socket.on("user_joined", (data) => {
    // registra/atualiza o nome do participante que entrou
    atualizarNome(data.id, data.nome);

    const hora = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });

    adicionarSistema(`${data.nome} entrou na reunião às ${hora}`);
});

socket.on("chat", (data) => {
    adicionarMsg(data.nome, data.msg);
});

socket.on("user-disconnected", (id) => {
    removeVideo(id);
});

/* ================= REMOÇÃO ================= */

function removeVideo(id) {
    const container = document.getElementById("user_" + id);

    if (container) {
        container.remove();
    }

    if (peers[id]) {
        peers[id].close();
        delete peers[id];
    }
}

/* ================= FUNÇÕES GERAIS ================= */

function encerrarReuniao() {
    Object.values(peers).forEach(pc => pc.close());
    socket.disconnect();
    window.location.href = "/dashboard";
}

function adicionarMsg(nome, msg) {
    const box = document.getElementById("messages");
    if (!box) return;

    const nomeFinal = nome || "Usuário";

    const div = document.createElement("div");

    const isMe = nomeFinal === nomeUsuario;
    const isIA = nomeFinal.includes("Nexy");

    div.style.display = "flex";
    div.style.justifyContent = isMe ? "flex-end" : "flex-start";

    const bubble = document.createElement("div");

    bubble.style.maxWidth = "60%";
    bubble.style.padding = "10px";
    bubble.style.margin = "5px";
    bubble.style.borderRadius = "10px";
    bubble.style.fontSize = "14px";

    if (isIA) {
        bubble.style.background = "#22c55e";
    } else if (isMe) {
        bubble.style.background = "#3b82f6";
    } else {
        bubble.style.background = "#1e293b";
    }

    const hora = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });

    bubble.innerHTML = `
        <b>${nomeFinal}</b>
        <span style="font-size:10px;opacity:0.6;">${hora}</span><br>
        ${msg}
    `;

    div.appendChild(bubble);
    box.appendChild(div);

    box.scrollTop = box.scrollHeight;
}

async function enviarMsg() {
    const input = document.getElementById("msgInput");
    const msg = input.value;

    if (!msg.trim()) return;

    adicionarMsg(nomeUsuario, msg);

    if (msg.toLowerCase().startsWith("@nexy")) {
        const pergunta = msg.replace(/@nexy/i, "").trim();

        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    msg: pergunta
                })
            });

            const data = await res.json();

            adicionarMsg("🤖 Nexy IA", data.resposta);

            socket.emit("chat", {
                room,
                nome: "🤖 Nexy IA",
                msg: data.resposta
            });

        } catch (erro) {
            console.error(erro);
            adicionarMsg("🤖 Nexy IA", "Erro ao responder.");
        }

    } else {
        socket.emit("chat", {
            room,
            nome: nomeUsuario,
            msg
        });
    }

    input.value = "";
}

document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("btnEnviar");
    const input = document.getElementById("msgInput");

    if (btn) {
        btn.addEventListener("click", enviarMsg);
    }

    if (input) {
        input.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                enviarMsg();
            }
        });
    }
});

function adicionarSistema(msg) {
    const box = document.getElementById("messages");
    if (!box) return;

    const div = document.createElement("div");

    div.style.textAlign = "center";
    div.style.fontSize = "12px";
    div.style.opacity = "0.7";
    div.style.margin = "5px";

    div.innerText = msg;

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

/* ================= COMPARTILHAR TELA CORRIGIDO ================= */

async function compartilharTela() {
    try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: true,
            audio: false
        });

        const screenTrack = screenStream.getVideoTracks()[0];

        Object.values(peers).forEach(pc => {
            const sender = pc.getSenders().find(s => s.track && s.track.kind === "video");

            if (sender) {
                sender.replaceTrack(screenTrack);
            }
        });

        const localVideo = document.getElementById("localVideo");
        localVideo.srcObject = screenStream;
        // tela compartilhada não deve ser espelhada
        localVideo.classList.remove("mirror");

        screenTrack.onended = async () => {
            const cameraTrack = window.localStream?.getVideoTracks()[0];

            Object.values(peers).forEach(pc => {
                const sender = pc.getSenders().find(s => s.track && s.track.kind === "video");

                if (sender && cameraTrack) {
                    sender.replaceTrack(cameraTrack);
                }
            });

            localVideo.srcObject = window.localStream;
            // volta a espelhar a câmera
            localVideo.classList.add("mirror");
        };

    } catch (err) {
        alert("Erro ao compartilhar tela");
        console.error(err);
    }
}

/* ================= GRAVAÇÃO ================= */

let recorder;
let gravando = false;

async function iniciarGravacao() {
    if (gravando) return;

    const stream = window.localStream;

    if (!stream) {
        alert("Sem vídeo para gravar");
        return;
    }

    recorder = new MediaRecorder(stream);

    let chunks = [];

    recorder.ondataavailable = e => chunks.push(e.data);

    recorder.onstop = () => {
        const blob = new Blob(chunks, { type: "video/webm" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = "reuniao.webm";
        a.click();
    };

    recorder.start();
    gravando = true;

    const status = document.getElementById("recStatus");
    if (status) {
        status.style.display = "block";
    }
}

function pararGravacao() {
    if (recorder && gravando) {
        recorder.stop();
        gravando = false;

        const status = document.getElementById("recStatus");

        if (status) {
            status.innerText = "✅ Gravação encerrada";
            status.style.background = "green";

            setTimeout(() => {
                status.style.display = "none";
                status.innerText = "🔴 Gravando reunião...";
                status.style.background = "red";
            }, 3000);
        }
    }
}

/* ================= INIT ================= */

window.onload = iniciar;