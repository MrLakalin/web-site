from flask import Flask, render_template, request, redirect, url_for, session
import random
import string
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

USERS_FILE = "users.txt"


# --- функции для работы с пользователями ---
def load_users():
    users = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                login, password = line.strip().split("|")
                users.append({'login': login, 'password': password})
    return users


def save_user(login, password):
    with open(USERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{login}|{password}\n")


def user_exists(login):
    users = load_users()
    return any(u['login'] == login for u in users)


def check_user(login, password):
    users = load_users()
    for user in users:
        if user['login'] == login and user['password'] == password:
            return True
    return False


# --- генерация паролей ---
def generate_password(length, complexity):
    if complexity == "low":
        chars = string.ascii_lowercase
    elif complexity == "medium":
        chars = string.ascii_letters
    elif complexity == "high":
        chars = string.ascii_letters + string.digits
    else:  # max
        chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))


# --- маршруты ---
@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']

        if user_exists(login):
            return render_template('register.html', error='Пользователь уже существует')

        save_user(login, password)
        session['user'] = login
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/generator', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect(url_for('register'))

    passwords = []
    if request.method == 'POST':
        try:
            length = int(request.form['length'])
            count = int(request.form['count'])
            complexity = request.form['complexity']
            with open("password_history.txt", "a", encoding="utf-8") as f:
                for _ in range(count):
                    pwd = generate_password(length, complexity)
                    passwords.append(pwd)
                    f.write(f"{session['user']} | {pwd}\n")
        except:
            passwords = ["Ошибка ввода. Попробуйте ещё раз."]

    return render_template('index.html', passwords=passwords, user=session['user'])


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('register'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7000)