import csv
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Configurações ───────────────────────────────────────────────────────────
CSV_FILE = "leads_homeservices.csv"  # Arquivo gerado pelo miner_leads_v2.py

# Suas contas de e-mail (Google Workspace ou Gmail com "senha de app")
# Distribua os envios entre várias contas para evitar limites
CONTAS_EMAIL = [
    {"email": "henry@seudominio1.com", "senha": "sua_senha_de_app"},
    {"email": "henry@seudominio2.com", "senha": "sua_senha_de_app"},
    {"email": "henry@seudominio3.com", "senha": "sua_senha_de_app"},
]

INTERVALO_MIN = 120  # segundos entre envios (2 min)
INTERVALO_MAX = 300  # (5 min)
MAX_ENVIOS_POR_CONTA = 60  # Limite diário por conta
# ────────────────────────────────────────────────────────────────────────────


def criar_mensagem(lead: dict, conta_email: str) -> MIMEMultipart:
    """Cria o e-mail frio personalizado baseado no lead."""
    nome_empresa = lead.get("nome", "there")
    cidade = lead.get("cidade", "your city")
    nicho = lead.get("nicho", "home service")
    pitch = lead.get("pitch_abertura", "")
    score = lead.get("score_mobile", "N/A")

    subject = f"your {nicho} website is losing customers"

    # Corpo do e-mail focado em dinheiro perdido, não em tecnologia
    body = f"""Hi,

I was looking for a {nicho} in {cidade} and came across {nome_empresa}.

{pitch}

I specialize in building ultra-fast websites for {nicho}s that load instantly and turn visitors into calls.

If you're curious, I can send you a free preview of how your new site could look in just a few hours. No commitment, no cost to check it out.

Just reply "yes" and I'll take care of the rest.

Best,
Henry"""

    msg = MIMEMultipart()
    msg["From"] = conta_email
    msg["To"] = lead.get("email", "")
    msg["Subject"] = subject
    
    msg.attach(MIMEText(body, "plain", "utf-8"))
    return msg


def enviar_email(conta: dict, lead: dict) -> bool:
    """Envia um e-mail usando SMTP do Google e retorna True se bem-sucedido."""
    try:
        msg = criar_mensagem(lead, conta["email"])
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(conta["email"], conta["senha"])
            server.send_message(msg)
        
        print(f"✅ Enviado para {lead.get('nome', 'N/A')} via {conta['email']}")
        return True
        
    except Exception as e:
        print(f"❌ Falha ao enviar para {lead.get('nome', 'N/A')}: {e}")
        return False


def main():
    """Função principal."""
    # Lê o CSV de leads
    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            leads = list(reader)
    except FileNotFoundError:
        raise SystemExit(f"❌ Arquivo {CSV_FILE} não encontrado. Rode o miner_leads_v2.py primeiro.")

    if not leads:
        raise SystemExit("⚠️ Nenhum lead no arquivo CSV.")

    # Filtra leads sem e-mail (não terão como receber)
    leads = [l for l in leads if l.get("email")]
    if not leads:
        raise SystemExit("⚠️ Nenhum lead com e-mail disponível.")

    print(f"📧 Iniciando envio de {len(leads)} e-mails...")
    
    contador_por_conta = {conta["email"]: 0 for conta in CONTAS_EMAIL}
    total_enviados = 0
    total_falhas = 0
    
    # Log de envios
    with open("log_envios.txt", "a", encoding="utf-8") as log:
        log.write(f"\n--- Nova rodada em {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        
        for i, lead in enumerate(leads):
            # Seleciona a conta com menor número de envios (distribuição balanceada)
            conta = min(CONTAS_EMAIL, key=lambda c: contador_por_conta[c["email"]])
            
            # Respeita o limite diário por conta
            if contador_por_conta[conta["email"]] >= MAX_ENVIOS_POR_CONTA:
                print(f"⚠️ Conta {conta['email']} atingiu limite diário. Pulando...")
                continue
            
            sucesso = enviar_email(conta, lead)
            
            if sucesso:
                contador_por_conta[conta["email"]] += 1
                total_enviados += 1
                log.write(f"ENVIADO | {time.strftime('%H:%M:%S')} | {lead.get('nome', 'N/A')} | via {conta['email']}\n")
            else:
                total_falhas += 1
                log.write(f"FALHA   | {time.strftime('%H:%M:%S')} | {lead.get('nome', 'N/A')} | via {conta['email']}\n")
            
            # Intervalo aleatório entre envios (comportamento humano)
            if i < len(leads) - 1:
                pausa = random.randint(INTERVALO_MIN, INTERVALO_MAX)
                print(f"⏳ Aguardando {pausa // 60}min {pausa % 60}s...")
                time.sleep(pausa)
    
    print("\n" + "="*50)
    print(f"✅ Enviados: {total_enviados}")
    print(f"❌ Falhas:   {total_falhas}")
    print(f"📊 Distribuição por conta: {contador_por_conta}")
    print("="*50)


if __name__ == "__main__":
    main()