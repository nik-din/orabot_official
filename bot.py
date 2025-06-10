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
        host=host,
        database=db,
        user=user,
        password=pwd
    )
    return conn, conn.cursor()


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

#-------------------------------------------------------------------------------------------------
#       _    ___    _   _   _   _   ____     ___    _   _     ____     ___    ___   _   _   _____ 
#      | |  / _ \  | | | | | \ | | / ___|   / _ \  | \ | |   |  _ \   / _ \  |_ _| | \ | | |_   _|
#   _  | | | | | | | |_| | |  \| | \___ \  | | | | |  \| |   | |_) | | | | |  | |  |  \| |   | |  
#  | |_| | | |_| | |  _  | | |\  |  ___) | | |_| | | |\  |   |  __/  | |_| |  | |  | |\  |   | |  
#   \___/   \___/  |_| |_| |_| \_| |____/   \___/  |_| \_|   |_|      \___/  |___| |_| \_|   |_|  
#--------------------------------------------------------------------------------------------------

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
    username = message.from_user.username or message.from_user.first_name or 'Utente'
    bot.reply_to(message, f'{username}!\nAttento! Stai per cancellare tutte le informazioni che ti riguardano!\nSei hai davvero così tanta skill issue rispondi con: "/confermo {code}" a questo messaggio.')

@bot.message_handler(commands=['confermo'])
def confermo(message):
    global code
    if code == "":
        bot.reply_to(message, "Non hai generato ancora nessun codice.\nUsa /skillissue per saperne di più.")
        return
    if code == get_text(message.text).strip():
        conn, cur = get_pg_cursor()
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or 'Utente'
        try:
            cur.execute('''
                UPDATE user_scores 
                SET points = %s, correct_answers = %s, wrong_answers = %s 
                WHERE user_id = %s
            ''', (0, 0, 0, user_id))
            conn.commit()
            bot.reply_to(message, f"Tutte le informazioni riguardanti {username} sono state ufficialmente cancellate!\nVedi di non skill issueare questa volta.")
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
    username = message.from_user.username or message.from_user.first_name or 'Utente'
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
    
#-----------------------------------------------------------------------------------------
#   ____       _      _   _   ____     ___    __  __ 
#  |  _ \     / \    | \ | | |  _ \   / _ \  |  \/  |
#  | |_) |   / _ \   |  \| | | | | | | | | | | |\/| |
#  |  _ <   / ___ \  | |\  | | |_| | | |_| | | |  | |
#  |_| \_\ /_/   \_\ |_| \_| |____/   \___/  |_|  |_|
#-----------------------------------------------------------------------------------------

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

@bot.message_handler(commands=['rm_random'])
def rm_random(message):
    if not message.reply_to_message:
        text = get_text(message.text).strip()
        if text != '':
            frase_to_remove = text
        else:
            bot.reply_to(message, "Inserire una frase da rimuove o ripsondere ad un messaggio che ne contiene una.")
            return
        
    elif message.reply_to_message.text and message.reply_to_message.text.startswith('/add_random'):
        frase_to_remove = get_text(message.reply_to_message.text)
    else:
        frase_to_remove = message.reply_to_message.text

    if not frase_to_remove:
        bot.reply_to(message, "Inserire una frase da rimuove o ripsondere ad un messaggio che ne contiene una.")
        return

    conn, cur = get_pg_cursor()
    try:
        cur.execute('DELETE FROM random WHERE frase = %s', (frase_to_remove,))
        conn.commit()
        
        if cur.rowcount > 0:
            bot.reply_to(message, f"Frase rimossa:\n{frase_to_remove}")
        else:
            bot.reply_to(message, f"Frase non trovata:\n{frase_to_remove}")
    finally:
        conn.close()


#-----------------------------------------------------------------------------------------
#    ___    ____       _      ____     ____    ___    ____    _____ 
#   / _ \  |  _ \     / \    / ___|   / ___|  / _ \  |  _ \  | ____|
#  | | | | | |_) |   / _ \   \___ \  | |     | | | | | |_) | |  _|  
#  | |_| | |  _ <   / ___ \   ___) | | |___  | |_| | |  _ <  | |___ 
#   \___/  |_| \_\ /_/   \_\ |____/   \____|  \___/  |_| \_\ |_____|
#-----------------------------------------------------------------------------------------


