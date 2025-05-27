import json
import os
import psycopg2
import random
import requests
import telebot
import sqlite3
from telebot.types import InlineQueryResultArticle, InputTextMessageContent

from johnson import johnson_image

from keep_alive_ping import create_service

service = create_service(ping_interval=600)



BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

db = os.environ.get('DB')
host = os.environ.get('DB_HOST')
user = os.environ.get('DB_USER')
pwd = os.environ.get('DB_PASSWORD')

started = False
answer = ''

conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS user_scores (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER NOT NULL DEFAULT 0
)
''')
conn.commit()

def table_needs_reset():
    cur.execute("PRAGMA table_info(user_scores)")
    columns = [col[1] for col in cur.fetchall()]
    expected_columns = {'user_id', 'username', 'points', 'correct_answers', 'wrong_answers'}
    return not expected_columns.issubset(set(columns))

if table_needs_reset():
    cur.execute("DROP TABLE IF EXISTS user_scores")
    cur.execute('''
        CREATE TABLE user_scores (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER NOT NULL DEFAULT 0,
            correct_answers INTEGER NOT NULL DEFAULT 0,
            wrong_answers INTEGER NOT NULL DEFAULT 0
        )
    ''')
    conn.commit()

def update_points(user_id, delta, username=None, correct=False, wrong=False):
    cur.execute('SELECT points, correct_answers, wrong_answers FROM user_scores WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    if row:
        new_points = max(0, row[0] + delta)
        correct_count = row[1] + (1 if correct else 0)
        wrong_count = row[2] + (1 if wrong else 0)
        cur.execute('''
            UPDATE user_scores 
            SET points = ?, username = ?, correct_answers = ?, wrong_answers = ? 
            WHERE user_id = ?
        ''', (new_points, username, correct_count, wrong_count, user_id))
    else:
        initial_points = max(0, delta)
        cur.execute('''
            INSERT INTO user_scores (user_id, username, points, correct_answers, wrong_answers) 
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, initial_points, 1 if correct else 0, 1 if wrong else 0))
    conn.commit()


def get_points(user_id):
    cur.execute('SELECT points FROM user_scores WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    return row[0] if row else 0

@bot.message_handler(commands=['punti'])
def punti(message):
    user_id = message.from_user.id
    cur.execute('SELECT points, correct_answers, wrong_answers FROM user_scores WHERE user_id = ?', (user_id,))
    row = cur.fetchone()
    if row:
        points, correct, wrong = row
        bot.reply_to(message, f"Hai {points} punti di Johnson.\nRisposte corrette: {correct}\nRisposte sbagliate: {wrong}")
    else:
        bot.reply_to(message, "Non ci sono abbastanza dati su di te.")

@bot.message_handler(commands=['skill'])
def skill(message):
    cur.execute('''
        SELECT username, correct_answers, wrong_answers 
        FROM user_scores 
        ORDER BY correct_answers DESC, wrong_answers ASC 
        LIMIT 12
    ''')
    rows = cur.fetchall()

    if not rows:
        bot.reply_to(message, 'Nessun dato disponibile.')
        return

    ranking = "Classifica skill Johnson:\n"
    ranking += "--------------------------\n"
    ranking += "Corrette / Sbagliate\n"
    for username, correct, wrong in rows:
        username = username or 'Utente sconosciuto'
        ranking += f"{username}: {correct} / {wrong}\n"

    bot.reply_to(message, ranking)


@bot.message_handler(commands=['classifica'])
def classifica(message):
    cur.execute('SELECT username, points FROM user_scores ORDER BY points DESC LIMIT 12')
    rows = cur.fetchall()
    
    if not rows:
        bot.reply_to(message, 'Nessun utente trovato.')
        return
    
    ranking = "Classifica punti Johnson:\n"
    ranking += "--------------------------\n"
    for username, points in rows:
        username = username or 'Utente sconosciuto'
        ranking += f"{username}: {points}\n"

    bot.reply_to(message, ranking)

@bot.inline_handler(func=lambda query: query.query.startswith('johnson'))
def query_johnson(inline_query):
    query_text = inline_query.query[len('johnson'):].strip().lower().replace(' ', '_')

    results = []
    for solid in johnson_image:
        if query_text in solid:
            results.append(
                InlineQueryResultArticle(
                    id=solid,
                    title=solid.replace('_', ' ').capitalize(),
                    input_message_content=InputTextMessageContent(f'/johnson {solid}')
                )
            )
    results = results[:20]
    bot.answer_inline_query(inline_query.id, results)


def get_text(message):
    words = message.replace('\n', ' \n').split()
    return ' '.join(words[1:])

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, '...')

