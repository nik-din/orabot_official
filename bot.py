import json
import os
import psycopg2
import random
import requests
import telebot
import string
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
quiz_id = None
chat_quiz_id = None
guessed_by = []
code = ""

def get_pg_cursor():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )
    return conn, conn.cursor()

def update_points(user_id, delta, username=None, correct=False, wrong=False):
    conn, cur = get_pg_cursor()
    try:
        cur.execute('SELECT points, correct_answers, wrong_answers FROM user_scores WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
        
        if row:
            new_points = max(0, row[0] + delta)
            correct_count = row[1] + (1 if correct else 0)
            wrong_count = row[2] + (1 if wrong else 0)
            cur.execute('''
                UPDATE user_scores 
                SET points = %s, correct_answers = %s, wrong_answers = %s 
                WHERE user_id = %s
            ''', (new_points, correct_count, wrong_count, user_id))
        else:
            initial_points = max(0, delta)
            cur.execute('''
                INSERT INTO user_scores (user_id, username, points, correct_answers, wrong_answers) 
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, username, initial_points, 1 if correct else 0, 1 if wrong else 0))
        conn.commit()
    finally:
        conn.close()


def get_points(user_id):
    conn, cur = get_pg_cursor()
    try:
        cur.execute('SELECT points FROM user_scores WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()

def key():
    lettere = ''.join(random.choices(string.ascii_uppercase, k=3))

    numeri = ''.join(random.choices(string.digits, k=3))
    
    chiave_mista = list(lettere + numeri)
    random.shuffle(chiave_mista)
    chiave = '-'.join([
        ''.join(chiave_mista[:3]),
        ''.join(chiave_mista[3:])
    ])[:7]

    return chiave

@bot.message_handler(commands=['score'])
def score(message):
    conn, cur = get_pg_cursor()
    try:
        user_id = message.from_user.id
        cur.execute('SELECT points, correct_answers, wrong_answers FROM user_scores WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
        
        if row:
            points, correct, wrong = row
            bot.reply_to(message, f"Hai {points} punti di Johnson.\nRisposte corrette: {correct}\nRisposte sbagliate: {wrong}")
        else:
            bot.reply_to(message, "Non ci sono abbastanza dati su di te.")
    finally:
        conn.close()

@bot.message_handler(commands=['skill'])
def skill(message):
    conn, cur = get_pg_cursor()
    try:
        cur.execute('''
            SELECT username, correct_answers, wrong_answers 
            FROM user_scores 
            ORDER BY (correct_answers::float)/(wrong_answers+1) DESC, correct_answers DESC
            LIMIT 12
        ''')
        rows = cur.fetchall()

        ranking = "Classifica skill Johnson:\nCorrette / Sbagliate\n--------------------------\n"
        for username, correct, wrong in rows:
            ranking += f"{username or 'Utente'}: {correct} / {wrong}\n"

        bot.reply_to(message, ranking if rows else 'Nessun dato disponibile.')
    finally:
        conn.close()

@bot.message_handler(commands=['skillissue'])
def skillissue(message):
    global code
    code = key()
    username = message.from_user.username or 'Utente'
    bot.reply_to(message, f'{username}!\nAttento! Stai per cancellare tutte le informazioni che ti riguardano!\nSei hai davvero così tanta skill issue rispondi con: "/confermo {code}" a questo messaggio.')

@bot.message_handler(commands=['confermo'])
def confermo(message):
    global code
    if code in message.text:
        conn, cur = get_pg_cursor()
        user_id = message.from_user.id
        try:
            cur.execute('''
                UPDATE user_scores 
                SET points = %s, correct_answers = %s, wrong_answers = %s 
                WHERE user_id = %s
            ''', (0, 0, 0, user_id))
            conn.commit()
            bot.reply_to(message, 'Tutte le informazioni che ti riguardano sono state ufficialmente cancellate!\nVedi di non skill issueare questa volta.')
        finally:
            conn.close()
    else:
        bot.reply_to(message, 'Chiave non valida.\nÈ necessario generarne una nuova.')
    code = ""

@bot.message_handler(commands=['ranking'])
def ranking(message):
    conn, cur = get_pg_cursor()
    try:
        cur.execute('''
            SELECT username, points 
            FROM user_scores 
            ORDER BY points DESC 
            LIMIT 12
        ''')
        rows = cur.fetchall()

        ranking = "Classifica punti Johnson:\n--------------------------\n"
        for username, points in rows:
            ranking += f"{username or 'Utente'}: {points}\n"

        bot.reply_to(message, ranking if rows else 'Nessun utente trovato.')
    finally:
        conn.close()

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
    global answer, quiz_id, chat_quiz_id, guessed_by
    options = random.sample(johnson_image, 3)
    answer = random.choice(options).replace('_', ' ')
    if quiz_id is not None and chat_quiz_id is not None:
        bot.delete_message(chat_quiz_id, quiz_id)

    markup = telebot.types.ReplyKeyboardMarkup()
    for item in options:
        markup.row(telebot.types.KeyboardButton('/ans ' + item.replace('_', ' ')))

    sent_msg = bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + answer.capitalize() + '.png', 'Che solido di Johnson è?', reply_to_message_id=message.id, reply_markup=markup)
    quiz_id = sent_msg.message_id
    chat_quiz_id = sent_msg.chat.id
    guessed_by = []

@bot.message_handler(commands=['ans'])
def ans(message):
    global answer, quiz_id, chat_quiz_id, guessed_by
    user_id = message.from_user.id
    username = message.from_user.username or 'Utente'
    markup = telebot.types.ReplyKeyboardRemove(selective=False)

    if answer == '':
        bot.reply_to(message, 'Nessun quiz in corso. Per avviarne uno usa /quiz.', reply_markup=markup)
    elif user_id not in guessed_by:
        guessed_by.append(user_id)
        if get_text(message.text) == answer:
            bot.reply_to(message, 'Corretto!' + '\n' + username + " ha guadagnato 1 punto.", reply_markup=markup)
            answer = ''
            update_points(user_id, 1, username, correct=True)
        else:
            bot.reply_to(message, 'Errato! La risposta corretta è ' + answer.replace('_', ' ') + '.\n' + username + " ha perso 1 punto.", reply_markup=markup)
            answer = ''
            update_points(user_id, -1, username, wrong=True)
        if quiz_id:
            try:
                bot.delete_message(message.chat.id, quiz_id)
            except:
                pass
    else:
        bot.reply_to(message, 'Hai già risposto a questo quiz!\nSmettila di provare a imbrogliare!!')
    quiz_id = None
    chat_quiz_id = None
    

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