# """
# CREATE TABLE polls (
#     poll_id TEXT PRIMARY KEY,
#     chat_id BIGINT NOT NULL,
#     message_id INTEGER NOT NULL,
#     question TEXT NOT NULL,
#     options TEXT[] NOT NULL,  -- Array di stringhe con le opzioni
#     resolved BOOLEAN DEFAULT FALSE,
#     winning_option INTEGER,  -- Opzione vincente (NULL finché non risolto)
#     creator_id BIGINT NOT NULL,
#     creator_username TEXT
# );
# CREATE TABLE user_orascore (
#     user_id BIGINT PRIMARY KEY,
#     userame TEXT,
#     orascore INTEGER NOT NULL DEFAULT 0,
#     locked_points INTEGER DEFAULT 0
# );
# CREATE TABLE bets (
#     bet_id SERIAL PRIMARY KEY,
#     user_id BIGINT NOT NULL,
#     poll_id TEXT NOT NULL,
#     option_id INTEGER NOT NULL,
#     amount INTEGER NOT NULL,
#     resolved BOOLEAN DEFAULT FALSE,
# );
# """
def get_orascore(user_id):
    conn, cur = get_pg_cursor()
    try:
        cur.execute('SELECT orascore FROM user_orascore WHERE user_id = %s', (user_id,))
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


@bot.message_handler(commands=['poll'])
def poll(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or 'Utente'
    chat_id = message.chat.id

    # Formato: /creasondaggio "Domanda?" "Opzione 1" "Opzione 2" ...
    if message.text == "":
        bot.reply_to(message, "Inserire una domanda e almeno due risposte nel seguente formato:\n/\"domanda\" \"opzione 1\" \"opzione 2\" ...")
        return
    parts = message.text.split('"')[1::2]
    if len(parts) < 3:
        bot.reply_to(message, "Inserire una domanda e almeno due risposte nel seguente formato:\n/\"domanda\" \"opzione 1\" \"opzione 2\" ...")
        return
    question = parts[0]
    options = parts[1:]
    
    if len(options) < 2:
        bot.reply_to(message, "Devi fornire almeno 2 opzioni.")
        return
        
    poll = bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=False,
        reply_to_message_id=message.id
    )
    
    conn, cur = get_pg_cursor()
    try:
        cur.execute(
            "INSERT INTO polls (poll_id, chat_id, message_id, question, options, creator_id, creator_username) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (poll.id, chat_id, poll.message_id, question, options, user_id, username)
        )
        conn.commit()
        bot.reply_to(poll, f"Pool_id: {poll.id}")
    finally:
        conn.close()
            

