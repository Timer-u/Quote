import logging
import os
import smtplib
import tempfile
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
from email import encoders

import gnupg
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 从环境变量获取敏感信息
ALAPI_TOKEN = os.getenv("ALAPI_TOKEN")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
PGP_PUBLIC_KEY = os.getenv("PGP_PUBLIC_KEY")
RECIPIENT_KEY_ID = "171EBC63CE71906C"


def get_quote():
    """从 API 获取励志名言"""
    url = "https://v3.alapi.cn/api/mingyan"
    params = {"token": ALAPI_TOKEN, "format": "json"}

    try:
        logger.info("请求API获取名言...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == 200:
            quote = data["data"]["content"]
            author = data["data"]["author"]
            logger.info(f"获取到名言: {quote[:20]}... - {author}")
            return f"{quote}\n\n——{author}"
        logger.warning(f"API响应异常: {data}")
        return "获取名言失败，请检查API状态"
    except requests.exceptions.JSONDecodeError as e:
        logger.error(f"API响应非JSON格式: {str(e)}")
        logger.error(f"收到的响应内容: {response.text}")
        return "API响应格式错误，无法解析名言。"
    except Exception as e:
        logger.error(f"API请求错误: {str(e)}")
        return f"API请求错误: {str(e)}"


def create_email_content():
    """创建邮件内容"""
    quote = get_quote()
    date_str = datetime.now().strftime("%Y年%m月%d日")
    content = f"今日励志名言 ({date_str})：\n\n" f"{quote}\n\n"
    logger.info("邮件内容创建完成")
    return content


def encrypt_message(content):
    """使用PGP加密消息"""
    try:
        logger.info("初始化GPG...")
        with tempfile.TemporaryDirectory() as temp_dir:
            # 指定 UTF-8 编码来支持中文字符
            gpg = gnupg.GPG(gnupghome=temp_dir, encoding="utf-8")

            logger.info("导入公钥...")
            import_result = gpg.import_keys(PGP_PUBLIC_KEY)

            if not import_result.fingerprints:
                raise ValueError("公钥导入失败")

            logger.info(f"使用 Key ID {RECIPIENT_KEY_ID} 加密内容...")
            encrypted = gpg.encrypt(
                content,  # 正确处理中文
                recipients=[RECIPIENT_KEY_ID],
                always_trust=True,
                armor=True,  # 输出ASCII armor格式
                sign=False,
            )

            if not encrypted.ok:
                error_msg = f"加密失败: {encrypted.status}\n{encrypted.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info("内容加密成功")
            return str(encrypted)  # 返回ASCII armor格式的字符串
    except Exception as e:
        logger.exception("加密过程中发生异常")
        raise


def send_email(encrypted_data):
    """通过 Gmail 发送符合RFC 3156的加密邮件"""
    try:
        logger.info("准备发送符合RFC 3156的加密邮件...")

        # 创建 multipart/encrypted 容器
        msg = MIMEMultipart(_subtype="encrypted", protocol="application/pgp-encrypted")
        msg["Subject"] = "每日励志名言"
        msg["From"] = GMAIL_USER
        msg["To"] = RECIPIENT_EMAIL
        msg["Date"] = formatdate(localtime=True)  # 使用formatdate确保正确的日期格式
        msg["Message-ID"] = make_msgid(domain=GMAIL_USER.split("@")[1])

        # 第一部分：控制信息 (application/pgp-encrypted)
        control_part = MIMEBase("application", "pgp-encrypted")
        control_part.set_payload("Version: 1\r\n")
        msg.attach(control_part)

        # 第二部分：加密数据 (application/octet-stream)
        encrypted_part = MIMEBase("application", "octet-stream")
        encrypted_part.set_payload(encrypted_data)
        # 设置文件名
        encrypted_part.add_header(
            "Content-Disposition", "inline", filename="encrypted.asc"
        )
        msg.attach(encrypted_part)

        # 发送邮件
        logger.info(f"连接到Gmail服务器...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
            logger.info("邮件发送成功")
    except Exception as e:
        logger.exception("邮件发送失败")
        raise


if __name__ == "__main__":
    # 检查必要的环境变量
    required_vars = [
        "ALAPI_TOKEN",
        "RECIPIENT_EMAIL",
        "GMAIL_USER",
        "GMAIL_APP_PASSWORD",
        "PGP_PUBLIC_KEY",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.critical(f"缺少必要的环境变量: {', '.join(missing_vars)}")
    else:
        try:
            content = create_email_content()
            encrypted_data = encrypt_message(content)
            send_email(encrypted_data)
        except Exception as e:
            logger.critical(f"程序执行失败: {str(e)}")
