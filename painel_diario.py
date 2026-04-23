import csv
import email
import imaplib
import os
import random
import re
import smtplib
import time
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
SENHA_APP = os.getenv("SENHA_APP")
EMAIL_CONTA = os.getenv("EMAIL_CONTA", "seu_email@gmail.com")

ARQUIVO_LEADS = "leads_do_dia.csv"
ARQUIVO_HISTORICO = "historico_envios.csv"

NICHOS = ["plumber", "electrician"]
CIDADES = ["Austin TX", "Phoenix AZ"]
MAX_POR_BUSCA = 20
LIMITE_ENVIOS = 30
INTERVALO_MIN = 120
INTERVALO_MAX = 300

CAMPO_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def buscar_empresas(nicho: str, cidade: str) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": f"{nicho} company in {cidade}", "key": API_KEY}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("results", [])


def buscar_detalhes(place_id: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,website,rating,user_ratings_total",
        "key": API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", {})


def checar_pagespeed(url: str) -> dict:
    api = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": url, "strategy": "mobile", "key": API_KEY}

    try:
        resp = requests.get(api, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        cats = data.get("lighthouseResult", {}).get("categories", {})
        score = int(cats.get("performance", {}).get("score", 0) * 100)

        audits = data.get("lighthouseResult", {}).get("audits", {})
        fcp_ms = audits.get("first-contentful-paint", {}).get("numericValue", 0)
        fcp_s = round(fcp_ms / 1000, 1)
        tem_botao = "tel:" in resp.text.lower()

        return {"score": score, "fcp_segundos": fcp_s, "tem_botao_chamada": tem_botao}
    except Exception as exc:
        print(f"    ⚠️  PageSpeed falhou para {url}: {exc}")
        return {"score": None, "fcp_segundos": None, "tem_botao_chamada": None}


def gerar_pitch(nome: str, fcp, score, tem_botao) -> str:
    problemas = []

    if fcp and fcp > 5:
        problemas.append(f"your site takes {fcp}s to load on mobile")
    if score and score < 50:
        problemas.append("your mobile performance is critical")
    if tem_botao is False:
        problemas.append("there is no visible call button on mobile")

    if not problemas:
        score_texto = score if score is not None else "N/A"
        problemas.append(f"the mobile performance score is {score_texto}/100")

    problema_str = " and ".join(problemas)
    return (
        f"Hi, I checked {nome}'s website and noticed {problema_str}. "
        "Most customers search on their phone, so a slow or hard-to-use site "
        "often sends them to a competitor instead."
    )


def extrair_emails_do_html(html: str) -> list[str]:
    encontrados = []
    for email_addr in CAMPO_EMAIL_RE.findall(html or ""):
        email_limpo = email_addr.strip(".,;:()[]{}<>\"'")
        if email_limpo not in encontrados:
            encontrados.append(email_limpo)
    return encontrados


def extrair_email_do_site(website: str) -> str:
    if not website:
        return ""

    urls_para_tentar = [
        website,
        urljoin(website, "/contact"),
        urljoin(website, "/contact-us"),
        urljoin(website, "/about"),
    ]

    headers = {"User-Agent": "Mozilla/5.0"}

    for url in urls_para_tentar:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            emails = extrair_emails_do_html(resp.text)
            if emails:
                return emails[0]
        except Exception:
            continue

    return ""


def prioridade_para_score(score) -> str:
    if score == 0:
        return "🔥 SEM SITE"
    if isinstance(score, int) and score < 40:
        return "🔴 CRÍTICO"
    return "🟡 RUIM"


def minerar_leads() -> list[dict]:
    if not API_KEY:
        raise SystemExit(
            "GOOGLE_API_KEY não encontrada no .env. Crie a variável antes de rodar."
        )

    leads = []
    vistos = set()

    for nicho in NICHOS:
        for cidade in CIDADES:
            print(f"\n🔍 Minerando {nicho} em {cidade}...")
            try:
                empresas = buscar_empresas(nicho, cidade)
            except Exception as exc:
                print(f"    ⚠️  Falha na busca de empresas em {cidade}: {exc}")
                continue

            for empresa in empresas[:MAX_POR_BUSCA]:
                place_id = empresa.get("place_id")
                nome = empresa.get("name", "")

                if not place_id or place_id in vistos:
                    continue
                vistos.add(place_id)

                try:
                    detalhes = buscar_detalhes(place_id)
                except Exception as exc:
                    print(f"    ⚠️  Falha nos detalhes de {nome}: {exc}")
                    continue

                website = detalhes.get("website", "") or ""
                telefone = detalhes.get("formatted_phone_number", "") or ""
                rating = detalhes.get("rating", "")
                reviews = detalhes.get("user_ratings_total", 0)
                email = extrair_email_do_site(website) if website else ""

                if not website:
                    pitch_abertura = (
                        f"Hi, I noticed {nome} doesn't have a website yet. "
                        "Most customers search online before calling, so you may be "
                        "losing jobs to competitors every day."
                    )
                    leads.append(
                        {
                            "nome": nome,
                            "nicho": nicho,
                            "cidade": cidade,
                            "website": "SEM SITE",
                            "email": email,
                            "telefone": telefone,
                            "avaliacao": rating,
                            "num_avaliacoes": reviews,
                            "score_mobile": 0,
                            "fcp_segundos": "N/A",
                            "botao_chamada": "N/A",
                            "prioridade": "🔥 SEM SITE",
                            "pitch_abertura": pitch_abertura,
                        }
                    )
                    print(f"    🔥 {nome} - SEM SITE")
                    continue

                print(f"    ⚡ Testando {nome}...")
                ps = checar_pagespeed(website)
                score = ps["score"]
                fcp = ps["fcp_segundos"]
                botao = ps["tem_botao_chamada"]

                if score is not None and score >= 65:
                    print(f"       ✅ Score {score} - site ok, pulando")
                    time.sleep(0.3)
                    continue

                prioridade = prioridade_para_score(score if score is not None else -1)
                pitch_abertura = gerar_pitch(nome, fcp, score, botao)

                leads.append(
                    {
                        "nome": nome,
                        "nicho": nicho,
                        "cidade": cidade,
                        "website": website,
                        "email": email,
                        "telefone": telefone,
                        "avaliacao": rating,
                        "num_avaliacoes": reviews,
                        "score_mobile": score if score is not None else "erro",
                        "fcp_segundos": fcp if fcp is not None else "erro",
                        "botao_chamada": botao,
                        "prioridade": prioridade,
                        "pitch_abertura": pitch_abertura,
                    }
                )

                print(f"       🎯 Score {score} | {prioridade} - lead adicionado")
                time.sleep(0.4)

    leads.sort(
        key=lambda lead: (
            0 if lead.get("score_mobile") == 0 else 1,
            lead.get("score_mobile") if isinstance(lead.get("score_mobile"), int) else 999,
        )
    )
    return leads


def salvar_leads_csv(leads: list[dict]) -> None:
    campos = [
        "nome",
        "nicho",
        "cidade",
        "website",
        "email",
        "telefone",
        "avaliacao",
        "num_avaliacoes",
        "score_mobile",
        "fcp_segundos",
        "botao_chamada",
        "prioridade",
        "pitch_abertura",
    ]

    with open(ARQUIVO_LEADS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(leads)


def carregar_leads_para_envio() -> list[dict]:
    try:
        with open(ARQUIVO_LEADS, "r", encoding="utf-8") as f:
            leads = list(csv.DictReader(f))
    except FileNotFoundError:
        raise SystemExit(
            f"Arquivo {ARQUIVO_LEADS} não encontrado. A etapa de mineração falhou."
        )

    def score_ordenacao(lead: dict) -> int:
        valor = lead.get("score_mobile", "")
        try:
            return int(valor)
        except Exception:
            return 999

    leads_criticos = [
        lead
        for lead in leads
        if "CRÍTICO" in (lead.get("prioridade", "") or "").upper()
    ]
    leads_criticos.sort(key=score_ordenacao)
    return leads_criticos[:LIMITE_ENVIOS]


def criar_mensagem(lead: dict) -> MIMEMultipart:
    assunto = f"your {lead.get('nicho', 'home service')} website is losing customers"
    pitch = lead.get("pitch_abertura", "").strip()
    corpo = f"{pitch}\n\nBest, Henry"

    msg = MIMEMultipart()
    msg["From"] = EMAIL_CONTA
    msg["To"] = lead.get("email", "")
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))
    return msg


def registrar_historico(nome_empresa: str, email_destino: str, status_envio: str) -> None:
    novo_arquivo = not os.path.exists(ARQUIVO_HISTORICO)
    with open(ARQUIVO_HISTORICO, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["data_envio", "nome_empresa", "email", "status_envio"],
        )
        if novo_arquivo:
            writer.writeheader()
        writer.writerow(
            {
                "data_envio": time.strftime("%Y-%m-%d %H:%M:%S"),
                "nome_empresa": nome_empresa,
                "email": email_destino,
                "status_envio": status_envio,
            }
        )


def enviar_email(lead: dict) -> bool:
    if not SENHA_APP:
        raise SystemExit("SENHA_APP não encontrada no .env.")

    msg = criar_mensagem(lead)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_CONTA, SENHA_APP)
            server.send_message(msg)
        print(f"✅ Enviado para {lead.get('nome', 'N/A')} - {lead.get('email', '')}")
        return True
    except Exception as exc:
        print(f"❌ Falha ao enviar para {lead.get('nome', 'N/A')}: {exc}")
        return False


