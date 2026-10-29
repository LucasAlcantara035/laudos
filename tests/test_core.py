import os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LAUDOS_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import db, auth, checklists as C, validacao as V, pdf
db.DB_PATH = os.environ["LAUDOS_DB"]


class Core(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init()
        cls.a = auth.cadastrar("a@x.com", "senhaforte1", aprovado=True)
        cls.b = auth.cadastrar("b@x.com", "senhaforte2", aprovado=True)

    def laudo(self, tipo="bt", cliente="Cliente A"):
        d = C.novo(tipo); d["cliente"] = cliente; return d

    def test_isolamento(self):
        d = self.laudo()
        db.salvar_laudo(self.a, "L1", d)
        from PIL import Image
        import io
        imagem = io.BytesIO()
        Image.new("RGB", (2, 2), "white").save(imagem, "PNG")
        db.add_foto(self.a, "L1", "bt1", "foto", imagem.getvalue())
        self.assertIsNotNone(db.obter(self.a, "L1"))
        self.assertIsNone(db.obter(self.b, "L1"))
        self.assertEqual(db.listar(self.b), [])
        self.assertFalse(db.excluir(self.b, "L1"))
        self.assertEqual(db.listar_fotos(self.b, "L1"), [])
        with self.assertRaises(PermissionError): db.salvar_laudo(self.b, "L1", d)
        with self.assertRaises(PermissionError): db.add_foto(self.b, "L1", "i", "l", imagem.getvalue())
        self.assertEqual(len(db.listar_fotos(self.a, "L1")), 1)
        self.assertIsNotNone(db.obter(self.a, "L1"))

    def test_login(self):
        self.assertEqual(auth.entrar("A@x.com", "senhaforte1"), self.a)
        with self.assertRaises(ValueError): auth.entrar("a@x.com", "errada")
        with self.assertRaises(ValueError): auth.cadastrar("a@x.com", "senhaforte1", aprovado=True)
        with self.assertRaises(ValueError): auth.cadastrar("c@x.com", "curta")
        c = auth.cadastrar("c@x.com", "senhaforte3", aprovado=True)
        for _ in range(auth.MAX_FALHAS):
            with self.assertRaises(ValueError): auth.entrar("c@x.com", "errada")
        with self.assertRaises(PermissionError): auth.entrar("c@x.com", "senhaforte3")

    def test_validacao(self):
        d = self.laudo(); d["res"] = "12,5"; d["iso"] = "0.3"; d["ck"] = {"bt1": {"s": "NC", "o": "sem DR"}}
        self.assertEqual(len(V.nao_conformidades(d)), 3)
        d["res"], d["iso"] = "5", "2"
        self.assertEqual(len(V.nao_conformidades(d)), 1)

    def test_pdf_todos_os_tipos(self):
        for t in C.TIPOS:
            d = self.laudo(t); d["spda"] = True; d["res"] = "11"; d["resp"] = "Eng. Teste"
            d["laudo"] = {"analise": "Texto com acentuação ç ã é.", "recs": "1. Item\n2. Item", "conclusao": "Conforme com ressalvas."}
            out = pdf.gerar_pdf(d, [], "abcdef123456")
            self.assertTrue(out.startswith(b"%PDF") and len(out) > 2000, t)

    def test_pdf_com_foto(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow ausente")
        import io
        b = io.BytesIO(); Image.new("RGB", (400, 300), "gray").save(b, "PNG")
        out = pdf.gerar_pdf(self.laudo(), [{"item": "bt1", "legenda": "Quadro", "imagem": b.getvalue()}], "xyz12345")
        self.assertTrue(out.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
