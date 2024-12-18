import re
import tkinter as tk
from tkinter import ttk
import serial
import threading
import datetime
import crcmod

class SerialMonitorGUI:
    def __init__(self, master):
        self.master = master
        master.title("O2 Monitor")

        # Переменные для настроек COM-порта
        self.port = tk.StringVar(value="COM10")
        self.baudrate = tk.IntVar(value=115200)
        self.databits = tk.IntVar(value=8)
        self.parity = tk.StringVar(value="N")
        self.stopbits = tk.IntVar(value=1)
        self.encoding = tk.StringVar(value="O2")
        self.skip_requests = True

        self.req_pattern1 = "ff011f6c"
        self.req_pattern2 = "ff021f48"
        self.ack_pattern1 = "6f6c"
        self.ack_pattern2 = "6f1d"

        self.counter_req = 0
        self.counter_ack = 0  # Counter for second type of request
        self.custom_skip_pattern = tk.StringVar(value="")  # Для пользовательского шаблона
        self.counter_custom = 0  # Счетчик для пользовательского шаблона

        self.MAX_BUFFER_SIZE = 1024 * 1024  # 1 MB
        self.data_buffer = ""  # Буфер для накопления данных

        # Создание элементов интерфейса
        self.create_widgets()

        # Serial port object
        self.ser = None
        self.serial_thread = None
        self.stop_event = threading.Event()

    def create_widgets(self):
         # Frame для настроек COM-порта
        settings_frame = ttk.LabelFrame(self.master, text="Настройки COM-порта")
        settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Labels и Entry для параметров
        ttk.Label(settings_frame, text="Порт:").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings_frame, textvariable=self.port, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(settings_frame, text="Скорость:").grid(row=1, column=0, sticky="w")
        ttk.Entry(settings_frame, textvariable=self.baudrate, width=10).grid(row=1, column=1, padx=5)

        ttk.Label(settings_frame, text="Биты данных:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.databits, values=[5, 6, 7, 8], width=8).grid(row=2, column=1, padx=5)

        ttk.Label(settings_frame, text="Четность:").grid(row=3, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.parity, values=["N", "E", "O", "M", "S"], width=8).grid(row=3, column=1, padx=5)

        ttk.Label(settings_frame, text="Стоп-биты:").grid(row=4, column=0, sticky="w")
        ttk.Combobox(settings_frame, textvariable=self.stopbits, values=[1, 1.5, 2], width=8).grid(row=4, column=1, padx=5)

        # Кнопка "Открыть порт"
        self.open_button = ttk.Button(settings_frame, text="Открыть порт", command=self.open_port)
        self.open_button.grid(row=5, column=0, columnspan=1, pady=(10, 0))

        # Кнопка "Сохранить лог"
        self.save_log_button = ttk.Button(settings_frame, text="Сохранить лог", command=self.save_log_to_file)
        self.save_log_button.grid(row=7, column=0, columnspan=1, pady=(5, 0))

        # Clear Screen button
        self.clear_button = ttk.Button(settings_frame, text="Очистить экран", command=self.clear_screen)
        self.clear_button.grid(row=7, column=1, pady=(5, 0))

        # Add O2 settings
        o2_frame = ttk.LabelFrame(self.master, text="Функции Орион 2")
        o2_frame.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Сounters display
        self.counter_frame = ttk.LabelFrame(o2_frame, text="Счетчики пропущенных запросов")
        self.counter_frame.grid(row=7, column=0, pady=(5, 0), sticky="w")

        # В counter_frame добавим поле для пользовательского шаблона
        self.custom_pattern_frame = ttk.Frame(self.counter_frame)
        self.custom_pattern_frame.grid(row=2, column=0, padx=5, pady=2, sticky="w")

        ttk.Label(self.custom_pattern_frame, text="Свой шаблон:").grid(row=0, column=0, padx=(0, 5))
        self.custom_pattern_entry = ttk.Entry(self.custom_pattern_frame, textvariable=self.custom_skip_pattern,
                                               width=10)
        self.custom_pattern_entry.grid(row=0, column=1)

        # Добавим счетчик для пользовательского шаблона
        self.counter_label_custom = ttk.Label(self.counter_frame, text="Свой шаблон: 0")
        self.counter_label_custom.grid(row=3, column=0, padx=5, pady=2, sticky="w")

        self.counter_label1 = ttk.Label(self.counter_frame, text="Запросы: 0")
        self.counter_label1.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.counter_label2 = ttk.Label(self.counter_frame, text="Ответы: 0")
        self.counter_label2.grid(row=1, column=0, padx=5, pady=2, sticky="w")

        ttk.Radiobutton(o2_frame, text="O2", variable=self.encoding, value="O2").grid(row=0, column=0,
                                                                                             sticky="w")
        # Кнопка "Пропускать запросы"
        self.skip_button = ttk.Button(o2_frame, text="Включен пропуск запросов", command=self.toggle_skip_requests)
        self.skip_button.grid(row=6, column=0, columnspan=2, pady=(5, 0))

        # Add encoding settings
        encoding_frame = ttk.LabelFrame(self.master, text="Кодировка")
        encoding_frame.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        ttk.Radiobutton(encoding_frame, text="HEX", variable=self.encoding, value="HEX").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="BIN", variable=self.encoding, value="BIN").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(encoding_frame, text="ASCII", variable=self.encoding, value="ASCII").grid(row=3, column=0, sticky="w")

        # Text widget для вывода данных с полосой прокрутки
        text_frame = ttk.Frame(self.master)
        text_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.text_area.yview)

        # Настройка динамического изменения размеров
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)


    def open_port(self):
        try:
            # Закрываем порт, если он уже открыт
            if self.ser and self.ser.is_open:
                self.close_port()

            # Открываем порт с заданными параметрами
            self.ser = serial.Serial(
                port=self.port.get(),
                baudrate=self.baudrate.get(),
                bytesize=self.databits.get(),
                parity=self.parity.get(),
                stopbits=self.stopbits.get(),
                timeout=0.01  # Timeout для чтения данных (1 секунда)
            )

            self.open_button.config(text="Закрыть порт", command=self.close_port)
            self.start_reading()
        except serial.SerialException as e:
            self.text_area.insert(tk.END, f"Ошибка открытия порта: {e}\n")
            return

    def close_port(self):
        try:
            self.stop_event.set()  # Сигнализируем потоку о завершении

            if self.serial_thread and self.serial_thread.is_alive():
                self.serial_thread.join(timeout=1.0)

            if self.ser and self.ser.is_open:
                self.ser.close()

            self.open_button.config(text="Открыть порт", command=self.open_port)
            self.text_area.insert(tk.END, "Порт закрыт.\n")

        except Exception as e:
            self.text_area.insert(tk.END, f"Ошибка закрытия порта: {e}\n")
        finally:
            self.serial_thread = None  # Очищаем ссылку на поток

    def toggle_skip_requests(self):
        self.skip_requests = not self.skip_requests
        if self.skip_requests:
            self.skip_button.config(text="Включен пропуск запросов")
        else:
            self.skip_button.config(text="Пропускать запросы")

    def clear_screen(self):
        self.counter_req = 0
        self.counter_ack = 0
        self.counter_custom = 0
        self.update_counters()
        self.text_area.delete(1.0, tk.END)

    def update_counters(self):
        self.counter_label1.config(text=f"Запросы: {self.counter_req}")
        self.counter_label2.config(text=f"Ответы: {self.counter_ack}")
        custom_pattern = self.custom_skip_pattern.get()
        if custom_pattern:
            self.counter_label_custom.config(text=f"Свой шаблон ({custom_pattern}): {self.counter_custom}")
        else:
            self.counter_label_custom.config(text="Свой шаблон: 0")

    def save_log_to_file(self):
        try:
            # Открываем файл для записи
            with open("log.txt", "w", encoding="utf-8") as log_file:
                log_file.write(self.text_area.get("1.0", tk.END))  # Сохраняем содержимое text_area
            self.text_area.insert(tk.END, "Лог успешно сохранен в файл 'log.txt'.\n")
        except Exception as e:
            self.text_area.insert(tk.END, f"Ошибка при сохранении лога: {e}\n")

    def read_serial(self):
        while not self.stop_event.is_set():
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)

                    if self.encoding.get() == "O2":
                        # Добавляем новые данные в буфер
                        self.data_buffer += data.hex()

                        # Ищем полные пакеты в буфере
                        while 'ff' in self.data_buffer:
                            # Находим индекс следующего маркера начала пакета
                            next_ff = self.data_buffer.find('ff', 2)

                            if next_ff == -1:
                                # Если больше нет маркеров, берём весь оставшийся буфер
                                packet = self.data_buffer
                                self.data_buffer = ""
                            else:
                                # Берём данные до следующего маркера
                                packet = self.data_buffer[:next_ff]
                                self.data_buffer = self.data_buffer[next_ff:]

                            if self.skip_requests:
                                # Подсчёт и удаление шаблонов из целого пакета
                                self.counter_req += packet.count(self.req_pattern1) + packet.count(self.req_pattern2)
                                self.counter_ack += packet.count(self.ack_pattern1) + packet.count(self.ack_pattern2)

                                custom_pattern = self.custom_skip_pattern.get().lower()
                                if custom_pattern:
                                    self.counter_custom += packet.count(custom_pattern)
                                    packet = packet.replace(custom_pattern, "")

                                packet = packet.replace(self.req_pattern1, "")
                                packet = packet.replace(self.ack_pattern1, "")
                                packet = packet.replace(self.req_pattern2, "")
                                packet = packet.replace(self.ack_pattern2, "")

                                self.master.after(0, self.update_counters)

                            if packet.strip():
                                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                                formatted_data = f"{timestamp}: {packet}"
                                self.master.after(0, self.update_text_area, formatted_data)
                    elif self.encoding.get() == "HEX":
                        decoded_data = data.hex()
                    elif self.encoding.get() == "BIN":
                        decoded_data = ''.join(format(byte, '08b') for byte in data)
                    else:  # ASCII
                        try:
                            decoded_data = data.decode("ascii", errors="ignore")
                        except UnicodeDecodeError:
                            decoded_data = data.decode("latin-1", errors="ignore")


                    if self.encoding.get() != "O2":
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")
                        formatted_data = f"{timestamp}: {decoded_data}"
                        self.master.after(0, self.update_text_area, formatted_data)

                    if len(self.data_buffer) > self.MAX_BUFFER_SIZE:
                        self.data_buffer = self.data_buffer[-self.MAX_BUFFER_SIZE:]


            except serial.SerialException as e:
                self.master.after(0, self.update_text_area, f"Ошибка чтения данных: {e}\n")
                self.close_port()
                break


    def update_text_area(self, formatted_data):
        self.text_area.insert(tk.END, formatted_data + "\n")
        self.text_area.see(tk.END)  # Автоматическая прокрутка к концу


    def start_reading(self):
        self.stop_event.clear()  # Сбрасываем флаг остановки
        self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.serial_thread.start()


root = tk.Tk()
app = SerialMonitorGUI(root)
root.mainloop()