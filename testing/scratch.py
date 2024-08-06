import sys
import pickle
import logging
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QDialog, QFormLayout, QDialogButtonBox, QListWidget, QListWidgetItem, QSplitter
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.QtCore import QUrl, Qt, QDateTime
from PyQt5.QtNetwork import QNetworkCookie

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Define the parent directory path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(CURRENT_DIR, 'sessions')  # Directory to store session data

def ensure_sessions_dir():
    if not os.path.exists(SESSIONS_DIR):
        os.makedirs(SESSIONS_DIR)
        logging.debug(f"Created sessions directory at {SESSIONS_DIR}")
    else:
        logging.debug(f"Sessions directory already exists at {SESSIONS_DIR}")

class NewUserDialog(QDialog):
    def __init__(self, parent=None, user_info=None):
        super().__init__(parent)
        self.setWindowTitle("New User" if user_info is None else "Modify User")
        self.setModal(True)

        self.form_layout = QFormLayout(self)
        self.display_name_input = QLineEdit(self)
        self.username_input = QLineEdit(self)
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)

        if user_info:
            self.display_name_input.setText(user_info['display_name'])
            self.username_input.setText(user_info['username'])
            self.password_input.setText(user_info['password'])

        self.form_layout.addRow("Display Name:", self.display_name_input)
        self.form_layout.addRow("Username:", self.username_input)
        self.form_layout.addRow("Password:", self.password_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.form_layout.addRow(self.button_box)

    def get_user_info(self):
        return {
            'display_name': self.display_name_input.text(),
            'username': self.username_input.text(),
            'password': self.password_input.text()
        }

class CityMapApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('RBC City Map')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create the splitter to divide the left and right columns
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left column for user list and buttons
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.character_list = QListWidget()
        self.character_list.itemClicked.connect(self.login_character)
        left_layout.addWidget(self.character_list)

        button_layout = QHBoxLayout()

        new_button = QPushButton('New')
        new_button.clicked.connect(self.new_character)
        button_layout.addWidget(new_button)

        modify_button = QPushButton('Modify')
        modify_button.clicked.connect(self.modify_character)
        button_layout.addWidget(modify_button)

        delete_button = QPushButton('Delete')
        delete_button.clicked.connect(self.delete_character)
        button_layout.addWidget(delete_button)

        left_layout.addLayout(button_layout)

        splitter.addWidget(left_widget)
        left_widget.setFixedWidth(300)

        # Right column for web view
        self.webview = QWebEngineView()
        self.profile = QWebEngineProfile.defaultProfile()
        self.cookie_store = self.profile.cookieStore()
        splitter.addWidget(self.webview)
        self.webview.show()  # Ensure the webview is shown

        logging.debug("Webview added to layout and shown")

        self.load_user_list()
        self.load_active_user()

    def load_user_list(self):
        self.character_list.clear()
        users = load_user_info()
        for user in users:
            item = QListWidgetItem(user['display_name'])
            item.setData(Qt.UserRole, user)
            self.character_list.addItem(item)
        logging.debug("User list loaded")

    def new_character(self):
        dialog = NewUserDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            user_info = dialog.get_user_info()
            users = load_user_info()
            users.append(user_info)
            save_user_info(users)
            self.load_user_list()

    def modify_character(self):
        current_item = self.character_list.currentItem()
        if current_item:
            user_info = current_item.data(Qt.UserRole)
            dialog = NewUserDialog(self, user_info)
            if dialog.exec_() == QDialog.Accepted:
                new_user_info = dialog.get_user_info()
                users = load_user_info()
                for i, user in enumerate(users):
                    if user == user_info:
                        users[i] = new_user_info
                        break
                save_user_info(users)
                self.load_user_list()

    def delete_character(self):
        current_item = self.character_list.currentItem()
        if current_item:
            user_info = current_item.data(Qt.UserRole)
            users = load_user_info()
            users = [user for user in users if user != user_info]
            save_user_info(users)
            self.load_user_list()
            save_active_user(None)

    def login_character(self, item):
        user_info = item.data(Qt.UserRole)
        self.set_active_user(user_info)

    def set_active_user(self, user_info):
        logging.debug(f"Setting active user: {user_info}")
        save_active_user(user_info)
        self.load_session(user_info['username'])
        self.webview.setUrl(QUrl('https://quiz.ravenblack.net/blood.pl?action=city'))

    def load_active_user(self):
        user_info = load_active_user()
        if user_info:
            self.set_active_user(user_info)

    def load_session(self, username):
        """
        Load session for the specified user and set it in the web engine profile.
        """
        ensure_sessions_dir()
        session_file = os.path.join(SESSIONS_DIR, f'session_{username}.pkl')
        logging.debug(f"Attempting to load session file: {session_file}")
        if os.path.exists(session_file):
            with open(session_file, 'rb') as file:
                session_data = pickle.load(file)
                logging.debug(f"Loaded session data for user {username}: {session_data}")
                self.apply_session_data(session_data)
        else:
            logging.debug(f"No session file found for user {username}. Logging in normally.")

    def save_session(self, username):
        """
        Save session for the specified user from the web engine profile.
        """
        self.cookie_store.cookiesForUrl(QUrl('https://quiz.ravenblack.net')).then(
            lambda cookies: self._extract_and_save_session(cookies, username)
        )

    def _extract_and_save_session(self, cookies, username):
        """
        Extract session data and save it for the specified user.
        """
        session_data = {
            'cookies': []
        }
        for cookie in cookies:
            session_data['cookies'].append({
                'name': cookie.name().data().decode(),
                'value': cookie.value().data().decode(),
                'domain': cookie.domain(),
                'path': cookie.path(),
                'expires': cookie.expirationDate().toMSecsSinceEpoch(),
                'is_secure': cookie.isSecure(),
                'is_httponly': cookie.isHttpOnly()
            })
        ensure_sessions_dir()
        session_file = os.path.join(SESSIONS_DIR, f'session_{username}.pkl')
        with open(session_file, 'wb') as file:
            pickle.dump(session_data, file)
        logging.debug(f"Session data saved for user {username} in {session_file}: {session_data}")

    def apply_session_data(self, session_data):
        """
        Apply session data to the web engine profile.
        """
        #self.clear_cookies()
        for cookie_data in session_data.get('cookies', []):
            q_cookie = QNetworkCookie(cookie_data['name'].encode(), cookie_data['value'].encode())
            q_cookie.setDomain(cookie_data['domain'])
            q_cookie.setPath(cookie_data['path'])
            q_cookie.setExpirationDate(QDateTime.fromMSecsSinceEpoch(cookie_data['expires']))
            q_cookie.setSecure(cookie_data['is_secure'])
            q_cookie.setHttpOnly(cookie_data['is_httponly'])
            self.cookie_store.setCookie(q_cookie, QUrl('https://quiz.ravenblack.net'))
        logging.debug("Session data applied")
"""
    def clear_cookies(self):
        logging.debug("Clearing cookies")
        self.cookie_store.deleteAllCookies()
"""
def save_user_info(user_info):
    ensure_sessions_dir()
    users_file = os.path.join(SESSIONS_DIR, 'users.pkl')
    with open(users_file, 'wb') as file:
        pickle.dump(user_info, file)
    logging.debug(f"User info saved: {user_info}")

def load_user_info():
    ensure_sessions_dir()
    users_file = os.path.join(SESSIONS_DIR, 'users.pkl')
    logging.debug(f"Attempting to load user info from: {users_file}")
    try:
        with open(users_file, 'rb') as file:
            user_info = pickle.load(file)
            logging.debug(f"Loaded user info: {user_info}")
            return user_info
    except FileNotFoundError:
        logging.debug("User info file not found.")
        return []

def save_active_user(user):
    ensure_sessions_dir()
    active_user_file = os.path.join(SESSIONS_DIR, 'active_user.pkl')
    with open(active_user_file, 'wb') as file:
        pickle.dump(user, file)
    logging.debug(f"Active user saved: {user}")

def load_active_user():
    ensure_sessions_dir()
    active_user_file = os.path.join(SESSIONS_DIR, 'active_user.pkl')
    logging.debug(f"Attempting to load active user from: {active_user_file}")
    try:
        with open(active_user_file, 'rb') as file:
            active_user = pickle.load(file)
            logging.debug(f"Loaded active user: {active_user}")
            return active_user
    except FileNotFoundError:
        logging.debug("Active user file not found.")
        return None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CityMapApp()
    window.show()
    sys.exit(app.exec_())
