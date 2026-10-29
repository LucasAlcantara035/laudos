"""Recuperação pelo operador do servidor (útil se o único admin ficar bloqueado).
Uso: python admin_cli.py desbloquear|redefinir|aprovar|promover email@exemplo.com"""
import secrets, sys
import auth, db

if len(sys.argv) != 3 or sys.argv[1] not in ("desbloquear", "redefinir", "aprovar", "promover"):
    sys.exit(__doc__)
cmd, email = sys.argv[1], sys.argv[2].strip().lower()
db.init()
with db.conn() as c:
    u = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not u:
        sys.exit("Usuário não encontrado.")
    if cmd == "desbloquear":
        c.execute("UPDATE users SET falhas=0, bloqueado_ate=0 WHERE id=?", (u["id"],))
    elif cmd == "aprovar":
        c.execute("UPDATE users SET aprovado=1 WHERE id=?", (u["id"],))
    elif cmd == "promover":
        c.execute("UPDATE users SET papel='admin', aprovado=1, ativo=1 WHERE id=?", (u["id"],))
    else:
        t = secrets.token_urlsafe(9)
        c.execute("UPDATE users SET senha_hash=?, deve_trocar=1, falhas=0, bloqueado_ate=0 WHERE id=?", (auth.hash_senha(t), u["id"]))
        print("Senha temporária:", t)
print("Feito:", cmd, email)
