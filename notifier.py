import requests
import logging
import time

logger = logging.getLogger("ERPAutomation.Notifier")

class TelegramNotifier:
    def __init__(self, bot_token, chat_id, ai_api_key=None):
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.ai_api_key = ai_api_key
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.get_updates_url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        self.last_update_id = None

    def send_message(self, message):
        """Gửi tin nhắn qua Telegram Bot."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram Bot Token hoặc Chat ID chưa được cấu hình.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Lỗi gửi thông báo Telegram: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Lỗi kết nối Telegram: {e}")
            return False

    def send_report(self, date_str, total, success, error):
        """Gửi báo cáo tóm tắt tiến độ."""
        msg = f"<b>BÁO CÁO CẬP NHẬT ERP</b>\n"
        msg += f"Ngày: {date_str}\n"
        msg += f"Tổng cộng: {total} dòng\n"
        msg += f"Thành công: {success} dòng\n"
        msg += f"Lỗi/Bỏ qua: {error} dòng\n"
        return self.send_message(msg)

    def ask_ai_about_error(self, error_message):
        """Dùng Google Gemini để phân tích lỗi ERP."""
        if not self.ai_api_key:
            return "Chưa cấu hình AI API Key. Vui lòng kiểm tra lỗi theo cách thủ công."
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.ai_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Tôi đang dùng ERP và gặp lỗi sau: '{error_message}'. Bạn hãy phân tích ngắn gọn nguyên nhân và đề xuất cách xử lý bằng tiếng Việt trong 2-3 câu."
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Lỗi khi gọi AI: {e}"

    def wait_for_user_command(self, timeout=60):
        """Chờ lệnh từ user trên Telegram (ví dụ: 'skip' hoặc 'stop')."""
        if not self.bot_token:
            return "skip" # Default nếu không có bot
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                params = {"timeout": 5}
                if self.last_update_id:
                    params["offset"] = self.last_update_id + 1
                    
                resp = requests.get(self.get_updates_url, params=params, timeout=10).json()
                if resp.get("ok"):
                    for result in resp.get("result", []):
                        self.last_update_id = result["update_id"]
                        msg = result.get("message", {})
                        if str(msg.get("chat", {}).get("id")) == self.chat_id:
                            text = msg.get("text", "").lower().strip()
                            if text in ["skip", "stop", "continue", "ignore"]:
                                return text
            except Exception:
                pass
            time.sleep(2)
        return "timeout"
