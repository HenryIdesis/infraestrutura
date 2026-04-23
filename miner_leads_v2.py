"""
Lead Miner v2 — Encanadores & Eletricistas nos EUA
====================================================
Busca empresas de home services, checa performance do site
e exporta CSV ordenado pelos piores sites (melhores leads).

Requisitos:
    pip install requests python-dotenv

APIs necessárias (ambas GRATUITAS):
    - Google Places API      → https://console.cloud.google.com
    - PageSpeed Insights API → mesma chave do Places

Crie um arquivo .env na mesma pasta com:
    GOOGLE_API_KEY=SuaChaveAqui
"""

import os
import csv
import time
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

# ── Configurações ───────────────────────────────────────────────────────────

NICHOS = [
    "plumber",       # Encanador
    "electrician",   # Eletricista
]

# Cidades médias nos EUA — bom equilíbrio entre volume e competição
CIDADES = [
    "Austin TX",
    "Phoenix AZ",
    "Tampa FL",
    "Denver CO",
    "Charlotte NC",
    "Nashville TN",
    "San Antonio TX",
]

MAX_POR_BUSCA  = 20   # Máximo da Places API por chamada
SCORE_LIMITE   = 65   # Leads com score ABAIXO disso (piores sites = maiores oportunidades)
OUTPUT_CSV     = "leads_homeservices.csv"

# ───────────────────────────────────────────────────────────────────────────


def buscar_empresas(nicho: str, cidade: str) -> list[dict]:
    """Retorna lista de empresas do Google Places."""
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{nicho} company in {cidade}",
        "key": API_KEY,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("results", [])


def buscar_detalhes(place_id: str) -> dict:
    """Retorna website, telefone e avaliação de um lugar."""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,website,rating,user_ratings_total",
        "key": API_KEY,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("result", {})


