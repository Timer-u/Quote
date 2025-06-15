import os
import requests
import gnupg
import smtplib
import logging
import tempfile
from email.mime.text import MIMEText
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 从环境变量获取敏感信息
ALAPI_TOKEN = os.getenv("ALAPI_TOKEN")
RECIPIENT = os.getenv("RECIPIENT_EMAIL")


def get_quote():
    """从 API 获取励志名言"""
    url = "https://v3.alapi.cn/api/mingyan"
    params = {"token": ALAPI_TOKEN, "format": "json"}
    headers = {"Content-Type": "application/json"}

    try:
        logger.info("请求API获取名言...")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data.get("code") == 200:
            quote = data["data"]["content"]
            author = data["data"]["author"]
            logger.info(f"获取到名言: {quote[:20]}... - {author}")
            return f"{quote}\n\n——{author}"
        logger.warning(f"API响应异常: {data}")
        return "获取名言失败，请检查API状态"
    except Exception as e:
        logger.error(f"API请求错误: {str(e)}")
        return f"API请求错误: {str(e)}"


def create_email_content():
    """创建邮件内容（中文格式）"""
    quote = get_quote()
    date_str = datetime.now().strftime("%Y年%m月%d日")
    content = (
        f"亲爱的同学，高考加油！\n\n"
        f"✨ 今日励志名言 ({date_str})：\n\n"
        f"{quote}\n\n"
        f"—— 来自您的备考助手\n\n"
        f"注：此邮件使用PGP端到端加密，签名密钥ID: 171EBC63CE71906C"
    )
    logger.info("邮件内容创建完成")
    return content


def encrypt_message(content):
    """使用PGP加密消息"""
    try:
        logger.info("初始化GPG...")
        # 创建临时目录用于存储密钥环
        with tempfile.TemporaryDirectory() as temp_dir:
            # 初始化GPG实例
            gpg = gnupg.GPG(gnupghome=temp_dir)

            public_key = os.getenv("PGP_PUBLIC_KEY")
            logger.info("导入公钥...")
            import_result = gpg.import_keys(public_key)

            if not import_result.fingerprints:
                raise ValueError("公钥导入失败")

            logger.info("加密内容...")
            # 直接传递文本内容（GPG会自动处理编码）
            encrypted = gpg.encrypt(
                content, recipients=["171EBC63CE71906C"], always_trust=True, sign=False
            )

            if not encrypted.ok:
                error_msg = f"加密失败: {encrypted.status}\n{encrypted.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info("内容加密成功")
            return str(encrypted)
    except Exception as e:
        logger.exception("加密过程中发生异常")
        raise


def send_email(encrypted_content):
    """通过Gmail发送加密邮件"""
    try:
        logger.info("准备发送邮件...")
        msg = MIMEText(encrypted_content, _charset="utf-8")
        msg["Subject"] = "📚 您的每日备考励志名言"
        msg["From"] = os.getenv("GMAIL_USER")
        msg["To"] = RECIPIENT
        msg["X-PGP-Key-ID"] = "171EBC63CE71906C"

        logger.info(f"连接到Gmail服务器...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"))
            server.send_message(msg)
            logger.info("邮件发送成功")
    except Exception as e:
        logger.exception("邮件发送失败")
        raise


if __name__ == "__main__":
    try:
        content = create_email_content()
        encrypted_content = encrypt_message(content)
        send_email(encrypted_content)
    except Exception as e:
        logger.critical(f"程序执行失败: {str(e)}")
        raise
