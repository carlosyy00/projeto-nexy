// 🔐 CONTROLE GLOBAL DO NEXY

const App = {

    // 🔥 verifica login
    checkAuth() {
        const user = localStorage.getItem("usuario");

        if (!user) {
            window.location.href = "/loginpage";
        }
    },

    // 🔥 pega usuário
    getUser() {
        return localStorage.getItem("usuario");
    },

    // 🔥 logout
    logout() {
        localStorage.clear();
        window.location.href = "/loginpage";
    },

    // 🔥 navegação padrão
    go(page) {
        window.location.href = page;
    },

    // 🔥 voltar sempre pro dashboard
    voltar() {
        window.location.href = "/dashboard";
    },

    // 🔥 nome no dashboard
    setUserName() {
        const el = document.getElementById("nomeUsuario");

        if (el) {
            el.innerText = "Bem-vindo, " + this.getUser();
        }
    }
};