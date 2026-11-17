"""Testes com dados de exemplo nos formatos das fontes oficiais.
Rode com:  python -m unittest discover -s tests
"""
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# usa um banco temporário para não sujar os dados reais
_tmp = tempfile.mkdtemp()
from app import db  # noqa: E402
db.ARQUIVO = Path(_tmp) / "teste.db"

from app import caminhos, coleta, curriculo, golpes, pontuacao  # noqa: E402
from app.config import carregar_perfil  # noqa: E402
from app.fontes import dol_h2b, jobbank, lmia  # noqa: E402
from app.ocupacoes import classificar, conjuge_pode_trabalhar_canada  # noqa: E402
from app.planilha import ler_xlsx  # noqa: E402

PERFIL = {
    "nome": "Teste", "estado_civil": "casado", "filhos": [{"idade": 5}, {"idade": 8}, {"idade": 11}],
    "ingles": "basico", "pais_cidadania": "Brasil",
    "escolaridade": {"nivel": "superior_cursando", "curso": "Ciência da Computação"},
    "experiencias": [{"categoria": "construcao", "cargo": "Ajudante", "anos": 3},
                     {"categoria": "eletrica", "cargo": "Ajudante elétrica", "anos": 1}],
    "cursos": [{"categoria": "soldagem", "nome": "Curso de soldador", "horas": 160}],
    "preferencias": {"score_minimo": 40},
}


class TestOcupacoes(unittest.TestCase):
    def test_classificar(self):
        self.assertEqual(classificar("Welder - MIG"), "soldagem")
        self.assertEqual(classificar("Construction Laborer", "47-2061.00"), "construcao")
        self.assertEqual(classificar("x", "72106-Welders and related machine operators"), "soldagem")
        self.assertEqual(classificar("Landscape Laborer", "37-3011"), "servicos_gerais")

    def test_sowp(self):
        self.assertTrue(conjuge_pode_trabalhar_canada("72106"))
        self.assertFalse(conjuge_pode_trabalhar_canada("75110"))
        self.assertFalse(conjuge_pode_trabalhar_canada("62020"))  # TEER 2 fora da lista
        self.assertTrue(conjuge_pode_trabalhar_canada("21231"))   # TEER 1


class TestH2B(unittest.TestCase):
    def _zip(self, dados):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("h2b.json", json.dumps(dados))
        return buf.getvalue()

    def test_formato_maiusculo(self):
        rec = {"CASE_NUMBER": "H-400-26300-123456", "JOB_TITLE": "CONSTRUCTION LABORER",
               "SOC_CODE": "47-2061.00", "SOC_TITLE": "Construction Laborers",
               "EMPLOYER_BUSINESS_NAME": "ACME BUILDERS LLC", "WORKSITE_CITY": "AUSTIN", "WORKSITE_STATE": "TX",
               "WAGE_OFFERED_FROM": "21.50", "WAGE_PER": "Hour", "BEGIN_DATE": "2027-03-01", "END_DATE": "2027-11-30",
               "TOTAL_WORKERS_NEEDED": "15", "AGENT_ATTORNEY_CITY": "MIAMI"}
        regs = dol_h2b._ler_pacote(self._zip([rec]))
        v = dol_h2b.converter(regs[0])
        self.assertEqual(v["id"], "h2b:H-400-26300-123456")
        self.assertEqual(v["cidade"], "Austin")
        self.assertEqual(v["estado"], "TX")
        self.assertEqual(v["salario_hora"], 21.5)
        self.assertEqual(v["vagas_qtd"], 15)
        self.assertIn("seasonaljobs.dol.gov/jobs/H-400-26300-123456", v["url"])

    def test_formato_aninhado_camel(self):
        rec = {"caseNumber": "H-400-26301-000001", "jobTitle": "Welder", "empBusinessName": "Steel Co",
               "jobInfo": {"jobCity": "Mobile", "jobState": "AL", "wageFrom": "45000", "per": "Year"},
               "socCode": "51-4121"}
        v = dol_h2b.converter(dol_h2b._ler_pacote(self._zip({"data": [rec]}))[0])
        self.assertEqual(v["titulo"], "Welder")
        self.assertEqual(v["empresa"], "Steel Co")
        self.assertEqual(v["cidade"], "Mobile")
        self.assertAlmostEqual(v["salario_hora"], 21.63, places=1)


