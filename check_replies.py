# check_replies.py
import imaplib
import email
from email.header import decode_header
import re

# ── CONFIGURAÇÕES ──────────────────────────────────────────────────────────
EMAIL_CONTA = "seu_email@gmail.com"
SENHA_APP = "sua_senha_de_app"
# ────────────────────────────────────────────────────────────────────────────

def buscar_respostas():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL_CONTA, SENHA_APP)
    mail.select("inbox")
    
    # Busca e-mails não lidos das últimas 24h
    status, messages = mail.search(None, '(UNSEEN SINCE {date}")'.format(
        date=time.strftime("%d-%b-%Y")))
    
    if status != "OK":
        print("Nenhuma resposta nova.")
        return []
    
    leads_interessados = []
    for msg_id in messages[0].split():
        status, data = mail.fetch(msg_id, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])
        
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8")
        
        # Verifica se o assunto contém referência ao nosso e-mail
        if "your" in subject.lower() and "website" in subject.lower():
            from_ = msg["From"]
            print(f"🎯 Resposta de interesse: {from_} - {subject}")
            # Extrai o nome da empresa do campo "To" do nosso e-mail original
            # (você pode refinar essa lógica)
            leads_interessados.append(from_)
    
    mail.logout()
    return leads_interessados

if __name__ == "__main__":
    interessados = buscar_respostas()
    if interessados:
        print(f"\n🚀 {len(interessados)} leads para contatar imediatamente com o mockup!")
    else:
        print("📭 Nenhuma resposta de lead ainda.")