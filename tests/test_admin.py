import os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db, auth


class Admin(unittest.TestCase):
    def setUp(self):
        self._old = db.DB_PATH
        db.DB_PATH = os.path.join(tempfile.mkdtemp(), "a.db")
        db.init()
        self.adm = auth.cadastrar("adm@x.com", "senhaadmin1", papel="admin", aprovado=True)
        self.u = auth.cadastrar("u@x.com", "senhauser1")

    def tearDown(self):
        db.DB_PATH = self._old

    def test_conta_nova_exige_autorizacao(self):
        with self.assertRaises(PermissionError): auth.entrar("u@x.com", "senhauser1")
        with self.assertRaises(ValueError): auth.entrar("u@x.com", "errada")  # não revela o estado da conta
        auth.aprovar(self.adm, self.u)
        self.assertEqual(auth.entrar("u@x.com", "senhauser1"), self.u)

    def test_usuario_comum_nao_administra(self):
        auth.aprovar(self.adm, self.u)
        for f in (lambda: auth.listar_usuarios(self.u), lambda: auth.aprovar(self.u, self.u),
                  lambda: auth.desbloquear(self.u, self.adm), lambda: auth.redefinir_senha(self.u, self.adm),
                  lambda: auth.definir_ativo(self.u, self.adm, False)):
            with self.assertRaises(PermissionError): f()

    def test_desbloqueio_e_redefinicao(self):
        auth.aprovar(self.adm, self.u)
        for _ in range(auth.MAX_FALHAS):
            with self.assertRaises(ValueError): auth.entrar("u@x.com", "errada")
        with self.assertRaises(PermissionError): auth.entrar("u@x.com", "senhauser1")
        auth.desbloquear(self.adm, self.u)
        self.assertEqual(auth.entrar("u@x.com", "senhauser1"), self.u)
        temp = auth.redefinir_senha(self.adm, self.u)
        with self.assertRaises(ValueError): auth.entrar("u@x.com", "senhauser1")
        self.assertEqual(auth.entrar("u@x.com", temp), self.u)
        self.assertTrue(auth.perfil(self.u)["deve_trocar"])
        auth.trocar_senha(self.u, temp, "novasenha99")
        self.assertFalse(auth.perfil(self.u)["deve_trocar"])
        with self.assertRaises(ValueError): auth.redefinir_senha(self.adm, self.adm)

    def test_desativar_encerra_sessao_e_log(self):
        auth.aprovar(self.adm, self.u)
        auth.definir_ativo(self.adm, self.u, False)
        self.assertIsNone(auth.perfil(self.u))
        with self.assertRaises(PermissionError): auth.entrar("u@x.com", "senhauser1")
        with self.assertRaises(ValueError): auth.definir_ativo(self.adm, self.adm, False)
        self.assertTrue(any(r["acao"] == "desativar" for r in auth.auditoria_recente(self.adm)))

    def test_recusar_so_remove_pendente(self):
        auth.recusar(self.adm, self.u)
        self.assertEqual([x["email"] for x in auth.listar_usuarios(self.adm)], ["adm@x.com"])
        auth.recusar(self.adm, self.adm)
        self.assertEqual(len(auth.listar_usuarios(self.adm)), 1)

    def test_admin_inicial_por_ambiente(self):
        os.environ["ADMIN_EMAIL"], os.environ["ADMIN_SENHA"] = "novo@x.com", "senhainicial1"
        try:
            self.assertTrue(auth.garantir_admin()); self.assertFalse(auth.garantir_admin())
        finally:
            del os.environ["ADMIN_EMAIL"], os.environ["ADMIN_SENHA"]
        self.assertEqual(auth.perfil(auth.entrar("novo@x.com", "senhainicial1"))["papel"], "admin")

    def test_migracao_banco_antigo(self):
        import sqlite3
        db.DB_PATH = os.path.join(tempfile.mkdtemp(), "old.db")
        c = sqlite3.connect(db.DB_PATH)
        c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL, falhas INTEGER DEFAULT 0, bloqueado_ate REAL DEFAULT 0, criado REAL)")
        c.execute("INSERT INTO users(email,senha_hash,criado) VALUES('velho@x.com',?,0)", (auth.hash_senha("senhavelha1"),)); c.commit(); c.close()
        db.init()
        self.assertIsNotNone(auth.entrar("velho@x.com", "senhavelha1"))  # conta antiga continua aprovada


if __name__ == "__main__":
    unittest.main()
