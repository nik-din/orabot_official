import json
import os
import psycopg2
import random
import requests
import telebot

from johnson import johnson_image

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

db = os.environ.get('DB')
host = os.environ.get('DB_HOST')
user = os.environ.get('DB_USER')
pwd = os.environ.get('DB_PASSWORD')

started = False
length = 0
answer = ''

def get_text(message):
    words = message.split()
    return ' '.join(words[1:])

@bot.message_handler(commands=['start'])
def start(message):
    global started
    if started == False:
        with psycopg2.connect(host=host,database=db, user=user, password=pwd) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM random_array')
                global length
                length = cur.rowcount
        started = True
        bot.reply_to(message, 'Il bot è stato inizializzato correttamente.')
    else:
        bot.reply_to(message, 'Il bot è già stato inizializzato.')

@bot.message_handler(commands=['ciao'])
def ciao(message):
    bot.reply_to(message, 'Buondì!')

@bot.message_handler(commands=['ora'])
def ora(message):
    bot.reply_to(message, 'A che ora è mate?')

@bot.message_handler(commands=['johnson'])
def johnson(message):
    solid = random.choice(johnson_image).capitalize()
    bot.send_photo(message.chat.id, 'https://it.wikipedia.org/wiki/File:' + solid + '.png', solid.replace('_', ' '), reply_to_message_id=message.id)

@bot.message_handler(commands=['random'])
def random_(message):
    with psycopg2.connect(host=host, database=db, user=user, password=pwd) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT frase FROM random_array OFFSET floor(random()*(%s)) LIMIT 1', (length, ))
            bot.reply_to(message, cur.fetchone())

@bot.message_handler(commands=['add_random'])
def add_random(message):
    global length
    text = get_text(message.text)

    if text != '':
        with psycopg2.connect(host=host, database=db, user=user,password=pwd) as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO random_array(frase) VALUES(%s) RETURNING random_id', (text,))
        length += 1
        bot.reply_to(message, 'Aggiunto!')
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

    if answer == '':
        bot.reply_to(message, 'Nessun quiz in corso. Per avviarne uno usa /quiz.')
    else:
        markup = telebot.types.ReplyKeyboardRemove(selective=False)
        if get_text(message.text) == answer:
            bot.reply_to(message, 'Corretto!', reply_markup=markup)
        else:
            bot.reply_to(message, 'Sbagliato!', reply_markup=markup)
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
        bot.send_document(message.chat.id, 'https://training.olinfo.it/api/files/' + statement['statements']['it'] + '/testo.pdf', message.id, name + '\n' + str(statement['time_limit']) + ' sec\n' + str(statement['memory_limit']/1048576) + ' MiB')
    else:
        bot.reply_to(message, 'Nome del problema sbagliato. Riprovare.')

bot.infinity_polling()
