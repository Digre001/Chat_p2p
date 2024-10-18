import sys
import json
import hashlib
import socket
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QSpacerItem, QSizePolicy, QTextEdit
from PyQt5.QtCore import Qt, QTimer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import random
import time

USER_DATA = 'user_data2.json'
BROADCAST_IP = "192.168.178.255"  # Indirizzo broadcast
PORT = 5000  # Porta UDP usata per la comunicazione
BUFFER_SIZE = 1024
PEER_TIMEOUT = 10  # Timeout per considerare un peer offline
PEER_LIST = {}  # Dizionario per tracciare i peer attivi e l'ultimo tempo in cui sono stati visti

class UserManager:
    def __init__(self, user_data_file=USER_DATA):
        self.user_data_file = user_data_file

    def load_users(self):
        try:
            with open(self.user_data_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_users(self, users):
        with open(self.user_data_file, 'w') as file:
            json.dump(users, file, indent=4)

    def register_user(self, username, password):
        users = self.load_users()
        if username in users:
            return False, "Username già in uso"
        else:
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.BestAvailableEncryption(password.encode())
            )
            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            users[username] = {
                'password': password_hash,
                'private_key': private_key_bytes.decode(),
                'public_key': public_key.decode(),
                'status': 'inactive'  # Lo stato è inattivo dopo la registrazione
            }
            self.save_users(users)
            return True, f"Registrazione completata per {username}"

    def login_user(self, username, password):
        users = self.load_users()
        if username not in users:
            return False, "Utente non trovato!"
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != users[username]['password']:
            return False, "Password errata!"
        users[username]['status'] = 'active'  # Cambia lo stato in attivo al login
        self.save_users(users)
        return True, f"Accesso effettuato per {username}!"

    def update_user_status(self, username, status):
        users = self.load_users()
        if username in users:
            users[username]['status'] = status
            self.save_users(users)

    def get_active_users(self):
        users = self.load_users()
        active_users = [user for user, data in users.items() if data.get('status') == 'active']
        return active_users

    def update_peer_status(self, peer_ip, status):
        users = self.load_users()
        for user, data in users.items():
            if data.get('ip_address') == peer_ip:
                data['status'] = status
                self.save_users(users)
                break


class ChatWindow(QWidget):
    def __init__(self, username, user_manager):
        super().__init__()
        self.username = username
        self.user_manager = user_manager

        # Usa una porta casuale per evitare conflitti sulla stessa macchina
        self.port = random.randint(5001, 6000)  # Porta casuale tra 5001 e 6000

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Abilita il broadcast

        self.sock.bind(('0.0.0.0', self.port))  # Ascolta sulla porta assegnata
        self.init_ui()
        self.start_receiving()
        self.start_broadcasting()

    def init_ui(self):
        self.setWindowTitle("Chat P2P")
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Inserisci il tuo messaggio...")
        layout.addWidget(self.message_input)

        self.btn_send = QPushButton("Invia")
        self.btn_send.clicked.connect(self.send_message)
        layout.addWidget(self.btn_send)

        self.message_input.returnPressed.connect(self.send_message)

        self.active_users_display = QLabel("Utenti attivi: Nessuno")
        layout.addWidget(self.active_users_display)

        self.setLayout(layout)

    def send_message(self):
        message = self.message_input.text()
        if message == "!UTENTI_ATTIVI":
            active_users = self.user_manager.get_active_users()
            self.chat_display.append(f"Utenti attivi: {', '.join(active_users)}")
        elif message:
            full_message = f"{self.username}: {message}"
            self.chat_display.append(full_message)
            self.sock.sendto(full_message.encode(), ('<broadcast>', self.port))  # Invia a tutti
        self.message_input.clear()

    def start_receiving(self):
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def start_broadcasting(self):
        threading.Thread(target=self.broadcast_presence, daemon=True).start()
        threading.Thread(target=self.check_peer_timeout, daemon=True).start()

    def broadcast_presence(self):
        while True:
            try:
                # Invia un messaggio che include il nome utente e lo stato
                message = f"{self.username}:active"
                self.sock.sendto(message.encode(), (BROADCAST_IP, self.port))
                time.sleep(5)
            except Exception as e:
                print(f"Errore invio broadcast: {e}")
                break

    def receive_messages(self):
        while True:
            data, addr = self.sock.recvfrom(BUFFER_SIZE)
            message = data.decode()

            # Parsing del messaggio per ottenere l'utente e lo stato
            if ":" in message:
                user, status = message.split(":")
                if status == "active":
                    PEER_LIST[addr[0]] = time.time()  # Aggiorna il tempo di avvistamento
                    self.active_users.add(user)  # Aggiungi l'utente alla lista degli utenti attivi
                    self.update_active_users_display()
                elif status == "inactive":
                    if user in self.active_users:
                        self.active_users.remove(user)
                        self.update_active_users_display()

            self.chat_display.append(message)

    def check_peer_timeout(self):
        while True:
            current_time = time.time()
            for peer_ip, last_seen in list(PEER_LIST.items()):
                if current_time - last_seen > PEER_TIMEOUT:  # Se è passato troppo tempo dall'ultimo avvistamento
                    del PEER_LIST[peer_ip]
                    self.user_manager.update_peer_status(peer_ip, 'inactive')
            time.sleep(5)

    def update_active_users_display(self):
        # Aggiorna la visualizzazione degli utenti attivi nell'interfaccia
        if self.active_users:
            self.active_users_display.setText(f"Utenti attivi: {', '.join(self.active_users)}")
        else:
            self.active_users_display.setText("Utenti attivi: Nessuno")

    def closeEvent(self, event):
        # Imposta lo stato su inattivo alla chiusura e manda il messaggio di disconnessione
        self.user_manager.update_user_status(self.username, 'inactive')
        message = f"{self.username}:inactive"
        self.sock.sendto(message.encode(), (BROADCAST_IP, self.port))
        self.sock.close()  # Assicurati di chiudere il socket
        event.accept()


class LoginApp(QWidget):
    def __init__(self, user_manager):
        super().__init__()
        self.user_manager = user_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.label_username = QLabel("Username:")
        layout.addWidget(self.label_username)
        self.entry_username = QLineEdit()
        layout.addWidget(self.entry_username)

        self.label_password = QLabel("Password:")
        layout.addWidget(self.label_password)
        self.entry_password = QLineEdit()
        self.entry_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.entry_password)

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addItem(spacer)

        self.btn_login = QPushButton("Login")  # Prima login
        self.btn_login.clicked.connect(self.login_user)
        layout.addWidget(self.btn_login)

        self.btn_register = QPushButton("Registrati")  # Poi registrati
        self.btn_register.clicked.connect(self.register_user)
        layout.addWidget(self.btn_register)

        self.setLayout(layout)
        self.setWindowTitle("Login System")

    def register_user(self):
        username = self.entry_username.text()
        password = self.entry_password.text()

        if not username or not password:
            QMessageBox.warning(self, "Errore", "Inserisci almeno un carattere per nome utente e password!")
            return

        success, msg = self.user_manager.register_user(username, password)
        QMessageBox.information(self, "Registrazione", msg)

    def login_user(self):
        username = self.entry_username.text()
        password = self.entry_password.text()
        success, msg = self.user_manager.login_user(username, password)
        if success:
            QMessageBox.information(self, "Login", msg)
            self.chat_window = ChatWindow(username, self.user_manager)
            self.chat_window.show()
            self.hide()
        else:
            QMessageBox.warning(self, "Errore", msg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    user_manager = UserManager()
    window = LoginApp(user_manager)
    window.show()
    sys.exit(app.exec_())