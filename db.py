"""Persistência SQLite com SQLAlchemy e isolamento obrigatório por usuário."""
import json, os, sqlite3, time, uuid
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy import Boolean, Column, Float, Integer, LargeBinary, MetaData, String, Table, Text, create_engine

DB_PATH = os.environ.get("LAUDOS_DB", "laudos.db")
UPLOAD_DIR = Path(os.environ.get("LAUDOS_UPLOAD_DIR", "uploads"))
MAX_FOTO_BYTES = 5 * 1024 * 1024
_metadata = MetaData()
_users = Table("users", _metadata,
    Column("id", Integer, primary_key=True), Column("email", String, unique=True, nullable=False),
    Column("senha_hash", String, nullable=False), Column("falhas", Integer, default=0),
    Column("bloqueado_ate", Float, default=0), Column("criado", Float), Column("papel", String, default="usuario"),
    Column("aprovado", Boolean, default=True), Column("ativo", Boolean, default=True),
    Column("deve_trocar", Boolean, default=False))
_laudos = Table("laudos", _metadata,
    Column("id", String, primary_key=True), Column("user_id", Integer, nullable=False),
    Column("dados", Text, nullable=False), Column("criado", Float), Column("atualizado", Float))
_versoes = Table("versoes", _metadata,
    Column("id", Integer, primary_key=True), Column("laudo_id", String, nullable=False),
    Column("user_id", Integer, nullable=False), Column("dados", Text, nullable=False), Column("em", Float))
_fotos = Table("fotos", _metadata,
    Column("id", String, primary_key=True), Column("laudo_id", String, nullable=False),
    Column("user_id", Integer, nullable=False), Column("item", String), Column("legenda", String),
    Column("imagem", LargeBinary, nullable=False), Column("caminho", String))
_engine = None


