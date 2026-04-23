# simple_sender.py
import csv
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── CONFIGURAÇÕES (Preencha aqui) ──────────────────────────────────────────
CSV_FILE = "leads.csv"  # Seu CSV gerado pelo miner_leads_v2.py
EMAIL_CONTA = "seu_email@gmail.com"  # Substitua
SENHA_APP = "sua_senha_de_app"      # Senha de App do Gmail
INTERVALO_MIN = 120  # 2 minutos entre envios
INTERVALO_MAX = 300  # 5 minutos entre envios
MAX_ENVIOS = 30      # Limite diário seguro para começar
# ────────────────────────────────────────────────────────────────────────────

def criar_mensagem(lead, remetente):
    """Monta o e-mail personalizado com o pitch do CSV."""
    # Usa o pitch gerado pelo miner_leads_v2.py ou cria um genérico
    pitch = lead.get("pitch_abertura", "Your website loads slowly on mobile and you may be losing customers.")
    assunto = f"your {lead.get('nicho', 'home service')} website is losing customers"
    
    corpo = f"""Hi {lead.get('nome', 'there')},

{pitch}

I build ultra-fast websites for {lead.get('nicho', 'home service')}s that help you get more calls.

If you're curious, I can send you a free preview of a new site for your business. Just reply "yes".

Best,
Henry"""

    msg = MIMEMultipart()
    msg["From"] = remetente
    msg["To"] = lead.get("email", "")
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))
    return msg

def main():
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))
    
    leads = [l for l in leads if l.get("email")]  # Filtra quem tem e-mail
    print(f"📧 Enviando e-mails para {min(MAX_ENVIOS, len(leads))} leads...")
    
    for i, lead in enumerate(leads[:MAX_ENVIOS]):
        msg = criar_mensagem(lead, EMAIL_CONTA)
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(EMAIL_CONTA, SENHA_APP)
                server.send_message(msg)
            print(f"✅ {lead.get('nome', 'N/A')} - Enviado")
        except Exception as e:
            print(f"❌ {lead.get('nome', 'N/A')} - Falha: {e}")
        
        if i < min(MAX_ENVIOS, len(leads)) - 1:
            pausa = random.randint(INTERVALO_MIN, INTERVALO_MAX)
            print(f"⏳ Aguardando {pausa // 60}min...")
            time.sleep(pausa)
    
    print("✅ Rodada de envios concluída.")

if __name__ == "__main__":
    main()