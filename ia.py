"""Geração do texto técnico com a API da Anthropic. A chave vem de ANTHROPIC_API_KEY."""
import json, os, re
import checklists as C, validacao as V

MODELO = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SISTEMA = ("Você é engenheiro eletricista redigindo laudo técnico em português do Brasil. Use SOMENTE os dados "
           "fornecidos, sem inventar medições, itens ou fatos. Cite apenas as normas listadas em 'normas'. Itens "
           "'não avaliado' devem constar como pendentes. Tom formal e objetivo. Responda apenas com JSON no formato "
           '{"analise":"texto em parágrafos","recs":["recomendação priorizada por risco", "..."],'
           '"conclusao":"conforme, conforme com ressalvas ou não conforme, com justificativa"}')


def resumo(d):
    itens = [{"norma": C.CK[g]["t"], "item": t, "resultado": d.get("ck", {}).get(k, {}).get("s", "não avaliado"),
              "obs": d.get("ck", {}).get(k, {}).get("o", "")} for g in C.grupos(d) for k, t in C.CK[g]["l"]]
    return {"tipo": C.TIPOS[d["tipo"]], "normas": C.normas(d), "finalidade": d["finalidade"], "cliente": d["cliente"],
            "local": d["local"], "data": d["data"], "tensao": d["tensao"], "potencia": d["potencia"],
            "esquema_aterramento": d["esquema"], "sistemas_avaliados": d["quadros"], "descricao": d["desc"],
            "itens": itens, "nao_conformidades": V.nao_conformidades(d),
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
