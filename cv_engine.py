import cv2
import numpy as np
import pyautogui
import time
import logging

logger = logging.getLogger("ERPAutomation.CVEngine")

class CVEngine:
    def __init__(self, confidence=0.8):
        self.confidence = confidence

    def find_image_on_screen(self, template_path, confidence=None, region=None):
        """
        Tìm hình ảnh trên màn hình và trả về tọa độ trung tâm.
        """
        conf = confidence if confidence else self.confidence
        try:
            # pyautogui.locateCenterOnScreen sử dụng pyscreeze và cv2 ở backend (nếu cài opencv)
            center = pyautogui.locateCenterOnScreen(template_path, confidence=conf, region=region)
            return center
        except pyautogui.ImageNotFoundException:
            return None
        except Exception as e:
            logger.error(f"Lỗi khi tìm ảnh {template_path}: {e}")
            return None

    def wait_and_click(self, template_path, timeout=10, confidence=None, region=None, double_click=False):
        """
        Chờ đợi một hình ảnh xuất hiện và click vào nó.
        """
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            center = self.find_image_on_screen(template_path, confidence, region)
            if center:
                logger.info(f"Đã tìm thấy {template_path} tại {center}. Thực hiện click.")
                if double_click:
                    pyautogui.doubleClick(center.x, center.y)
                else:
                    pyautogui.click(center.x, center.y)
                return True
            time.sleep(0.5)
        
        logger.warning(f"Timeout! Không tìm thấy {template_path} sau {timeout} giây.")
        raise TimeoutError(f"Không tìm thấy phần tử giao diện: {template_path}")

    def is_present(self, template_path, timeout=3, confidence=None, region=None):
        """
        Kiểm tra xem một hình ảnh có đang xuất hiện trên màn hình hay không.
        """
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            center = self.find_image_on_screen(template_path, confidence, region)
            if center:
                return True
            time.sleep(0.5)
        return False