@bot.message_handler(commands=['ciao'])
def ciao(message):
    print(message.chat.id)
    print(message.id)
    bot.reply_to(message, 'Buondì!')

@bot.message_handler(commands=['ora'])
def ora(message):
    bot.reply_to(message, 'A che ora è mate?')

@bot.message_handler(commands=['johnson'])
def johnson(message):
    global length
    text = get_text(message.text)
    textl = text.split()
    for i in range(len(textl)):
        textl[i] = textl[i].lower()
        if i == 0:
            text = textl[i]
        else:
            text += '_' + textl[i]  

    if text == '':
        solid = random.choice(johnson_image).capitalize()
        bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + solid + '.png', solid.replace('_', ' '), reply_to_message_id=message.id)
    elif text in johnson_image:
        solid = text.capitalize()
        bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + solid + '.png', solid.replace('_', ' '), reply_to_message_id=message.id)
    else:
        bot.reply_to(message, 'Solido non valido.')

@bot.message_handler(commands=['random'])
def random_(message):
    with psycopg2.connect(host=host, database=db, user=user, password=pwd) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT frase FROM random ORDER BY RANDOM() LIMIT 1')
            bot.reply_to(message, cur.fetchone())

@bot.message_handler(commands=['add_random'])
def add_random(message):
    global length
    text = get_text(message.text)

    if text != '':
        with psycopg2.connect(host=host, database=db, user=user,password=pwd) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute('INSERT INTO random (frase) VALUES (%s)', (text,))
                    bot.reply_to(message, 'Aggiunto!')
                except:
                    bot.reply_to(message, 'Questa frase è già stata inserita!')
    else:
        bot.reply_to(message, 'Inserire un messaggio.')

@bot.message_handler(commands=['quiz'])
def quiz(message):
    global answer
    options = random.sample(johnson_image, 3)
    answer = random.choice(options).replace('_', ' ')

    markup = telebot.types.ReplyKeyboardMarkup()
    for item in options:
        markup.row(telebot.types.KeyboardButton('/ans ' + item.replace('_', ' ')))

    bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + answer.capitalize() + '.png', 'Che solido di Johnson è?', reply_to_message_id=message.id, reply_markup=markup)

@bot.message_handler(commands=['ans'])
def ans(message):
    global answer
    user_id = message.chat.id
    username = message.from_user.username or 'Utente'

    if answer == '':
        bot.reply_to(message, 'Nessun quiz in corso. Per avviarne uno usa /quiz.')
    else:
        markup = telebot.types.ReplyKeyboardRemove(selective=False)
        if get_text(message.text) == answer:
            update_points(user_id, 1, username, correct=True)
            bot.reply_to(message, 'Corretto!', reply_markup=markup)
        else:
            update_points(user_id, -1, username, wrong=True)
            bot.reply_to(message, 'Errato! La risposta corretta è ' + answer.replace('_', ' ') + '.\n' + username + " ha perso 1 punto.", reply_markup=markup)
        answer = ''

@bot.message_handler(commands=['testo'])
def testo(message):
    name = get_text(message.text)
    url = 'https://training.olinfo.it/api/task'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        'action': 'get',
        'name': ''
    }
    statement = {}

    prefix = ['', 'oii_', 'ois_', 'abc_', 'gator_', 'luiss_', 'mat_', 'preoii_', 'pre_boi_', 'pre-egoi-', 'roiti_', 'unimi_', 'weoi_']
    for i in prefix:
        data['name'] = i + name
        r = requests.post(url, headers=headers, data=json.dumps(data))
        statement = json.loads(r.text)
        print(data['name'])
        if statement['success'] == 1:
            name = data['name']
            break

    if statement['success'] == 1:
        ids = statement['statements']
        link = 'https://training.olinfo.it/api/files/' + (ids['it'] if 'it' in ids.keys() else ids['en']) + '/testo.pdf'
        tl = str(statement['time_limit']) + ' sec'
        ml = str(statement['memory_limit']/1048576) + ' MiB'
        pt = '<span class="tg-spoiler">' + str(round(statement['score_multiplier']*100)) + ' punti</span>'
        tg = ''
        for tag in statement['tags']:
            tg += '<span class="tg-spoiler">' + tag['name'] + '</span> '
        bot.send_document(message.chat.id, link, message.id, name + '\n' + pt + '\n' + tl + '\n' + ml + '\n' + tg, parse_mode='HTML')
        # bot.send_document(message.chat.id, link, message.id, name + '\n' + tl + '\n' + ml)
    else:
        bot.reply_to(message, 'Nome del problema sbagliato. Riprovare.')

bot.infinity_polling()
