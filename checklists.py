"""Checklists, normas e rótulos. Revise os itens com um engenheiro antes do uso profissional."""

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
