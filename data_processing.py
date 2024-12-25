import datetime
import queue
import threading

class DataProcessing:
    def __init__(self, data_proc_queue, logger_queue, main_gui):
        # Поток обработки данных
        self.data_process_thread = None
        self.data_process_event = threading.Event()

        # Очереди
        self.data_proc_queue = data_proc_queue
        self.logger_queue = logger_queue

        # Интерфейс пользователя
        self.main_gui = main_gui

        # Паттерны ориона2
        self.req_ack_pattern1 = "ff011f6c" + "6f6c"
        self.req_ack_pattern2 = "ff021f48" + "6f1d"

        # Счетчики
        self.counter_req_ack1 = 0
        self.counter_req_ack2 = 0
        self.counter_search = 0
        self.counter_custom = 0

        self.timestamp = ""

    def start_data_processing(self):
        # Запускаем отдельный поток для обработки данных
        self.data_process_event.clear()
        self.data_process_thread = threading.Thread(target=self.encodings_handler, daemon=True)
        self.data_process_thread.start()

    def stop_data_processing(self):
        # Останавливаем обработку данных
        self.data_process_event.set()
        if self.data_process_thread and self.data_process_thread.is_alive():
            self.data_process_thread.join(timeout=1.0)
        # Очищаем ссылку на поток
        self.data_process_thread = None

    def encodings_handler(self):
        """Обработка кодировок данных."""
        while not self.data_process_event.is_set():
            try:
                # Пытаемся получить данные из очереди
                current_buffer = self.data_proc_queue.get(timeout=1)
                self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
            except queue.Empty:
                continue  # Если нет данных, продолжаем ожидание

            # Значение по умолчанию
            decoded_data = ""
            encoding = self.main_gui.encoding.get()
            if encoding == "O2":
                # Передаем данные напрямую в парсер
                self.orion2_parser(current_buffer.hex())
            elif encoding == "HEX":
                decoded_data = current_buffer.hex()
            elif encoding == "BIN":
                decoded_data = ''.join(format(byte, '08b') for byte in current_buffer)
            elif encoding == "ASCII":
                try:
                    decoded_data = current_buffer.decode("ascii", errors="ignore")
                    while decoded_data and not self.data_process_event.is_set():
                        end = decoded_data.find('\n', 0)
                        if end == -1:
                            additional_buffer = self.data_proc_queue.get(timeout=1)
                            decoded_data += additional_buffer.decode("ascii", errors="ignore")
                            packet = ""
                            self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                        else:
                            # Берём данные до следующего маркера
                            packet = decoded_data[:end]
                            decoded_data = decoded_data[end:]
                        if packet:
                            try:
                                self.logger_queue.put(f"{self.timestamp}  {packet}  ")
                            except queue.Full:
                                self.main_gui.update_message_area(f"Очередь заполнена")
                except UnicodeDecodeError:
                    decoded_data = current_buffer.decode("latin-1", errors="ignore")
            if encoding != "O2" and decoded_data:
                try:
                    self.logger_queue.put(f"{self.timestamp}  {decoded_data}  ")
                except queue.Full:
                    self.main_gui.update_message_area(f"Очередь заполнена")

    def orion2_parser(self, data):
        """Парсер для кодировки Orion2."""
        packet = ""
        while data and not self.data_process_event.is_set():
            # Ищем 'ff', начиная со 2 символа, если буфер достаточно длинный
            next_ff = data.find('ff', 2 if len(data) > 2 else 0)

            if next_ff == -1:
                try:
                    # Пытаемся получить данные из очереди
                    additional_buffer = self.data_proc_queue.get(timeout=1)
                    self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                except queue.Empty:
                    continue  # Если нет данных, продолжаем ожидание
                data += additional_buffer.hex()
                packet = ""
            elif next_ff % 2 != 0:
                # Если длина в битах нечетная, вероятно пакет разбит не правильно (например из-за F на конце пакета)
                # в этом случае дополняем пакет до четного размера и парсинг следующего начинаем со следующего элемента
                packet = data[:next_ff + 1]
                data = data[next_ff + 1:]
            else:
                # Берём данные до следующего маркера
                packet = data[:next_ff]
                data = data[next_ff:]

            if self.main_gui.skip_requests:
                # Подсчёт и удаление шаблонов из целого пакета
                if packet == self.req_ack_pattern1:
                    self.counter_req_ack1 += 1
                    packet = ""
                if packet == self.req_ack_pattern2:
                    self.counter_req_ack2 += 1
                    packet = ""
                # Временный функционал подсчета пакетов SEARCH известной длины
                if next_ff == 14:
                    self.counter_search += 1
                    packet = ""

                custom_pattern = self.main_gui.custom_skip_pattern.get().lower()
                if custom_pattern: # and all(c in "0123456789abcdef"for c in custom_pattern):
                    try:
                        self.counter_custom += packet.count(custom_pattern)
                        packet = packet.replace(custom_pattern, "")
                    except Exception as e:
                        self.main_gui.update_message_area(f"Ошибка обработки пользовательского шаблона: {e}")
                # else:
                #     self.update_message_area("Некорректный пользовательский шаблон")

                self.main_gui.update_counters()
            if packet:
                try:
                    self.logger_queue.put(f"{self.timestamp}  {packet}  ")
                except queue.Full:
                    self.main_gui.update_message_area(f"Очередь заполнена")