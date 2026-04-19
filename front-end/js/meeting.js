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

        // 🔥 só entra depois de pegar câmera
        socket.emit("join", { room, nome: nomeUsuario });

    } catch (erro) {
        alert("Permita câmera e microfone!");
    }
}
function criarPeer(id) {

    // 🔥 evita duplicar conexão
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

        const video = document.createElement("video");
        video.id = id;
        video.autoplay = true;
        video.playsInline = true;

        const nome = document.createElement("span");
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

    peers[id] = pc;
    return pc;
}
socket.on("all_users", async (data) => {

    // 🔥 apenas quem entrou agora recebe essa lista
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
    adicionarSistema(`${data.nome} entrou na reunião`);
});

socket.on("chat", (data) => {
    console.log("MSG RECEBIDA:", data);
    adicionarMsg(data.nome, data.msg);
});
function encerrarReuniao(){
    Object.values(peers).forEach(pc => pc.close());
    socket.disconnect();
    window.location.href = "/dashboard";
}

function adicionarMsg(nome, msg) {

    const box = document.getElementById("messages");
    if (!box) return;

    const div = document.createElement("div");

    const isMe = nome === nomeUsuario;
    const isIA = nome.includes("Nexy");

    div.style.display = "flex";
    div.style.justifyContent = isMe ? "flex-end" : "flex-start";

    const bubble = document.createElement("div");

    bubble.style.maxWidth = "60%";
    bubble.style.padding = "10px";
    bubble.style.margin = "5px";
    bubble.style.borderRadius = "10px";
    bubble.style.fontSize = "14px";

    // 🎨 cores
    if (isIA) {
        bubble.style.background = "#22c55e";
        bubble.style.color = "white";
    } else if (isMe) {
        bubble.style.background = "#3b82f6";
        bubble.style.color = "white";
    } else {
        bubble.style.background = "#1e293b";
        bubble.style.color = "white";
    }

const hora = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

bubble.innerHTML = `
    <b>${nome}</b> <span style="font-size:10px;opacity:0.6;">${hora}</span><br>
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

    // 🔥 IA ativada com @nexy
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

async function compartilharTela() {
    try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: true
        });

        const screenTrack = screenStream.getVideoTracks()[0];

        // troca em TODOS os peers
        Object.values(peers).forEach(pc => {
            const sender = pc.getSenders().find(s => s.track.kind === "video");
            if (sender) {
                sender.replaceTrack(screenTrack);
            }
        });

        document.getElementById("localVideo").srcObject = screenStream;

        screenTrack.onended = async () => {

            const camStream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true
            });

            const camTrack = camStream.getVideoTracks()[0];

            Object.values(peers).forEach(pc => {
                const sender = pc.getSenders().find(s => s.track.kind === "video");
                if (sender) {
                    sender.replaceTrack(camTrack);
                }
            });

            document.getElementById("localVideo").srcObject = camStream;
            window.localStream = camStream;
        };

    } catch (err) {
        alert("Erro ao compartilhar tela");
        console.error(err);
    }
}


/*gravar tela*/
let recorder;
let gravando = false;

async function iniciarGravacao() {

    if (gravando) return;

    const stream = document.getElementById("localVideo").srcObject;

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

    // 🔥 MOSTRAR AVISO
    document.getElementById("recStatus").style.display = "block";
}

function pararGravacao(){

    if(recorder){
        recorder.stop();
        gravando = false;

        // 🔥 MENSAGEM DE ENCERRAMENTO
        const status = document.getElementById("recStatus");

        status.innerText = "✅ Gravação encerrada";
        status.style.background = "green";

        setTimeout(() => {
            status.style.display = "none";
            status.innerText = "🔴 Gravando reunião...";
            status.style.background = "red";
        }, 3000);
    }
}

document.addEventListener("DOMContentLoaded", () => {

    const btn = document.getElementById("btnEnviar");

    if (btn) {
        btn.addEventListener("click", enviarMsg);
    }

});
function adicionarSistema(msg){

    const box = document.getElementById("messages");

    const div = document.createElement("div");

    div.style.textAlign = "center";
    div.style.fontSize = "12px";
    div.style.opacity = "0.7";
    div.style.margin = "5px";

    div.innerText = msg;

    box.appendChild(div);
}
window.onload = iniciar;