"""Laudos Técnicos com IA: aplicativo em um único arquivo.

Rodar:    streamlit run app.py
Recuperar acesso (no servidor):  python app.py desbloquear|redefinir|aprovar|promover email@exemplo.com
Variáveis de ambiente: ANTHROPIC_API_KEY, ANTHROPIC_MODEL (opcional), LAUDOS_DB (opcional),
                       ADMIN_EMAIL e ADMIN_SENHA (cria o primeiro administrador).
Os checklists e limites abaixo são um modelo inicial: um engenheiro deve revisá-los antes do uso profissional.
"""
import hashlib, hmac, json, os, re, secrets, sqlite3, sys, time, uuid
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

try:
    import streamlit as st
except ImportError:  # permite importar o arquivo (testes, linha de comando) sem o Streamlit
    st = None


# ============================================================================
# 1. CHECKLISTS, NORMAS E RÓTULOS
# ============================================================================
CK = {
 "bt": {"t": "Baixa tensão (NBR 5410)", "l": [
  ("bt1", "Dispositivos DR (até 30 mA) em tomadas de áreas molhadas e externas"),
  ("bt2", "Condutor de proteção (PE) presente e contínuo em todos os circuitos"),
  ("bt3", "Seção dos condutores compatível com a corrente de projeto"),
  ("bt4", "Disjuntores dimensionados e identificados"),
  ("bt5", "Quadro fechado, identificado e sem partes vivas expostas"),
  ("bt6", "Equipotencialização principal executada"),
  ("bt7", "DPS instalado onde exigido"),
  ("bt8", "Conexões e terminais sem aquecimento ou oxidação")]},
 "mt": {"t": "Média tensão (NBR 14039)", "l": [
  ("mt1", "Cubículos e painéis de média tensão em bom estado e sinalizados"),
  ("mt2", "Relés de proteção e disjuntor de MT ensaiados"),
  ("mt3", "Malha de aterramento da subestação inspecionada"),
  ("mt4", "Transformador sem vazamentos e com temperatura normal"),
  ("mt5", "Intertravamentos e bloqueios funcionais"),
  ("mt6", "Acesso restrito e distâncias de segurança respeitadas"),
  ("mt7", "Extintor, sinalização e iluminação de emergência na subestação")]},
 "nr": {"t": "Segurança (NR-10)", "l": [
  ("nr1", "Prontuário das instalações elétricas disponível e atualizado"),
  ("nr2", "Diagramas unifilares atualizados"),
  ("nr3", "Procedimentos de trabalho e sinalização de segurança"),
  ("nr4", "Treinamento NR-10 dos trabalhadores em dia")]},
 "sp": {"t": "SPDA (NBR 5419)", "l": [
  ("sp1", "Captores, descidas e aterramento íntegros e sem corrosão"),
  ("sp2", "Resistência de aterramento do SPDA medida e registrada")]},
 "inc": {"t": "Sistemas de incêndio (NBR 17240, 10898, 12693, 13714 e Corpo de Bombeiros)", "l": [
  ("i1", "Central de alarme e detecção em operação, sem falhas ou avisos ativos"),
  ("i2", "Detectores e acionadores manuais íntegros, desobstruídos e testados"),
  ("i3", "Sirenes e avisadores sonoros e visuais audíveis em todas as áreas"),
  ("i4", "Iluminação de emergência acende na falta de rede e cumpre a autonomia mínima"),
  ("i5", "Extintores na validade, lacrados, sinalizados e com acesso livre"),
  ("i6", "Hidrantes e mangotinhos: mangueiras, esguichos e registros em bom estado"),
  ("i7", "Reserva técnica de incêndio e bomba de incêndio com acionamento testado"),
  ("i8", "Sinalização de emergência e rotas de fuga desobstruídas"),
  ("i9", "Alimentação elétrica dedicada e circuitos do sistema protegidos"),
  ("i10", "Certificado do Corpo de Bombeiros (AVCB, CERCON ou equivalente) vigente")]},
 "aut": {"t": "Projeto de automação (NBR IEC 61131, NBR IEC 61439, NBR 5410, NR-12)", "l": [
  ("a1", "Documentação completa: diagramas, lista de I/O e topologia de rede"),
  ("a2", "CLP, fontes e módulos de I/O corretamente especificados e dimensionados"),
  ("a3", "Quadro de comando com grau de proteção, identificação e organização adequados"),
  ("a4", "Sensores, atuadores e instrumentos identificados conforme o projeto"),
  ("a5", "Rede de comunicação (protocolos, endereçamento, cabeamento e blindagem) conforme o projeto"),
  ("a6", "Lógica de controle documentada, com intertravamentos e tratamento de falhas"),
  ("a7", "Circuitos de emergência, parada e funções de segurança implementados e testados"),
  ("a8", "Aterramento, blindagens e proteção contra surtos e interferência eletromagnética"),
  ("a9", "Testes FAT e SAT realizados e registrados"),
  ("a10", "IHM ou supervisório com alarmes, níveis de acesso e backup do programa")]},
}