def checar_pagespeed(url: str) -> dict:
    """Roda PageSpeed Insights mobile e retorna score + tempo de carregamento."""
    api = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": url,
        "strategy": "mobile",  # Mobile é crítico — dono de casa busca no celular
        "key": API_KEY,
    }
    try:
        resp = requests.get(api, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        cats  = data.get("lighthouseResult", {}).get("categories", {})
        score = int(cats.get("performance", {}).get("score", 0) * 100)

        audits = data.get("lighthouseResult", {}).get("audits", {})
        fcp_ms = audits.get("first-contentful-paint", {}).get("numericValue", 0)
        fcp_s  = round(fcp_ms / 1000, 1)

        # Checa se tem botão de chamada visível (heurística básica)
        has_tel = "tel:" in resp.text.lower()

        return {"score": score, "fcp_segundos": fcp_s, "tem_botao_chamada": has_tel}

    except Exception as e:
        print(f"    ⚠️  PageSpeed falhou: {e}")
        return {"score": None, "fcp_segundos": None, "tem_botao_chamada": None}


def gerar_pitch(nome: str, fcp: float, score: int, tem_botao: bool) -> str:
    """
    Gera o pitch personalizado para o e-mail frio.
    Foca em dinheiro perdido, não em tecnologia.
    """
    problemas = []

    if fcp and fcp > 5:
        problemas.append(f"seu site leva {fcp}s para abrir no celular")
    if score and score < 50:
        problemas.append("a performance está crítica")
    if tem_botao is False:
        problemas.append("não tem botão de chamada visível no celular")

    if not problemas:
        problemas.append(f"o score de performance mobile é {score}/100")

    problema_str = " e ".join(problemas)
    return (
        f"Hi, I checked {nome}'s website and noticed {problema_str}. "
        f"Most customers search on their phone — a slow or hard-to-use site "
        f"means they call your competitor instead."
    )


def main():
    if not API_KEY:
        raise SystemExit(
            "❌  GOOGLE_API_KEY não encontrada.\n"
            "   Crie um arquivo .env na mesma pasta com:\n"
            "   GOOGLE_API_KEY=SuaChaveAqui"
        )

    leads = []
    vistos = set()  # Evita duplicatas entre nichos

    for nicho in NICHOS:
        for cidade in CIDADES:
            print(f"\n🔍  '{nicho}' em {cidade}...")
            empresas = buscar_empresas(nicho, cidade)
            print(f"    {len(empresas)} empresas encontradas")

            for empresa in empresas[:MAX_POR_BUSCA]:
                place_id = empresa.get("place_id")
                nome     = empresa.get("name", "")

                if place_id in vistos:
                    continue
                vistos.add(place_id)

                detalhes = buscar_detalhes(place_id)
                website  = detalhes.get("website", "")
                telefone = detalhes.get("formatted_phone_number", "")
                rating   = detalhes.get("rating", "")
                reviews  = detalhes.get("user_ratings_total", 0)

                # Sem site = oportunidade diferente (oferecer criação do zero, preço maior)
                if not website:
                    leads.append({
                        "nome":              nome,
                        "nicho":             nicho,
                        "cidade":            cidade,
                        "website":           "SEM SITE",
                        "telefone":          telefone,
                        "avaliacao":         rating,
                        "num_avaliacoes":    reviews,
                        "score_mobile":      0,
                        "fcp_segundos":      "N/A",
                        "botao_chamada":     "N/A",
                        "prioridade":        "🔥 SEM SITE",
                        "pitch_abertura":    (
                            f"Hi, I noticed {nome} doesn't have a website yet. "
                            f"Most customers search online before calling — "
                            f"you might be losing jobs to competitors every day."
                        ),
                    })
                    print(f"    🔥  {nome} — SEM SITE (oportunidade premium)")
                    continue

                print(f"    ⚡  Testando {nome}...")
                ps    = checar_pagespeed(website)
                score = ps["score"]
                fcp   = ps["fcp_segundos"]
                botao = ps["tem_botao_chamada"]

                # Filtra sites bons (não são leads)
                if score is not None and score >= SCORE_LIMITE:
                    print(f"       ✅  Score {score} — site ok, pulando")
                    time.sleep(0.3)
                    continue

                prioridade = "🔴 CRÍTICO" if (score or 100) < 40 else "🟡 RUIM"
                pitch = gerar_pitch(nome, fcp, score, botao)

                leads.append({
                    "nome":           nome,
                    "nicho":          nicho,
                    "cidade":         cidade,
                    "website":        website,
                    "telefone":       telefone,
                    "avaliacao":      rating,
                    "num_avaliacoes": reviews,
                    "score_mobile":   score if score is not None else "erro",
                    "fcp_segundos":   fcp if fcp is not None else "erro",
                    "botao_chamada":  botao,
                    "prioridade":     prioridade,
                    "pitch_abertura": pitch,
                })

                print(f"       🎯  Score {score} | {fcp}s | {prioridade} — LEAD ADICIONADO")
                time.sleep(0.4)

    # Ordena: sem site primeiro, depois por pior score
    leads.sort(key=lambda x: (
        0 if x["score_mobile"] == 0 else 1,
        x["score_mobile"] if isinstance(x["score_mobile"], int) else 999
    ))

    if leads:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=leads[0].keys())
            writer.writeheader()
            writer.writerows(leads)

        sem_site  = sum(1 for l in leads if l["score_mobile"] == 0)
        criticos  = sum(1 for l in leads if l["prioridade"] == "🔴 CRÍTICO")
        ruins     = sum(1 for l in leads if l["prioridade"] == "🟡 RUIM")

        print(f"\n{'='*55}")
        print(f"✅  {len(leads)} leads exportados → '{OUTPUT_CSV}'")
        print(f"   🔥  Sem site:  {sem_site}")
        print(f"   🔴  Críticos:  {criticos}")
        print(f"   🟡  Ruins:     {ruins}")
        print(f"{'='*55}")
        print("\nTop 5 oportunidades:")
        for l in leads[:5]:
            print(
                f"  • {l['nome']} ({l['cidade']}) | "
                f"Score: {l['score_mobile']} | {l['prioridade']}"
            )
    else:
        print("\n⚠️  Nenhum lead encontrado. Tente aumentar o SCORE_LIMITE.")


if __name__ == "__main__":
    main()