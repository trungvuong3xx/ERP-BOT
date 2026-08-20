import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_for_updates():
    """Kiểm tra xem có bản cập nhật mới trên Github không."""
    try:
        logger.info("Đang kiểm tra bản cập nhật (git fetch)...")
        subprocess.run(["git", "fetch"], check=True, capture_output=True)
        
        result = subprocess.run(["git", "status", "-uno"], capture_output=True, text=True)
        if "Your branch is behind" in result.stdout:
            return True
        return False
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra cập nhật (Bạn đã cài Git chưa?): {e}")
        return False

def apply_update_and_restart():
    """Kéo code mới về và khởi động lại phần mềm."""
    try:
        logger.info("Đang tải bản cập nhật (git pull)...")
        subprocess.run(["git", "pull"], check=True)
        
        logger.info("Đang cài đặt thư viện (nếu có)...")
        if os.path.exists("requirements.txt"):
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
            
        logger.info("Khởi động lại phần mềm...")
        
        # Restart the current process
        os.execv(sys.executable, ['python'] + sys.argv)
    except Exception as e:
        logger.error(f"Lỗi khi tải bản cập nhật: {e}")
        return False
