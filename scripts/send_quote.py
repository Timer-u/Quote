import os
import requests
import gnupg
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# 从环境变量获取敏感信息
ALAPI_TOKEN = os.getenv("ALAPI_TOKEN")
RECIPIENT = os.getenv("RECIPIENT_EMAIL")


def get_quote():
    """从 API 获取励志名言"""
    url = "https://v3.alapi.cn/api/mingyan"
    params = {"token": ALAPI_TOKEN, "format": "json"}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data.get("code") == 200:
            quote = data["data"]["content"]
            author = data["data"]["author"]
            return f"{quote}\n\n——{author}"
        return "获取名言失败，请检查API状态"
    except Exception as e:
        return f"API请求错误: {str(e)}"


def create_email_content():
    """创建邮件内容（中文格式）"""
    quote = get_quote()
    date_str = datetime.now().strftime("%Y年%m月%d日")
    return f"✨ 今日励志名言 ({date_str})：\n\n" f"{quote}\n\n"


def encrypt_message(content):
    """使用PGP加密消息"""
    gpg = gnupg.GPG()
    public_key = os.getenv("PGP_PUBLIC_KEY")
    import_result = gpg.import_keys(public_key)

    if not import_result.fingerprints:
        raise ValueError("公钥导入失败")

    encrypted = gpg.encrypt(
        content,
        recipients=["171EBC63CE71906C"],  # 使用 ECDH 密钥ID
        always_trust=True,
        sign=False,
    )
    if not encrypted.ok:
        raise RuntimeError(f"加密失败: {encrypted.status}")
    return str(encrypted)


def send_email(encrypted_content):
    """通过Gmail发送加密邮件"""
    msg = MIMEText(encrypted_content, _charset="utf-8")
    msg["Subject"] = "📚 您的每日备考励志名言"
    msg["From"] = os.getenv("GMAIL_USER")
    msg["To"] = RECIPIENT
    msg["X-PGP-Key-ID"] = "171EBC63CE71906C"  # 帮助邮件客户端识别密钥

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"))
        server.send_message(msg)


if __name__ == "__main__":
    content = create_email_content()
    encrypted_content = encrypt_message(content)
    send_email(encrypted_content)
    print("邮件发送成功")
