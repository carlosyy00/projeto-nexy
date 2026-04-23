const socket = io();

const room = window.location.pathname.split("/")[2];
const nomeUsuario = localStorage.getItem("usuario");

if (!nomeUsuario) {
    window.location.href = "/loginpage";
}

let peers = {};
window.localStream = null;

const config = {
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
};

async function iniciar() {

    try {
        window.localStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true
        });

        document.getElementById("localVideo").srcObject = window.localStream;

        socket.emit("join", { room, nome: nomeUsuario });

    } catch (erro) {
        alert("Permita câmera e microfone!");
    }
}

function criarPeer(id) {

    if (peers[id]) {
        return peers[id];
    }

    const pc = new RTCPeerConnection(config);

    window.localStream.getTracks().forEach(track => {
        pc.addTrack(track, window.localStream);
    });

    pc.ontrack = (event) => {

        let container = document.getElementById("user_" + id);

        if (!container) {

            container = document.createElement("div");
            container.id = "user_" + id;
            container.classList.add("video-wrapper"); // 🔥 organização

            const video = document.createElement("video");
            video.autoplay = true;
            video.playsInline = true;

            const nome = document.createElement("span");
            nome.classList.add("nome-video");
            nome.innerText = "Usuário";

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

    // 🔥 REMOVE AUTOMATICAMENTE SE DESCONECTAR
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

    const hora = new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    adicionarSistema(`${data.nome} entrou na reunião às ${hora}`);
});
socket.on("chat", (data) => {
    adicionarMsg(data.nome, data.msg);
});

/* 🔥 CORRIGIDO AQUI */
socket.on("user-disconnected", (id) => {
    removeVideo(id);
});

/* ================= REMOÇÃO CORRETA ================= */

function removeVideo(id){

    const container = document.getElementById("user_" + id);

    if(container){
        container.remove();
    }

    if(peers[id]){
        peers[id].close();
        delete peers[id];
    }
}

/* ================= FUNÇÕES GERAIS ================= */

function encerrarReuniao(){
    Object.values(peers).forEach(pc => pc.close());
    socket.disconnect();
    window.location.href = "/dashboard";
}

function adicionarMsg(nome, msg) {

    const box = document.getElementById("messages");
    if (!box) return;

    // 🔥 GARANTE QUE SEMPRE TEM NOME
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
        hour: '2-digit',
        minute: '2-digit'
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

    if (msg.startsWith("@nexy")) {

        const pergunta = msg.replace("@nexy", "").trim();

        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ msg: pergunta })
            });

            const data = await res.json();

            socket.emit("chat", {
                room,
                nome: "🤖 Nexy IA",
                msg: data.resposta
            });

        } catch {
            adicionarMsg("🤖 Nexy IA", "Erro ao responder.");
        }

    } else {
        socket.emit("chat", { room, nome: nomeUsuario, msg });
    }

    input.value = "";
}

document.addEventListener("DOMContentLoaded", () => {

    const btn = document.getElementById("btnEnviar");
    const input = document.getElementById("msgInput");

    if (btn) {
        btn.addEventListener("click", enviarMsg);
    }

    // 🔥 enviar com ENTER também
    if (input) {
        input.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                enviarMsg();
            }
        });
    }

});

function adicionarSistema(msg){

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

/* ================= COMPARTILHAR TELA ================= */

async function compartilharTela() {
    try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: true
        });

        const screenTrack = screenStream.getVideoTracks()[0];

        // 🔥 ATUALIZA STREAM GLOBAL
        window.localStream = screenStream;

        // troca vídeo em todos os peers
        Object.values(peers).forEach(pc => {
            const sender = pc.getSenders().find(s => s.track.kind === "video");
            if (sender) {
                sender.replaceTrack(screenTrack);
            }
        });

        document.getElementById("localVideo").srcObject = screenStream;

        // 🔥 quando parar de compartilhar
        screenTrack.onended = async () => {

            const camStream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true
            });

            const camTrack = camStream.getVideoTracks()[0];

            // 🔥 VOLTA PARA CAMERA
            window.localStream = camStream;

            Object.values(peers).forEach(pc => {
                const sender = pc.getSenders().find(s => s.track.kind === "video");
                if (sender) {
                    sender.replaceTrack(camTrack);
                }
            });

            document.getElementById("localVideo").srcObject = camStream;
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

    // 🔥 USA SEMPRE O STREAM ATUAL
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

    // 🔥 STATUS VISUAL
    const status = document.getElementById("recStatus");
    if (status) {
        status.style.display = "block";
    }
}

/* ================= PARAR GRAVAÇÃO ================= */

function pararGravacao(){

    if(recorder && gravando){
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