TIPOS = {"bt": "Baixa tensão (residencial/comercial)", "mt": "Média tensão (industrial)",
         "inc": "Sistemas de incêndio", "aut": "Projeto de automação"}

NORMAS = {
 "bt": "ABNT NBR 5410:2004; NR-10 (MTE, 2022)",
 "mt": "ABNT NBR 14039:2021; NR-10 (MTE, 2022)",
 "inc": "ABNT NBR 17240; NBR 10898; NBR 12693; NBR 13714; normas técnicas do Corpo de Bombeiros do estado",
 "aut": "ABNT NBR IEC 61131; NBR IEC 61439; NBR 5410:2004; NR-10 (MTE, 2022); NR-12 (MTE)"}

# rótulos: (campo "sistemas avaliados", campo "ensaio específico")
LB = {"bt": ("Quadros e circuitos inspecionados", "Continuidade do PE (resultado)"),
      "mt": ("Quadros e circuitos inspecionados", "Continuidade do PE (resultado)"),
      "inc": ("Sistemas e áreas inspecionadas (central, detecção, hidrantes, extintores)",
              "Autonomia da iluminação de emergência e pressão do hidrante (resultado)"),
      "aut": ("Painéis, CLPs e pontos de I/O avaliados", "Ensaios funcionais FAT/SAT (resultado)")}

TITULOS = {"bt": "LAUDO TÉCNICO DE INSPEÇÃO ELÉTRICA", "mt": "LAUDO TÉCNICO DE INSPEÇÃO ELÉTRICA",
           "inc": "LAUDO TÉCNICO DE SISTEMAS DE PREVENÇÃO E COMBATE A INCÊNDIO",
           "aut": "LAUDO TÉCNICO DE PROJETO DE AUTOMAÇÃO"}

FINALIDADES = ["Periódico", "Inicial", "Reforma", "Pericial"]
ESQUEMAS = ["TN-S", "TN-C", "TN-C-S", "TT", "IT"]


def grupos(d):
    g = [d["tipo"]]
    if d["tipo"] != "inc":
        g.append("nr")
    if d.get("spda"):
        g.append("sp")
    return g


def normas(d):
    return NORMAS[d["tipo"]] + ("; ABNT NBR 5419:2015" if d.get("spda") else "")


def novo(tipo="bt"):
    import datetime
    return {"tipo": tipo, "spda": False, "cliente": "", "doc": "", "local": "",
            "data": datetime.date.today().isoformat(), "finalidade": "Periódico",
            "tensao": "", "potencia": "", "esquema": "TN-S", "quadros": "", "desc": "",
            "ck": {}, "res": "", "iso": "", "cont": "", "obs": "",
            "laudo": None, "resp": "", "crea": "", "art": ""}


# ============================================================================
# 2. VALIDAÇÃO DAS MEDIÇÕES
# ============================================================================
LIMITE_RES_OHM = 10.0   # referência usual; ajuste conforme o critério do engenheiro
LIMITE_ISO_MOHM = 0.5   # mínimo de referência para isolação


