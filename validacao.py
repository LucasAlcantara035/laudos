"""Validação automática de medições e lista de não conformidades."""
import checklists as C

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
    for g in C.grupos(d):
        for k, t in C.CK[g]["l"]:
            v = d.get("ck", {}).get(k, {})
            if v.get("s") == "NC":
                out.append({"norma": C.CK[g]["t"], "item": t, "obs": v.get("o", "")})
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
    n = sum(1 for g in C.grupos(d) for k, _ in C.CK[g]["l"] if not d.get("ck", {}).get(k, {}).get("s"))
    if n:
        p.append(f"{n} item(ns) do checklist não avaliado(s)")
    return p