@bot.message_handler(commands=['bet'])
def place_bet(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or 'Utente'
    
    # Formato: /scommetti <poll_id> <option_num> <amount>
    parts = message.text.split()
    if len(parts) < 4:
        bot.reply_to(message, "Inserire la propria scomessa nel seguente formato: /bet <poll_id> <option_num> <amount>")
        return
        
    poll_id = parts[1]
    option_id = int(parts[2])
    amount = int(parts[3])
    print(amount)
    current_points = get_orascore(user_id)
    if amount <= 0:
        bot.reply_to(message, "Ci hai provato! L'importo deve essere positivo.")
        return
    if current_points < amount:
        bot.reply_to(message, f"Non hai abbastanza OraScore, povero! Hai solo {current_points} di OraScore.")
        return
        
    conn, cur = get_pg_cursor()
    try:
        cur.execute("SELECT * FROM polls WHERE poll_id = %s", (poll_id,))
        poll = cur.fetchone()
        if not poll:
            bot.reply_to(message, "Sondaggio non trovato.")
            return
            
        if user_id == poll[7]:
            bot.reply_to(message, "Sei tu il creatore di questo sondaggio!")
            return
        
        if option_id < 0 or option_id >= len(poll[4]):
            bot.reply_to(message, "Opzione non valida.")
            return
            
        cur.execute(
            "UPDATE user_orascore SET orascore = orascore - %s, locked_points = locked_points + %s WHERE user_id = %s",
            (amount, amount, user_id)
        )
        
        cur.execute(
            "INSERT INTO bets (user_id, poll_id, option_id, amount) VALUES (%s, %s, %s, %s)",
            (user_id, poll_id, option_id, amount)
        )
        option_text = poll[4][option_id]
        conn.commit()
        bot.reply_to(message, f"{username} ha scommesso {amount} di OraScore sull'opzione {option_id}: {option_text} del sondaggio con id: {poll_id}!")
    finally:
        conn.close()
        

@bot.message_handler(commands=['solve_poll'])
def resolve_poll(message):
    # FORMATO: /risultato <poll_id> <winning_option_num>
    if get_text(message.text).strip() == "":
        bot.reply_to(message, "Inserire la solve del sondaggio nel seguente formato: /solve <poll_id> <winning_option_num>")
        return
    
    parts = get_text(message.text).split()
    if len(parts) != 2:
        bot.reply_to(message, "Inserire la solve del sondaggio nel seguente formato: /solve <poll_id> <winning_option_num>")
        return
    poll_id = get_text(message.text).split()[0]
    winning_option = int(get_text(message.text).split()[1])
    user_id = message.from_user.id
    
    conn, cur = get_pg_cursor()

    try:

        poll_id = parts[0]

        conn, cur = get_pg_cursor()
        
        cur.execute("SELECT * FROM polls WHERE poll_id = %s", (poll_id,))
        poll = cur.fetchone()

        
        if not poll:
            bot.reply_to(message, "Sondaggio non trovato o già risolto!")
            return
        winning_text = poll[4][winning_option]
        if user_id != poll[7]:
            bot.reply_to(message, f"Non sei tu il creatore di questo sondaggio!\nIl creatore è {poll[8]}")
            return
            
        if winning_option < 0 or winning_option >= len(poll[4]):
            bot.reply_to(message, "Opzione non valida!")
            return
        
        
    finally:
        conn.close()
    
    conn, cur = get_pg_cursor()

    try:
        cur.execute("SELECT * FROM bets WHERE poll_id = %s AND resolved = FALSE", (poll_id,))
        bets = cur.fetchall()
        
        winning_points = 0
        losing_points = 0
        
        for bet in bets:
            if bet[3] == winning_option:
                winning_points += bet[4]
            else:
                losing_points += bet[4]
        
        if winning_points > 0:
            multiplier = 1 + (losing_points / winning_points)
        else:
            multiplier = 1
            
        for bet in bets:
            if bet[3] == winning_option:
                win_amount = round(bet[4] * multiplier)
                cur.execute(
                    "UPDATE user_orascore SET locked_points = locked_points - %s, orascore = orascore + %s WHERE user_id = %s",
                    (bet[4], win_amount, bet[1]))
            else:
                cur.execute(
                    "UPDATE user_orascore SET locked_points = locked_points - %s WHERE user_id = %s",
                    (bet[4], bet[1]))
            
            cur.execute(
                "UPDATE bets SET resolved = TRUE WHERE bet_id = %s",
                (bet[0],)
            )
        
        cur.execute(
            "DELETE FROM bets WHERE poll_id = %s",
            (poll_id,)
        )

        cur.execute(
            "DELETE FROM polls WHERE poll_id = %s",
            (poll_id,)
        )

        
        conn.commit()
        
        result_text = (
            f"Sondaggio chiuso!\n"
            f"Opzione vincente: {winning_option}: {winning_text}\n"
            f"Totale punti vincenti: {winning_points}\n"
            f"Totale punti perdenti: {losing_points}\n"
            f"Moltiplicatore: x{multiplier:.2f}\n"
        )
        bot.reply_to(message, result_text) 

    except ValueError:
        bot.reply_to(message, "L'opzione vincente deve essere un numero!")
    finally:
        conn.close()

@bot.message_handler(commands=['orascore'])
def orascore(message):
    conn, cur = get_pg_cursor()
    try:
        cur.execute('''
            SELECT username, orascore 
            FROM user_orascore 
            ORDER BY orascore DESC 
            LIMIT 12
        ''')
        rows = cur.fetchall()

        ranking = "Classifica Orascore:\n--------------------------\n"
        for username, points in rows:
            ranking += f"{username or 'Utente'}: {points}\n"

        bot.reply_to(message, ranking if rows else 'Nessun utente trovato.')
    finally:
        conn.close()
bot.infinity_polling()