RSS = b"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Job Bank</title>
<item><title>welder</title><link>https://www.jobbank.gc.ca/jobsearch/jobposting/50702906?source=rss</link>
<description>&lt;ul&gt;&lt;li&gt;Employer: Prairie Steel Ltd.&lt;/li&gt;&lt;li&gt;Location: Regina (SK)&lt;/li&gt;&lt;li&gt;Salary: $30.00 hourly&lt;/li&gt;&lt;/ul&gt;</description>
<pubDate>Mon, 09 Nov 2026 10:00:00 EST</pubDate></item>
<item><title>Construction labourer - Build Co - Halifax (NS)</title><link>https://www.jobbank.gc.ca/jobsearch/jobposting/50700001</link>
<description>$22.00 hourly</description><pubDate>Sun, 08 Nov 2026 10:00:00 EST</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Job Bank</title>
<entry><title type="html">welder</title><link rel="alternate" type="text/html" href="https://www.jobbank.gc.ca/jobsearch/jobposting/50702906"/>
<id>https://www.jobbank.gc.ca/jobsearch/jobSearchRSSfeed?id=3716626</id><updated>2026-11-10T13:22:00Z</updated>
<summary type="html">&lt;strong&gt;Job number:&lt;/strong&gt; 3716626&lt;br /&gt;&lt;strong&gt;Location:&lt;/strong&gt; Timmins (ON)&lt;br /&gt;&lt;strong&gt;Employer:&lt;/strong&gt; MWB Contracting Inc.&lt;br /&gt;&lt;strong&gt;Salary:&lt;/strong&gt; $30.00 to $52.00 hourly (To be negotiated)</summary></entry>
</feed>"""

ANUNCIO = """<html><body><h1>welder</h1><p>Posted on Job Bank</p>
<h2>Job details</h2><p>$30.00 hourly / 40 hours per week</p>
<p>Who can apply to this job? Only apply to this job if: You are a Canadian citizen, a permanent or temporary resident of Canada.
<b>Who can apply to this job?</b> The employer accepts applications from: Canadian citizens and permanent or temporary residents of Canada.
Other candidates with or without a valid Canadian work permit.</p><p>If you are not legally authorized to work in Canada, you should search for jobs advertised by employers who are recruiting international candidates instead.</p>
<p>This employer is requesting a Labour Market Impact Assessment (LMIA).</p><p>NOC 2021: 72106</p></body></html>"""


class TestJobBank(unittest.TestCase):
    def test_rss(self):
        itens = jobbank.ler_rss(RSS)
        self.assertEqual(len(itens), 2)
        b = jobbank._extrair_basico(itens[0])
        self.assertEqual(b["empresa"], "Prairie Steel Ltd.")
        self.assertEqual(b["cidade"], "Regina")
        self.assertEqual(b["estado"], "SK")
        b2 = jobbank._extrair_basico(itens[1])
        self.assertEqual(b2["empresa"], "Build Co")
        self.assertEqual(b2["estado"], "NS")
        self.assertEqual(jobbank.salario_por_hora("$62,400 annually"), 30.0)

    def test_anuncio(self):
        r = jobbank.analisar_anuncio(ANUNCIO)
        self.assertEqual(r["aceita_estrangeiro"], 1)
        self.assertEqual(r["lmia"], "solicitado")
        self.assertEqual(r["codigo_ocupacao"], "72106")

    def test_atom(self):
        itens = jobbank.ler_rss(ATOM)
        self.assertEqual(len(itens), 1)
        b = jobbank._extrair_basico(itens[0])
        self.assertEqual(b["empresa"], "MWB Contracting Inc.")
        self.assertEqual((b["cidade"], b["estado"]), ("Timmins", "ON"))
        self.assertEqual(jobbank.salario_por_hora(b["salario_txt"]), 30.0)
        self.assertEqual(itens[0]["pub"], "2026-11-10")

    def test_anuncio_formato_novo(self):
        html = ("<h3>Who can apply for this job?</h3><p>The employer accepts applications from:</p><ul><li>Canadian "
                "citizens and permanent or temporary residents of Canada</li><li>other candidates, with or without a "
                "valid Canadian work permit</li></ul>")
        self.assertEqual(jobbank.analisar_anuncio(html)["aceita_estrangeiro"], 1)

    def test_anuncio_so_locais(self):
        html = ("<p>You can apply if you are: Canadian citizens, permanent residents, temporary residents with a valid "
                "work permit. Do not apply if you are not authorized to work in Canada.</p><p>If you are not legally "
                "authorized to work in Canada, you should search for jobs advertised by employers who are recruiting "
                "international candidates instead.</p><p>welder NOC 72106</p>")
        r = jobbank.analisar_anuncio(html)
        self.assertEqual(r["aceita_estrangeiro"], 0)
        self.assertEqual(r["codigo_ocupacao"], "72106")


class TestLMIA(unittest.TestCase):
    def test_planilha(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Employers who were issued a positive LMIA, 2026Q2"])
        ws.append([])
        ws.append(["Province/Territory", "Program Stream", "Employer", "Address", "Occupation",
                   "Incorporate Status", "Approved LMIAs", "Approved Positions"])
        ws.append(["Saskatchewan", "High-wage", "Prairie Steel Ltd.", "Regina, SK S4P 1A1",
                   "72106-Welders and related machine operators", "Incorporated", 1, 4])
        ws.append(["", "", "Café Bom", "Regina, SK", "65201-Food counter attendants", "Incorporated", 1, 2])
        ws.append(["Alberta", "Low-wage", "Build Co", "Calgary, AB", "75110-Construction trades helpers and labourers", "", 1, 3])
        buf = io.BytesIO()
        wb.save(buf)
        linhas = ler_xlsx(buf.getvalue())
        self.assertEqual(linhas[2][2], "Employer")
        itens = lmia.processar_tabela(buf.getvalue(), "2026T2", "x", {"soldagem", "construcao"})
        self.assertEqual(len(itens), 2)
        self.assertEqual(itens[0]["regiao"], "Saskatchewan")
        self.assertEqual(itens[0]["posicoes"], 4)
        self.assertEqual(itens[1]["categoria"], "construcao")

    def test_recursos(self):
        pacote = {"result": {"resources": [
            {"name": "2025Q4-Employers Who Were Issued a Positive LMIA", "format": "XLSX", "language": ["en"], "url": "a_en.xlsx", "created": "2026-03-16"},
            {"name": "2025Q4-Employeurs ... positive", "format": "XLSX", "language": ["fr"], "url": "a_fr.xlsx", "created": "2026-03-16"},
            {"name": "2026Q1-Employers Who Were Issued a Positive LMIA", "format": "XLSX", "language": ["en"], "url": "b_en.xlsx", "created": "2026-06-16"},
            {"name": "2026Q1-Employers Who Were Issued a Negative LMIA", "format": "XLSX", "language": ["en"], "url": "n.xlsx", "created": "2026-06-16"},
        ]}}
        r = lmia.recursos_recentes(pacote, 4)
        self.assertEqual([x["url"] for x in r], ["b_en.xlsx", "a_en.xlsx"])


class TestNovasFontes(unittest.TestCase):
    def test_perm(self):
        import openpyxl
        from app.fontes import perm
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["CASE_NUMBER", "CASE_STATUS", "DECISION_DATE", "EMP_BUSINESS_NAME", "EMP_CITY", "EMP_STATE",
                   "PWD_SOC_CODE", "PWD_SOC_TITLE", "JOB_TITLE", "JOB_OPP_WAGE_FROM", "JOB_OPP_WAGE_PER",
                   "PRIMARY_WORKSITE_CITY", "PRIMARY_WORKSITE_STATE"])
        ws.append(["G-1", "Certified", "45964", "Steel Co", "Mobile", "AL", "51-4121.00", "Welders", "Welder", "45760", "Year", "MOBILE", "AL"])
        ws.append(["G-2", "Certified - Expired", "45990", "Steel Co", "Mobile", "AL", "51-4121.00", "Welders", "Welder", "24", "Hour", "MOBILE", "AL"])
        ws.append(["G-3", "Denied", "45990", "Bad Co", "X", "TX", "51-4121.00", "Welders", "Welder", "24", "Hour", "X", "TX"])
        ws.append(["G-4", "Certified", "45990", "Soft Co", "X", "TX", "15-1252.00", "Software", "Developer", "60", "Hour", "X", "TX"])
        arq = Path(_tmp) / "perm.xlsx"; wb.save(arq)
        itens = perm.processar(arq, "FY2026 T3", "x", {"soldagem"}, log=lambda *a: None)
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["casos"], 2)
        self.assertEqual(itens[0]["salario_min"], 22.0)
        self.assertEqual(itens[0]["ultima_decisao"], "2025-11-29")
        self.assertEqual(itens[0]["locais"], "Mobile, AL")

    def test_aip_normalizar(self):
        from app.fontes.aip import normalizar
        self.assertIn("mary brown s", normalizar("10113 Newfoundland Ltd. o/a Mary Brown's"))
        self.assertEqual(normalizar("Zutphen Equipment Inc."), "zutphen equipment")

    def test_aviso_texto(self):
        from app import avisos
        con = db.conectar()
        v = {"id": "teste:aviso", "fonte": "t", "pais": "CA", "titulo": "welder", "empresa": "A&B", "cidade": "Regina",
             "estado": "SK", "aceita_estrangeiro": 1, "url": "http://x", "descricao": "", "codigo_ocupacao": "72106",
             "salario_txt": "$30 hourly"}
        db.salvar_vaga(con, coleta._preparar(v, PERFIL)); con.commit()
        enviados = []
        original = avisos.enviar
        avisos.enviar = lambda tok, chat, txt: enviados.append(txt)
        try:
            n = avisos.avisar_novas(con, {"ativo": True, "token": "t", "chat_id": "c", "nota_minima": 10}, "2000-01-01", log=lambda *a: None)
        finally:
            avisos.enviar = original
            con.execute("DELETE FROM vagas WHERE id='teste:aviso'"); con.commit()
        self.assertGreaterEqual(n, 1)
        self.assertIn("A&amp;B", enviados[0])


class TestGolpes(unittest.TestCase):
    def test_golpe(self):
        r = golpes.analisar("Vaga garantida no Canadá com LMIA! Taxa de processamento de R$ 8.000 via PIX. "
                            "Chame no WhatsApp, últimas vagas. contato: agencia.canada@gmail.com")
        self.assertEqual(r["nivel"], "ALTO")
        self.assertGreaterEqual(len(r["alertas"]), 4)

    def test_legitimo(self):
        r = golpes.analisar("Welder needed. Apply via jobbank.gc.ca. Employer pays all LMIA costs. "
                            "Candidates with or without a valid Canadian work permit are welcome.")
        self.assertEqual(r["nivel"], "BAIXO")


class TestPontuacaoCaminhos(unittest.TestCase):
    def test_score(self):
        v = {"pais": "CA", "titulo": "Welder", "codigo_ocupacao": "72106", "aceita_estrangeiro": 1,
             "lmia": "solicitado", "salario_hora": 30}
        s, m = pontuacao.pontuar(v, PERFIL)
        self.assertGreaterEqual(s, 60)
        v2 = {"pais": "CA", "titulo": "Software developer", "aceita_estrangeiro": 0}
        s2, _ = pontuacao.pontuar(v2, PERFIL)
        self.assertEqual(s2, 0)

    def test_caminhos(self):
        r = caminhos.avaliar(PERFIL)
        ids = [c["id"] for c in r["caminhos"]]
        self.assertIn("us_h2b", ids)
        self.assertIn("ca_lmia", ids)
        self.assertTrue(r["plano"])
        r2 = caminhos.avaliar(carregar_perfil())  # perfil real do arquivo
        self.assertTrue(r2["caminhos"])

    def test_curriculo(self):
        html = curriculo.gerar_curriculo(PERFIL, {"titulo": "Welder", "categoria": "soldagem", "pais": "CA"})
        self.assertIn("Welding Course", html)
        self.assertNotIn("casado", html)
        carta = curriculo.gerar_carta(PERFIL, {"id": "jobbank:123", "titulo": "Welder", "empresa": "X", "pais": "CA",
                                               "categoria": "soldagem"})
        self.assertIn("Job Bank #123", carta)


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer
        from app.servidor import Painel
        con = db.conectar()
        for i, (pais, tit, aceita) in enumerate([("CA", "Welder", 1), ("US", "Construction Laborer", 1),
                                                  ("CA", "Cook", 0)]):
            v = {"id": f"teste:{i}", "fonte": "teste", "pais": pais, "titulo": tit, "empresa": "E",
                 "aceita_estrangeiro": aceita, "url": "http://x", "descricao": "", "codigo_ocupacao": ""}
            db.salvar_vaga(con, coleta._preparar(v, PERFIL))
        con.commit()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Painel)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _get(self, rota):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.porta}{rota}") as r:
            return r.read().decode("utf-8")

    def _post(self, rota, dados):
        req = urllib.request.Request(f"http://127.0.0.1:{self.porta}{rota}", data=json.dumps(dados).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def test_rotas(self):
        self.assertIn("RotaNorte", self._get("/"))
        resumo = json.loads(self._get("/api/resumo"))
        self.assertEqual(resumo["vagas"], 3)
        vagas = json.loads(self._get("/api/vagas?so_estrangeiro=1&min=0"))
        self.assertEqual(len(vagas), 2)
        self.assertTrue(self._post("/api/candidatura", {"vaga_id": "teste:0", "status": "aplicado"})["ok"])
        cand = json.loads(self._get("/api/vagas?status=_com&min=0"))
        self.assertEqual(len(cand), 1)
        self.assertIn("Resume", self._get("/doc/curriculo?id=teste:0"))
        self.assertIn("Dear Hiring Manager", self._get("/doc/carta?id=teste:0"))
        self.assertEqual(self._post("/api/golpe", {"texto": "pague taxa de LMIA por pix"})["nivel"], "ALTO")
        self.assertTrue(json.loads(self._get("/api/caminhos"))["caminhos"])
        csv = self._get("/api/exportar.csv?min=0&so_estrangeiro=")
        self.assertIn("Welder", csv)
        self.assertIn("itens", json.loads(self._get("/api/perm")))
        self.assertIn("links", json.loads(self._get("/api/aip")))
        r = self._post("/api/vaga_manual", {"texto": "Welder job, send $500 fee by western union", "titulo": "Welder"})
        self.assertGreaterEqual(r["risco_golpe"], 40)


if __name__ == "__main__":
    unittest.main()
