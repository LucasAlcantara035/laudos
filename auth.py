"""Autenticação e administração de contas com bcrypt e bloqueio por tentativas."""
import os, re, secrets, sqlite3, time
import bcrypt
import db

MAX_FALHAS = 5
BLOQUEIO_S = 15 * 60
_MSG = "E-mail ou senha incorretos."


def hash_senha(senha):
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha, armazenado):
    try:
        return bcrypt.checkpw(senha.encode(), armazenado.encode("ascii"))
    except Exception:
        return False


def _valida(email, senha):
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Informe um e-mail válido.")
    if len(senha or "") < 8:
        raise ValueError("A senha precisa ter pelo menos 8 caracteres.")
    return email


def cadastrar(email, senha, papel="usuario", aprovado=False):
    """Conta nova fica pendente até o administrador autorizar (aprovado=False)."""
    email = _valida(email, senha)
    try:
        with db.conn() as c:
            return c.execute(
                "INSERT INTO users(email,senha_hash,criado,papel,aprovado,falhas,bloqueado_ate,ativo,deve_trocar) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (email, hash_senha(senha), time.time(), papel, int(aprovado), 0, 0, 1, 0),
            ).lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Este e-mail já está cadastrado.")


def garantir_admin():
    """Cria o primeiro administrador a partir de ADMIN_EMAIL e ADMIN_SENHA (só se o e-mail ainda não existir)."""
    email, senha = os.environ.get("ADMIN_EMAIL", "").strip().lower(), os.environ.get("ADMIN_SENHA", "")
    if not email or not senha:
        return False
    with db.conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            return False
    cadastrar(email, senha, papel="admin", aprovado=True)
    return True


def entrar(email, senha):
    email = (email or "").strip().lower()
    with db.conn() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if u is None:
            verificar_senha(senha or "", "00:00")  # custo similar
            raise ValueError(_MSG)
        if (u["bloqueado_ate"] or 0) > time.time():
            raise PermissionError("Conta bloqueada por tentativas erradas. Aguarde ou peça o desbloqueio ao administrador.")
        if verificar_senha(senha or "", u["senha_hash"]):
            if not u["ativo"]:
                raise PermissionError("Conta desativada. Procure o administrador.")
            if not u["aprovado"]:
                raise PermissionError("Conta aguardando autorização do administrador.")
            c.execute("UPDATE users SET falhas=0, bloqueado_ate=0 WHERE id=?", (u["id"],))
            return u["id"]
        falhas = (u["falhas"] or 0) + 1
        if falhas >= MAX_FALHAS:
            c.execute("UPDATE users SET falhas=0, bloqueado_ate=? WHERE id=?", (time.time() + BLOQUEIO_S, u["id"]))
        else:
            c.execute("UPDATE users SET falhas=? WHERE id=?", (falhas, u["id"]))
    raise ValueError(_MSG)


def perfil(uid):
    """Dados da sessão. Retorna None se a conta foi desativada ou revogada (encerra a sessão)."""
    with db.conn() as c:
        u = c.execute("SELECT id,email,papel,deve_trocar,ativo,aprovado FROM users WHERE id=?", (uid,)).fetchone()
    if not u or not u["ativo"] or not u["aprovado"]:
        return None
    return {"id": u["id"], "email": u["email"], "papel": u["papel"], "deve_trocar": bool(u["deve_trocar"])}


def trocar_senha(uid, atual, nova):
    if len(nova or "") < 8:
        raise ValueError("A nova senha precisa ter pelo menos 8 caracteres.")
    with db.conn() as c:
        u = c.execute("SELECT senha_hash FROM users WHERE id=?", (uid,)).fetchone()
        if not u or not verificar_senha(atual or "", u["senha_hash"]):
            raise ValueError("Senha atual incorreta.")
        if nova == atual:
            raise ValueError("A nova senha deve ser diferente da atual.")
        c.execute("UPDATE users SET senha_hash=?, deve_trocar=0 WHERE id=?", (hash_senha(nova), uid))


# ---------------- administração (cada função confere no servidor se quem chama é admin) ----------------
def _admin(c, admin_id):
    r = c.execute("SELECT papel,ativo,aprovado FROM users WHERE id=?", (admin_id,)).fetchone()
    if not r or r["papel"] != "admin" or not r["ativo"] or not r["aprovado"]:
        raise PermissionError("Acesso restrito ao administrador.")


def _log(c, admin_id, acao, alvo):
    c.execute("INSERT INTO auditoria(em,admin_id,acao,alvo_id) VALUES(?,?,?,?)", (time.time(), admin_id, acao, alvo))


def listar_usuarios(admin_id):
    with db.conn() as c:
        _admin(c, admin_id)
        agora = time.time()
        return [{"id": r["id"], "email": r["email"], "papel": r["papel"], "aprovado": bool(r["aprovado"]),
                 "ativo": bool(r["ativo"]), "bloqueado": (r["bloqueado_ate"] or 0) > agora, "criado": r["criado"]}
                for r in c.execute("SELECT * FROM users ORDER BY aprovado ASC, criado DESC")]


def aprovar(admin_id, alvo):
    with db.conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET aprovado=1 WHERE id=?", (alvo,)); _log(c, admin_id, "aprovar", alvo)


def recusar(admin_id, alvo):
    """Remove um cadastro que nunca foi aprovado."""
    with db.conn() as c:
        _admin(c, admin_id)
        if c.execute("DELETE FROM users WHERE id=? AND aprovado=0", (alvo,)).rowcount:
            _log(c, admin_id, "recusar", alvo)


def desbloquear(admin_id, alvo):
    with db.conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET falhas=0, bloqueado_ate=0 WHERE id=?", (alvo,)); _log(c, admin_id, "desbloquear", alvo)


def redefinir_senha(admin_id, alvo):
    """Gera senha temporária (mostrada uma vez ao admin). O usuário será obrigado a trocá-la no próximo acesso."""
    if alvo == admin_id:
        raise ValueError("Para a sua própria senha, use 'Alterar senha'.")
    temp = secrets.token_urlsafe(9)
    with db.conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET senha_hash=?, deve_trocar=1, falhas=0, bloqueado_ate=0 WHERE id=?",
                  (hash_senha(temp), alvo))
        _log(c, admin_id, "redefinir_senha", alvo)
    return temp


def definir_ativo(admin_id, alvo, ativo):
    if alvo == admin_id:
        raise ValueError("Você não pode desativar a própria conta.")
    with db.conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET ativo=? WHERE id=?", (int(ativo), alvo))
        _log(c, admin_id, "reativar" if ativo else "desativar", alvo)


def auditoria_recente(admin_id, n=20):
    with db.conn() as c:
        _admin(c, admin_id)
        return [dict(r) for r in c.execute(
            "SELECT a.em,a.acao,u.email AS admin,t.email AS alvo FROM auditoria a "
            "LEFT JOIN users u ON u.id=a.admin_id LEFT JOIN users t ON t.id=a.alvo_id ORDER BY a.em DESC LIMIT ?", (n,))]