def _engine_for_path():
    return create_engine(f"sqlite:///{Path(DB_PATH).resolve()}", future=True)


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    global _engine
    _engine = _engine_for_path()
    _metadata.create_all(_engine)
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
          senha_hash TEXT NOT NULL, falhas INTEGER DEFAULT 0, bloqueado_ate REAL DEFAULT 0, criado REAL,
          papel TEXT DEFAULT 'usuario', aprovado INTEGER DEFAULT 1, ativo INTEGER DEFAULT 1, deve_trocar INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT, em REAL, admin_id INTEGER,
          acao TEXT, alvo_id INTEGER);
        CREATE TABLE IF NOT EXISTS laudos(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          dados TEXT NOT NULL, criado REAL, atualizado REAL);
        CREATE TABLE IF NOT EXISTS versoes(id INTEGER PRIMARY KEY AUTOINCREMENT, laudo_id TEXT NOT NULL,
          user_id INTEGER NOT NULL, dados TEXT NOT NULL, em REAL);
        CREATE TABLE IF NOT EXISTS fotos(id TEXT PRIMARY KEY, laudo_id TEXT NOT NULL, user_id INTEGER NOT NULL,
          item TEXT, legenda TEXT, imagem BLOB NOT NULL);
        """)
        # migração de bancos criados antes do perfil de administrador (contas antigas ficam aprovadas)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        for col, ddl in [("papel", "TEXT DEFAULT 'usuario'"), ("aprovado", "INTEGER DEFAULT 1"),
                         ("ativo", "INTEGER DEFAULT 1"), ("deve_trocar", "INTEGER DEFAULT 0")]:
            if col not in cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        c.execute("UPDATE users SET falhas=0 WHERE falhas IS NULL")
        c.execute("UPDATE users SET bloqueado_ate=0 WHERE bloqueado_ate IS NULL")
        c.execute("UPDATE users SET aprovado=1 WHERE aprovado IS NULL")
        c.execute("UPDATE users SET ativo=1 WHERE ativo IS NULL")
        c.execute("UPDATE users SET deve_trocar=0 WHERE deve_trocar IS NULL")
        if "caminho" not in {r["name"] for r in c.execute("PRAGMA table_info(fotos)")}:
            c.execute("ALTER TABLE fotos ADD COLUMN caminho TEXT")


def _dono(c, user_id, laudo_id):
    return c.execute("SELECT 1 FROM laudos WHERE id=? AND user_id=?", (laudo_id, user_id)).fetchone() is not None


def salvar_laudo(user_id, laudo_id, dados):
    agora, js = time.time(), json.dumps(dados, ensure_ascii=False)
    with conn() as c:
        ex = c.execute("SELECT user_id FROM laudos WHERE id=?", (laudo_id,)).fetchone()
        if ex is None:
            c.execute("INSERT INTO laudos(id,user_id,dados,criado,atualizado) VALUES(?,?,?,?,?)",
                      (laudo_id, user_id, js, agora, agora))
        elif ex["user_id"] != user_id:
            raise PermissionError("Laudo não pertence ao usuário.")
        else:
            c.execute("UPDATE laudos SET dados=?, atualizado=? WHERE id=? AND user_id=?", (js, agora, laudo_id, user_id))
        c.execute("INSERT INTO versoes(laudo_id,user_id,dados,em) VALUES(?,?,?,?)", (laudo_id, user_id, js, agora))


def obter(user_id, laudo_id):
    with conn() as c:
        r = c.execute("SELECT dados FROM laudos WHERE id=? AND user_id=?", (laudo_id, user_id)).fetchone()
    return json.loads(r["dados"]) if r else None


def listar(user_id):
    with conn() as c:
        rows = c.execute("SELECT id,dados,atualizado FROM laudos WHERE user_id=? ORDER BY atualizado DESC", (user_id,)).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["dados"])
        out.append({"id": r["id"], "cliente": d.get("cliente", ""), "local": d.get("local", ""),
                    "data": d.get("data", ""), "tipo": d.get("tipo", "bt"), "atualizado": r["atualizado"]})
    return out


def historico(user_id, cliente, excluir_id=""):
    if not cliente.strip():
        return []
    return [l for l in listar(user_id) if l["cliente"].strip().lower() == cliente.strip().lower() and l["id"] != excluir_id]


def excluir(user_id, laudo_id):
    with conn() as c:
        caminhos = [r["caminho"] for r in c.execute(
            "SELECT caminho FROM fotos WHERE laudo_id=? AND user_id=?", (laudo_id, user_id)
        ) if r["caminho"]]
        cur = c.execute("DELETE FROM laudos WHERE id=? AND user_id=?", (laudo_id, user_id))
        if cur.rowcount:
            c.execute("DELETE FROM fotos WHERE laudo_id=? AND user_id=?", (laudo_id, user_id))
            c.execute("DELETE FROM versoes WHERE laudo_id=? AND user_id=?", (laudo_id, user_id))
            for caminho in caminhos:
                Path(caminho).unlink(missing_ok=True)
        return bool(cur.rowcount)


def versoes(user_id, laudo_id):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id,em FROM versoes WHERE laudo_id=? AND user_id=? ORDER BY em DESC", (laudo_id, user_id))]


def add_foto(user_id, laudo_id, item, legenda, imagem):
    if not imagem or len(imagem) > MAX_FOTO_BYTES:
        raise ValueError("A foto deve ter entre 1 byte e 5 MB.")
    try:
        with Image.open(BytesIO(imagem)) as picture:
            if picture.format not in {"JPEG", "PNG"}:
                raise ValueError("A foto deve estar no formato JPG ou PNG.")
            picture.verify()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("O arquivo enviado não é uma imagem JPG ou PNG válida.") from exc
    with conn() as c:
        if not _dono(c, user_id, laudo_id):
            raise PermissionError("Laudo não pertence ao usuário.")
        foto_id = uuid.uuid4().hex
        pasta = UPLOAD_DIR / str(user_id)
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"{foto_id}.img"
        caminho.write_bytes(imagem)
        c.execute("INSERT INTO fotos(id,laudo_id,user_id,item,legenda,imagem,caminho) VALUES(?,?,?,?,?,?,?)",
                  (foto_id, laudo_id, user_id, item, legenda, imagem, str(caminho)))


def listar_fotos(user_id, laudo_id):
    with conn() as c:
        fotos = [dict(r) for r in c.execute("SELECT id,item,legenda,imagem,caminho FROM fotos WHERE laudo_id=? AND user_id=?", (laudo_id, user_id))]
    for foto in fotos:
        if foto.get("caminho") and Path(foto["caminho"]).is_file():
            foto["imagem"] = Path(foto["caminho"]).read_bytes()
    return fotos


def excluir_foto(user_id, foto_id):
    with conn() as c:
        row = c.execute("SELECT caminho FROM fotos WHERE id=? AND user_id=?", (foto_id, user_id)).fetchone()
        if row and row["caminho"]:
            Path(row["caminho"]).unlink(missing_ok=True)
        c.execute("DELETE FROM fotos WHERE id=? AND user_id=?", (foto_id, user_id))
