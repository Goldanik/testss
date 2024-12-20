import queue
import threading

class FileLogger:
    def __init__(self, filename="log.txt", log_queue=None):
        self.log_file = filename
        self.log_queue = log_queue or queue.Queue()  # Используем переданную очередь или создаем новую
        self.log_thread = None
        self.log_stop_event = threading.Event()

    def start_log_thread(self):
        """Запускаем поток для записи лога"""
        # Проверяем что файл можно открыть
        try:
            with open(self.log_file, "a", encoding="utf-8", buffering=1):
                pass  # Проверяем, что файл доступен для записи
        except Exception as e:
            self.master.after(0, self.update_message_area, f"Ошибка открытия файла лога: {e}")
            return
        # Проверяем что поток был остановлен перед повторным открытием
        if self.log_thread and self.log_thread.is_alive():
            self.master.after(0, self.update_message_area, "Поток записи уже запущен.")
            return

        self.log_stop_event.clear()
        self.log_thread = threading.Thread(target=self.log_data_to_file, daemon=True)
        self.log_thread.start()

    def stop_log_thread(self):
        """Останавливаем поток записи лога"""
        self.log_stop_event.set()
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join(timeout=1.0)
        # Ожидаем завершения потока
        if self.log_thread and self.log_thread.is_alive():
            self.log_thread.join()

    def log_data_to_file(self):
        """Фоновый поток для записи лога"""
        while not self.log_stop_event.is_set():
            try:
                # Пытаемся получить данные из очереди
                data = self.log_queue.get(timeout=1)
            except queue.Empty:
                continue # Если нет данных, продолжаем ожидание

            try:
                # Пишем данные в файл
                with open(self.log_file, "a", encoding="utf-8", buffering=2) as log_file:
                    log_file.write(data + "\n")
            except Exception as e:
                self.master.after(0, self.update_message_area, f"Ошибка записи лога: {e}")  # Вызов в главном потоке