def _num(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return None


def med_flags(d):
    f = []
    r, i = _num(d.get("res")), _num(d.get("iso"))
    if r is not None:
        f.append(("res", r <= LIMITE_RES_OHM,
                  f"Dentro da referência usual (até {LIMITE_RES_OHM:g} Ω)" if r <= LIMITE_RES_OHM
                  else f"Acima da referência usual de {LIMITE_RES_OHM:g} Ω: avaliar como não conformidade"))
    if i is not None:
        f.append(("iso", i >= LIMITE_ISO_MOHM,
                  f"Atende ao mínimo de {LIMITE_ISO_MOHM:g} MΩ" if i >= LIMITE_ISO_MOHM
                  else f"Abaixo do mínimo de {LIMITE_ISO_MOHM:g} MΩ: não conformidade"))
    return f


def nao_conformidades(d):
    out = []
    for g in grupos(d):
        for k, t in CK[g]["l"]:
            v = d.get("ck", {}).get(k, {})
            if v.get("s") == "NC":
                out.append({"norma": CK[g]["t"], "item": t, "obs": v.get("o", "")})
    for _, ok, msg in med_flags(d):
        if not ok:
            out.append({"norma": "Medições", "item": msg, "obs": ""})
    return out


def pendencias(d):
    p = []
    for campo, nome in [("cliente", "Cliente"), ("local", "Endereço"), ("resp", "Engenheiro responsável"),
                        ("crea", "CREA")]:
        if not str(d.get(campo, "")).strip():
            p.append(f"Campo vazio: {nome}")
    n = sum(1 for g in grupos(d) for k, _ in CK[g]["l"] if not d.get("ck", {}).get(k, {}).get("s"))
    if n:
        p.append(f"{n} item(ns) do checklist não avaliado(s)")
    return p


# ============================================================================
# 3. BANCO DE DADOS (todas as consultas filtram por user_id)
# ============================================================================
DB_PATH = os.environ.get("LAUDOS_DB", "laudos.db")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
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
        cur = c.execute("DELETE FROM laudos WHERE id=? AND user_id=?", (laudo_id, user_id))
        if cur.rowcount:
            c.execute("DELETE FROM fotos WHERE laudo_id=? AND user_id=?", (laudo_id, user_id))
            c.execute("DELETE FROM versoes WHERE laudo_id=? AND user_id=?", (laudo_id, user_id))
        return bool(cur.rowcount)


def versoes(user_id, laudo_id):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id,em FROM versoes WHERE laudo_id=? AND user_id=? ORDER BY em DESC", (laudo_id, user_id))]


def add_foto(user_id, laudo_id, item, legenda, imagem):
    with conn() as c:
        if not _dono(c, user_id, laudo_id):
            raise PermissionError("Laudo não pertence ao usuário.")
        c.execute("INSERT INTO fotos(id,laudo_id,user_id,item,legenda,imagem) VALUES(?,?,?,?,?,?)",
                  (uuid.uuid4().hex, laudo_id, user_id, item, legenda, imagem))


def listar_fotos(user_id, laudo_id):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT id,item,legenda,imagem FROM fotos WHERE laudo_id=? AND user_id=?", (laudo_id, user_id))]


def excluir_foto(user_id, foto_id):
    with conn() as c:
        c.execute("DELETE FROM fotos WHERE id=? AND user_id=?", (foto_id, user_id))


# ============================================================================
# 4. LOGIN, ADMINISTRAÇÃO E SENHAS
# ============================================================================
MAX_FALHAS = 5
BLOQUEIO_S = 15 * 60
_MSG = "E-mail ou senha incorretos."


def hash_senha(senha):
    salt = os.urandom(16)
    h = hashlib.scrypt(senha.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return salt.hex() + ":" + h.hex()


def verificar_senha(senha, armazenado):
    try:
        salt, h = armazenado.split(":")
        novo = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(novo.hex(), h)
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
        with conn() as c:
            return c.execute("INSERT INTO users(email,senha_hash,criado,papel,aprovado) VALUES(?,?,?,?,?)",
                             (email, hash_senha(senha), time.time(), papel, int(aprovado))).lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Este e-mail já está cadastrado.")


def garantir_admin():
    """Cria o primeiro administrador a partir de ADMIN_EMAIL e ADMIN_SENHA (só se o e-mail ainda não existir)."""
    email, senha = os.environ.get("ADMIN_EMAIL", "").strip().lower(), os.environ.get("ADMIN_SENHA", "")
    if not email or not senha:
        return False
    with conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            return False
    cadastrar(email, senha, papel="admin", aprovado=True)
    return True


def entrar(email, senha):
    email = (email or "").strip().lower()
    with conn() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if u is None:
            verificar_senha(senha or "", "00:00")  # custo similar
            raise ValueError(_MSG)
        if u["bloqueado_ate"] > time.time():
            raise PermissionError("Conta bloqueada por tentativas erradas. Aguarde ou peça o desbloqueio ao administrador.")
        if verificar_senha(senha or "", u["senha_hash"]):
            if not u["ativo"]:
                raise PermissionError("Conta desativada. Procure o administrador.")
            if not u["aprovado"]:
                raise PermissionError("Conta aguardando autorização do administrador.")
            c.execute("UPDATE users SET falhas=0, bloqueado_ate=0 WHERE id=?", (u["id"],))
            return u["id"]
        falhas = u["falhas"] + 1
        if falhas >= MAX_FALHAS:
            c.execute("UPDATE users SET falhas=0, bloqueado_ate=? WHERE id=?", (time.time() + BLOQUEIO_S, u["id"]))
        else:
            c.execute("UPDATE users SET falhas=? WHERE id=?", (falhas, u["id"]))
    raise ValueError(_MSG)


def perfil(uid):
    """Dados da sessão. Retorna None se a conta foi desativada ou revogada (encerra a sessão)."""
    with conn() as c:
        u = c.execute("SELECT id,email,papel,deve_trocar,ativo,aprovado FROM users WHERE id=?", (uid,)).fetchone()
    if not u or not u["ativo"] or not u["aprovado"]:
        return None
    return {"id": u["id"], "email": u["email"], "papel": u["papel"], "deve_trocar": bool(u["deve_trocar"])}


def trocar_senha(uid, atual, nova):
    if len(nova or "") < 8:
        raise ValueError("A nova senha precisa ter pelo menos 8 caracteres.")
    with conn() as c:
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
    with conn() as c:
        _admin(c, admin_id)
        agora = time.time()
        return [{"id": r["id"], "email": r["email"], "papel": r["papel"], "aprovado": bool(r["aprovado"]),
                 "ativo": bool(r["ativo"]), "bloqueado": r["bloqueado_ate"] > agora, "criado": r["criado"]}
                for r in c.execute("SELECT * FROM users ORDER BY aprovado ASC, criado DESC")]


def aprovar(admin_id, alvo):
    with conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET aprovado=1 WHERE id=?", (alvo,)); _log(c, admin_id, "aprovar", alvo)


def recusar(admin_id, alvo):
    """Remove um cadastro que nunca foi aprovado."""
    with conn() as c:
        _admin(c, admin_id)
        if c.execute("DELETE FROM users WHERE id=? AND aprovado=0", (alvo,)).rowcount:
            _log(c, admin_id, "recusar", alvo)


def desbloquear(admin_id, alvo):
    with conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET falhas=0, bloqueado_ate=0 WHERE id=?", (alvo,)); _log(c, admin_id, "desbloquear", alvo)


def redefinir_senha(admin_id, alvo):
    """Gera senha temporária (mostrada uma vez ao admin). O usuário será obrigado a trocá-la no próximo acesso."""
    if alvo == admin_id:
        raise ValueError("Para a sua própria senha, use 'Alterar senha'.")
    temp = secrets.token_urlsafe(9)
    with conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET senha_hash=?, deve_trocar=1, falhas=0, bloqueado_ate=0 WHERE id=?",
                  (hash_senha(temp), alvo))
        _log(c, admin_id, "redefinir_senha", alvo)
    return temp


def definir_ativo(admin_id, alvo, ativo):
    if alvo == admin_id:
        raise ValueError("Você não pode desativar a própria conta.")
    with conn() as c:
        _admin(c, admin_id)
        c.execute("UPDATE users SET ativo=? WHERE id=?", (int(ativo), alvo))
        _log(c, admin_id, "reativar" if ativo else "desativar", alvo)


def auditoria_recente(admin_id, n=20):
    with conn() as c:
        _admin(c, admin_id)
        return [dict(r) for r in c.execute(
            "SELECT a.em,a.acao,u.email AS admin,t.email AS alvo FROM auditoria a "
            "LEFT JOIN users u ON u.id=a.admin_id LEFT JOIN users t ON t.id=a.alvo_id ORDER BY a.em DESC LIMIT ?", (n,))]


# ============================================================================
# 5. IA (texto técnico do laudo)
# ============================================================================
MODELO = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SISTEMA = ("Você é engenheiro eletricista redigindo laudo técnico em português do Brasil. Use SOMENTE os dados "
           "fornecidos, sem inventar medições, itens ou fatos. Cite apenas as normas listadas em 'normas'. Itens "
           "'não avaliado' devem constar como pendentes. Tom formal e objetivo. Responda apenas com JSON no formato "
           '{"analise":"texto em parágrafos","recs":["recomendação priorizada por risco", "..."],'
           '"conclusao":"conforme, conforme com ressalvas ou não conforme, com justificativa"}')


def resumo(d):
    itens = [{"norma": CK[g]["t"], "item": t, "resultado": d.get("ck", {}).get(k, {}).get("s", "não avaliado"),
              "obs": d.get("ck", {}).get(k, {}).get("o", "")} for g in grupos(d) for k, t in CK[g]["l"]]
    return {"tipo": TIPOS[d["tipo"]], "normas": normas(d), "finalidade": d["finalidade"], "cliente": d["cliente"],
            "local": d["local"], "data": d["data"], "tensao": d["tensao"], "potencia": d["potencia"],
            "esquema_aterramento": d["esquema"], "sistemas_avaliados": d["quadros"], "descricao": d["desc"],
            "itens": itens, "nao_conformidades": nao_conformidades(d),
            "medicoes": {"resistencia_aterramento_ohm": d["res"] or "não medido", "isolacao_min_megohm": d["iso"] or "não medido",
                         "ensaio_especifico": d["cont"] or "não informado", "outras": d["obs"]}}


def gerar_texto(d):
    try:
        import anthropic
        cli = anthropic.Anthropic(timeout=90)
        msg = cli.messages.create(model=MODELO, max_tokens=3000, system=SISTEMA,
                                  messages=[{"role": "user", "content": "DADOS DO LAUDO:\n" + json.dumps(resumo(d), ensure_ascii=False)}])
        txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
        r = json.loads(txt)
        recs = r.get("recs", "")
        return {"analise": r.get("analise", ""), "recs": "\n".join(recs) if isinstance(recs, list) else str(recs),
                "conclusao": r.get("conclusao", "")}
    except json.JSONDecodeError:
        raise RuntimeError("A IA devolveu uma resposta fora do formato. Tente gerar novamente.")
    except Exception as e:
        raise RuntimeError(f"Não foi possível gerar o texto com a IA ({type(e).__name__}). Verifique a chave ANTHROPIC_API_KEY e tente de novo.")


# ============================================================================
# 6. PDF (assinatura do engenheiro em branco)
# ============================================================================
AZUL = colors.HexColor("#0b4f6c")
_ss = getSampleStyleSheet()
TXT = ParagraphStyle("t", parent=_ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13)
NEG = ParagraphStyle("n", parent=TXT, fontName="Helvetica-Bold")
RED = ParagraphStyle("r", parent=TXT, fontName="Helvetica-Bold", textColor=colors.HexColor("#b3261e"))
TIT = ParagraphStyle("tit", parent=TXT, fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=4)
SEC = ParagraphStyle("s", parent=TXT, fontName="Helvetica-Bold", fontSize=10.5, textColor=colors.white,
                     backColor=AZUL, borderPadding=(3, 4, 3, 4), spaceBefore=12, spaceAfter=7)
CEN = ParagraphStyle("c", parent=TXT, alignment=1)


def _s(t):
    """Texto seguro para a fonte Helvetica (sem ômega)."""
    return escape(str(t if t not in (None, "") else "-")).replace("MΩ", " megaohm").replace("Ω", " ohm").replace("\n", "<br/>")


def P(t, st=TXT):
    return Paragraph(_s(t), st)


def gerar_pdf(d, fotos, laudo_id):
    buf, agora = BytesIO(), datetime.now().strftime("%d/%m/%Y %H:%M")

    def rodape(c, doc):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.grey)
        c.drawString(2 * cm, 1.1 * cm, f"Laudo {laudo_id[:8]} · gerado em {agora}")
        c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Página {doc.page}")
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=2 * cm, title=TITULOS[d["tipo"]])
    L = d.get("laudo") or {}
    data_br = "/".join(reversed(str(d["data"]).split("-")))
    f = [P(TITULOS[d["tipo"]], TIT), P(f"{TIPOS[d['tipo']]} · Finalidade: {d['finalidade']}"), Spacer(1, 4)]

    f.append(P("1. Identificação", SEC))
    for k, v in [("Cliente", d["cliente"]), ("CPF/CNPJ", d["doc"]), ("Local", d["local"]), ("Data da inspeção", data_br)]:
        f.append(P(f"{k}: {v or '-'}"))
    f.append(P("2. Normas de referência", SEC)); f.append(P(normas(d)))
    f.append(P("3. Características da instalação", SEC))
    for k, v in [("Tensão nominal", d["tensao"]), ("Potência/demanda", d["potencia"]), ("Esquema de aterramento", d["esquema"]),
                 (LB[d["tipo"]][0], d["quadros"]), ("Descrição", d["desc"])]:
        f.append(P(f"{k}: {v or '-'}"))

    f.append(P("4. Checklist de inspeção", SEC))
    nome = {"C": "Conforme", "NC": "NÃO CONFORME", "NA": "N/A"}
    for g in grupos(d):
        f.append(P(CK[g]["t"], NEG))
        rows = []
        for k, t in CK[g]["l"]:
            v = d.get("ck", {}).get(k, {})
            st = RED if v.get("s") == "NC" else TXT
            rows.append([P(t), P(nome.get(v.get("s"), "Não avaliado"), st), P(v.get("o", ""))])
        tb = Table(rows, colWidths=[8.4 * cm, 2.8 * cm, 5.8 * cm], repeatRows=0)
        tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        f += [tb, Spacer(1, 6)]

    f.append(P("5. Medições e ensaios", SEC))
    eletrico = d["tipo"] in ("bt", "mt")
    if eletrico or d["res"]:
        f.append(P(f"Resistência de aterramento: {d['res'] + ' Ω' if d['res'] else 'não medida'}"))
    if eletrico or d["iso"]:
        f.append(P(f"Isolação mínima: {d['iso'] + ' MΩ' if d['iso'] else 'não medida'}"))
    f.append(P(f"{LB[d['tipo']][1].replace(' (resultado)', '')}: {d['cont'] or 'não informado'}"))
    if d["obs"]:
        f.append(P("Observações: " + d["obs"]))

    f.append(P("6. Não conformidades", SEC))
    nc = nao_conformidades(d)
    if nc:
        for i, x in enumerate(nc, 1):
            f.append(P(f"{i}. [{x['norma']}] {x['item']}" + (f" ({x['obs']})" if x["obs"] else "")))
    else:
        f.append(P("Nenhuma não conformidade registrada."))

    for n, tit, chave in [(7, "Análise técnica", "analise"), (8, "Recomendações", "recs"), (9, "Conclusão", "conclusao")]:
        f.append(P(f"{n}. {tit}", SEC)); f.append(P(L.get(chave) or "Texto não gerado."))

    if fotos:
        f.append(P("10. Registro fotográfico", SEC))
        for i, ft in enumerate(fotos, 1):
            try:
                w, h = ImageReader(BytesIO(ft["imagem"])).getSize()
                esc = min(12 * cm / w, 8 * cm / h)
                f.append(KeepTogether([Image(BytesIO(ft["imagem"]), w * esc, h * esc),
                                       P(f"Foto {i}: {ft['item'] or ''} {ft['legenda'] or ''}"), Spacer(1, 6)]))
            except Exception:
                f.append(P(f"Foto {i}: arquivo de imagem inválido."))

    f.append(KeepTogether([Spacer(1, 2.2 * cm), HRFlowable(width="55%", thickness=.6, color=colors.black, hAlign="CENTER"),
                           Spacer(1, 4), P(d["resp"] or "Engenheiro responsável", ParagraphStyle("b", parent=CEN, fontName="Helvetica-Bold")),
                           P(f"CREA: {d['crea'] or '________'}   ART: {d['art'] or '________'}", CEN),
                           P("Assinatura do engenheiro responsável", CEN)]))
    doc.build(f, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()


# ============================================================================
# 7. INTERFACE (Streamlit)
# ============================================================================
AVISO = "O texto gerado por IA é um rascunho. A revisão e a assinatura do engenheiro responsável são obrigatórias."
S = st.session_state if st else {}


def tela_login():
    st.title("⚡ Laudos Técnicos")
    t1, t2 = st.tabs(["Entrar", "Criar conta"])
    with t1, st.form("login"):
        e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            try:
                uid = entrar(e, s)
                S.uid, S.perfil = uid, perfil(uid)
                st.rerun()
            except (ValueError, PermissionError) as ex:
                st.error(str(ex))
    with t2, st.form("cadastro"):
        e, s = st.text_input("E-mail", key="ce"), st.text_input("Senha (mínimo 8 caracteres)", type="password", key="cs")
        if st.form_submit_button("Criar conta"):
            try:
                cadastrar(e, s)
                st.success("Conta criada. Você poderá entrar assim que o administrador autorizar o acesso.")
            except (ValueError, PermissionError) as ex:
                st.error(str(ex))


def abrir(lid, dados):
    S.lid, S.d, S.pdf = lid, dados, None
    st.rerun()


def tela_lista():
    st.subheader("Meus laudos")
    if st.button("Novo laudo", type="primary"):
        abrir(uuid.uuid4().hex, novo())
    busca = st.text_input("Buscar por cliente ou local").lower()
    itens = [l for l in listar(S.uid) if busca in (l["cliente"] + " " + l["local"]).lower()]
    if not itens:
        st.info("Nenhum laudo encontrado. Crie o primeiro para começar.")
    for l in itens:
        with st.container(border=True):
            st.markdown(f"**{l['cliente'] or 'Sem cliente'}**  \n{l['local']} · {l['data']} · {TIPOS[l['tipo']]}")
            a, b, c = st.columns(3)
            if a.button("Abrir", key="o" + l["id"]):
                abrir(l["id"], obter(S.uid, l["id"]))
            if b.button("Duplicar", key="d" + l["id"]):
                cp = obter(S.uid, l["id"])
                cp.update(laudo=None, ck={}, art="")
                abrir(uuid.uuid4().hex, cp)
            if c.button("Excluir", key="x" + l["id"]):
                excluir(S.uid, l["id"])
                st.rerun()


def txt(d, k, rotulo, area=False, **kw):
    f = st.text_area if area else st.text_input
    d[k] = f(rotulo, d.get(k, ""), key=f"{S.lid}_{k}", **kw)


def sel(d, k, rotulo, opcoes, fmt=str):
    i = opcoes.index(d[k]) if d[k] in opcoes else 0
    d[k] = st.selectbox(rotulo, opcoes, index=i, key=f"{S.lid}_{k}", format_func=fmt)


def salvar():
    salvar_laudo(S.uid, S.lid, S.d)
    st.toast("Laudo salvo.")


def tela_editor():
    d, lid = S.d, S.lid
    t = st.tabs(["Identificação", "Instalação", "Checklist", "Medições", "Fotos", "Laudo"])
    with t[0]:
        sel(d, "tipo", "Tipo de laudo", list(TIPOS), TIPOS.get)
        txt(d, "cliente", "Cliente"); txt(d, "doc", "CPF/CNPJ"); txt(d, "local", "Endereço da instalação")
        d["data"] = st.date_input("Data da inspeção", value=__import__("datetime").date.fromisoformat(d["data"]),
                                  key=f"{lid}_data").isoformat()
        sel(d, "finalidade", "Finalidade", FINALIDADES)
        txt(d, "resp", "Engenheiro responsável"); txt(d, "crea", "CREA"); txt(d, "art", "Nº da ART")
        d["spda"] = st.checkbox("Incluir SPDA (NBR 5419)", d["spda"], key=f"{lid}_spda")
        ant = historico(S.uid, d["cliente"], lid)
        if ant:
            st.caption("Laudos anteriores deste cliente: " + "; ".join(f"{a['data']} ({TIPOS[a['tipo']]})" for a in ant))
    with t[1]:
        txt(d, "tensao", "Tensão nominal (V ou kV)"); txt(d, "potencia", "Potência instalada / demanda (kW)")
        sel(d, "esquema", "Esquema de aterramento", ESQUEMAS)
        txt(d, "quadros", LB[d["tipo"]][0], area=True); txt(d, "desc", "Descrição geral da instalação", area=True)
    with t[2]:
        for g in grupos(d):
            st.markdown(f"**{CK[g]['t']}**")
            for k, texto in CK[g]["l"]:
                v = d["ck"].setdefault(k, {})
                op = ["C", "NC", "NA"]
                nomes = {"C": "Conforme", "NC": "Não conforme", "NA": "Não se aplica"}
                v["s"] = st.radio(texto, op, index=op.index(v["s"]) if v.get("s") in op else None,
                                  format_func=nomes.get, horizontal=True, key=f"{lid}_{k}_s")
                v["o"] = st.text_input("Observação", v.get("o", ""), key=f"{lid}_{k}_o", label_visibility="collapsed",
                                       placeholder="Observação (opcional)")
    with t[3]:
        c1, c2 = st.columns(2)
        with c1: txt(d, "res", "Resistência de aterramento (Ω)")
        with c2: txt(d, "iso", "Isolação mínima (MΩ)")
        txt(d, "cont", LB[d["tipo"]][1]); txt(d, "obs", "Outras medições e observações", area=True)
        for _, ok, msg in med_flags(d):
            (st.success if ok else st.error)(msg)
        st.caption("As referências de 10 Ω e 0,5 MΩ são sinalizações de apoio. A avaliação final é do engenheiro.")
    with t[4]:
        itens = [""] + [k for g in grupos(d) for k, _ in CK[g]["l"]]
        arqs = st.file_uploader("Fotos (JPG ou PNG, até 5 MB cada)", type=["jpg", "jpeg", "png"], accept_multiple_files=True,
                                key=f"{lid}_up")
        item = st.selectbox("Vincular ao item", itens, key=f"{lid}_fi")
        leg = st.text_input("Legenda", key=f"{lid}_fl")
        if st.button("Adicionar fotos") and arqs:
            salvar()
            for a in arqs:
                if a.size > 5 * 1024 * 1024:
                    st.error(f"{a.name} passa de 5 MB.")
                else:
                    add_foto(S.uid, lid, item, leg, a.getvalue())
            st.rerun()
        for f in listar_fotos(S.uid, lid):
            st.image(f["imagem"], caption=f"{f['item']} {f['legenda']}", width=260)
            if st.button("Remover", key="rf" + f["id"]):
                excluir_foto(S.uid, f["id"]); st.rerun()
    with t[5]:
        st.warning(AVISO)
        nc = nao_conformidades(d)
        st.write(f"{len(nc)} não conformidade(s) identificada(s).")
        if st.button("Gerar texto com IA"):
            with st.spinner("Redigindo o laudo…"):
                try:
                    d["laudo"] = gerar_texto(d)
                    for k in ("analise", "recs", "conclusao"):
                        S.pop(f"{lid}_L{k}", None)
                    salvar()
                except RuntimeError as e:
                    st.error(str(e))
        if d.get("laudo"):
            for k, n in [("analise", "Análise técnica"), ("recs", "Recomendações"), ("conclusao", "Conclusão")]:
                d["laudo"][k] = st.text_area(n, d["laudo"].get(k, ""), height=180, key=f"{lid}_L{k}")
            if st.button("Preparar PDF"):
                p = pendencias(d)
                if p:
                    st.warning("Pendências: " + "; ".join(p))
                S.pdf = gerar_pdf(d, listar_fotos(S.uid, lid), lid)
            if S.get("pdf"):
                st.download_button("Baixar PDF", S.pdf, file_name=f"laudo-{(d['cliente'] or 'instalacao').replace(' ', '_')}.pdf",
                                   mime="application/pdf")
    st.divider()
    a, b = st.columns(2)
    if a.button("Salvar", type="primary"):
        salvar()
    if b.button("Voltar à lista"):
        salvar(); S.lid = None; st.rerun()


def tela_trocar(obrigatoria):
    st.subheader("Alterar senha")
    if obrigatoria:
        st.info("Sua senha foi redefinida pelo administrador. Escolha uma senha nova para continuar.")
    with st.form("troca"):
        a, n, n2 = (st.text_input("Senha atual", type="password"), st.text_input("Nova senha", type="password"),
                    st.text_input("Repita a nova senha", type="password"))
        ok = st.form_submit_button("Salvar nova senha")
    if ok:
        try:
            if n != n2:
                raise ValueError("As senhas novas não conferem.")
            trocar_senha(S.uid, a, n)
            S.pop("trocar", None)
            st.rerun()
        except ValueError as ex:
            st.error(str(ex))
    if not obrigatoria and st.button("Cancelar"):
        S.pop("trocar", None)
        st.rerun()


def tela_admin():
    st.subheader("Administração de acessos")
    st.caption("O administrador gerencia contas e senhas, mas não tem acesso aos laudos dos usuários.")
    if S.get("temp"):
        email, senha = S.pop("temp")
        st.success(f"Senha temporária de {email}: `{senha}`. Ela aparece só agora; envie ao usuário, que terá de trocá-la no primeiro acesso.")
    try:
        us = listar_usuarios(S.uid)
        pend = [u for u in us if not u["aprovado"]]
        st.markdown(f"**Aguardando autorização ({len(pend)})**")
        if not pend:
            st.write("Nenhum cadastro pendente.")
        for u in pend:
            with st.container(border=True):
                st.write(u["email"])
                a, b = st.columns(2)
                if a.button("Autorizar", key=f"ap{u['id']}", type="primary"):
                    aprovar(S.uid, u["id"]); st.rerun()
                if b.button("Recusar", key=f"rc{u['id']}"):
                    recusar(S.uid, u["id"]); st.rerun()
        st.markdown("**Usuários**")
        for u in [x for x in us if x["aprovado"]]:
            with st.container(border=True):
                marcas = [("Administrador" if u["papel"] == "admin" else "Usuário"), ("Ativo" if u["ativo"] else "Desativado")]
                if u["bloqueado"]:
                    marcas.append("Bloqueado")
                st.markdown(f"**{u['email']}**  \n{' · '.join(marcas)}")
                if u["id"] != S.uid:
                    a, b, c = st.columns(3)
                    if u["bloqueado"] and a.button("Desbloquear", key=f"db{u['id']}"):
                        desbloquear(S.uid, u["id"]); st.rerun()
                    if b.button("Redefinir senha", key=f"rs{u['id']}"):
                        S.temp = (u["email"], redefinir_senha(S.uid, u["id"])); st.rerun()
                    if c.button("Reativar" if not u["ativo"] else "Desativar", key=f"at{u['id']}"):
                        definir_ativo(S.uid, u["id"], not u["ativo"]); st.rerun()
        with st.expander("Registro de ações"):
            for r in auditoria_recente(S.uid):
                st.write(f"{time.strftime('%d/%m/%Y %H:%M', time.localtime(r['em']))} · {r['admin']} · {r['acao']} · {r['alvo']}")
    except (ValueError, PermissionError) as ex:
        st.error(str(ex))




def run():
    st.set_page_config(page_title="Laudos Técnicos", page_icon="⚡", layout="centered")
    init()
    garantir_admin()
    if "uid" not in S:
        tela_login()
    else:
        p = perfil(S.uid)  # confere a cada ação: conta desativada perde a sessão
        if p is None:
            S.clear(); st.rerun()
        S.perfil = p
        with st.sidebar:
            st.write(p["email"])
            area = st.radio("Área", ["Laudos", "Administração"], key="area") if p["papel"] == "admin" else "Laudos"
            if st.button("Alterar senha"):
                S.trocar = True; st.rerun()
            if st.button("Sair"):
                S.clear(); st.rerun()
        if p["deve_trocar"] or S.get("trocar"):
            tela_trocar(p["deve_trocar"])
        elif area == "Administração":
            tela_admin()
        elif S.get("lid"):
            tela_editor()
        else:
            tela_lista()


def _cli(cmd, email):
    """Recuperação pelo operador do servidor (útil se o único administrador ficar bloqueado)."""
    init()
    email = email.strip().lower()
    with conn() as c:
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
            c.execute("UPDATE users SET senha_hash=?, deve_trocar=1, falhas=0, bloqueado_ate=0 WHERE id=?",
                      (hash_senha(t), u["id"]))
            print("Senha temporária:", t)
    print("Feito:", cmd, email)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] in ("desbloquear", "redefinir", "aprovar", "promover"):
        _cli(sys.argv[1], sys.argv[2])
    elif st is not None:
        run()
    else:
        print("Instale as dependências (pip install -r requirements.txt) e rode: streamlit run app.py")