def enviar_leads(leads: list[dict]) -> None:
    if not leads:
        print("Nenhum lead crítico com e-mail encontrado para envio.")
        return

    print(f"\n📧 Iniciando envio para até {len(leads)} leads críticos...")

    for indice, lead in enumerate(leads):
        email_destino = (lead.get("email") or "").strip()

        if not email_destino:
            print(f"⚠️  {lead.get('nome', 'N/A')} sem e-mail. Ignorando.")
            continue

        sucesso = enviar_email(lead)
        registrar_historico(
            lead.get("nome", "N/A"),
            email_destino,
            "ok" if sucesso else "falha",
        )

        if indice < len(leads) - 1:
            pausa = random.randint(INTERVALO_MIN, INTERVALO_MAX)
            print(f"⏳ Aguardando {pausa // 60}min {pausa % 60}s...")
            time.sleep(pausa)


def decodificar_assunto(valor) -> str:
    if not valor:
        return ""

    partes = decode_header(valor)
    texto = ""
    for parte, encoding in partes:
        if isinstance(parte, bytes):
            texto += parte.decode(encoding or "utf-8", errors="ignore")
        else:
            texto += parte
    return texto


def checar_respostas() -> None:
    if not SENHA_APP:
        print("⚠️  SENHA_APP não encontrada no .env. Pulando checagem de respostas.")
        return

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_CONTA, SENHA_APP)
        mail.select("inbox")

        status, mensagens = mail.search(None, "UNSEEN")
        if status != "OK":
            print("Nenhuma resposta nova.")
            mail.logout()
            return

        for msg_id in mensagens[0].split():
            status, data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not data or not data[0]:
                continue

            msg = email.message_from_bytes(data[0][1])
            assunto = decodificar_assunto(msg.get("Subject", ""))
            remetente = decodificar_assunto(msg.get("From", ""))

            assunto_lower = assunto.lower()
            if "your" in assunto_lower and "website" in assunto_lower:
                print(f"🎯 RESPOSTA DE LEAD: {assunto} - {remetente}")

        mail.logout()
    except Exception as exc:
        print(f"⚠️  Falha ao checar respostas: {exc}")


def main() -> None:
    print("1) Minerando leads")
    leads = minerar_leads()
    salvar_leads_csv(leads)
    print(f"✅ CSV gerado em {ARQUIVO_LEADS}")

    print("\n2) Preparando envio")
    leads_para_envio = carregar_leads_para_envio()
    print(f"✅ {len(leads_para_envio)} leads críticos selecionados")

    print("\n3) Enviando e-mails")
    enviar_leads(leads_para_envio)

    print("\n4) Checando respostas")
    checar_respostas()

    resposta = input("\nRodar novamente amanhã? Pressione Enter para encerrar. ")
    if resposta.strip().lower() in {"s", "sim", "y", "yes"}:
        print("Certo. Execute o script novamente amanhã.")


if __name__ == "__main__":
    main()
