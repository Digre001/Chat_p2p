import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QTextEdit, QMessageBox
from user_manager import UserManager
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from udp_discovery import PeerNetwork  # Assuming PeerNetwork is in peer_network.py

# Worker class for receiving messages asynchronously
class MessageReceiver(QThread):
    message_received = pyqtSignal(str)  # Signal emitted when a message is received

    def __init__(self, peer_network, parent=None):
        super().__init__(parent)
        self.peer_network = peer_network

    def run(self):
        # Start the peer network TCP server to listen for messages
        self.peer_network.start_peer_server(5001)  # Assuming peers communicate on port 5001

# Login Window Class
class LoginApp(QWidget):
    def __init__(self, user_manager, peer_network):
        super().__init__()
        self.user_manager = user_manager
        self.peer_network = peer_network
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.username_field = QLineEdit()
        self.username_field.setPlaceholderText("Username")
        layout.addWidget(self.username_field)

        self.password_field = QLineEdit()
        self.password_field.setPlaceholderText("Password")
        self.password_field.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_field)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.login_user)
        layout.addWidget(self.login_button)

        self.setLayout(layout)
        self.setWindowTitle("Login")

    def login_user(self):
        username = self.username_field.text()
        password = self.password_field.text()
        success, msg = self.user_manager.login_user(username, password)

        if success:
            self.peer_network.start(username)  # Pass the username to start the network
            self.open_message_app(username)
        else:
            QMessageBox.warning(self, "Error", msg)

    def open_message_app(self, username):
        self.message_app = MessageApp(username, self.user_manager, self.peer_network)
        self.message_app.show()
        self.close()


# Message Window Class
class MessageApp(QWidget):
    def __init__(self, username, user_manager, peer_network):
        super().__init__()
        self.username = username
        self.user_manager = user_manager
        self.peer_network = peer_network
        self.init_ui()

        # Set up message receiver thread
        self.message_receiver = MessageReceiver(peer_network)
        self.message_receiver.message_received.connect(self.receive_message)
        self.message_receiver.start()

        # Connect the peer network signal to the receive_message function
        self.peer_network.message_received_signal.connect(self.receive_message)

    def init_ui(self):
        layout = QVBoxLayout()

        self.label_user = QLabel(f"Welcome, {self.username}!")
        layout.addWidget(self.label_user)

        self.received_messages = QTextEdit()
        self.received_messages.setPlaceholderText("Receive messages here...")
        self.received_messages.setReadOnly(True)
        layout.addWidget(self.received_messages)

        self.input_message = QLineEdit()
        self.input_message.setPlaceholderText("Write a message...")
        layout.addWidget(self.input_message)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        layout.addWidget(self.send_button)

        self.connected_users_label = QLabel("Connected Devices:")
        layout.addWidget(self.connected_users_label)

        self.connected_users_display = QTextEdit()
        self.connected_users_display.setReadOnly(True)
        layout.addWidget(self.connected_users_display)

        self.setLayout(layout)
        self.setWindowTitle("Messages")

        self.update_connected_users()  # Show connected users at start

        # Start a timer to update the connected users display every second
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_connected_users)
        self.timer.start(1000)  # Update every second

    def send_message(self):
        message = self.input_message.text()
        if message:
            self.received_messages.append(f"{self.username}: {message}")

            # Send message to all connected peers
            connected_users = self.peer_network.get_connected_ips()  # Dictionary of connected IPs and usernames
            for ip, _ in connected_users.items():
                self.peer_network.send_message(ip, 5001, f"{self.username}: {message}")  # Send message over TCP
            
            self.input_message.clear()

    def receive_message(self, message):
        """Slot called when a new message is received."""
        self.received_messages.append(f"{message}")  # Display the received message in the text edit

    def update_connected_users(self):
        connected_users_info = self.peer_network.get_connected_ips()  # Should return a dictionary now
        user_list = "\n".join([f"{ip}: {username}" for ip, username in connected_users_info.items()])  # Create display string
        self.connected_users_display.setPlainText(user_list)


# Starting the application
if __name__ == '__main__':
    app = QApplication(sys.argv)
    user_manager = UserManager()
    peer_network = PeerNetwork()  # Initialize peer network
    login_window = LoginApp(user_manager, peer_network)
    login_window.show()
    sys.exit(app.exec_())
